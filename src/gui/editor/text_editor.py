from __future__ import annotations

"""
智能文本编辑器
基于novelWriter的GuiDocEditor和PlotBunni的AutoExpandingTextarea设计
实现专业的小说写作编辑器
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QFrame, QLabel, QPushButton, QToolButton,
    QScrollBar, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, pyqtSlot, QRect, QSize,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QFontMetrics, QTextCursor, QTextDocument,
    QTextCharFormat, QColor, QPainter, QTextBlock,
    QKeyEvent, QMouseEvent, QWheelEvent, QPaintEvent, QPalette
)

from typing import TYPE_CHECKING
from core.auto_replace import get_auto_replace_engine
from .syntax_highlighter import NovelWriterHighlighter
from .completion_widget import CompletionWidget
from .inline_completion import InlineCompletionManager
from .smart_completion_manager import SmartCompletionManager
from .completion_status_indicator import EmbeddedStatusIndicator
from .ghost_text_completion import ModernGhostTextCompletion
# from .ai_status_indicator import FloatingAIStatusIndicator  # 已移除，使用ModernAIStatusIndicator
from .modern_ai_indicator import AIStatusManager


logger = logging.getLogger(__name__)


class LineNumberArea(QWidget):
    """行号区域"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event: QPaintEvent):
        self.editor.line_number_area_paint_event(event)


class IntelligentTextEditor(QPlainTextEdit):
    """智能文本编辑器"""
    
    # 信号定义
    textModified = pyqtSignal(str)  # 文本修改信号
    cursorPositionChanged = pyqtSignal(int, int)  # 光标位置变化信号
    completionRequested = pyqtSignal(str, int)  # 补全请求信号
    conceptDetected = pyqtSignal(list)  # 概念检测信号
    metadataChanged = pyqtSignal(dict)  # 元数据变化信号
    autoSaveTriggered = pyqtSignal(str)  # 自动保存信号
    
    def __init__(self, config: Config, shared: Shared, parent=None):
        super().__init__(parent)
        
        self._config = config
        self._shared = shared
        
        # 编辑器状态
        self._is_modified = False
        self._last_save_content = ""
        self._current_document_id = None
        
        # 自动保存定时器
        self._auto_save_timer = QTimer()
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._trigger_auto_save)
        
        # 概念检测定时器
        self._concept_timer = QTimer()
        self._concept_timer.setSingleShot(True)
        self._concept_timer.timeout.connect(self._detect_concepts)
        
        # 行号区域
        self._line_number_area = LineNumberArea(self)

        # 语法高亮器
        self._syntax_highlighter = NovelWriterHighlighter(self._config, self.document())

        # 元数据提取器

        # 智能补全引擎
        from .completion_engine import CompletionEngine
        self._completion_engine = CompletionEngine(self._config, self)

        # 补全界面组件
        self._completion_widget = CompletionWidget(self)

        # 内联补全管理器
        self._inline_completion = InlineCompletionManager(self)

        # 智能补全管理器（统一管理所有补全）
        self._smart_completion = SmartCompletionManager(self, self._completion_engine)

        # Ghost Text补全系统
        self._ghost_completion = ModernGhostTextCompletion(self)

        # 现代AI状态指示器 - 使用新的优雅设计
        self._ai_status_manager = AIStatusManager(self)
        
        # 移除旧的FloatingAIStatusIndicator以防止冲突
        # self._ai_status_indicator = FloatingAIStatusIndicator(self)
        logger.debug("Modern AI status indicator initialized")

        # Ghost Text渲染属性
        self._ghost_text = ""
        self._ghost_cursor_position = 0
        self._ghost_font_metrics = None

        # 创建状态栏
        self._create_status_bar()

        # 自动替换引擎
        self._auto_replace_engine = get_auto_replace_engine()

        # Codex高亮器（可选）
        self._codex_highlighter = None
        try:
            from .codex_highlighter import CodexHighlighter
            self._codex_highlighter = CodexHighlighter(self, parent=self)
            logger.info("Codex highlighter initialized")
        except ImportError:
            logger.debug("Codex highlighter not available")

        # 当前文档信息
        self._current_document_id: Optional[str] = None
        self._project_manager = None

        # 初始化编辑器
        self._init_editor()
        self._init_signals()
        self._init_style()

        logger.info("Intelligent text editor initialized")

    def paintEvent(self, event: QPaintEvent):
        """重写paintEvent以支持Ghost Text渲染"""
        # 首先调用父类的paintEvent绘制正常文本
        super().paintEvent(event)

        # 然后绘制Ghost Text
        if self._ghost_text and self._ghost_cursor_position >= 0:
            self._paint_ghost_text()

    def _paint_ghost_text(self):
        """重新设计的Ghost Text渲染器 - 完全解决重叠和换行问题"""
        try:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            # 设置字体（与编辑器完全一致）
            painter.setFont(self.font())
            font_metrics = QFontMetrics(self.font())

            # 获取触发位置的光标
            cursor = QTextCursor(self.document())
            cursor.setPosition(self._ghost_cursor_position)
            cursor_rect = self.cursorRect(cursor)
            
            # 获取当前行信息
            current_block = cursor.block()
            block_text = current_block.text()
            cursor_position_in_block = cursor.position() - current_block.position()
            text_before_cursor = block_text[:cursor_position_in_block]
            text_after_cursor = block_text[cursor_position_in_block:]
            
            # 设置清晰的Ghost Text颜色
            base_color = self.palette().color(QPalette.ColorRole.Text)
            if base_color.lightness() > 128:  # 浅色主题
                ghost_color = QColor(100, 100, 100, 180)  # 更深的灰色，更不透明
            else:  # 深色主题
                ghost_color = QColor(140, 140, 140, 200)  # 更亮的灰色，更不透明
            
            painter.setPen(ghost_color)

            # 获取文档布局信息
            document_layout = self.document().documentLayout()
            margin = self.document().documentMargin()
            line_height = font_metrics.height()
            
            # 修复：计算更准确的布局信息，解决中句触发的重叠问题
            viewport_width = self.viewport().width()
            effective_line_width = viewport_width - margin * 2
            
            # 关键修复：正确计算光标后文本的真实宽度
            after_cursor_width = font_metrics.horizontalAdvance(text_after_cursor) if text_after_cursor.strip() else 0
            
            # 计算光标到行末的实际可用空间
            cursor_x_in_viewport = cursor_rect.left() - margin
            remaining_space_on_line = effective_line_width - cursor_x_in_viewport - after_cursor_width
            
            logger.debug(f"Ghost text精确布局: cursor_x={cursor_x_in_viewport}, after_width={after_cursor_width}")
            logger.debug(f"effective_line_width={effective_line_width}, remaining_space={remaining_space_on_line}")
            
            # 关键改进：智能判断是否需要换行，考虑中文字符宽度
            min_ghost_width = font_metrics.horizontalAdvance(self._ghost_text[:10]) if len(self._ghost_text) >= 10 else font_metrics.horizontalAdvance(self._ghost_text)
            need_new_line = remaining_space_on_line < min_ghost_width or remaining_space_on_line < 80  # 至少80像素
            
            # 修复：处理中句触发的情况
            if text_after_cursor.strip() and not need_new_line:
                # 中句触发且有足够空间：在光标后但不覆盖现有文本的位置显示
                start_y = cursor_rect.top() + font_metrics.ascent()
                start_x = cursor_rect.right() + 5  # 在光标右侧留5像素间隙
                available_width = remaining_space_on_line - 5
                first_line_mode = 'inline'  # 内联模式
                logger.debug(f"Ghost text内联模式: ({start_x}, {start_y}), 可用宽度={available_width}")
            elif need_new_line or text_after_cursor.strip():
                # 需要换行或有后续文本：从下一行开始
                start_y = cursor_rect.bottom() + font_metrics.ascent()
                start_x = margin
                available_width = effective_line_width
                first_line_mode = 'newline'  # 换行模式
                logger.debug(f"Ghost text换行模式: ({start_x}, {start_y}), 可用宽度={available_width}")
            else:
                # 行末触发：直接在光标位置继续
                start_y = cursor_rect.top() + font_metrics.ascent()
                start_x = cursor_rect.right()
                available_width = remaining_space_on_line
                first_line_mode = 'continue'  # 继续模式
                logger.debug(f"Ghost text继续模式: ({start_x}, {start_y}), 可用宽度={available_width}")
            
            # 按行分割Ghost Text，使用改进的换行逻辑
            ghost_lines = self._split_ghost_text_with_smart_wrapping(
                self._ghost_text, available_width, effective_line_width, font_metrics, first_line_mode
            )
            
            # 绘制Ghost Text行
            current_y = start_y
            
            for i, line_text in enumerate(ghost_lines[:5]):  # 最多5行
                if not line_text.strip():
                    current_y += line_height
                    continue
                    
                # 检查是否超出可视区域
                if current_y > self.viewport().height():
                    break
                
                if i == 0 and first_line_mode in ['inline', 'continue']:
                    # 第一行：从光标位置或指定位置开始
                    painter.drawText(int(start_x), int(current_y), line_text)
                    logger.debug(f"Ghost text第1行({first_line_mode}): ({int(start_x)}, {int(current_y)}) '{line_text[:30]}...'")
                else:
                    # 后续行：从左边距开始，确保对齐
                    painter.drawText(int(margin), int(current_y), line_text)
                    logger.debug(f"Ghost text第{i+1}行: ({int(margin)}, {int(current_y)}) '{line_text[:30]}...'")
                
                current_y += line_height

            logger.debug(f"Ghost text绘制完成: {len(ghost_lines)} 行, 模式: {first_line_mode}")

        except Exception as e:
            logger.error(f"Ghost text绘制错误: {e}")
    
    def _split_ghost_text_properly(self, text: str, first_line_width: int, max_line_width: int, font_metrics: QFontMetrics, start_from_next_line: bool) -> list[str]:
        """正确分割Ghost Text，使用与编辑器一致的换行逻辑"""
        if not text:
            return []
        
        lines = []
        remaining_text = text.strip()
        
        # 处理第一行
        if start_from_next_line:
            current_width = max_line_width
        else:
            current_width = first_line_width
        
        line_count = 0
        while remaining_text and line_count < 5:
            # 二分查找最佳断行位置
            best_length = self._find_optimal_break_position(remaining_text, current_width, font_metrics)
            
            if best_length <= 0:
                # 如果连一个字符都放不下，强制取一个字符
                best_length = 1
            
            line_text = remaining_text[:best_length]
            
            # 在合适的位置断行（标点符号处）
            if best_length < len(remaining_text) and best_length > 10:
                better_break = self._find_smart_break_point(line_text)
                if better_break > 0:
                    line_text = line_text[:better_break]
            
            lines.append(line_text.rstrip())
            remaining_text = remaining_text[len(line_text):].lstrip()
            
            # 第一行之后都使用完整行宽
            current_width = max_line_width
            line_count += 1
        
        # 如果还有剩余文本，在最后一行添加省略号
        if remaining_text and lines:
            lines[-1] += "..."
        
        return lines
    
    def _split_ghost_text_with_smart_wrapping(self, text: str, first_line_width: int, max_line_width: int, font_metrics: QFontMetrics, mode: str) -> list[str]:
        """智能分割Ghost Text，支持不同显示模式的优化换行逻辑"""
        if not text:
            return []
        
        lines = []
        remaining_text = text.strip()
        
        # 根据模式设置第一行的处理策略
        if mode == 'newline':
            # 换行模式：所有行都使用完整宽度
            current_width = max_line_width
        else:
            # 内联/继续模式：第一行使用限制宽度
            current_width = first_line_width
        
        line_count = 0
        max_lines = 4  # 限制最大行数，避免过长的ghost text
        
        while remaining_text and line_count < max_lines:
            # 优化：使用更智能的断行算法
            best_length = self._find_optimal_break_position(remaining_text, current_width, font_metrics)
            
            if best_length <= 0:
                # 如果连一个字符都放不下，强制取最少字符
                best_length = min(3, len(remaining_text))
            
            line_text = remaining_text[:best_length]
            
            # 在合适的位置进行智能断行
            if best_length < len(remaining_text) and best_length > 5:
                optimized_break = self._find_smart_break_point(line_text)
                if optimized_break > 0:
                    line_text = line_text[:optimized_break]
            
            # 清理和添加行
            clean_line = line_text.rstrip()
            if clean_line:  # 只添加非空行
                lines.append(clean_line)
            
            # 更新剩余文本
            remaining_text = remaining_text[len(line_text):].lstrip()
            
            # 第一行之后使用完整行宽
            if line_count == 0 and mode in ['inline', 'continue']:
                current_width = max_line_width
            
            line_count += 1
        
        # 如果还有剩余文本，在最后一行添加省略号
        if remaining_text and lines:
            if len(lines[-1]) > 50:  # 如果最后一行过长，截断一些
                lines[-1] = lines[-1][:47] + "..."
            else:
                lines[-1] += "..."
        
        return lines
    
    def _find_optimal_break_position(self, text: str, max_width: int, font_metrics: QFontMetrics) -> int:
        """优化的断行位置查找，更准确地处理中文字符"""
        if max_width <= 20:  # 宽度太小
            return min(2, len(text))
        
        # 使用二分查找找到能放入的最大字符数
        left, right = 0, len(text)
        best_length = 0
        
        while left <= right:
            mid = (left + right) // 2
            test_text = text[:mid]
            
            try:
                text_width = font_metrics.horizontalAdvance(test_text)
            except Exception:
                # 如果测量失败，使用估算值
                text_width = len(test_text) * 12  # 估算每个字符12像素
            
            if text_width <= max_width:
                best_length = mid
                left = mid + 1
            else:
                right = mid - 1
        
        # 确保至少返回1个字符（除非宽度太小）
        return max(1, best_length) if max_width > 10 else 0
    
    def _find_smart_break_point(self, text: str) -> int:
        """智能找到更好的断行点，优先在标点符号和空格处断行"""
        if len(text) <= 5:
            return len(text)
        
        # 从后向前查找最佳断点，优先级从高到低
        search_range = min(20, len(text))  # 在最后20个字符中查找
        
        # 第一优先级：中文句号后面
        for i in range(len(text) - 1, max(0, len(text) - search_range), -1):
            if text[i] in '。！？；：':
                return i + 1
        
        # 第二优先级：中文逗号后面
        for i in range(len(text) - 1, max(0, len(text) - search_range), -1):
            if text[i] in '，、':
                return i + 1
        
        # 第三优先级：空格或tab
        for i in range(len(text) - 1, max(0, len(text) - search_range), -1):
            if text[i] in ' \t':
                return i
        
        # 第四优先级：英文标点
        for i in range(len(text) - 1, max(0, len(text) - search_range), -1):
            if text[i] in '.!?;:':
                return i + 1
        
        # 第五优先级：括号后面
        for i in range(len(text) - 1, max(0, len(text) - search_range), -1):
            if text[i] in '）】》"\'':
                return i + 1
        
        # 如果没有找到合适的断点，返回原长度
        return len(text)

    def set_ghost_text(self, text: str, cursor_position: int):
        """设置Ghost Text内容和位置"""
        self._ghost_text = text
        self._ghost_cursor_position = cursor_position
        
        # 立即强制清除所有ExtraSelections，防止任何高亮显示
        self.setExtraSelections([])
        
        # 确保AI状态指示器不会干扰显示
        # FloatingAIStatusIndicator已被移除
        # if hasattr(self, '_ai_status_indicator'):
        #     self._ai_status_indicator.hide()
        #     self._ai_status_indicator.set_visible(False)
        
        # 触发重绘
        self.viewport().update()
        
        # 再次确保没有ExtraSelections残留
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1, lambda: self.setExtraSelections([]))
        
        logger.debug(f"Ghost Text已设置: position={cursor_position}, content='{text[:50]}...'")

    def clear_ghost_text(self):
        """清除Ghost Text"""
        self._ghost_text = ""
        self._ghost_cursor_position = -1
        
        # 强制清除所有ExtraSelections，防止渲染残留
        self.setExtraSelections([])
        
        # 触发重绘
        self.viewport().update()
        
        # 延迟恢复当前行高亮，确保Ghost Text完全清除
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, self._highlight_current_line)
        
        logger.debug("Ghost Text已清除")

    def _create_status_bar(self):
        """创建状态栏"""
        # 创建嵌入式状态指示器
        self._status_indicator = EmbeddedStatusIndicator()

        # FloatingStatusIndicator已从SmartCompletionManager中移除
        # 所有状态显示由EmbeddedStatusIndicator和ModernAIStatusIndicator负责
        
        logger.info("All floating status indicators disabled, using embedded status bar")

        # 连接信号
        self._status_indicator.modeChangeRequested.connect(
            self._smart_completion.set_completion_mode
        )

        # 设置初始状态
        self._status_indicator.set_completion_mode('auto_ai')
        self._status_indicator.set_ai_status('idle')
        self._status_indicator.set_ai_available(True)
    
    def _init_editor(self):
        """初始化编辑器设置"""
        # 字体设置
        font_family = self._config.get("editor", "font_family", "Consolas")
        font_size = self._config.get("editor", "font_size", 14)
        
        font = QFont(font_family, font_size)
        font.setFixedPitch(True)
        self.setFont(font)
        
        # 编辑器行为设置
        self.setTabStopDistance(40)  # Tab宽度
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setUndoRedoEnabled(True)
        
        # 显示设置
        show_line_numbers = self._config.get("editor", "show_line_numbers", False)
        if show_line_numbers:
            self._update_line_number_area_width()
        
        # 高亮当前行
        if self._config.get("editor", "highlight_current_line", True):
            self._highlight_current_line()
        
        # 设置占位符文本
        self.setPlaceholderText("开始写作您的小说...")
    
    def _init_signals(self):
        """初始化信号连接"""
        # 文本变化信号
        self.textChanged.connect(self._on_text_changed)
        # 注意：这里连接的是QPlainTextEdit的内置信号，不是我们自定义的信号
        super().cursorPositionChanged.connect(self._on_cursor_position_changed)
        
        # 滚动信号
        self.verticalScrollBar().valueChanged.connect(self._update_line_numbers)
        
        # 块计数变化信号
        self.blockCountChanged.connect(self._update_line_number_area_width)
        
        # 更新请求信号
        self.updateRequest.connect(self._update_line_number_area)

        # 补全相关信号
        self._completion_widget.suggestionAccepted.connect(self._on_suggestion_accepted)
        self._completion_widget.cancelled.connect(self._on_completion_cancelled)
    
    def _init_style(self):
        """初始化样式"""
        # Style is now managed globally by the theme QSS files.
        self.setStyleSheet("""
            QPlainTextEdit {
                padding: 12px;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
    
    def _highlight_current_line(self):
        """高亮当前行"""
        extra_selections = []
        
        # 如果当前显示Ghost Text，完全禁用当前行高亮以避免渲染冲突
        if self._ghost_text and self._ghost_cursor_position >= 0:
            self.setExtraSelections([])
            return
        
        # 检查是否启用了当前行高亮
        if not self._config.get("editor", "highlight_current_line", True):
            self.setExtraSelections([])
            return
        
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            
            # 使用更温和的颜色，避免与Ghost Text颜色冲突
            # 根据主题选择合适的颜色
            base_color = self.palette().color(QPalette.ColorRole.Base)
            if base_color.lightness() > 128:  # 浅色主题
                line_color = QColor(248, 248, 248, 30)  # 非常浅的灰色，更低透明度
            else:  # 深色主题
                line_color = QColor(40, 44, 52, 40)  # 更淡的半透明深灰色，更低透明度
            
            selection.format.setBackground(line_color)
            
            # 完全移除FullWidthSelection相关属性，防止全宽渲染
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)
    
    def line_number_area_width(self) -> int:
        """计算行号区域宽度"""
        if not self._config.get("editor", "show_line_numbers", False):
            return 0
        
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def _update_line_number_area_width(self):
        """更新行号区域宽度"""
        if self._config.get("editor", "show_line_numbers", False):
            self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        else:
            self.setViewportMargins(0, 0, 0, 0)
    
    def _update_line_number_area(self, rect: QRect, dy: int):
        """更新行号区域"""
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), 
                                        self._line_number_area.width(), 
                                        rect.height())
        
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()
    
    def _update_line_numbers(self):
        """更新行号显示"""
        if self._config.get("editor", "show_line_numbers", False):
            self._line_number_area.update()
    
    def line_number_area_paint_event(self, event: QPaintEvent):
        """绘制行号区域"""
        if not self._config.get("editor", "show_line_numbers", False):
            return
        
        painter = QPainter(self._line_number_area)
        # Use the base color from the palette for the line number area background
        painter.fillRect(event.rect(), self.palette().color(QPalette.ColorRole.Base))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        height = self.fontMetrics().height()
        
        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                # Use the text color from the palette for the line numbers
                painter.setPen(self.palette().color(QPalette.ColorRole.Text))
                painter.drawText(0, int(top), self._line_number_area.width() - 3, 
                               height, Qt.AlignmentFlag.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def resizeEvent(self, event):
        """窗口大小变化事件"""
        super().resizeEvent(event)
        
        if self._config.get("editor", "show_line_numbers", False):
            cr = self.contentsRect()
            self._line_number_area.setGeometry(
                QRect(cr.left(), cr.top(), 
                     self.line_number_area_width(), cr.height())
            )
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件处理 - 优化Ghost Text和补全处理"""
        key = event.key()
        modifiers = event.modifiers()

        # 第一优先级：Ghost Text补全处理
        if hasattr(self, '_ghost_completion') and self._ghost_completion:
            if self._ghost_completion.handle_key_press(event):
                return

        # 第二优先级：智能补全管理器处理
        if self._smart_completion.handle_key_press(event):
            return

        # 第三优先级：弹出式补全组件处理
        if self._completion_widget.isVisible():
            if key in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                # 将事件传递给补全组件（但不包括Tab键，Tab键由Ghost Text处理）
                self._completion_widget.keyPressEvent(event)
                return
            elif key == Qt.Key.Key_Escape:
                # ESC键隐藏补全组件
                self._completion_widget.hide()
                return
            elif key in [Qt.Key.Key_Backspace, Qt.Key.Key_Delete]:
                # 删除键：先处理删除，然后更新补全
                super().keyPressEvent(event)
                self._update_completion_on_text_change()
                return

        # Tab键：智能补全触发（如果没有Ghost Text显示）
        if key == Qt.Key.Key_Tab and not modifiers:
            # 检查是否有Ghost Text显示
            if hasattr(self, '_ghost_completion') and self._ghost_completion and self._ghost_completion.is_showing():
                # Ghost Text已经在上面处理了，这里不应该到达
                return
            else:
                # 根据当前补全模式决定行为
                current_mode = getattr(self._smart_completion, '_completion_mode', 'auto_ai')
                if current_mode == 'manual_ai':
                    # 手动AI模式：手动触发AI补全
                    self._smart_completion.trigger_completion('manual')
                elif current_mode == 'auto_ai':
                    # 自动AI模式：手动触发AI补全
                    self._smart_completion.trigger_completion('manual')
                elif current_mode == 'disabled':
                    # 禁用模式：使用默认Tab行为（插入制表符或缩进）
                    super().keyPressEvent(event)
                else:
                    # 兜底：使用传统补全
                    self._trigger_completion()
                return

        # Ctrl+Space：强制AI补全
        elif key == Qt.Key.Key_Space and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._trigger_ai_completion()
            return

        # 回车键：智能换行
        elif key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            self._handle_smart_return(event)
            return

        # 处理其他按键
        super().keyPressEvent(event)

        # 如果是字符输入，检查自动替换和补全
        if event.text() and event.text().isprintable():
            self._handle_auto_replace(event)
            self._check_auto_completion()

        # 延迟触发概念检测
        self._concept_timer.start(500)

    def _handle_auto_replace(self, event: QKeyEvent):
        """处理自动替换"""
        if not self._auto_replace_engine.is_enabled():
            return

        # 获取当前文本和光标位置
        text = self.toPlainText()
        cursor = self.textCursor()
        cursor_position = cursor.position()

        # 只在特定字符后触发自动替换
        trigger_chars = [' ', '.', ',', '!', '?', ';', ':', '\n', '\t']
        if event.text() not in trigger_chars:
            return

        try:
            # 处理自动替换
            new_text, new_cursor_position = self._auto_replace_engine.process_text(
                text, cursor_position
            )

            # 如果文本发生了变化，更新编辑器
            if new_text != text:
                # 保存当前选择状态
                old_cursor = self.textCursor()

                # 更新文本
                self.setPlainText(new_text)

                # 恢复光标位置
                new_cursor = self.textCursor()
                new_cursor.setPosition(new_cursor_position)
                self.setTextCursor(new_cursor)

                logger.debug(f"Auto replace applied at position {cursor_position}")

        except Exception as e:
            logger.error(f"Auto replace failed: {e}")

    def _update_completion_on_text_change(self):
        """文本变化时更新补全"""
        if self._completion_widget.isVisible():
            # 重新触发补全以更新建议
            self._trigger_completion()

    def _check_auto_completion(self):
        """检查是否需要自动触发补全"""
        cursor = self.textCursor()
        text = self.toPlainText()
        pos = cursor.position()

        # 检查是否在@标记后
        if pos > 0 and text[pos-1] == '@':
            # 刚输入@，不立即触发
            return

        # 检查是否在@标记中输入
        start_pos = max(0, pos - 10)  # 向前查找最多10个字符
        recent_text = text[start_pos:pos]

        # 如果最近的文本包含@且没有空格，可能是在输入@标记
        if '@' in recent_text and ' ' not in recent_text.split('@')[-1]:
            # 延迟触发补全，避免过于频繁
            if not hasattr(self, '_auto_completion_timer'):
                from PyQt6.QtCore import QTimer
                self._auto_completion_timer = QTimer()
                self._auto_completion_timer.setSingleShot(True)
                self._auto_completion_timer.timeout.connect(self._trigger_completion)

            self._auto_completion_timer.start(300)  # 300ms后触发
    
    def _handle_smart_return(self, event: QKeyEvent):
        """智能换行处理"""
        cursor = self.textCursor()
        
        # 获取当前行文本
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        current_line = cursor.selectedText()
        
        # 计算缩进
        indent = ""
        for char in current_line:
            if char in [' ', '\t']:
                indent += char
            else:
                break
        
        # 插入换行和缩进
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText('\n' + indent)
        
        self.setTextCursor(cursor)
    
    def _trigger_completion(self):
        """触发智能补全"""
        cursor_pos = self.textCursor().position()
        text = self.toPlainText()

        # 使用补全引擎获取建议
        suggestions = self._completion_engine.get_completions(text, cursor_pos)

        if suggestions:
            # 定位补全组件
            cursor_rect = self.cursorRect()
            global_rect = cursor_rect.translated(self.mapToGlobal(cursor_rect.topLeft()) - cursor_rect.topLeft())
            self._completion_widget.position_near_cursor(global_rect)

            # 显示建议
            self._completion_widget.show_suggestions(suggestions)
        else:
            self._completion_widget.show_no_suggestions()

        logger.debug(f"Completion triggered: {len(suggestions)} suggestions")
    
    def _trigger_ai_completion(self):
        """触发AI补全"""
        cursor_pos = self.textCursor().position()
        text = self.toPlainText()
        
        # 发出AI补全请求信号
        self.completionRequested.emit(text, cursor_pos)
        logger.debug("AI completion requested")

    def show_inline_ai_completion(self, suggestion: str):
        """显示内联AI补全建议"""
        if suggestion and self._inline_completion:
            self._inline_completion.show_completion(suggestion)
            logger.info(f"Inline AI completion shown: {suggestion[:50]}...")

    def show_ghost_ai_completion(self, suggestion: str):
        """显示Ghost Text AI补全建议"""
        if suggestion and self._ghost_completion:
            self._ghost_completion.show_completion(suggestion)
            logger.info(f"Ghost text AI completion shown: {suggestion[:50]}...")

    def hide_inline_completion(self):
        """隐藏内联补全"""
        if self._inline_completion:
            self._inline_completion.hide_completion()

    def hide_ghost_completion(self):
        """隐藏Ghost Text补全"""
        if self._ghost_completion:
            self._ghost_completion.hide_completion()

    def show_inline_ai_completion(self, suggestion: str):
        """显示内联AI补全建议"""
        if suggestion and self._inline_completion:
            self._inline_completion.show_completion(suggestion)
            logger.info(f"Inline AI completion shown: {suggestion[:50]}...")

    def hide_inline_completion(self):
        """隐藏内联补全"""
        if self._inline_completion:
            self._inline_completion.hide_completion()
    
    @pyqtSlot()
    def _on_text_changed(self):
        """文本变化处理"""
        self._is_modified = True

        # 立即清除Ghost Text（用户输入时应该清除补全预览）
        self.clear_ghost_text()

        # 重启自动保存定时器
        auto_save_interval = self._config.get("app", "auto_save_interval", 30) * 1000
        self._auto_save_timer.start(auto_save_interval)

        # 发出文本变化信号
        text = self.toPlainText()

        # 发出文本修改信号
        self.textModified.emit(text)

    def _on_suggestion_accepted(self, suggestion):
        """处理补全建议接受"""
        cursor = self.textCursor()

        # 移动到插入位置
        cursor.setPosition(suggestion.insert_position)

        # 选择要替换的文本
        if suggestion.replace_length > 0:
            cursor.setPosition(
                suggestion.insert_position + suggestion.replace_length,
                QTextCursor.MoveMode.KeepAnchor
            )

        # 插入补全文本
        cursor.insertText(suggestion.text)

        # 更新光标位置
        self.setTextCursor(cursor)

        logger.info(f"Suggestion accepted: {suggestion.text}")

    def _on_completion_cancelled(self):
        """处理补全取消"""
        logger.debug("Completion cancelled")
    
    @pyqtSlot()
    def _on_cursor_position_changed(self):
        """光标位置变化处理"""
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1  # 行数从1开始
        column = cursor.columnNumber()  # 列数使用Qt原始值（修复多1的问题）

        logger.debug(f"Text editor cursor position changed: line={line}, column={column}")

        # Ghost Text状态检查 - 如果有Ghost Text显示，完全跳过当前行高亮
        if self._ghost_text and self._ghost_cursor_position >= 0:
            # 确保没有任何ExtraSelections在Ghost Text显示时存在
            self.setExtraSelections([])
        else:
            # 只有在没有Ghost Text时才进行当前行高亮
            if self._config.get("editor", "highlight_current_line", True):
                self._highlight_current_line()

        # 发出光标位置变化信号
        self.cursorPositionChanged.emit(line, column)
    
    @pyqtSlot()
    def _trigger_auto_save(self):
        """触发自动保存"""
        if self._is_modified:
            content = self.toPlainText()
            if content != self._last_save_content:
                self._last_save_content = content

                # 如果有当前文档和项目管理器，直接保存
                if self._current_document_id and self._project_manager:
                    success = self._project_manager.update_document_content(self._current_document_id, content)
                    if success:
                        self._is_modified = False
                        logger.debug(f"Auto saved document: {self._current_document_id}")
                    else:
                        logger.warning(f"Failed to auto save document: {self._current_document_id}")

                # 发出信号以便其他组件处理
                self.autoSaveTriggered.emit(content)
                logger.debug("Auto save triggered")
    
    @pyqtSlot()
    def _detect_concepts(self):
        """检测概念 - 概念系统已移除，发出空列表"""
        # 概念检测系统已被移除，发出空的概念列表
        self.conceptDetected.emit([])
        logger.debug("Concept detection system has been removed")
    
    def set_document_content(self, content: str, document_id: str = None):
        """设置文档内容"""
        self.setPlainText(content)
        self._current_document_id = document_id
        self._last_save_content = content
        self._is_modified = False
        
        logger.info(f"Document content set: {document_id}")
    
    def get_document_content(self) -> str:
        """获取文档内容"""
        return self.toPlainText()
    
    def is_modified(self) -> bool:
        """检查是否已修改"""
        return self._is_modified
    
    def save_document(self):
        """保存文档"""
        if self._is_modified:
            content = self.toPlainText()
            self._last_save_content = content
            self._is_modified = False
            self.autoSaveTriggered.emit(content)
            logger.info("Document saved manually")
    
    def insert_text_at_cursor(self, text: str):
        """在光标位置插入文本"""
        cursor = self.textCursor()
        cursor.insertText(text)
        self.setTextCursor(cursor)
    
    def get_current_word(self) -> str:
        """获取光标处的当前单词"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()
    
    def get_current_line(self) -> str:
        """获取当前行文本"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        return cursor.selectedText()
    
    def get_context_around_cursor(self, chars_before: int = 500, chars_after: int = 100) -> str:
        """获取光标周围的上下文"""
        cursor_pos = self.textCursor().position()
        text = self.toPlainText()

        start = max(0, cursor_pos - chars_before)
        end = min(len(text), cursor_pos + chars_after)

        return text[start:end]

    def update_syntax_highlighter_theme(self, theme: str):
        """更新语法高亮器主题"""
        if self._syntax_highlighter:
            self._syntax_highlighter.update_theme(theme)
            logger.info(f"Syntax highlighter theme updated to: {theme}")

    def get_syntax_highlighter(self) -> NovelWriterHighlighter:
        """获取语法高亮器"""
        return self._syntax_highlighter



    def set_project_manager(self, project_manager):
        """设置项目管理器"""
        self._project_manager = project_manager
        logger.info("Project manager set for text editor")
    
    def set_codex_components(self, codex_manager, reference_detector):
        """设置Codex组件（用于引用高亮）"""
        if self._codex_highlighter:
            self._codex_highlighter.set_codex_manager(codex_manager)
            self._codex_highlighter.set_reference_detector(reference_detector)
            logger.info("Codex components set for text editor")
            
            # 如果已有文本，立即执行高亮
            if self.toPlainText():
                self._codex_highlighter.refresh()
    
    def set_codex_highlight_enabled(self, enabled: bool):
        """启用/禁用Codex引用高亮"""
        if self._codex_highlighter:
            self._codex_highlighter.set_highlight_enabled(enabled)

    def load_document(self, document_id: str) -> bool:
        """加载文档内容"""
        if not self._project_manager:
            logger.warning("No project manager set, cannot load document")
            return False

        content = self._project_manager.get_document_content(document_id)
        if content is not None:
            # 暂时断开信号以避免触发保存
            self.textChanged.disconnect()

            # 设置文档内容
            self.setPlainText(content)
            self._current_document_id = document_id
            self._is_modified = False
            self._last_save_content = content

            # 重新连接信号
            self.textChanged.connect(self._on_text_changed)

            logger.info(f"Document loaded: {document_id}")
            return True
        else:
            logger.warning(f"Failed to load document: {document_id}")
            return False

    def save_current_document(self) -> bool:
        """保存当前文档"""
        if not self._current_document_id or not self._project_manager:
            logger.warning("No current document or project manager to save")
            return False

        content = self.toPlainText()
        success = self._project_manager.update_document_content(self._current_document_id, content)

        if success:
            self._is_modified = False
            self._last_save_content = content
            logger.info(f"Document saved: {self._current_document_id}")
        else:
            logger.warning(f"Failed to save document: {self._current_document_id}")

        return success

    def get_current_document_id(self) -> Optional[str]:
        """获取当前文档ID"""
        return self._current_document_id

    def is_document_modified(self) -> bool:
        """检查文档是否已修改"""
        return self._is_modified

    def clear_editor(self):
        """清空编辑器"""
        self.clear()
        self._current_document_id = None
        self._is_modified = False
        self._last_save_content = ""
        logger.debug("Editor cleared")
