"""
补全状态指示器
显示当前补全模式和AI状态
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QIcon, QPixmap, QPainter

logger = logging.getLogger(__name__)


class StatusIndicatorWidget(QFrame):
    """状态指示器组件"""
    
    # 信号定义
    modeChangeRequested = pyqtSignal(str)  # 模式切换请求
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._current_mode = 'auto_ai'
        self._ai_status = 'idle'  # idle, thinking, error
        self._is_ai_available = True
        
        self._init_ui()
        self._setup_style()
        
        # 状态更新定时器
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_display)
        self._status_timer.start(1000)  # 每秒更新一次
        
        logger.debug("Completion status indicator initialized")
        
    def _init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # 补全模式指示器
        self._mode_label = QLabel()
        self._mode_label.setFont(QFont("Segoe UI", 9))
        self._mode_label.setMinimumWidth(80)
        layout.addWidget(self._mode_label)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # AI状态指示器
        self._ai_status_label = QLabel()
        self._ai_status_label.setFont(QFont("Segoe UI", 9))
        self._ai_status_label.setMinimumWidth(60)
        layout.addWidget(self._ai_status_label)
        
        # 模式切换按钮
        self._mode_button = QPushButton("切换")
        self._mode_button.setFont(QFont("Segoe UI", 8))
        self._mode_button.setMaximumWidth(50)
        self._mode_button.clicked.connect(self._on_mode_button_clicked)
        layout.addWidget(self._mode_button)
        
        # 初始化显示
        self._update_display()
        
    def _setup_style(self):
        """设置样式"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        
        # 设置背景色
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(64, 64, 64, 180);
                border: 1px solid rgba(128, 128, 128, 100);
                border-radius: 6px;
            }
            QLabel {
                color: #E0E0E0;
                background: transparent;
                border: none;
            }
            QPushButton {
                background-color: rgba(80, 80, 80, 200);
                border: 1px solid rgba(128, 128, 128, 150);
                border-radius: 3px;
                color: #E0E0E0;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: rgba(100, 100, 100, 200);
            }
            QPushButton:pressed {
                background-color: rgba(60, 60, 60, 200);
            }
        """)
        
    def set_completion_mode(self, mode: str):
        """设置补全模式"""
        if mode != self._current_mode:
            self._current_mode = mode
            self._update_display()
            logger.debug(f"Completion mode indicator updated: {mode}")
            
    def set_ai_status(self, status: str):
        """设置AI状态"""
        if status != self._ai_status:
            self._ai_status = status
            self._update_display()
            logger.debug(f"AI status indicator updated: {status}")
            
    def set_ai_available(self, available: bool):
        """设置AI可用性"""
        if available != self._is_ai_available:
            self._is_ai_available = available
            self._update_display()
            
    def _update_display(self):
        """更新显示"""
        # 更新模式显示
        mode_texts = {
            'manual_ai': '🎯 手动AI',
            'disabled': '❌ 禁用',
            'auto_ai': '🤖 自动AI'
        }

        mode_tooltips = {
            'manual_ai': '手动AI模式：按Tab键手动触发AI补全',
            'disabled': '禁用模式：关闭AI补全，使用默认补全',
            'auto_ai': '自动AI模式：自动识别并触发AI补全'
        }
        
        mode_text = mode_texts.get(self._current_mode, self._current_mode)
        self._mode_label.setText(mode_text)
        self._mode_label.setToolTip(mode_tooltips.get(self._current_mode, ''))
        
        # 更新AI状态显示
        if not self._is_ai_available:
            ai_text = "❌ 不可用"
            ai_tooltip = "AI服务不可用"
            ai_color = "#FF6B6B"
        elif self._ai_status == 'thinking':
            ai_text = "🤔 思考中"
            ai_tooltip = "AI正在生成补全建议"
            ai_color = "#4ECDC4"
        elif self._ai_status == 'error':
            ai_text = "⚠️ 错误"
            ai_tooltip = "AI服务出现错误"
            ai_color = "#FFE66D"
        else:  # idle
            ai_text = "✅ 就绪"
            ai_tooltip = "AI服务就绪"
            ai_color = "#95E1D3"
            
        self._ai_status_label.setText(ai_text)
        self._ai_status_label.setToolTip(ai_tooltip)
        self._ai_status_label.setStyleSheet(f"color: {ai_color};")
        
        # 更新按钮状态
        self._mode_button.setEnabled(True)
        
    def _on_mode_button_clicked(self):
        """模式按钮点击处理"""
        # 循环切换模式
        modes = ['manual_ai', 'disabled', 'auto_ai']
        current_index = modes.index(self._current_mode) if self._current_mode in modes else 0
        next_mode = modes[(current_index + 1) % len(modes)]

        self.modeChangeRequested.emit(next_mode)
        
    def get_current_mode(self) -> str:
        """获取当前模式"""
        return self._current_mode
        
    def get_ai_status(self) -> str:
        """获取AI状态"""
        return self._ai_status


class FloatingStatusIndicator(StatusIndicatorWidget):
    """浮动状态指示器 - 显示在编辑器右下角"""
    
    def __init__(self, text_editor):
        super().__init__(text_editor)
        
        self._text_editor = text_editor
        self._is_enabled = False  # 默认禁用
        
        # 设置为浮动窗口
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # 立即隐藏并禁用
        self.hide()
        self.setVisible(False)
        
        logger.debug("FloatingStatusIndicator initialized and disabled")
        
    def _update_position(self):
        """更新位置到编辑器右下角"""
        # 禁用位置更新，防止意外显示
        if not self._is_enabled or not self._text_editor:
            return
            
        try:
            editor_rect = self._text_editor.geometry()
            editor_global_pos = self._text_editor.mapToGlobal(editor_rect.bottomRight())
            
            # 计算位置（右下角，留出边距）
            x = editor_global_pos.x() - self.width() - 20
            y = editor_global_pos.y() - self.height() - 20
            
            # 确保在屏幕边界内
            screen = self._text_editor.screen()
            if screen:
                screen_rect = screen.availableGeometry()
                x = max(0, min(x, screen_rect.width() - self.width()))
                y = max(0, min(y, screen_rect.height() - self.height()))
            
            self.move(x, y)
        except Exception as e:
            logger.warning(f"Failed to update FloatingStatusIndicator position: {e}")
        
    def _on_editor_resize(self, event):
        """编辑器大小变化处理"""
        # 调用原始的resizeEvent
        if hasattr(self._text_editor, '_original_resize_event'):
            self._text_editor._original_resize_event(event)

        # 只在启用时更新指示器位置
        if self._is_enabled:
            self._update_position()
        
    def showEvent(self, event):
        """显示事件"""
        # 只在启用时才显示
        if not self._is_enabled:
            self.hide()
            return
        super().showEvent(event)
        self._update_position()
        
    def set_visible(self, visible: bool):
        """设置可见性"""
        # 强制禁用显示，防止bug
        self._force_hide()
        
    def _force_hide(self):
        """强制隐藏"""
        self.hide()
        self.setVisible(False)
        self._is_enabled = False
        logger.debug("FloatingStatusIndicator force hidden")
        
    def enable_floating_indicator(self, enabled: bool = True):
        """启用或禁用浮动指示器（调试用）"""
        self._is_enabled = enabled
        if not enabled:
            self._force_hide()
        logger.debug(f"FloatingStatusIndicator enabled: {enabled}")


class EmbeddedStatusIndicator(StatusIndicatorWidget):
    """嵌入式状态指示器 - 嵌入到编辑器状态栏"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 调整样式为嵌入式
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QLabel {
                color: #B0B0B0;
                background: transparent;
                border: none;
            }
            QPushButton {
                background-color: rgba(80, 80, 80, 100);
                border: 1px solid rgba(128, 128, 128, 100);
                border-radius: 3px;
                color: #B0B0B0;
                padding: 1px 4px;
            }
            QPushButton:hover {
                background-color: rgba(100, 100, 100, 150);
            }
        """)
        
        # 调整大小
        self.setMaximumHeight(24)
        
    def _setup_style(self):
        """重写样式设置"""
        pass  # 在__init__中已设置

    def set_visible(self, visible: bool):
        """设置可见性"""
        if visible:
            self.show()
        else:
            self.hide()
