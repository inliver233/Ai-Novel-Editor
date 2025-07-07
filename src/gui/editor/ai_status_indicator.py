"""
AI补全状态指示器
提供专业的AI补全状态显示，包括等待、思考、完成等状态
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QBrush, QPen

logger = logging.getLogger(__name__)


class AIStatusIndicator(QWidget):
    """AI补全状态指示器 - 现代化设计"""
    
    # 状态枚举
    STATUS_IDLE = "idle"           # 空闲
    STATUS_WAITING = "waiting"     # 等待触发
    STATUS_THINKING = "thinking"   # AI思考中
    STATUS_COMPLETED = "completed" # 补全完成
    STATUS_ERROR = "error"         # 错误状态
    STATUS_DISABLED = "disabled"   # 功能禁用
    
    # 信号
    statusChanged = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_status = self.STATUS_IDLE
        self._is_visible = False
        
        # 设置基本属性
        self.setFixedSize(120, 24)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 初始化UI
        self._init_ui()
        self._init_animations()
        
        # 默认隐藏
        self.hide()
        
    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        
        # 状态指示点
        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        self._status_dot.setStyleSheet("""
            QLabel {
                background-color: #666666;
                border-radius: 4px;
            }
        """)
        
        # 状态文本
        self._status_label = QLabel("AI补全")
        self._status_label.setFont(QFont("Segoe UI", 9))
        self._status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                background: transparent;
            }
        """)
        
        layout.addWidget(self._status_dot)
        layout.addWidget(self._status_label)
        layout.addStretch()
        
        # 设置整体样式
        self.setStyleSheet("""
            AIStatusIndicator {
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 12px;
            }
        """)
        
    def _init_animations(self):
        """初始化动画效果"""
        # 透明度动画
        self._opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self._opacity_effect)
        
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(300)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 思考动画定时器
        self._thinking_timer = QTimer()
        self._thinking_timer.timeout.connect(self._animate_thinking)
        self._thinking_dots = 0
        
    def set_status(self, status: str, message: Optional[str] = None):
        """设置状态 - 已禁用以防止黄色横条bug"""
        # 强制禁用所有状态更新和显示，防止黄色横条bug
        if status == self._current_status:
            return
            
        old_status = self._current_status
        self._current_status = status
        
        # 更新UI（但不显示）
        self._update_status_display(message)
        
        # 强制隐藏，禁用显示逻辑
        self._hide_with_animation()
        self.hide()
        self.setVisible(False)
            
        # 发出信号
        self.statusChanged.emit(status)
        
        logger.debug(f"AI status changed: {old_status} -> {status} (显示已禁用)")

    def set_visible(self, visible: bool):
        """设置可见性 - 强制禁用以防止黄色横条bug"""
        # 强制禁用可见性设置，防止黄色横条bug
        self._is_visible = False  # 始终设为False
        self.hide()
        self.setVisible(False)
        logger.debug("AI状态指示器可见性被强制禁用")

    def _update_status_display(self, message: Optional[str] = None):
        """更新状态显示"""
        status_config = {
            self.STATUS_IDLE: {
                "color": "#666666",
                "text": "AI补全",
                "dot_color": "#666666"
            },
            self.STATUS_WAITING: {
                "color": "#FFA500",
                "text": "等待中...",
                "dot_color": "#FFA500"
            },
            self.STATUS_THINKING: {
                "color": "#007ACC",
                "text": "思考中",
                "dot_color": "#007ACC"
            },
            self.STATUS_COMPLETED: {
                "color": "#28A745",
                "text": "已完成",
                "dot_color": "#28A745"
            },
            self.STATUS_ERROR: {
                "color": "#DC3545",
                "text": "错误",
                "dot_color": "#DC3545"
            },
            self.STATUS_DISABLED: {
                "color": "#999999",
                "text": "已禁用",
                "dot_color": "#999999"
            }
        }
        
        config = status_config.get(self._current_status, status_config[self.STATUS_IDLE])
        
        # 更新文本
        display_text = message if message else config["text"]
        self._status_label.setText(display_text)
        self._status_label.setStyleSheet(f"""
            QLabel {{
                color: {config["color"]};
                background: transparent;
            }}
        """)
        
        # 更新指示点
        self._status_dot.setStyleSheet(f"""
            QLabel {{
                background-color: {config["dot_color"]};
                border-radius: 4px;
            }}
        """)
        
        # 特殊动画处理
        if self._current_status == self.STATUS_THINKING:
            self._start_thinking_animation()
        else:
            self._stop_thinking_animation()
            
    def _start_thinking_animation(self):
        """开始思考动画"""
        self._thinking_timer.start(500)  # 每500ms更新一次
        self._thinking_dots = 0
        
    def _stop_thinking_animation(self):
        """停止思考动画"""
        self._thinking_timer.stop()
        
    def _animate_thinking(self):
        """思考动画效果"""
        self._thinking_dots = (self._thinking_dots + 1) % 4
        dots = "." * self._thinking_dots
        self._status_label.setText(f"思考中{dots}")
        
    def _show_with_animation(self):
        """带动画显示 - 已禁用以防止黄色横条bug"""
        # 强制禁用显示动画，防止黄色横条bug
        self._is_visible = False
        self.hide()
        self.setVisible(False)
        logger.debug("AI状态指示器显示动画被强制禁用")
        
    def _hide_with_animation(self):
        """带动画隐藏"""
        if not self._is_visible:
            return
            
        self._is_visible = False
        
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.finished.connect(self.hide)
        self._fade_animation.start()
        
    def set_position(self, x: int, y: int):
        """设置位置"""
        self.move(x, y)
        
    def get_status(self) -> str:
        """获取当前状态"""
        return self._current_status
        
    def is_active(self) -> bool:
        """是否处于活跃状态"""
        return self._current_status not in [self.STATUS_IDLE, self.STATUS_DISABLED]


class FloatingAIStatusIndicator(AIStatusIndicator):
    """浮动AI状态指示器 - 已完全禁用以防止黄色横条bug"""
    
    def __init__(self, parent_editor):
        super().__init__(parent_editor)
        self._parent_editor = parent_editor
        
        # 立即彻底隐藏，防止黄色横条bug
        self.hide()
        self.setVisible(False)
        self._is_visible = False
        
        # 禁用父编辑器大小变化监听
        # if parent_editor:
        #     parent_editor.resizeEvent = self._on_parent_resize
        
        logger.info("FloatingAIStatusIndicator已彻底禁用，防止黄色横条bug")
            
    def _on_parent_resize(self, event):
        """父编辑器大小变化时更新位置 - 已禁用"""
        # 禁用位置更新，防止意外显示
        pass
        
    def _update_position(self):
        """更新位置到右上角 - 已禁用"""
        # 禁用位置更新，防止意外显示
        self.hide()
        self.setVisible(False)
        
    def showEvent(self, event):
        """显示时更新位置 - 强制隐藏"""
        # 强制隐藏，防止任何显示
        self.hide()
        self.setVisible(False)
        event.ignore()
