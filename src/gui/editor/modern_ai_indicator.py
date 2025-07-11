"""
现代AI状态指示器
优雅的动态状态显示，支持动画效果和自动管理
"""

import logging
from enum import Enum
from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect, QMainWindow, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QFont

logger = logging.getLogger(__name__)


class AIStatus(Enum):
    """AI状态枚举"""
    IDLE = "idle"                    # 空闲
    REQUESTING = "requesting"        # 请求中
    THINKING = "thinking"           # AI思考中
    GENERATING = "generating"       # 生成中
    COMPLETED = "completed"         # 完成
    ERROR = "error"                 # 错误
    CANCELLED = "cancelled"         # 取消


class ModernAIStatusIndicator(QWidget):
    """现代AI状态指示器 - 优雅的动态显示"""
    
    # 信号
    statusChanged = pyqtSignal(str)
    cancelRequested = pyqtSignal()
    
    def __init__(self, parent_editor):
        super().__init__(parent_editor)
        
        self._parent_editor = parent_editor
        self._current_status = AIStatus.IDLE
        self._status_text = ""
        self._is_visible = False
        
        # 设置基本属性
        self.setFixedSize(180, 36)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 不再设置窗口标志，作为普通子widget
        # self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        
        # 初始化UI和动画
        self._init_ui()
        self._init_animations()
        
        # 监听父编辑器的大小变化以调整位置
        if self._parent_editor:
            self._parent_editor.resizeEvent = self._on_editor_resize_wrapper
        
        # 确保始终在最上层
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        
        # 默认隐藏
        self.hide()
        
        logger.info("现代AI状态指示器已初始化")
    
    def _init_ui(self):
        """初始化UI"""
        # 创建布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # 设置背景颜色和边框
        self.setAutoFillBackground(True)
        
        # 状态指示点
        self._status_dot = QWidget()
        self._status_dot.setFixedSize(12, 12)
        self._status_dot.setStyleSheet("""
            QWidget {
                background-color: #64748b;
                border-radius: 6px;
            }
        """)
        
        # 状态文本
        self._status_label = QLabel("AI就绪")
        self._status_label.setFont(QFont("Microsoft YaHei UI", 9))
        self._status_label.setStyleSheet("""
            QLabel {
                color: #e2e8f0;
                background: transparent;
            }
        """)
        
        layout.addWidget(self._status_dot)
        layout.addWidget(self._status_label)
        layout.addStretch()
        
        # 设置整体样式 - 现代玻璃效果
        self._update_widget_style()
    
    def _init_animations(self):
        """初始化动画系统"""
        # 透明度动画
        self._opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self._opacity_effect)
        
        # 淡入淡出动画
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(300)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 脉冲动画定时器（用于思考状态）
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._animate_pulse)
        self._pulse_phase = 0
        
        # 旋转动画定时器（用于加载状态）
        self._rotate_timer = QTimer()
        self._rotate_timer.timeout.connect(self._animate_rotate)
        self._rotate_angle = 0
        
        # 文本动画定时器（用于省略号动画）
        self._text_timer = QTimer()
        self._text_timer.timeout.connect(self._animate_text)
        self._text_dots = 0
    
    def set_status(self, status: AIStatus, message: Optional[str] = None):
        """设置AI状态"""
        if status == self._current_status and not message:
            return
        
        old_status = self._current_status
        self._current_status = status
        self._status_text = message or self._get_default_message(status)
        
        # 更新显示
        self._update_display()
        
        # 管理动画
        self._manage_animations()
        
        # 发出信号
        self.statusChanged.emit(status.value)
        
        logger.debug(f"AI状态变更: {old_status.value} -> {status.value}")
    
    def _get_default_message(self, status: AIStatus) -> str:
        """获取默认状态消息"""
        messages = {
            AIStatus.IDLE: "AI就绪",
            AIStatus.REQUESTING: "发送请求",
            AIStatus.THINKING: "AI思考中",
            AIStatus.GENERATING: "生成内容",
            AIStatus.COMPLETED: "生成完成",
            AIStatus.ERROR: "生成失败",
            AIStatus.CANCELLED: "已取消"
        }
        return messages.get(status, "未知状态")
    
    def _update_display(self):
        """更新显示内容"""
        # 状态配置
        status_config = {
            AIStatus.IDLE: {
                "dot_color": "#64748b",
                "text_color": "#e2e8f0",
                "bg_color": "rgba(30, 41, 59, 0.95)",
                "border_color": "rgba(148, 163, 184, 0.2)"
            },
            AIStatus.REQUESTING: {
                "dot_color": "#3b82f6",
                "text_color": "#dbeafe",
                "bg_color": "rgba(30, 58, 138, 0.95)",
                "border_color": "rgba(59, 130, 246, 0.3)"
            },
            AIStatus.THINKING: {
                "dot_color": "#8b5cf6",
                "text_color": "#e9d5ff",
                "bg_color": "rgba(76, 29, 149, 0.95)",
                "border_color": "rgba(139, 92, 246, 0.3)"
            },
            AIStatus.GENERATING: {
                "dot_color": "#f59e0b",
                "text_color": "#fef3c7",
                "bg_color": "rgba(146, 64, 14, 0.95)",
                "border_color": "rgba(245, 158, 11, 0.3)"
            },
            AIStatus.COMPLETED: {
                "dot_color": "#10b981",
                "text_color": "#d1fae5",
                "bg_color": "rgba(6, 95, 70, 0.95)",
                "border_color": "rgba(16, 185, 129, 0.3)"
            },
            AIStatus.ERROR: {
                "dot_color": "#ef4444",
                "text_color": "#fecaca",
                "bg_color": "rgba(153, 27, 27, 0.95)",
                "border_color": "rgba(239, 68, 68, 0.3)"
            },
            AIStatus.CANCELLED: {
                "dot_color": "#6b7280",
                "text_color": "#d1d5db",
                "bg_color": "rgba(55, 65, 81, 0.95)",
                "border_color": "rgba(107, 114, 128, 0.3)"
            }
        }
        
        config = status_config[self._current_status]
        
        # 更新状态点样式
        self._status_dot.setStyleSheet(f"""
            QWidget {{
                background-color: {config["dot_color"]};
                border-radius: 6px;
            }}
        """)
        
        # 更新文本样式
        self._status_label.setText(self._status_text)
        self._status_label.setStyleSheet(f"""
            QLabel {{
                color: {config["text_color"]};
                background: transparent;
            }}
        """)
        
        # 更新整体样式
        self._update_widget_style_with_config(config)
    
    def _manage_animations(self):
        """管理动画状态"""
        # 停止所有动画
        self._stop_all_animations()
        
        # 根据状态启动相应动画
        if self._current_status == AIStatus.THINKING:
            self._start_pulse_animation()
            self._start_text_animation()
        elif self._current_status in [AIStatus.REQUESTING, AIStatus.GENERATING]:
            self._start_rotate_animation()
            self._start_text_animation()
        elif self._current_status == AIStatus.COMPLETED:
            # 完成状态自动淡出
            QTimer.singleShot(2000, self.hide_with_animation)
    
    def _start_pulse_animation(self):
        """启动脉冲动画"""
        self._pulse_timer.start(100)  # 每100ms更新一次
    
    def _start_rotate_animation(self):
        """启动旋转动画"""
        self._rotate_timer.start(50)  # 每50ms更新一次
    
    def _start_text_animation(self):
        """启动文本动画"""
        self._text_timer.start(600)  # 每600ms更新一次
    
    def _stop_all_animations(self):
        """停止所有动画"""
        self._pulse_timer.stop()
        self._rotate_timer.stop()
        self._text_timer.stop()
    
    def _animate_pulse(self):
        """脉冲动画效果"""
        self._pulse_phase += 1
        opacity = 0.3 + 0.7 * (0.5 + 0.5 * __import__('math').sin(self._pulse_phase * 0.2))
        
        color = "#8b5cf6"
        self._status_dot.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-radius: 6px;
                border: 2px solid rgba(139, 92, 246, {opacity});
            }}
        """)
    
    def _animate_rotate(self):
        """旋转动画效果（通过颜色变化模拟）"""
        self._rotate_angle = (self._rotate_angle + 10) % 360
        
        # 通过改变颜色饱和度来模拟旋转效果
        if self._current_status == AIStatus.REQUESTING:
            base_color = "#3b82f6"
        else:  # GENERATING
            base_color = "#f59e0b"
        
        intensity = 0.5 + 0.5 * abs(__import__('math').sin(__import__('math').radians(self._rotate_angle)))
        
        self._status_dot.setStyleSheet(f"""
            QWidget {{
                background-color: {base_color};
                border-radius: 6px;
                border: 2px solid rgba(255, 255, 255, {intensity * 0.5});
            }}
        """)
    
    def _animate_text(self):
        """文本动画效果（省略号）"""
        base_text = self._status_text.rstrip('.')
        self._text_dots = (self._text_dots + 1) % 4
        dots = '.' * self._text_dots
        self._status_label.setText(f"{base_text}{dots}")
    
    def show_with_animation(self):
        """带动画显示"""
        if self._is_visible:
            return
        
        self._is_visible = True
        
        # 更新位置（作为子widget，只需设置相对位置）
        self._update_position()
        
        # 先显示widget，但透明度为0
        self.show()
        self._opacity_effect.setOpacity(0.0)
        
        # 淡入动画
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        
        # 安全地断开之前的连接
        try:
            self._fade_animation.finished.disconnect()
        except TypeError:
            # 没有连接存在，这是正常的
            pass
        
        self._fade_animation.start()
        
        self.raise_()
        
        logger.debug("AI状态指示器显示")
    
    def hide_with_animation(self):
        """带动画隐藏"""
        if not self._is_visible:
            return
        
        self._is_visible = False
        
        # 停止所有动画
        self._stop_all_animations()
        
        # 淡出动画
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        
        # 安全地连接hide信号
        try:
            self._fade_animation.finished.disconnect()
        except TypeError:
            # 没有连接存在，这是正常的
            pass
        
        self._fade_animation.finished.connect(self.hide)
        self._fade_animation.start()
        
        logger.debug("AI状态指示器隐藏")
    
    def _update_position(self):
        """更新位置到编辑器右下角"""
        if not self._parent_editor:
            return
        
        # 作为子widget，使用相对位置
        editor_size = self._parent_editor.size()
        
        # 计算指示器位置（右下角，留出边距）
        margin = 20
        x = editor_size.width() - self.width() - margin
        y = editor_size.height() - self.height() - margin
        
        # 设置相对位置
        self.move(x, y)
        logger.debug(f"更新指示器相对位置到: ({x}, {y})")
    
    def paintEvent(self, event):
        """自定义绘制事件"""
        super().paintEvent(event)
        
        # 如果需要自定义绘制效果，可以在这里添加
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 可以添加额外的视觉效果，比如阴影等
        # 目前使用CSS样式就足够了
        
        painter.end()
    
    def mousePressEvent(self, event):
        """鼠标点击事件 - 可以添加交互功能"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 如果是正在进行的操作，可以取消
            if self._current_status in [AIStatus.REQUESTING, AIStatus.THINKING, AIStatus.GENERATING]:
                self.cancelRequested.emit()
                self.set_status(AIStatus.CANCELLED, "用户取消")
        
        super().mousePressEvent(event)
    
    def is_visible_status(self) -> bool:
        """返回是否应该显示状态"""
        return self._is_visible
    
    def get_current_status(self) -> AIStatus:
        """获取当前状态"""
        return self._current_status
    
    def _on_editor_resize_wrapper(self, event):
        """编辑器大小变化时的包装器"""
        # 调用原始的resizeEvent
        super(type(self._parent_editor), self._parent_editor).resizeEvent(event)
        
        # 更新位置
        if self._is_visible:
            self._update_position()
    
    def _update_widget_style(self):
        """更新widget样式"""
        self.setStyleSheet("""
            ModernAIStatusIndicator {
                background-color: rgba(30, 41, 59, 0.95);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 18px;
            }
        """)
    
    def _update_widget_style_with_config(self, config):
        """根据配置更新widget样式"""
        self.setStyleSheet(f"""
            ModernAIStatusIndicator {{
                background-color: {config["bg_color"]};
                border: 1px solid {config["border_color"]};
                border-radius: 18px;
            }}
        """)


class AIStatusManager:
    """AI状态管理器 - 简化的接口"""
    
    def __init__(self, parent_editor):
        self._indicator = ModernAIStatusIndicator(parent_editor)
        self._auto_hide_timer = QTimer()
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._indicator.hide_with_animation)
    
    def show_requesting(self, message: str = "发送AI请求"):
        """显示请求状态"""
        self._indicator.set_status(AIStatus.REQUESTING, message)
        self._indicator.show_with_animation()
        self._cancel_auto_hide()
    
    def show_thinking(self, message: str = "AI思考中"):
        """显示思考状态"""
        self._indicator.set_status(AIStatus.THINKING, message)
        self._indicator.show_with_animation()
        self._cancel_auto_hide()
    
    def show_generating(self, message: str = "生成内容中"):
        """显示生成状态"""
        self._indicator.set_status(AIStatus.GENERATING, message)
        self._indicator.show_with_animation()
        self._cancel_auto_hide()
    
    def show_completed(self, message: str = "生成完成"):
        """显示完成状态"""
        self._indicator.set_status(AIStatus.COMPLETED, message)
        self._indicator.show_with_animation()
        # 2秒后自动隐藏
        self._auto_hide_timer.start(2000)
    
    def show_error(self, message: str = "生成失败"):
        """显示错误状态"""
        self._indicator.set_status(AIStatus.ERROR, message)
        self._indicator.show_with_animation()
        # 3秒后自动隐藏
        self._auto_hide_timer.start(3000)
    
    def hide(self):
        """隐藏指示器"""
        self._indicator.hide_with_animation()
        self._cancel_auto_hide()
    
    def _cancel_auto_hide(self):
        """取消自动隐藏"""
        if self._auto_hide_timer.isActive():
            self._auto_hide_timer.stop()
    
    def connect_cancel_signal(self, slot):
        """连接取消信号"""
        self._indicator.cancelRequested.connect(slot)
    
    def is_showing(self) -> bool:
        """是否正在显示"""
        return self._indicator.is_visible_status()