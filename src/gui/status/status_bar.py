"""
状态栏组件
显示应用程序状态、字数统计、AI状态、进度指示器等信息
"""

import logging
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QStatusBar, QLabel, QProgressBar, QPushButton, QWidget, 
    QHBoxLayout, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPalette

logger = logging.getLogger(__name__)


class StatusIndicator(QLabel):
    """状态指示器组件"""
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        
        self._setup_style()
        
    def _setup_style(self):
        """设置样式"""
        self.setFont(QFont("", 9))
        self.setStyleSheet("""
            QLabel {
                color: #656d76;
                padding: 2px 8px;
                border-right: 1px solid #e1e4e8;
            }
        """)
        
        # 设置固定高度
        self.setFixedHeight(22)
        
    def set_status(self, text: str, color: str = "#656d76"):
        """设置状态"""
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                padding: 2px 8px;
                border-right: 1px solid #e1e4e8;
            }}
        """)


class ProgressIndicator(QWidget):
    """进度指示器组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._init_ui()
        self._is_active = False
        
    def _init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(16)
        self._progress_bar.setFixedWidth(100)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e1e4e8;
                border-radius: 3px;
                text-align: center;
                background-color: #f8f9fa;
                font-size: 8px;
            }
            QProgressBar::chunk {
                background-color: #0969da;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self._progress_bar)
        
        # 进度文本
        self._progress_label = QLabel("")
        self._progress_label.setFont(QFont("", 8))
        self._progress_label.setStyleSheet("color: #656d76;")
        layout.addWidget(self._progress_label)
        
        # 默认隐藏
        self.hide()
    
    def show_progress(self, text: str = "处理中...", maximum: int = 0):
        """显示进度"""
        self._is_active = True
        self._progress_label.setText(text)
        
        if maximum > 0:
            self._progress_bar.setRange(0, maximum)
            self._progress_bar.setValue(0)
        else:
            # 无限进度条
            self._progress_bar.setRange(0, 0)
        
        self.show()
        
    def update_progress(self, value: int, text: str = ""):
        """更新进度"""
        if self._is_active:
            self._progress_bar.setValue(value)
            if text:
                self._progress_label.setText(text)
    
    def hide_progress(self):
        """隐藏进度"""
        self._is_active = False
        self.hide()


class AIStatusWidget(QWidget):
    """AI状态组件"""
    
    # 信号定义
    aiConfigRequested = pyqtSignal()  # AI配置请求信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._init_ui()
        self._setup_animations()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # AI状态图标
        self._ai_icon = QLabel("🤖")
        self._ai_icon.setFont(QFont("", 12))
        layout.addWidget(self._ai_icon)
        
        # AI状态文本
        self._ai_status = QLabel("就绪")
        self._ai_status.setFont(QFont("", 9))
        self._ai_status.setStyleSheet("color: #1a7f37;")
        layout.addWidget(self._ai_status)
        
        # AI配置按钮
        self._config_btn = QPushButton("⚙")
        self._config_btn.setFixedSize(16, 16)
        self._config_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-size: 10px;
                color: #656d76;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
                border-radius: 8px;
            }
        """)
        self._config_btn.setToolTip("AI配置")
        self._config_btn.clicked.connect(self.aiConfigRequested.emit)
        layout.addWidget(self._config_btn)
        
        # 设置固定高度
        self.setFixedHeight(22)
    
    def _setup_animations(self):
        """设置动画"""
        # 状态闪烁动画
        self._blink_timer = QTimer()
        self._blink_timer.timeout.connect(self._blink_status)
        
    def set_ai_status(self, status: str, color: str = "#1a7f37", blink: bool = False):
        """设置AI状态"""
        self._ai_status.setText(status)
        self._ai_status.setStyleSheet(f"color: {color};")
        
        if blink:
            self._blink_timer.start(500)
        else:
            self._blink_timer.stop()
    
    def _blink_status(self):
        """状态闪烁"""
        current_color = self._ai_status.styleSheet()
        if "#1a7f37" in current_color:
            self._ai_status.setStyleSheet("color: #656d76;")
        else:
            self._ai_status.setStyleSheet("color: #1a7f37;")


class EnhancedStatusBar(QStatusBar):
    """增强状态栏"""
    
    # 信号定义
    aiConfigRequested = pyqtSignal()  # AI配置请求信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._init_components()
        self._setup_style()
        
        # 状态数据
        self._word_count = 0
        self._char_count = 0
        self._paragraph_count = 0
        self._current_document = ""
        
        logger.debug("Enhanced status bar initialized")
    
    def _init_components(self):
        """初始化组件"""
        # 主要状态消息（左侧）
        self._main_message = QLabel("就绪")
        self._main_message.setFont(QFont("", 9))
        self.addWidget(self._main_message, 1)  # 拉伸因子为1

        # 行列位置指示器（左侧）
        self._cursor_position_label = StatusIndicator("行: 1, 列: 1")
        self._cursor_position_label.setToolTip("当前光标位置")
        self.addWidget(self._cursor_position_label)
        
        # 分隔符
        separator1 = self._create_separator()
        self.addPermanentWidget(separator1)
        
        # 进度指示器
        self._progress_indicator = ProgressIndicator()
        self.addPermanentWidget(self._progress_indicator)
        
        # 分隔符
        separator2 = self._create_separator()
        self.addPermanentWidget(separator2)
        
        # 字数统计
        self._word_count_label = StatusIndicator("字数: 0")
        self._word_count_label.setToolTip("当前文档的字数统计")
        self.addPermanentWidget(self._word_count_label)

        # 字符统计
        self._char_count_label = StatusIndicator("字符: 0")
        self._char_count_label.setToolTip("当前文档的字符数统计")
        self.addPermanentWidget(self._char_count_label)

        # 段落统计
        self._paragraph_count_label = StatusIndicator("段落: 0")
        self._paragraph_count_label.setToolTip("当前文档的段落数统计")
        self.addPermanentWidget(self._paragraph_count_label)

        # 文档状态
        self._doc_status_label = StatusIndicator("未保存")
        self._doc_status_label.setToolTip("当前文档的保存状态")
        self.addPermanentWidget(self._doc_status_label)
        
        # 分隔符
        separator3 = self._create_separator()
        self.addPermanentWidget(separator3)
        
        # AI状态
        self._ai_status_widget = AIStatusWidget()
        self._ai_status_widget.aiConfigRequested.connect(self.aiConfigRequested.emit)
        self.addPermanentWidget(self._ai_status_widget)
    
    def _create_separator(self) -> QFrame:
        """创建分隔符"""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setFixedHeight(16)
        separator.setStyleSheet("color: #e1e4e8;")
        return separator
    
    def _setup_style(self):
        """设置样式"""
        # 移除硬编码样式，使用主题样式
        # 状态栏样式现在由主题管理器控制

        # 设置固定高度
        self.setFixedHeight(26)
    
    def show_message(self, message: str, timeout: int = 0):
        """显示主要消息"""
        self._main_message.setText(message)
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self._main_message.setText("就绪"))
        
        logger.debug(f"Status message: {message}")
    
    def update_text_statistics(self, text: str):
        """更新文本统计信息（优化性能版本，支持中文）"""
        if not text:
            word_count = char_count = paragraph_count = 0
        else:
            # 中文友好的字数计算
            # 对于中文：按字符计算（排除空白字符）
            # 对于英文：按单词计算
            import re

            # 计算中文字符数
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))

            # 计算英文单词数
            english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))

            # 计算数字
            numbers = len(re.findall(r'\b\d+\b', text))

            # 总字数 = 中文字符数 + 英文单词数 + 数字个数
            word_count = chinese_chars + english_words + numbers

            # 字符数计算（不包括空白字符）
            char_count = sum(1 for c in text if not c.isspace())

            # 段落数计算（按双换行符分割）
            if '\n\n' in text:
                paragraphs = [p for p in text.split('\n\n') if p.strip()]
                paragraph_count = len(paragraphs)
            else:
                # 如果没有双换行符，按单换行符计算非空行
                lines = [line for line in text.split('\n') if line.strip()]
                paragraph_count = len(lines)

        self.update_word_count(word_count, char_count, paragraph_count)

    def update_cursor_position(self, line: int, column: int):
        """更新光标位置"""
        self._cursor_position_label.set_status(f"行: {line}, 列: {column}")

    def update_word_count(self, word_count: int, char_count: int, paragraph_count: int = 0):
        """更新字数统计"""
        self._word_count = word_count
        self._char_count = char_count
        self._paragraph_count = paragraph_count

        self._word_count_label.set_status(f"字数: {word_count:,}")
        self._char_count_label.set_status(f"字符: {char_count:,}")
        self._paragraph_count_label.set_status(f"段落: {paragraph_count:,}")
    
    def set_document_status(self, status: str, color: str = "#656d76"):
        """设置文档状态"""
        self._doc_status_label.set_status(status, color)
    
    def set_ai_status(self, status: str, color: str = "#1a7f37", blink: bool = False):
        """设置AI状态"""
        self._ai_status_widget.set_ai_status(status, color, blink)
    
    def show_progress(self, text: str = "处理中...", maximum: int = 0):
        """显示进度"""
        self._progress_indicator.show_progress(text, maximum)
    
    def update_progress(self, value: int, text: str = ""):
        """更新进度"""
        self._progress_indicator.update_progress(value, text)
    
    def hide_progress(self):
        """隐藏进度"""
        self._progress_indicator.hide_progress()
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "word_count": self._word_count,
            "char_count": self._char_count,
            "paragraph_count": self._paragraph_count,
            "current_document": self._current_document,
            "ai_status": self._ai_status_widget._ai_status.text()
        }
