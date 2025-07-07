"""
AI补全建议界面
实现分层补全策略的UI展示，包括瞬时补全、智能补全和被动建议
"""

import logging
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QTextEdit, QProgressBar, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QTextCursor

logger = logging.getLogger(__name__)


class CompletionSuggestionCard(QFrame):
    """AI补全建议卡片"""
    
    suggestionSelected = pyqtSignal(str, dict)  # 建议选择信号
    
    def __init__(self, suggestion_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self._suggestion_data = suggestion_data
        self._is_selected = False
        
        self._init_ui()
        self._setup_style()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
        # 建议类型和置信度
        header_layout = QHBoxLayout()
        
        # 类型标签
        type_label = QLabel(self._suggestion_data.get('type', '建议'))
        type_label.setFont(QFont("", 10, QFont.Weight.Bold))
        header_layout.addWidget(type_label)
        
        header_layout.addStretch()
        
        # 置信度
        confidence = self._suggestion_data.get('confidence', 0.8)
        confidence_label = QLabel(f"{confidence:.0%}")
        confidence_label.setFont(QFont("", 9))
        header_layout.addWidget(confidence_label)
        
        layout.addLayout(header_layout)
        
        # 建议内容
        content = self._suggestion_data.get('content', '')
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setFont(QFont("", 12))
        layout.addWidget(content_label)
        
        # 说明文字（如果有）
        description = self._suggestion_data.get('description', '')
        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setFont(QFont("", 10))
            desc_label.setStyleSheet("color: #656d76;")
            layout.addWidget(desc_label)
    
    def _setup_style(self):
        """设置样式"""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            CompletionSuggestionCard {
                background-color: rgba(124, 58, 237, 0.05);
                border: 1px solid rgba(124, 58, 237, 0.2);
                border-radius: 8px;
                margin: 2px;
            }
            CompletionSuggestionCard:hover {
                background-color: rgba(124, 58, 237, 0.1);
                border-color: rgba(124, 58, 237, 0.4);
            }
        """)
        
        # 设置鼠标样式
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.suggestionSelected.emit(
                self._suggestion_data.get('content', ''),
                self._suggestion_data
            )
        super().mousePressEvent(event)
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        if selected:
            self.setStyleSheet("""
                CompletionSuggestionCard {
                    background-color: rgba(124, 58, 237, 0.2);
                    border: 2px solid rgba(124, 58, 237, 0.6);
                    border-radius: 8px;
                    margin: 2px;
                }
            """)
        else:
            self._setup_style()


class CompletionWidget(QWidget):
    """AI补全建议主界面"""
    
    # 信号定义
    suggestionAccepted = pyqtSignal(str, dict)  # 建议接受信号
    suggestionRejected = pyqtSignal(dict)  # 建议拒绝信号
    moreOptionsRequested = pyqtSignal()  # 请求更多选项信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._suggestions = []
        self._selected_index = -1
        self._is_loading = False
        
        self._init_ui()
        self._setup_animations()
        
        # 隐藏初始状态
        self.hide()
        
        logger.debug("Completion widget initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标题栏
        title_frame = self._create_title_frame()
        layout.addWidget(title_frame)
        
        # 建议列表区域
        self._suggestions_area = self._create_suggestions_area()
        layout.addWidget(self._suggestions_area)
        
        # 加载指示器
        self._loading_frame = self._create_loading_frame()
        layout.addWidget(self._loading_frame)
        self._loading_frame.hide()
        
        # 操作按钮
        buttons_frame = self._create_buttons_frame()
        layout.addWidget(buttons_frame)
        
        # 设置整体样式
        self.setStyleSheet("""
            CompletionWidget {
                background-color: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
        """)
        
        # 修复黄色横条bug：不设置固定宽度，防止组件显示为横条
        # self.setFixedWidth(350)  # 注释掉固定宽度设置
        self.setMaximumWidth(350)   # 改用最大宽度限制
        self.setMinimumWidth(300)   # 设置最小宽度确保不会太小
        self.setMaximumHeight(400)
        self.setMinimumHeight(100)  # 设置最小高度防止收缩成横条
        
        # 默认隐藏组件，防止意外显示
        self.hide()
    
    def _create_title_frame(self) -> QFrame:
        """创建标题栏"""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # AI图标和标题
        title_label = QLabel("🤖 AI建议")
        title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-size: 16px;
                font-weight: bold;
                color: #656d76;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
                border-radius: 10px;
            }
        """)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)
        
        return frame
    
    def _create_suggestions_area(self) -> QScrollArea:
        """创建建议列表区域"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 建议容器
        self._suggestions_container = QWidget()
        self._suggestions_layout = QVBoxLayout(self._suggestions_container)
        self._suggestions_layout.setContentsMargins(8, 4, 8, 4)
        self._suggestions_layout.setSpacing(4)
        
        scroll_area.setWidget(self._suggestions_container)
        scroll_area.setMinimumHeight(100)
        scroll_area.setMaximumHeight(250)
        
        return scroll_area
    
    def _create_loading_frame(self) -> QFrame:
        """创建加载指示器"""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # 无限进度条
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                text-align: center;
                background-color: #f8f9fa;
            }
            QProgressBar::chunk {
                background-color: #7c3aed;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._progress_bar)
        
        # 加载文字
        loading_label = QLabel("AI正在思考中...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_label.setFont(QFont("", 10))
        loading_label.setStyleSheet("color: #656d76;")
        layout.addWidget(loading_label)
        
        return frame
    
    def _create_buttons_frame(self) -> QFrame:
        """创建操作按钮"""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # 更多选项按钮
        more_btn = QPushButton("更多选项")
        more_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
                border-color: #d0d7de;
            }
        """)
        more_btn.clicked.connect(self.moreOptionsRequested.emit)
        layout.addWidget(more_btn)
        
        layout.addStretch()
        
        # 接受按钮
        self._accept_btn = QPushButton("接受")
        self._accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #0969da;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #0550ae;
            }
            QPushButton:disabled {
                background-color: #e1e4e8;
                color: #656d76;
            }
        """)
        self._accept_btn.clicked.connect(self._accept_selected)
        self._accept_btn.setEnabled(False)
        layout.addWidget(self._accept_btn)
        
        return frame
    
    def _setup_animations(self):
        """设置动画"""
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(200)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def show_suggestions(self, suggestions: List[Dict[str, Any]]):
        """显示建议列表"""
        # 修复黄色横条bug：如果没有建议内容，不显示组件
        if not suggestions:
            logger.debug("No suggestions to show, hiding completion widget")
            self.hide()
            return
            
        self._suggestions = suggestions
        self._selected_index = -1
        
        # 清空现有建议
        self._clear_suggestions()
        
        # 添加新建议
        for i, suggestion in enumerate(suggestions):
            card = CompletionSuggestionCard(suggestion)
            card.suggestionSelected.connect(self._on_suggestion_selected)
            self._suggestions_layout.addWidget(card)
        
        # 添加弹性空间
        self._suggestions_layout.addStretch()
        
        # 更新按钮状态
        self._accept_btn.setEnabled(False)
        
        # 确保组件有足够的内容才显示，防止空横条显示
        if self._suggestions_layout.count() > 1:  # 至少有1个建议+弹性空间
            self._show_with_animation()
            logger.debug(f"Showing {len(suggestions)} suggestions")
        else:
            logger.debug("Insufficient content, hiding completion widget")
            self.hide()
    
    def show_loading(self, message: str = "正在加载建议..."):
        """显示加载状态"""
        # 修复黄色横条bug：加载状态时不显示组件，防止空横条
        logger.debug(f"Loading state requested: {message}, but display disabled to prevent horizontal bar bug")
        # 不再显示加载状态组件，改为在日志中记录
        # self._is_loading = True
        # self._loading_frame.show()
        # self._suggestions_area.hide()
        # self._show_with_animation()
        return

    def show_error(self, error_message: str):
        """显示错误状态"""
        # 修复黄色横条bug：错误状态时也不显示组件，防止空横条
        logger.debug(f"Error state requested: {error_message}, but display disabled to prevent horizontal bar bug")
        # 不再显示错误状态组件，改为在日志中记录
        self.hide()
        return

        # 创建错误标签（如果不存在）
        if not hasattr(self, '_error_label'):
            self._error_label = QLabel()
            self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._error_label.setStyleSheet("""
                QLabel {
                    background-color: #3d1a1a;
                    border: 1px solid #d73a49;
                    border-radius: 6px;
                    padding: 12px;
                    color: #f85149;
                    font-size: 12px;
                }
            """)
            self._main_layout.addWidget(self._error_label)

        self._error_label.setText(f"❌ {error_message}")
        self._error_label.show()

        # 显示界面
        self._show_with_animation()

        # 3秒后自动隐藏
        QTimer.singleShot(3000, self.hide)

        logger.debug(f"Showing error: {error_message}")

    def hide_loading(self):
        """隐藏加载状态"""
        self._is_loading = False
        self._loading_frame.hide()

        logger.debug("Loading state hidden")
    
    def hide_loading(self):
        """隐藏加载状态"""
        self._is_loading = False
        self._loading_frame.hide()
        self._suggestions_area.show()
    
    def _show_with_animation(self):
        """带动画显示"""
        if not self.isVisible():
            self.show()
            self._fade_animation.setStartValue(0.0)
            self._fade_animation.setEndValue(1.0)
            self._fade_animation.start()
    
    def _clear_suggestions(self):
        """清空建议列表"""
        while self._suggestions_layout.count():
            child = self._suggestions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    @pyqtSlot(str, dict)
    def _on_suggestion_selected(self, content: str, suggestion_data: dict):
        """建议选择处理"""
        # 更新选中状态
        for i in range(self._suggestions_layout.count()):
            item = self._suggestions_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, CompletionSuggestionCard):
                    widget.set_selected(widget._suggestion_data == suggestion_data)
        
        # 更新选中索引
        for i, suggestion in enumerate(self._suggestions):
            if suggestion == suggestion_data:
                self._selected_index = i
                break
        
        # 启用接受按钮
        self._accept_btn.setEnabled(True)
        
        logger.debug(f"Suggestion selected: {content[:50]}...")
    
    def _accept_selected(self):
        """接受选中的建议"""
        if self._selected_index >= 0 and self._selected_index < len(self._suggestions):
            suggestion = self._suggestions[self._selected_index]
            content = suggestion.get('content', '')
            
            self.suggestionAccepted.emit(content, suggestion)
            self.hide()
            
            logger.info(f"Suggestion accepted: {content[:50]}...")
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self._accept_btn.isEnabled():
                self._accept_selected()
        elif event.key() == Qt.Key.Key_Up:
            self._select_previous()
        elif event.key() == Qt.Key.Key_Down:
            self._select_next()
        else:
            super().keyPressEvent(event)
    
    def _select_previous(self):
        """选择上一个建议"""
        if self._suggestions and self._selected_index > 0:
            self._selected_index -= 1
            self._update_selection()
    
    def _select_next(self):
        """选择下一个建议"""
        if self._suggestions and self._selected_index < len(self._suggestions) - 1:
            self._selected_index += 1
            self._update_selection()
    
    def _update_selection(self):
        """更新选择状态"""
        for i in range(self._suggestions_layout.count()):
            item = self._suggestions_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, CompletionSuggestionCard):
                    widget.set_selected(i == self._selected_index)
        
        self._accept_btn.setEnabled(self._selected_index >= 0)
