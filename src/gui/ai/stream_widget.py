"""
流式响应显示组件
实时显示AI生成过程，支持中断和进度指示
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QLabel, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor

logger = logging.getLogger(__name__)


class StreamResponseWidget(QWidget):
    """流式响应显示组件"""
    
    # 信号定义
    responseCompleted = pyqtSignal(str)  # 响应完成信号
    responseCancelled = pyqtSignal()  # 响应取消信号
    responseAccepted = pyqtSignal(str)  # 响应接受信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._is_streaming = False
        self._current_response = ""
        self._typing_timer = QTimer()
        self._typing_timer.timeout.connect(self._simulate_typing)
        self._typing_index = 0
        self._full_text = ""
        
        self._init_ui()
        self._setup_animations()
        
        # 初始隐藏
        self.hide()
        
        logger.debug("Stream response widget initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标题栏
        title_frame = self._create_title_frame()
        layout.addWidget(title_frame)
        
        # 响应显示区域
        self._response_area = self._create_response_area()
        layout.addWidget(self._response_area)
        
        # 进度指示器
        self._progress_frame = self._create_progress_frame()
        layout.addWidget(self._progress_frame)
        
        # 操作按钮
        buttons_frame = self._create_buttons_frame()
        layout.addWidget(buttons_frame)
        
        # 设置整体样式
        self.setStyleSheet("""
            StreamResponseWidget {
                background-color: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
        """)
        
        self.setFixedWidth(400)
        self.setMinimumHeight(200)
        self.setMaximumHeight(500)
    
    def _create_title_frame(self) -> QFrame:
        """创建标题栏"""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # AI图标和标题
        self._title_label = QLabel("🤖 AI正在生成...")
        self._title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(self._title_label)
        
        layout.addStretch()
        
        # 状态指示器
        self._status_label = QLabel("●")
        self._status_label.setStyleSheet("color: #1a7f37; font-size: 16px;")
        layout.addWidget(self._status_label)
        
        return frame
    
    def _create_response_area(self) -> QTextEdit:
        """创建响应显示区域"""
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 12))
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                padding: 12px;
                line-height: 1.6;
            }
        """)
        
        # 设置光标样式
        cursor_format = QTextCharFormat()
        cursor_format.setBackground(QColor("#7c3aed"))
        
        return text_edit
    
    def _create_progress_frame(self) -> QFrame:
        """创建进度指示器"""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 4, 12, 4)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # 无限进度条
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                text-align: center;
                background-color: #f8f9fa;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #7c3aed;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._progress_bar)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        
        self._tokens_label = QLabel("Tokens: 0")
        self._tokens_label.setFont(QFont("", 9))
        self._tokens_label.setStyleSheet("color: #656d76;")
        stats_layout.addWidget(self._tokens_label)
        
        stats_layout.addStretch()
        
        self._time_label = QLabel("时间: 0s")
        self._time_label.setFont(QFont("", 9))
        self._time_label.setStyleSheet("color: #656d76;")
        stats_layout.addWidget(self._time_label)
        
        layout.addLayout(stats_layout)
        
        return frame
    
    def _create_buttons_frame(self) -> QFrame:
        """创建操作按钮"""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # 取消按钮
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setStyleSheet("""
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
        self._cancel_btn.clicked.connect(self._cancel_response)
        layout.addWidget(self._cancel_btn)
        
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
        self._accept_btn.clicked.connect(self._accept_response)
        self._accept_btn.setEnabled(False)
        layout.addWidget(self._accept_btn)
        
        return frame
    
    def _setup_animations(self):
        """设置动画"""
        # 状态指示器闪烁动画
        self._blink_timer = QTimer()
        self._blink_timer.timeout.connect(self._blink_status)
        
        # 淡入淡出动画
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(200)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def start_streaming(self, prompt: str = ""):
        """开始流式响应"""
        self._is_streaming = True
        self._current_response = ""
        self._typing_index = 0
        
        # 更新UI状态
        self._title_label.setText("🤖 AI正在生成...")
        self._response_area.clear()
        self._accept_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        
        # 开始动画
        self._blink_timer.start(500)
        self._progress_bar.setRange(0, 0)
        
        # 显示界面
        self._show_with_animation()
        
        logger.debug("Started streaming response")
    
    def append_text(self, text: str):
        """追加文本"""
        if not self._is_streaming:
            return
        
        self._current_response += text
        
        # 更新显示
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        
        # 滚动到底部
        scrollbar = self._response_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # 更新统计
        self._update_stats()
    
    def complete_streaming(self):
        """完成流式响应"""
        self._is_streaming = False
        
        # 更新UI状态
        self._title_label.setText("🤖 AI生成完成")
        self._status_label.setStyleSheet("color: #1a7f37; font-size: 16px;")
        self._accept_btn.setEnabled(True)
        self._cancel_btn.setText("关闭")
        
        # 停止动画
        self._blink_timer.stop()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        
        # 发出完成信号
        self.responseCompleted.emit(self._current_response)
        
        logger.info(f"Streaming completed, {len(self._current_response)} characters generated")
    
    def _show_with_animation(self):
        """带动画显示"""
        if not self.isVisible():
            self.show()
            self._fade_animation.setStartValue(0.0)
            self._fade_animation.setEndValue(1.0)
            self._fade_animation.start()
    
    def _blink_status(self):
        """状态指示器闪烁"""
        if self._is_streaming:
            current_color = self._status_label.styleSheet()
            if "#1a7f37" in current_color:
                self._status_label.setStyleSheet("color: #656d76; font-size: 16px;")
            else:
                self._status_label.setStyleSheet("color: #1a7f37; font-size: 16px;")
    
    def _update_stats(self):
        """更新统计信息"""
        # 简单的token计算（实际应该使用tokenizer）
        token_count = len(self._current_response.split())
        self._tokens_label.setText(f"Tokens: {token_count}")
        
        # TODO: 实现实际的时间统计
        self._time_label.setText("时间: 计算中...")
    
    def _cancel_response(self):
        """取消响应"""
        if self._is_streaming:
            self._is_streaming = False
            self._blink_timer.stop()
            self._title_label.setText("🤖 已取消生成")
            self._status_label.setStyleSheet("color: #cf222e; font-size: 16px;")
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(0)
            
            self.responseCancelled.emit()
            logger.info("Streaming cancelled by user")
        else:
            self.hide()
    
    def _accept_response(self):
        """接受响应"""
        if self._current_response:
            self.responseAccepted.emit(self._current_response)
            self.hide()
            logger.info("Response accepted by user")
    
    def simulate_streaming(self, text: str, speed: int = 50):
        """模拟流式输出（用于测试）"""
        self._full_text = text
        self._typing_index = 0
        
        self.start_streaming()
        self._typing_timer.start(speed)
    
    def _simulate_typing(self):
        """模拟打字效果"""
        if self._typing_index < len(self._full_text):
            char = self._full_text[self._typing_index]
            self.append_text(char)
            self._typing_index += 1
        else:
            self._typing_timer.stop()
            self.complete_streaming()
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_response()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self._accept_btn.isEnabled():
                self._accept_response()
        else:
            super().keyPressEvent(event)
