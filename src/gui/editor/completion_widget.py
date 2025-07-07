"""
智能补全界面组件
提供专业的补全建议显示和交互功能
"""

import logging
from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, 
    QLabel, QFrame, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QKeyEvent

from .completion_engine import CompletionSuggestion

logger = logging.getLogger(__name__)


class CompletionItemWidget(QWidget):
    """补全项目组件"""
    
    def __init__(self, suggestion: CompletionSuggestion, parent=None):
        super().__init__(parent)
        self.suggestion = suggestion
        self._setup_ui()
    
    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        
        # 主文本
        main_label = QLabel(self.suggestion.display_text)
        main_font = QFont()
        main_font.setBold(True)
        main_label.setFont(main_font)
        layout.addWidget(main_label)
        
        # 描述文本
        if self.suggestion.description:
            desc_label = QLabel(self.suggestion.description)
            desc_label.setStyleSheet("color: #666; font-size: 11px;")
            layout.addWidget(desc_label)
        
        # 类型标签
        type_label = QLabel(f"[{self.suggestion.completion_type}]")
        type_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(type_label)


class CompletionListWidget(QListWidget):
    """补全列表组件"""
    
    suggestionSelected = pyqtSignal(CompletionSuggestion)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._suggestions = []
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self):
        """设置界面"""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setMaximumHeight(200)
        self.setMinimumWidth(300)
        
        # 设置样式
        self.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                outline: none;
                selection-background-color: #0078d4;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333;
                border-radius: 2px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
                border: 1px solid #106ebe;
            }
            QListWidget::item:hover {
                background-color: #404040;
            }
            QListWidget::item:focus {
                background-color: #0078d4;
                color: white;
                border: 1px solid #106ebe;
            }
        """)
    
    def _setup_connections(self):
        """设置信号连接"""
        self.itemClicked.connect(self._on_item_clicked)
        self.itemActivated.connect(self._on_item_activated)
    
    def set_suggestions(self, suggestions: List[CompletionSuggestion]):
        """设置补全建议"""
        self._suggestions = suggestions
        self.clear()
        
        for suggestion in suggestions:
            item = QListWidgetItem()
            item_widget = CompletionItemWidget(suggestion)
            
            item.setSizeHint(item_widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, item_widget)
        
        # 选中第一项并确保可见
        if suggestions:
            self.setCurrentRow(0)
            self.setFocus()  # 确保列表获得焦点
    
    def get_selected_suggestion(self) -> Optional[CompletionSuggestion]:
        """获取选中的建议"""
        current_row = self.currentRow()
        if 0 <= current_row < len(self._suggestions):
            return self._suggestions[current_row]
        return None
    
    def _on_item_clicked(self, item):
        """项目点击处理"""
        suggestion = self.get_selected_suggestion()
        if suggestion:
            self.suggestionSelected.emit(suggestion)
    
    def _on_item_activated(self, item):
        """项目激活处理"""
        suggestion = self.get_selected_suggestion()
        if suggestion:
            self.suggestionSelected.emit(suggestion)
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件处理"""
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab]:
            suggestion = self.get_selected_suggestion()
            if suggestion:
                self.suggestionSelected.emit(suggestion)
                return
        elif event.key() == Qt.Key.Key_Escape:
            if self.parent():
                self.parent().hide()
            return
        elif event.key() in [Qt.Key.Key_Up, Qt.Key.Key_Down]:
            # 处理方向键导航
            current_row = self.currentRow()
            if event.key() == Qt.Key.Key_Up:
                new_row = max(0, current_row - 1)
            else:  # Down
                new_row = min(self.count() - 1, current_row + 1)

            self.setCurrentRow(new_row)
            return

        super().keyPressEvent(event)


class CompletionWidget(QWidget):
    """智能补全主组件"""
    
    suggestionAccepted = pyqtSignal(CompletionSuggestion)
    cancelled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_connections()
        
        # 自动隐藏定时器
        self._hide_timer = QTimer()
        self._hide_timer.timeout.connect(self.hide)
        self._hide_timer.setSingleShot(True)
        
        self.hide()  # 初始隐藏
    
    def _setup_ui(self):
        """设置界面 - 修复焦点管理问题"""
        # 使用Tool窗口而不是Popup，避免焦点跳出应用程序
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        # 确保窗口不会抢夺焦点，但仍然可见
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 补全列表
        self.completion_list = CompletionListWidget()
        layout.addWidget(self.completion_list)
        
        # 加载指示器
        self.loading_label = QLabel("正在加载建议...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 10px;
                color: #ccc;
            }
        """)
        layout.addWidget(self.loading_label)
        self.loading_label.hide()
        
        # 无建议标签
        self.no_suggestions_label = QLabel("无可用建议")
        self.no_suggestions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_suggestions_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 10px;
                color: #888;
            }
        """)
        layout.addWidget(self.no_suggestions_label)
        self.no_suggestions_label.hide()
    
    def _setup_connections(self):
        """设置信号连接"""
        self.completion_list.suggestionSelected.connect(self._on_suggestion_selected)
    
    def show_suggestions(self, suggestions: List[CompletionSuggestion]):
        """显示补全建议"""
        self.loading_label.hide()
        self.no_suggestions_label.hide()

        if suggestions:
            self.completion_list.set_suggestions(suggestions)
            self.completion_list.show()
            self.show()
            # 设置焦点到列表，使键盘导航生效
            self.completion_list.setFocus()
            self._start_hide_timer()
        else:
            self.show_no_suggestions()
    
    def show_loading(self, message: str = "正在加载建议..."):
        """显示加载状态"""
        self.completion_list.hide()
        self.no_suggestions_label.hide()
        
        self.loading_label.setText(message)
        self.loading_label.show()
        self.show()
    
    def show_no_suggestions(self):
        """显示无建议状态"""
        self.completion_list.hide()
        self.loading_label.hide()
        
        self.no_suggestions_label.show()
        self.show()
        self._start_hide_timer(2000)  # 2秒后自动隐藏
    
    def _start_hide_timer(self, timeout: int = 5000):
        """启动自动隐藏定时器"""
        self._hide_timer.start(timeout)
    
    def _on_suggestion_selected(self, suggestion: CompletionSuggestion):
        """建议选择处理"""
        self.suggestionAccepted.emit(suggestion)
        self.hide()
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件处理"""
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.hide()
            return
        elif event.key() in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab]:
            # 将导航和选择事件传递给列表
            if self.completion_list.isVisible():
                self.completion_list.keyPressEvent(event)
                return

        super().keyPressEvent(event)
    
    def hide(self):
        """隐藏组件"""
        self._hide_timer.stop()
        super().hide()
    
    def position_near_cursor(self, cursor_rect):
        """在光标附近定位 - 修复焦点管理问题"""
        # 确保有正确的父窗口
        if not self.parent():
            logger.warning("补全窗口没有父窗口，可能导致焦点问题")
            return

        # 获取父窗口的全局位置
        parent_global_pos = self.parent().mapToGlobal(self.parent().rect().topLeft())

        # 计算相对于父窗口的位置
        x = cursor_rect.x()
        y = cursor_rect.bottom() + 5

        # 转换为全局坐标
        global_x = parent_global_pos.x() + x
        global_y = parent_global_pos.y() + y

        # 确保不超出屏幕边界
        screen = self.parent().screen().availableGeometry()
        widget_size = self.sizeHint()

        if global_x + widget_size.width() > screen.right():
            global_x = screen.right() - widget_size.width()
        if global_y + widget_size.height() > screen.bottom():
            global_y = parent_global_pos.y() + cursor_rect.top() - widget_size.height() - 5

        # 确保不会跑到屏幕外
        global_x = max(screen.left(), global_x)
        global_y = max(screen.top(), global_y)

        self.move(global_x, global_y)
        logger.debug(f"补全窗口定位到: ({global_x}, {global_y})")
