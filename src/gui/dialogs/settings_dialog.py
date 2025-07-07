"""
设置对话框
应用程序的主要设置界面，包括通用设置、编辑器设置、AI设置等
"""

import logging
from typing import Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QComboBox, QPushButton, QLabel,
    QGroupBox, QSlider, QTextEdit, QFileDialog, QColorDialog, QFontDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from gui.themes import ThemeType

logger = logging.getLogger(__name__)


class GeneralSettingsWidget(QGroupBox):
    """通用设置组件"""
    
    def __init__(self, parent=None):
        super().__init__("通用设置", parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 语言设置
        self._language_combo = QComboBox()
        self._language_combo.addItems(["简体中文", "English", "繁體中文"])
        layout.addRow("界面语言:", self._language_combo)
        
        # 主题设置
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["深色主题", "浅色主题", "高对比度"])
        layout.addRow("界面主题:", self._theme_combo)
        
        # 启动设置
        self._auto_save_check = QCheckBox("启用自动保存")
        self._auto_save_check.setChecked(True)
        layout.addRow(self._auto_save_check)
        
        self._auto_save_interval = QSpinBox()
        self._auto_save_interval.setRange(1, 60)
        self._auto_save_interval.setValue(5)
        self._auto_save_interval.setSuffix(" 分钟")
        layout.addRow("自动保存间隔:", self._auto_save_interval)
        
        # 备份设置
        self._backup_enabled_check = QCheckBox("启用自动备份")
        self._backup_enabled_check.setChecked(True)
        layout.addRow(self._backup_enabled_check)
        
        self._backup_count = QSpinBox()
        self._backup_count.setRange(1, 20)
        self._backup_count.setValue(5)
        layout.addRow("保留备份数量:", self._backup_count)
        
        # 启动行为
        self._restore_session_check = QCheckBox("启动时恢复上次会话")
        self._restore_session_check.setChecked(True)
        layout.addRow(self._restore_session_check)
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "language": self._language_combo.currentText(),
            "theme": self._theme_combo.currentText(),
            "auto_save": self._auto_save_check.isChecked(),
            "auto_save_interval": self._auto_save_interval.value(),
            "backup_enabled": self._backup_enabled_check.isChecked(),
            "backup_count": self._backup_count.value(),
            "restore_session": self._restore_session_check.isChecked()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        self._language_combo.setCurrentText(settings.get("language", "简体中文"))
        self._theme_combo.setCurrentText(settings.get("theme", "深色主题"))
        self._auto_save_check.setChecked(settings.get("auto_save", True))
        self._auto_save_interval.setValue(settings.get("auto_save_interval", 5))
        self._backup_enabled_check.setChecked(settings.get("backup_enabled", True))
        self._backup_count.setValue(settings.get("backup_count", 5))
        self._restore_session_check.setChecked(settings.get("restore_session", True))


class EditorSettingsWidget(QGroupBox):
    """编辑器设置组件"""
    
    def __init__(self, parent=None):
        super().__init__("编辑器设置", parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 字体设置
        font_layout = QHBoxLayout()
        self._font_label = QLabel("微软雅黑, 12pt")
        font_layout.addWidget(self._font_label)
        
        self._font_button = QPushButton("选择字体...")
        self._font_button.clicked.connect(self._select_font)
        font_layout.addWidget(self._font_button)
        
        layout.addRow("编辑器字体:", font_layout)
        
        # 行为设置
        self._word_wrap_check = QCheckBox("自动换行")
        self._word_wrap_check.setChecked(True)
        layout.addRow(self._word_wrap_check)
        
        self._line_numbers_check = QCheckBox("显示行号")
        self._line_numbers_check.setChecked(True)
        layout.addRow(self._line_numbers_check)
        
        self._highlight_current_line_check = QCheckBox("高亮当前行")
        self._highlight_current_line_check.setChecked(True)
        layout.addRow(self._highlight_current_line_check)
        
        # 缩进设置
        self._tab_width = QSpinBox()
        self._tab_width.setRange(2, 8)
        self._tab_width.setValue(4)
        layout.addRow("制表符宽度:", self._tab_width)
        
        self._use_spaces_check = QCheckBox("使用空格代替制表符")
        self._use_spaces_check.setChecked(True)
        layout.addRow(self._use_spaces_check)
        
        # 显示设置
        self._show_whitespace_check = QCheckBox("显示空白字符")
        layout.addRow(self._show_whitespace_check)
        
        self._cursor_blink_check = QCheckBox("光标闪烁")
        self._cursor_blink_check.setChecked(True)
        layout.addRow(self._cursor_blink_check)
    
    def _select_font(self):
        """选择字体"""
        current_font = QFont("微软雅黑", 12)
        font, ok = QFontDialog.getFont(current_font, self)
        if ok:
            self._font_label.setText(f"{font.family()}, {font.pointSize()}pt")
            self._selected_font = font
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "font_family": getattr(self, '_selected_font', QFont("微软雅黑", 12)).family(),
            "font_size": getattr(self, '_selected_font', QFont("微软雅黑", 12)).pointSize(),
            "word_wrap": self._word_wrap_check.isChecked(),
            "line_numbers": self._line_numbers_check.isChecked(),
            "highlight_current_line": self._highlight_current_line_check.isChecked(),
            "tab_width": self._tab_width.value(),
            "use_spaces": self._use_spaces_check.isChecked(),
            "show_whitespace": self._show_whitespace_check.isChecked(),
            "cursor_blink": self._cursor_blink_check.isChecked()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        font_family = settings.get("font_family", "微软雅黑")
        font_size = settings.get("font_size", 12)
        self._selected_font = QFont(font_family, font_size)
        self._font_label.setText(f"{font_family}, {font_size}pt")
        
        self._word_wrap_check.setChecked(settings.get("word_wrap", True))
        self._line_numbers_check.setChecked(settings.get("line_numbers", True))
        self._highlight_current_line_check.setChecked(settings.get("highlight_current_line", True))
        self._tab_width.setValue(settings.get("tab_width", 4))
        self._use_spaces_check.setChecked(settings.get("use_spaces", True))
        self._show_whitespace_check.setChecked(settings.get("show_whitespace", False))
        self._cursor_blink_check.setChecked(settings.get("cursor_blink", True))


class AISettingsWidget(QGroupBox):
    """AI设置组件"""
    
    def __init__(self, parent=None):
        super().__init__("AI设置", parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # AI功能开关
        self._ai_enabled_check = QCheckBox("启用AI功能")
        self._ai_enabled_check.setChecked(True)
        layout.addRow(self._ai_enabled_check)
        
        # 自动补全设置
        self._auto_completion_check = QCheckBox("启用自动补全")
        self._auto_completion_check.setChecked(True)
        layout.addRow(self._auto_completion_check)
        
        self._completion_delay = QSpinBox()
        self._completion_delay.setRange(100, 5000)
        self._completion_delay.setValue(500)
        self._completion_delay.setSuffix(" ms")
        layout.addRow("补全触发延迟:", self._completion_delay)
        
        # AI建议设置
        self._suggestion_count = QSpinBox()
        self._suggestion_count.setRange(1, 10)
        self._suggestion_count.setValue(3)
        layout.addRow("建议数量:", self._suggestion_count)
        
        self._show_confidence_check = QCheckBox("显示置信度")
        self._show_confidence_check.setChecked(True)
        layout.addRow(self._show_confidence_check)
        
        # 概念检测设置
        self._concept_detection_check = QCheckBox("启用概念检测")
        self._concept_detection_check.setChecked(True)
        layout.addRow(self._concept_detection_check)
        
        self._auto_concept_check = QCheckBox("自动创建检测到的概念")
        layout.addRow(self._auto_concept_check)
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "ai_enabled": self._ai_enabled_check.isChecked(),
            "auto_completion": self._auto_completion_check.isChecked(),
            "completion_delay": self._completion_delay.value(),
            "suggestion_count": self._suggestion_count.value(),
            "show_confidence": self._show_confidence_check.isChecked(),
            "concept_detection": self._concept_detection_check.isChecked(),
            "auto_concept": self._auto_concept_check.isChecked()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        self._ai_enabled_check.setChecked(settings.get("ai_enabled", True))
        self._auto_completion_check.setChecked(settings.get("auto_completion", True))
        self._completion_delay.setValue(settings.get("completion_delay", 500))
        self._suggestion_count.setValue(settings.get("suggestion_count", 3))
        self._show_confidence_check.setChecked(settings.get("show_confidence", True))
        self._concept_detection_check.setChecked(settings.get("concept_detection", True))
        self._auto_concept_check.setChecked(settings.get("auto_concept", False))


class SettingsDialog(QDialog):
    """设置对话框"""
    
    # 信号定义
    settingsChanged = pyqtSignal(dict)  # 设置变更信号
    
    def __init__(self, parent=None, settings: Dict[str, Any] = None):
        super().__init__(parent)
        
        self._settings = settings or {}
        
        self._init_ui()
        self._load_settings()
        
        # 设置对话框属性
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        self.setWindowTitle("设置")
        
        logger.debug("Settings dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标签页
        self._tabs = QTabWidget()
        
        # 通用设置
        self._general_widget = GeneralSettingsWidget()
        self._tabs.addTab(self._general_widget, "通用")
        
        # 编辑器设置
        self._editor_widget = EditorSettingsWidget()
        self._tabs.addTab(self._editor_widget, "编辑器")
        
        # AI设置
        self._ai_widget = AISettingsWidget()
        self._tabs.addTab(self._ai_widget, "AI功能")
        
        layout.addWidget(self._tabs)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)
        
        # 重置按钮
        reset_btn = QPushButton("重置默认")
        reset_btn.clicked.connect(self._reset_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._save_settings)
        ok_btn.setDefault(True)
        layout.addWidget(ok_btn)
        
        return layout
    
    def _load_settings(self):
        """加载设置"""
        if not self._settings:
            return
        
        # 加载各个组件的设置
        general_settings = self._settings.get("general", {})
        self._general_widget.set_settings(general_settings)
        
        editor_settings = self._settings.get("editor", {})
        self._editor_widget.set_settings(editor_settings)
        
        ai_settings = self._settings.get("ai", {})
        self._ai_widget.set_settings(ai_settings)
    
    def _save_settings(self):
        """保存设置"""
        settings = {
            "general": self._general_widget.get_settings(),
            "editor": self._editor_widget.get_settings(),
            "ai": self._ai_widget.get_settings()
        }
        
        self.settingsChanged.emit(settings)
        self.accept()
        
        logger.info("Settings saved")
    
    def _reset_defaults(self):
        """重置为默认设置"""
        # 重置为默认值
        self._general_widget.set_settings({})
        self._editor_widget.set_settings({})
        self._ai_widget.set_settings({})
        
        logger.info("Settings reset to defaults")
    
    def get_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        return {
            "general": self._general_widget.get_settings(),
            "editor": self._editor_widget.get_settings(),
            "ai": self._ai_widget.get_settings()
        }
