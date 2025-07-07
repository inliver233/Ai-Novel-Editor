"""
内联AI补全组件
实现类似GitHub Copilot的灰色提示效果
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QTextCursor, QKeyEvent

logger = logging.getLogger(__name__)


class InlineCompletionWidget(QLabel):
    """内联补全提示组件"""
    
    # 信号定义
    suggestionAccepted = pyqtSignal(str)  # 建议被接受
    suggestionRejected = pyqtSignal()     # 建议被拒绝
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._suggestion_text = ""
        self._is_visible = False
        
        self._init_ui()
        self._init_timer()
        
    def _init_ui(self):
        """初始化UI"""
        # 设置样式
        self.setStyleSheet("""
            QLabel {
                color: #666666;
                background-color: transparent;
                border: none;
                font-style: italic;
            }
        """)
        
        # 设置字体
        font = QFont()
        font.setItalic(True)
        self.setFont(font)
        
        # 初始隐藏
        self.hide()
        
        # 设置为透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
    def _init_timer(self):
        """初始化定时器"""
        # 自动隐藏定时器
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_suggestion)
        
    def show_suggestion(self, suggestion: str, cursor_rect):
        """显示建议"""
        if not suggestion.strip():
            return

        self._suggestion_text = suggestion.strip()
        self._is_visible = True

        # 设置文本 - 只显示第一行或前50个字符
        display_text = self._suggestion_text.split('\n')[0]
        if len(display_text) > 50:
            display_text = display_text[:50] + "..."
        self.setText(display_text)

        # 调整大小
        self.adjustSize()

        # 定位到光标位置 - 使用相对于父组件的坐标
        if self.parent():
            # 确保位置在编辑器内
            parent_rect = self.parent().rect()
            x = min(cursor_rect.x(), parent_rect.width() - self.width())
            y = cursor_rect.y() + cursor_rect.height()  # 显示在光标下方

            # 确保不超出边界
            if y + self.height() > parent_rect.height():
                y = cursor_rect.y() - self.height()  # 显示在光标上方

            self.move(max(0, x), max(0, y))
        else:
            self.move(cursor_rect.x(), cursor_rect.y() + cursor_rect.height())

        # 显示
        self.show()
        self.raise_()

        # 设置自动隐藏（10秒后）
        self._hide_timer.start(10000)

        logger.debug(f"Inline suggestion shown: {suggestion[:50]}...")
        
    def hide_suggestion(self):
        """隐藏建议"""
        if self._is_visible:
            self._is_visible = False
            self._suggestion_text = ""
            self.hide()
            self._hide_timer.stop()
            logger.debug("Inline suggestion hidden")
            
    def accept_suggestion(self):
        """接受建议"""
        if self._is_visible and self._suggestion_text:
            suggestion = self._suggestion_text
            self.hide_suggestion()
            self.suggestionAccepted.emit(suggestion)
            logger.info(f"Inline suggestion accepted: {suggestion[:50]}...")
            
    def reject_suggestion(self):
        """拒绝建议"""
        if self._is_visible:
            self.hide_suggestion()
            self.suggestionRejected.emit()
            logger.debug("Inline suggestion rejected")
            
    def is_showing(self) -> bool:
        """是否正在显示建议"""
        return self._is_visible
        
    def get_suggestion(self) -> str:
        """获取当前建议文本"""
        return self._suggestion_text


class InlineCompletionManager:
    """内联补全管理器"""
    
    def __init__(self, text_editor):
        self._text_editor = text_editor
        self._completion_widget = None
        self._current_suggestion = ""
        
        self._init_completion_widget()
        self._connect_signals()
        
    def _init_completion_widget(self):
        """初始化补全组件"""
        self._completion_widget = InlineCompletionWidget(self._text_editor)
        self._completion_widget.suggestionAccepted.connect(self._on_suggestion_accepted)
        self._completion_widget.suggestionRejected.connect(self._on_suggestion_rejected)
        
    def _connect_signals(self):
        """连接信号"""
        # 监听文本变化，自动隐藏建议
        self._text_editor.textChanged.connect(self._on_text_changed)
        
    def show_completion(self, suggestion: str):
        """显示补全建议"""
        if not suggestion.strip():
            return
            
        # 获取光标位置
        cursor = self._text_editor.textCursor()
        cursor_rect = self._text_editor.cursorRect(cursor)
        
        # 转换为相对于编辑器的坐标
        widget_pos = cursor_rect.topLeft()
        
        # 显示建议
        self._current_suggestion = suggestion.strip()
        self._completion_widget.show_suggestion(self._current_suggestion, cursor_rect)
        
        logger.info(f"Inline completion shown: {suggestion[:50]}...")
        
    def hide_completion(self):
        """隐藏补全建议"""
        if self._completion_widget:
            self._completion_widget.hide_suggestion()
            
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """处理按键事件
        
        Returns:
            bool: 如果事件被处理则返回True，否则返回False
        """
        if not self._completion_widget.is_showing():
            return False
            
        key = event.key()
        
        # Tab键：接受建议
        if key == Qt.Key.Key_Tab:
            self._completion_widget.accept_suggestion()
            return True
            
        # Esc键：拒绝建议
        elif key == Qt.Key.Key_Escape:
            self._completion_widget.reject_suggestion()
            return True
            
        # 其他键：隐藏建议
        elif key in [Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            self._completion_widget.hide_suggestion()
            return False
            
        return False
        
    def _on_suggestion_accepted(self, suggestion: str):
        """建议被接受"""
        # 插入建议文本
        cursor = self._text_editor.textCursor()
        cursor.insertText(suggestion)
        
        logger.info(f"Inline suggestion accepted and inserted: {suggestion[:50]}...")
        
    def _on_suggestion_rejected(self):
        """建议被拒绝"""
        logger.debug("Inline suggestion rejected by user")
        
    def _on_text_changed(self):
        """文本变化时隐藏建议"""
        if self._completion_widget.is_showing():
            self._completion_widget.hide_suggestion()
            
    def is_showing(self) -> bool:
        """是否正在显示建议"""
        return self._completion_widget.is_showing() if self._completion_widget else False
