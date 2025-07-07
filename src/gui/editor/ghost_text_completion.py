"""
现代化的Ghost Text补全系统
实现类似Cursor/Copilot的灰色预览文本补全
"""

import logging
from typing import Optional, List
from PyQt6.QtWidgets import QWidget, QTextEdit
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QObject
from PyQt6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QPainter, 
    QFont, QFontMetrics, QPaintEvent, QKeyEvent
)

logger = logging.getLogger(__name__)


class GhostTextRenderer(QWidget):
    """Ghost Text渲染器 - 固定位置显示灰色预览文本"""

    def __init__(self, text_editor):
        super().__init__(text_editor)

        self._text_editor = text_editor
        self._ghost_text = ""
        self._trigger_cursor_position = 0  # 触发时的光标位置（固定）
        self._is_visible = False
        self._is_position_locked = False  # 位置是否已锁定
        self._fixed_geometry = None  # 固定的几何位置
        self._wrapped_lines = []  # 换行后的文本行

        # 设置透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置字体（确保与编辑器完全一致）
        self._font = QFont(text_editor.font())
        self._font.setFamily(text_editor.font().family())
        self._font.setPointSize(text_editor.font().pointSize())
        self._font.setWeight(text_editor.font().weight())
        self._font.setStyle(text_editor.font().style())
        self._font_metrics = QFontMetrics(self._font)

        # 隐藏初始状态
        self.hide()
        
    def set_ghost_text(self, text: str, cursor_pos: int):
        """设置Ghost Text - 固定位置显示"""
        self._ghost_text = text
        self._trigger_cursor_position = cursor_pos  # 保存触发位置
        self._is_visible = bool(text.strip())

        if self._is_visible:
            # 只在首次显示时计算并锁定位置
            if not self._is_position_locked:
                self._calculate_and_lock_position()
                self._is_position_locked = True
            self.show()
            self.update()
        else:
            self.hide()

    def clear_ghost_text(self):
        """清除Ghost Text并解锁位置"""
        self._ghost_text = ""
        self._is_visible = False
        self._is_position_locked = False  # 解锁位置，下次可重新计算
        self._fixed_geometry = None
        self._wrapped_lines = []  # 清空换行文本
        self.hide()
        
    def _calculate_and_lock_position(self):
        """计算并锁定Ghost Text位置 - 支持自动换行的多行显示"""
        if not self._is_visible or not self._ghost_text:
            return

        logger.debug(f"开始计算Ghost Text位置，原始文本长度: {len(self._ghost_text)}")

        # 使用触发时的光标位置（固定不变）
        cursor = self._text_editor.textCursor()
        cursor.setPosition(self._trigger_cursor_position)

        # 获取光标矩形作为基础
        cursor_rect = self._text_editor.cursorRect(cursor)
        logger.debug(f"光标矩形: x={cursor_rect.x()}, y={cursor_rect.y()}, w={cursor_rect.width()}, h={cursor_rect.height()}")

        # 获取当前文本块和光标在块中的位置
        block = cursor.block()
        position_in_block = cursor.positionInBlock()
        line_text = block.text()
        
        logger.debug(f"当前行文本: '{line_text}', 光标在行中位置: {position_in_block}")

        # 计算光标前文本的精确宽度
        text_before_cursor = line_text[:position_in_block]
        text_width = self._font_metrics.horizontalAdvance(text_before_cursor)
        
        logger.debug(f"光标前文本: '{text_before_cursor}', 宽度: {text_width}")

        # 精确计算X位置 - 直接使用光标矩形的左边位置加上当前字符位置的偏移
        # 而不是从行首计算，这样更准确
        start_x = cursor_rect.left()
        start_y = cursor_rect.top()
        
        logger.debug(f"初始位置: x={start_x}, y={start_y}")

        # 获取可视区域
        viewport_rect = self._text_editor.viewport().rect()
        
        # 计算可用宽度（从光标位置到右边界）
        available_width = viewport_rect.width() - start_x
        line_height = self._font_metrics.height()
        
        logger.debug(f"可用宽度: {available_width}, 行高: {line_height}")
        
        # 智能文本换行处理
        wrapped_lines = self._wrap_text_to_width(self._ghost_text, available_width)
        
        logger.debug(f"换行完成，原文本1行 -> {len(wrapped_lines)}行")
        for i, line in enumerate(wrapped_lines[:3]):  # 只打印前3行
            logger.debug(f"  第{i+1}行: '{line}'")
        
        # 计算所需的总高度
        total_height = len(wrapped_lines) * line_height
        
        # 计算最大实际宽度
        max_actual_width = 0
        for line in wrapped_lines:
            line_width = self._font_metrics.horizontalAdvance(line)
            max_actual_width = max(max_actual_width, line_width)

        # 边界检查和调整
        x = start_x
        y = start_y
        
        # 如果总高度超出下边界，显示在光标上方
        if y + total_height > viewport_rect.height():
            y = cursor_rect.top() - total_height
            if y < 0:
                # 如果上方也放不下，截断显示
                y = 0
                max_lines = viewport_rect.height() // line_height
                wrapped_lines = wrapped_lines[:max_lines]
                total_height = len(wrapped_lines) * line_height

        # 确保X位置不会超出右边界
        if x + max_actual_width > viewport_rect.width():
            x = max(0, viewport_rect.width() - max_actual_width - 10)
        
        # 确保位置不为负
        x = max(0, x)
        y = max(0, y)

        # 计算最终尺寸
        width = min(max_actual_width + 5, available_width)  # 留5像素边距
        height = total_height

        # 存储换行后的文本行（供paintEvent使用）
        self._wrapped_lines = wrapped_lines

        # 保存固定几何位置
        self._fixed_geometry = (x, y, width, height)

        # 应用固定位置
        self.setGeometry(x, y, width, height)

        logger.debug(f"Ghost text positioned at ({x}, {y}) size ({width}, {height})")
        logger.debug(f"Wrapped into {len(wrapped_lines)} lines, available_width: {available_width}")
        logger.debug(f"Original text: '{self._ghost_text[:50]}...'")
        logger.debug(f"First wrapped line: '{wrapped_lines[0] if wrapped_lines else 'N/A'}'")
        
    def _wrap_text_to_width(self, text: str, max_width: int) -> list[str]:
        """将文本按指定宽度进行智能换行
        
        Args:
            text: 原始文本
            max_width: 最大宽度（像素）
            
        Returns:
            换行后的文本行列表
        """
        logger.debug(f"_wrap_text_to_width: 输入文本长度={len(text)}, 最大宽度={max_width}")
        
        if max_width <= 50:  # 宽度太小，不换行
            logger.debug("_wrap_text_to_width: 宽度太小，返回原文本")
            return [text]
        
        lines = []
        remaining_text = text.strip()
        
        logger.debug(f"_wrap_text_to_width: 开始处理文本: '{remaining_text[:50]}...'")
        
        while remaining_text:
            # 尝试找到能放入当前行的最长文本
            line_text = ""
            
            # 优先在自然断点（标点符号、空格）处断行
            for i in range(1, len(remaining_text) + 1):
                test_text = remaining_text[:i]
                text_width = self._font_metrics.horizontalAdvance(test_text)
                
                if text_width <= max_width:
                    line_text = test_text
                else:
                    # 超出宽度，在最后一个合适的断点处断行
                    if len(line_text) < 3:  # 如果断行点太靠前，强制断行，至少3个字符
                        line_text = remaining_text[:max(3, i-1)]
                    break
            
            # 如果没有找到合适的断行点，至少取一个字符
            if not line_text and remaining_text:
                line_text = remaining_text[:5]  # 至少取5个字符
            
            # 尝试在标点符号或空格处优化断行
            if len(line_text) < len(remaining_text):
                # 向后查找合适的断点（标点符号、空格）
                best_break = len(line_text)
                for j in range(len(line_text) - 1, max(0, len(line_text) - 10), -1):
                    char = line_text[j]
                    if char in '，。！？；：、""''）】》':  # 中文标点后断行
                        best_break = j + 1
                        break
                    elif char in ' \t':  # 空格处断行
                        best_break = j
                        break
                
                line_text = line_text[:best_break]
            
            logger.debug(f"_wrap_text_to_width: 第{len(lines)+1}行: '{line_text}' (长度={len(line_text)})")
            
            lines.append(line_text)
            remaining_text = remaining_text[len(line_text):].lstrip()
            
            # 防止无限循环
            if not line_text:
                logger.warning("_wrap_text_to_width: 检测到潜在无限循环，强制退出")
                break
                
            # 限制最大行数防止性能问题
            if len(lines) >= 5:
                if remaining_text:
                    lines[-1] += "..."
                    logger.debug("_wrap_text_to_width: 达到最大行数限制，添加省略号")
                break
        
        logger.debug(f"_wrap_text_to_width: 换行完成，共{len(lines)}行")
        return lines

    def _update_position(self):
        """更新位置 - 仅在窗口大小变化时使用已锁定的位置"""
        if self._is_position_locked and self._fixed_geometry:
            x, y, width, height = self._fixed_geometry
            self.setGeometry(x, y, width, height)
            logger.debug(f"Ghost text position restored from lock: ({x}, {y})")
        elif not self._is_position_locked:
            # 如果位置未锁定，重新计算并锁定
            self._calculate_and_lock_position()
            self._is_position_locked = True
        
    def paintEvent(self, event: QPaintEvent):
        """绘制Ghost Text - 支持自动换行的多行显示和优化渲染效果"""
        if not self._is_visible or not self._ghost_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 设置字体（确保与编辑器字体一致）
        painter.setFont(self._font)

        # 使用更清晰的灰色，提高可读性
        ghost_color = QColor(120, 120, 120, 160)  # 稍微深一点，透明度60%
        painter.setPen(ghost_color)

        # 使用换行后的文本行（如果已经计算过），否则使用原始文本分割
        if hasattr(self, '_wrapped_lines') and self._wrapped_lines:
            display_lines = self._wrapped_lines
            logger.debug(f"paintEvent: 使用换行文本，共{len(display_lines)}行")
        else:
            # 回退到简单分割（兼容性）
            display_lines = self._ghost_text.split('\n')
            logger.debug(f"paintEvent: 回退到简单分割，共{len(display_lines)}行")
        
        line_height = self._font_metrics.height()
        
        # 逐行绘制文本
        y_offset = self._font_metrics.ascent()  # 使用字体上升高度作为基线偏移
        
        logger.debug(f"paintEvent: 开始绘制{len(display_lines)}行文本，y_offset={y_offset}, line_height={line_height}")
        
        for i, line in enumerate(display_lines):
            if line.strip():  # 只绘制非空行
                x = 0
                y = y_offset + (i * line_height)
                
                # 确保不超出widget边界
                if y > self.height():
                    logger.debug(f"paintEvent: 第{i+1}行超出边界，停止绘制")
                    break
                    
                painter.drawText(x, y, line)
                logger.debug(f"paintEvent: 第{i+1}行绘制完成: '{line}' at ({x}, {y})")
        
        logger.debug(f"paintEvent: Ghost text painted完成，widget rect {self.rect()}")
        
        
    def resizeEvent(self, event):
        """窗口大小变化时更新位置"""
        super().resizeEvent(event)
        if self._is_visible:
            self._update_position()


class SmartIncrementalCompletion:
    """智能增量补全 - 计算精确的补全差异"""
    
    @staticmethod
    def calculate_completion(current_text: str, cursor_pos: int, suggestion: str) -> Optional[str]:
        """计算增量补全 - 简化算法，优先依赖提示词质量

        Args:
            current_text: 当前文本
            cursor_pos: 光标位置
            suggestion: 建议文本

        Returns:
            需要补全的文本，如果不需要补全则返回None
        """
        if not suggestion or cursor_pos < 0:
            return None

        # 清理建议文本
        suggestion = suggestion.strip()
        if not suggestion:
            return None

        logger.debug(f"计算增量补全: cursor_pos={cursor_pos}, suggestion长度={len(suggestion)}")
        logger.debug(f"建议文本: '{suggestion[:100]}'")

        # 获取光标前的文本
        before_cursor = current_text[:cursor_pos]
        logger.debug(f"光标前文本后50字符: '{before_cursor[-50:]}'")

        # 方法1：直接检查是否有明显重复的开头
        # 检查建议是否以当前文本的结尾开始（最常见的重复情况）
        for check_length in [100, 50, 30, 20, 10, 5]:
            if len(before_cursor) >= check_length:
                recent_text = before_cursor[-check_length:]
                if suggestion.startswith(recent_text):
                    # 找到重复部分，返回差异
                    completion_part = suggestion[len(recent_text):]
                    if completion_part.strip():
                        logger.debug(f"检测到重复开头，返回差异部分: '{completion_part[:50]}...'")
                        return completion_part.strip()[:200]  # 限制长度

        # 方法2：检查建议是否包含当前文本的片段（在中间位置）
        if len(before_cursor) > 20:
            recent_text = before_cursor[-20:]  # 取最后20个字符
            pos = suggestion.find(recent_text)
            if pos >= 0:
                # 在建议中找到了当前文本片段
                after_pos = pos + len(recent_text)
                if after_pos < len(suggestion):
                    completion_part = suggestion[after_pos:]
                    if completion_part.strip():
                        logger.debug(f"在建议中找到当前文本片段，返回后续部分: '{completion_part[:50]}...'")
                        return completion_part.strip()[:200]

        # 方法3：如果没有明显重复，直接返回建议文本（信任提示词质量）
        # 但限制长度，避免过长的内容
        if len(suggestion) <= 200:
            logger.debug("没有检测到重复，直接返回建议文本")
            return suggestion
        else:
            # 在合适的断点处截断
            truncated = suggestion[:150]
            for punct in ['。', '！', '？', '，', '；', '\n']:
                punct_pos = truncated.rfind(punct)
                if punct_pos > 100:  # 确保不会截断得太短
                    truncated = suggestion[:punct_pos + 1]
                    break
            
            logger.debug(f"建议文本过长，截断返回: '{truncated}'")
            return truncated

        logger.debug("无法确定有效的补全内容")
        return None
        
    @staticmethod
    def _extract_current_word(text: str) -> str:
        """提取当前正在输入的单词"""
        if not text:
            return ""
            
        # 从末尾开始查找单词边界
        i = len(text) - 1
        while i >= 0:
            char = text[i]
            if char.isalnum() or char in ['@', '_', '-']:
                i -= 1
            else:
                break
                
        return text[i + 1:]


class ModernGhostTextCompletion(QObject):
    """现代化Ghost Text补全系统 - 使用内联渲染"""

    # 信号定义
    completionAccepted = pyqtSignal(str)
    completionRejected = pyqtSignal()

    def __init__(self, text_editor):
        super().__init__()
        self._text_editor = text_editor
        self._current_suggestion = ""
        self._current_completion = ""
        self._trigger_cursor_position = 0  # 触发时的光标位置

        # 自动隐藏定时器
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_completion)

        # 监听光标位置变化
        self._text_editor.cursorPositionChanged.connect(self._on_cursor_position_changed)

        logger.debug("Modern ghost text completion initialized with inline rendering")
        
    def show_completion(self, suggestion: str):
        """显示补全建议 - 使用内联渲染"""
        # 首先清除任何现有的Ghost Text
        self.hide_completion()

        if not suggestion or not suggestion.strip():
            return

        cursor = self._text_editor.textCursor()
        current_text = self._text_editor.toPlainText()
        cursor_pos = cursor.position()

        # 计算增量补全
        completion = SmartIncrementalCompletion.calculate_completion(
            current_text, cursor_pos, suggestion.strip()
        )

        if not completion:
            return

        # 保存状态
        self._current_suggestion = suggestion.strip()
        self._current_completion = completion
        self._trigger_cursor_position = cursor_pos  # 保存触发位置

        # 使用编辑器的内联渲染显示Ghost Text
        self._text_editor.set_ghost_text(completion, cursor_pos)

        # 设置自动隐藏（30秒，给用户足够时间审视和接受补全）
        self._hide_timer.start(30000)

        logger.info(f"Ghost text shown: '{completion[:30]}...' at trigger position {cursor_pos}")
        
    def hide_completion(self):
        """隐藏补全"""
        self._text_editor.clear_ghost_text()
        self._current_suggestion = ""
        self._current_completion = ""
        self._trigger_cursor_position = 0
        self._hide_timer.stop()

        logger.debug("Ghost text completion hidden and state cleared")

    def _on_cursor_position_changed(self):
        """光标位置变化时的处理 - 更宽松的隐藏逻辑，减少误触"""
        if not self._current_completion:
            return

        current_pos = self._text_editor.textCursor().position()

        # 更宽松的隐藏逻辑：只有在光标显著偏离时才隐藏
        position_diff = abs(current_pos - self._trigger_cursor_position)
        
        # 如果光标移动距离小于5个字符，不隐藏（允许小幅调整）
        if position_diff <= 5:
            return
            
        # 如果光标在触发位置左侧且距离较远，隐藏
        if current_pos < self._trigger_cursor_position - 3:
            self.hide_completion()
            logger.debug(f"Cursor moved significantly left from trigger position, hiding completion")
        # 如果光标移动超出补全范围较远，隐藏  
        elif current_pos > self._trigger_cursor_position + len(self._current_completion) + 10:
            self.hide_completion()
            logger.debug(f"Cursor moved significantly beyond completion range, hiding completion")
        
    def accept_completion(self):
        """接受补全"""
        if not self._current_completion:
            return False

        # 插入补全文本
        cursor = self._text_editor.textCursor()
        cursor.insertText(self._current_completion)

        # 清除Ghost Text
        completion_text = self._current_completion
        self.hide_completion()

        # 发出补全接受信号
        self.completionAccepted.emit(completion_text)

        logger.info(f"Ghost text completion accepted: '{completion_text}'")

        # 只在自动AI补全模式下才自动触发下一次补全
        if self._should_trigger_next_completion():
            # 延迟触发新的AI补全（给用户一点时间，然后基于新上下文生成补全）
            QTimer.singleShot(500, self._trigger_next_completion)

        return True
    
    def _should_trigger_next_completion(self) -> bool:
        """检查是否应该自动触发下一次补全"""
        try:
            # 获取当前补全模式
            if hasattr(self._text_editor, '_smart_completion'):
                current_mode = getattr(self._text_editor._smart_completion, '_completion_mode', 'auto_ai')
                # 只有在auto_ai模式下才自动触发下一次补全
                return current_mode == 'auto_ai'
            return False
        except Exception as e:
            logger.warning(f"Error checking completion mode: {e}")
            return False

    def _trigger_next_completion(self):
        """触发下一次AI补全"""
        try:
            # 通过AI管理器触发新的补全
            from ..ai.ai_manager import AIManager
            ai_manager = None

            # 查找AI管理器实例
            parent = self._text_editor.parent()
            while parent:
                if hasattr(parent, '_ai_manager'):
                    ai_manager = parent._ai_manager
                    break
                parent = parent.parent()

            if ai_manager:
                ai_manager.request_completion('smart')
                logger.debug("Triggered next AI completion after acceptance")
            else:
                logger.warning("Could not find AI manager to trigger next completion")
        except Exception as e:
            logger.error(f"Error triggering next completion: {e}")
        
    def reject_completion(self):
        """拒绝补全"""
        if self._current_completion:
            self.hide_completion()
            logger.debug("Ghost text completion rejected")
            return True
        return False
        
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """处理按键事件 - 优化Tab键处理

        Returns:
            bool: 如果事件被处理则返回True
        """
        # 如果没有当前补全，直接返回False
        if not self._current_completion or not self._current_completion.strip():
            return False

        key = event.key()
        modifiers = event.modifiers()

        # Tab键接受补全（无修饰键）
        if key == Qt.Key.Key_Tab and not modifiers:
            # 检查是否在有效的补全位置
            cursor = self._text_editor.textCursor()
            text = self._text_editor.toPlainText()
            position = cursor.position()

            # 验证补全位置是否仍然有效
            if self._is_completion_position_valid(text, position):
                success = self.accept_completion()
                logger.debug(f"Tab key pressed, completion accepted: {success}")
                return success
            else:
                # 位置无效，清除补全但不拦截Tab键
                self.hide_completion()
                logger.debug("Tab key pressed but completion position invalid, clearing completion")
                return False

        # Escape键拒绝补全
        elif key == Qt.Key.Key_Escape:
            success = self.reject_completion()
            logger.debug(f"Escape key pressed, completion rejected: {success}")
            return success

        # Enter键在新行时可以接受补全
        elif key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            cursor = self._text_editor.textCursor()
            text = self._text_editor.toPlainText()
            position = cursor.position()

            # 检查是否在空行且有有效补全
            if self._is_empty_line_completion(text, position):
                success = self.accept_completion()
                logger.debug(f"Enter key pressed on empty line, completion accepted: {success}")
                return success
            else:
                self.hide_completion()
                logger.debug("Enter key pressed, completion hidden")
                return False

        # 空格键时延迟隐藏补全（给用户思考时间）
        elif key == Qt.Key.Key_Space:
            # 不立即隐藏，而是重置定时器给用户更多时间
            self._hide_timer.stop()
            self._hide_timer.start(10000)  # 空格后给10秒时间
            logger.debug("Space key pressed, extending completion display time")
            return False  # 不拦截空格键

        # 字符输入时延迟隐藏而不是立即隐藏
        elif event.text() and event.text().isprintable():
            # 对于可打印字符，延迟隐藏而不是立即隐藏
            current_pos = self._text_editor.textCursor().position()
            # 如果用户在补全范围内输入，保持显示
            if self._trigger_cursor_position <= current_pos <= self._trigger_cursor_position + len(self._current_completion) + 5:
                self._hide_timer.stop()
                self._hide_timer.start(20000)  # 重置为20秒
                logger.debug("Character typed within completion range, extending display time")
            else:
                self.hide_completion()
                logger.debug("Character typed outside completion range, hiding completion")
            return False

        return False

    def _is_completion_position_valid(self, text: str, position: int) -> bool:
        """检查补全位置是否仍然有效"""
        if not self._trigger_cursor_position:
            return False

        # 检查光标是否在触发位置附近（允许一定的偏移）
        offset = position - self._trigger_cursor_position
        if offset < 0 or offset > 50:  # 最多允许50个字符的偏移
            return False

        return True

    def _is_empty_line_completion(self, text: str, position: int) -> bool:
        """检查是否在空行且适合接受补全"""
        if position <= 0:
            return False

        # 获取当前行
        lines = text[:position].split('\n')
        current_line = lines[-1] if lines else ""

        # 当前行为空或只有空白字符
        return not current_line.strip()

    def is_showing(self) -> bool:
        """是否正在显示补全"""
        return bool(self._current_completion)
        
    def update_position(self):
        """更新位置（当编辑器滚动时调用） - 使用固定位置"""
        if self._current_completion:
            # 只有在位置已锁定的情况下才更新
            self._ghost_renderer._update_position()

    def get_trigger_position(self) -> int:
        """获取触发位置"""
        return self._trigger_cursor_position
