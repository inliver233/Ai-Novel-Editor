"""
OptimalGhostText - 简化但功能完整的Ghost Text系统
实现用户的四个完整目标：
1. 行末续写：像正常打字一样自然延续，自动换行
2. 中间插入：真正推开后续文字，不重叠不遮挡
3. 完美预览：预览效果与实际插入后完全一样
4. 颜色区分：只有颜色不同（灰色vs白色），位置完全一致
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import (
    QTextDocument, QTextCursor, QTextCharFormat, 
    QColor, QKeyEvent, QFont
)

logger = logging.getLogger(__name__)


class OptimalGhostText(QObject):
    """最优Ghost Text系统 - 简化架构，完整功能"""
    
    # 信号
    ghost_text_accepted = pyqtSignal(str)
    ghost_text_rejected = pyqtSignal()
    
    # 兼容性信号
    completionAccepted = pyqtSignal(str)
    completionRejected = pyqtSignal()
    
    def __init__(self, text_editor: QTextEdit):
        super().__init__(text_editor)
        self.text_editor = text_editor
        self.document = text_editor.document()
        
        # 状态管理
        self._ghost_text = ""
        self._ghost_start_pos = -1
        self._ghost_end_pos = -1
        self._is_active = False
        self._base_char_format = None  # ��¼��ʾGhost Textǰ���λ�õĻ����ַ���ʽ
        
        # 创建Ghost Text格式
        self._ghost_format = self._create_ghost_format()
        
        # 保存undo状态用于清理
        self._undo_position = -1
        
        logger.info("OptimalGhostText系统初始化完成")
    
    def _create_ghost_format(self) -> QTextCharFormat:
        """创建Ghost Text专用格式 - 实现颜色区分"""
        ghost_format = QTextCharFormat()
        
        # 根据主题设置适当的灰色
        if hasattr(self.text_editor, 'palette'):
            base_color = self.text_editor.palette().text().color()
            if base_color.lightness() > 128:  # 浅色主题
                ghost_color = QColor(120, 120, 120, 200)  # 深灰色
            else:  # 深色主题
                ghost_color = QColor(160, 160, 160, 200)  # 亮灰色
        else:
            ghost_color = QColor(128, 128, 128, 200)  # 默认灰色
            
        ghost_format.setForeground(ghost_color)
        
        # 设置Ghost Text标记属性 - 完全兼容PyQt6
        self._set_ghost_property(ghost_format)
        
        return ghost_format
    
    def _set_ghost_property(self, ghost_format: QTextCharFormat):
        """安全设置Ghost Text属性 - 多重兼容性保障"""
        try:
            # 方法1: PyQt6标准方式
            from PyQt6.QtGui import QTextFormat
            ghost_format.setProperty(QTextFormat.UserProperty + 1, "ghost_text_marker")
            logger.debug("使用QTextFormat.UserProperty设置Ghost Text属性")
        except (AttributeError, ImportError):
            try:
                # 方法2: 硬编码值备用方案
                ghost_format.setProperty(0x100000 + 1, "ghost_text_marker")
                logger.debug("使用硬编码值设置Ghost Text属性")
            except Exception as e:
                # 方法3: 优雅降级
                logger.warning(f"无法设置Ghost Text自定义属性: {e}, 但不影响显示功能")
    
    def show_ghost_text(self, text: str, position: int) -> bool:
        """显示Ghost Text - 真正推开后续文字"""
        if not text or position < 0:
            return False
        
        # 清理现有的Ghost Text
        self.clear_ghost_text()
        
        try:
            # 保存当前undo状态
            self._undo_position = self.document.availableUndoSteps()
            
            # 创建光标
            cursor = QTextCursor(self.document)
            cursor.setPosition(position)
            
            # Record the base char format at insertion position for later restore
            try:
                self._base_char_format = cursor.charFormat()
            except Exception:
                self._base_char_format = None
            
            # 检测插入类型
            cursor_block = cursor.block()
            position_in_block = position - cursor_block.position()
            block_text = cursor_block.text()
            
            # 判断是行末续写还是中间插入
            is_end_of_line = (position_in_block >= len(block_text.rstrip()))
            
            if is_end_of_line:
                # 行末续写：自然延续，支持自动换行
                processed_text = self._process_end_of_line_text(text)
            else:
                # 中间插入：真正推开后续文字
                processed_text = self._process_middle_insertion_text(text, cursor)
            
            # 插入Ghost Text到文档 - 实现完美预览
            cursor.insertText(processed_text, self._ghost_format)
            
            # 更新状态
            self._ghost_text = processed_text
            self._ghost_start_pos = position
            self._ghost_end_pos = position + len(processed_text)
            self._is_active = True
            
            # 将光标移回插入位置，保持用户体验
            cursor.setPosition(position)
            self.text_editor.setTextCursor(cursor)
            
            logger.info(f"✅ Ghost Text显示成功: '{text[:30]}...' (pos={position}, type={'行末' if is_end_of_line else '中间'})")
            return True
            
        except Exception as e:
            logger.error(f"Ghost Text显示失败: {e}")
            return False
    
    def _process_end_of_line_text(self, text: str) -> str:
        """处理行末续写文本 - 实现自然延续和自动换行"""
        # 为行末续写添加智能换行
        # 如果文本很长，在合适位置添加换行
        processed_lines = []
        current_line = ""
        
        # 简单的换行逻辑：每80个字符换行，在句号或逗号处优先换行
        for char in text:
            current_line += char
            
            # 在标点符号处换行，或者行太长时强制换行
            if len(current_line) > 80 and char in "。，！？；":
                processed_lines.append(current_line)
                current_line = ""
            elif len(current_line) > 120:  # 强制换行
                processed_lines.append(current_line)
                current_line = ""
        
        if current_line:
            processed_lines.append(current_line)
        
        return "\n".join(processed_lines)
    
    def _process_middle_insertion_text(self, text: str, cursor: QTextCursor) -> str:
        """处理中间插入文本 - 确保推开后续文字"""
        # 对于中间插入，保持文本原样
        # QTextDocument的insertText已经会自动推开后续文字
        return text
    
    def clear_ghost_text(self):
        """清理Ghost Text"""
        if not self._is_active:
            return
        
        try:
            # 使用undo操作移除临时插入的文本
            if self._undo_position >= 0:
                current_undo_steps = self.document.availableUndoSteps()
                undo_count = current_undo_steps - self._undo_position
                
                # 撤销Ghost Text插入操作
                for _ in range(undo_count):
                    if self.document.isUndoAvailable():
                        self.document.undo()
            
            # 🔧 修复：使用统一的状态重置
            self._reset_all_states()
            
            logger.debug("✅ Ghost Text清理完成")
            
        except Exception as e:
            logger.error(f"Ghost Text清理失败: {e}")
            # 强制重置状态，即使undo失败
            self._reset_all_states()
    
    def _reset_all_states(self):
        """🔧 新增：统一的状态重置方法 - 确保所有状态变量一致"""
        self._ghost_text = ""
        self._ghost_start_pos = -1
        self._ghost_end_pos = -1
        self._is_active = False
        self._undo_position = -1
        self._base_char_format = None
        logger.debug("🔄 所有Ghost Text状态已重置")
    
    def accept_ghost_text(self) -> bool:
        """接受Ghost Text - 转换为正常文本"""
        if not self._is_active:
            return False
        
        try:
            ghost_text = self._ghost_text
            
            # 找到Ghost Text并移除特殊格式
            cursor = QTextCursor(self.document)
            cursor.setPosition(self._ghost_start_pos)
            cursor.setPosition(self._ghost_end_pos, QTextCursor.MoveMode.KeepAnchor)
            
            # 创建正常格式
            if self._base_char_format is not None:
                normal_format = QTextCharFormat(self._base_char_format)
            elif hasattr(self.text_editor, 'currentCharFormat'):
                normal_format = self.text_editor.currentCharFormat()
            else:
                normal_format = QTextCharFormat()
            
            # 应用正常格式，移除Ghost Text标记
            cursor.setCharFormat(normal_format)
            
            # 将光标移到文本末尾
            cursor.setPosition(self._ghost_end_pos)
            self.text_editor.setTextCursor(cursor)
            
            # 🔧 修复：使用统一的状态清理 - 确保完全重置
            self._reset_all_states()
            
            # 发射信号
            self.ghost_text_accepted.emit(ghost_text)
            self.completionAccepted.emit(ghost_text)
            
            logger.info(f"✅ Ghost Text已接受并完全清理: '{ghost_text[:30]}...'")
            return True
            
        except Exception as e:
            logger.error(f"Ghost Text接受失败: {e}")
            # 确保异常情况下也清理状态
            self._reset_all_states()
            return False
    
    def reject_ghost_text(self) -> bool:
        """拒绝Ghost Text - 完全移除"""
        if not self._is_active:
            return False
        
        # 🔧 修复：确保完全清理
        try:
            self.clear_ghost_text()
            
            # 发射信号
            self.ghost_text_rejected.emit()
            self.completionRejected.emit()
            
            logger.debug("✅ Ghost Text已拒绝并完全清理")
            return True
        except Exception as e:
            logger.error(f"Ghost Text拒绝时出错: {e}")
            # 强制重置状态
            self._reset_all_states()
            return False
    
    def has_active_ghost_text(self) -> bool:
        """检查是否有活跃的Ghost Text"""
        return self._is_active and bool(self._ghost_text)
    
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """处理按键事件"""
        if not self.has_active_ghost_text():
            return False
        
        # Tab键：接受Ghost Text
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            return self.accept_ghost_text()
        
        # ESC键：拒绝Ghost Text
        elif event.key() == Qt.Key.Key_Escape:
            return self.reject_ghost_text()
        
        # 其他可打印字符：拒绝Ghost Text，让用户继续输入
        elif event.text() and event.text().isprintable():
            self.reject_ghost_text()
            return False  # 让事件继续传递
        
        return False
    
    # ============ 兼容性API ============
    
    def show_completion(self, suggestion: str) -> bool:
        """显示补全建议 - 兼容API"""
        if not suggestion or not suggestion.strip():
            return False
        
        cursor = self.text_editor.textCursor()
        cursor_pos = cursor.position()
        
        # 计算增量补全
        current_text = self.text_editor.toPlainText()
        completion = self._calculate_incremental_completion(current_text, cursor_pos, suggestion.strip())
        
        if not completion:
            return False
        
        return self.show_ghost_text(completion, cursor_pos)
    
    def hide_completion(self):
        """隐藏补全 - 兼容API"""
        self.clear_ghost_text()
    
    def is_showing(self) -> bool:
        """是否正在显示补全 - 兼容API"""
        return self.has_active_ghost_text()
    
    def _calculate_incremental_completion(self, current_text: str, cursor_pos: int, suggestion: str) -> str:
        """计算增量补全"""
        if cursor_pos > len(current_text):
            return ""
        
        # 获取光标前的文本
        text_before_cursor = current_text[:cursor_pos]
        
        # 寻找公共前缀
        common_prefix_len = 0
        for i, char in enumerate(text_before_cursor):
            if i < len(suggestion) and char == suggestion[i]:
                common_prefix_len = i + 1
            else:
                break
        
        # 返回需要补全的部分
        if common_prefix_len == cursor_pos:
            return suggestion[cursor_pos:]
        elif common_prefix_len > 0:
            return suggestion[common_prefix_len:]
        else:
            return suggestion


def integrate_optimal_ghost_text(text_editor) -> OptimalGhostText:
    """将OptimalGhostText集成到文本编辑器"""
    ghost_text_manager = OptimalGhostText(text_editor)
    
    # 保存原始的keyPressEvent方法
    original_key_press_event = text_editor.keyPressEvent
    
    def enhanced_key_press_event(event: QKeyEvent):
        """增强的keyPressEvent，集成Ghost Text事件处理"""
        # 先让Ghost Text处理事件
        if ghost_text_manager.handle_key_press(event):
            return  # 事件已被处理
        
        # 否则调用原始的事件处理
        original_key_press_event(event)
    
    # 替换keyPressEvent方法
    text_editor.keyPressEvent = enhanced_key_press_event
    
    logger.info("✅ OptimalGhostText系统已集成到文本编辑器")
    return ghost_text_manager
