"""
简化的提示词配置组件
基于NovelCrafter的设计理念，提供标签化的简洁界面
"""

import logging
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QPushButton, QButtonGroup, QRadioButton,
    QTextEdit, QSlider, QSpinBox, QCheckBox, QFrame,
    QScrollArea, QGridLayout, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPalette, QColor

logger = logging.getLogger(__name__)


class StyleTagButton(QPushButton):
    """风格标签按钮"""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(32)
        self.setMinimumWidth(80)
        self._setup_style()
    
    def _setup_style(self):
        """设置按钮样式"""
        self.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid #d0d0d0;
                border-radius: 16px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 500;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e8f4fd;
                border-color: #4a90e2;
            }
            QPushButton:checked {
                background-color: #4a90e2;
                border-color: #3574c7;
                color: white;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #357abd;
            }
        """)


class ContextModeSelector(QWidget):
    """上下文模式选择器"""
    
    modeChanged = pyqtSignal(str)  # 模式变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("补全深度")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 模式选择
        modes_layout = QHBoxLayout()
        self.button_group = QButtonGroup(self)
        
        modes = [
            ("快速", "fast", "轻量补全，适合快速写作"),
            ("平衡", "balanced", "质量与速度并重，推荐使用"),
            ("深度", "full", "最佳效果，适合精细创作")
        ]
        
        for i, (text, mode, tooltip) in enumerate(modes):
            btn = QRadioButton(text)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, m=mode: self.modeChanged.emit(m))
            self.button_group.addButton(btn, i)
            modes_layout.addWidget(btn)
        
        # 默认选择平衡模式
        self.button_group.button(1).setChecked(True)
        
        modes_layout.addStretch()
        layout.addLayout(modes_layout)
    
    def get_current_mode(self) -> str:
        """获取当前选择的模式"""
        checked_id = self.button_group.checkedId()
        mode_map = {0: "fast", 1: "balanced", 2: "full"}
        return mode_map.get(checked_id, "balanced")
    
    def set_current_mode(self, mode: str):
        """设置当前模式"""
        mode_map = {"fast": 0, "balanced": 1, "full": 2}
        if mode in mode_map:
            self.button_group.button(mode_map[mode]).setChecked(True)


class GenreStyleSelector(QWidget):
    """文体风格选择器"""
    
    styleChanged = pyqtSignal(list)  # 选择的风格标签列表
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._selected_tags = []
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("文体风格")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 风格标签区域
        self._create_style_tags(layout)
    
    def _create_style_tags(self, parent_layout):
        """创建风格标签"""
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 标签容器
        tag_widget = QWidget()
        tag_layout = QGridLayout(tag_widget)
        tag_layout.setSpacing(8)
        
        # 风格标签定义
        style_categories = {
            "文学类型": ["武侠", "都市", "科幻", "奇幻", "历史", "悬疑", "言情", "青春"],
            "叙事风格": ["第一人称", "第三人称", "全知视角", "多线程", "倒叙", "插叙"],
            "情感色调": ["轻松幽默", "深沉内敛", "激昂热血", "温馨治愈", "悲伤忧郁", "紧张刺激"],
            "文字风格": ["简洁明快", "华丽辞藻", "口语化", "文言古风", "现代时尚", "诗意抒情"]
        }
        
        row = 0
        self.tag_buttons = {}
        
        for category, tags in style_categories.items():
            # 分类标题
            category_label = QLabel(category)
            category_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            category_label.setStyleSheet("color: #666; margin-top: 8px;")
            tag_layout.addWidget(category_label, row, 0, 1, 4)
            row += 1
            
            # 标签按钮
            col = 0
            for tag in tags:
                btn = StyleTagButton(tag)
                btn.clicked.connect(self._on_tag_clicked)
                self.tag_buttons[tag] = btn
                tag_layout.addWidget(btn, row, col)
                col += 1
                if col >= 4:  # 每行4个标签
                    col = 0
                    row += 1
            
            if col > 0:  # 如果当前行没满，移到下一行
                row += 1
        
        scroll.setWidget(tag_widget)
        parent_layout.addWidget(scroll)
        
        # 选择提示
        hint = QLabel("💡 选择适合您作品的风格标签，可多选")
        hint.setStyleSheet("color: #888; font-size: 10px; margin-top: 8px;")
        parent_layout.addWidget(hint)
    
    def _on_tag_clicked(self):
        """标签点击处理"""
        sender = self.sender()
        tag_text = sender.text()
        
        if sender.isChecked():
            if tag_text not in self._selected_tags:
                self._selected_tags.append(tag_text)
        else:
            if tag_text in self._selected_tags:
                self._selected_tags.remove(tag_text)
        
        self.styleChanged.emit(self._selected_tags)
    
    def get_selected_tags(self) -> List[str]:
        """获取选择的标签"""
        return self._selected_tags.copy()
    
    def set_selected_tags(self, tags: List[str]):
        """设置选择的标签"""
        self._selected_tags = tags.copy()
        
        # 更新界面
        for tag, btn in self.tag_buttons.items():
            btn.setChecked(tag in tags)


class AdvancedSettings(QWidget):
    """高级设置（可折叠）"""
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._expanded = False
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 展开/收起按钮
        self.toggle_btn = QPushButton("🔧 高级设置")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self._toggle_expanded)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                border: none;
                padding: 8px 0px;
                background: transparent;
                font-size: 11px;
                font-weight: bold;
                color: #4a90e2;
            }
            QPushButton:hover {
                color: #357abd;
            }
        """)
        layout.addWidget(self.toggle_btn)
        
        # 高级设置内容
        self.settings_widget = QWidget()
        self.settings_widget.setVisible(False)
        self._create_advanced_settings()
        layout.addWidget(self.settings_widget)
    
    def _create_advanced_settings(self):
        """创建高级设置内容"""
        layout = QVBoxLayout(self.settings_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # 创意度设置
        creativity_group = QGroupBox("创意度控制")
        creativity_layout = QVBoxLayout(creativity_group)
        
        # Temperature 滑块
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("创意度:"))
        self.temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self.temperature_slider.setRange(1, 20)  # 0.1 to 2.0
        self.temperature_slider.setValue(8)  # 0.8
        self.temperature_label = QLabel("0.8")
        self.temperature_slider.valueChanged.connect(
            lambda v: self.temperature_label.setText(f"{v/10:.1f}")
        )
        temp_layout.addWidget(self.temperature_slider)
        temp_layout.addWidget(self.temperature_label)
        creativity_layout.addLayout(temp_layout)
        
        # 长度控制
        length_layout = QHBoxLayout()
        length_layout.addWidget(QLabel("补全长度:"))
        self.length_spin = QSpinBox()
        self.length_spin.setRange(20, 200)
        self.length_spin.setValue(80)
        self.length_spin.setSuffix(" 字符")
        length_layout.addWidget(self.length_spin)
        length_layout.addStretch()
        creativity_layout.addLayout(length_layout)
        
        layout.addWidget(creativity_group)
        
        # 触发设置
        trigger_group = QGroupBox("触发设置")
        trigger_layout = QVBoxLayout(trigger_group)
        
        # 自动触发
        self.auto_trigger = QCheckBox("自动触发补全")
        self.auto_trigger.setChecked(True)
        trigger_layout.addWidget(self.auto_trigger)
        
        # 延迟设置
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("触发延迟:"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(100, 2000)
        self.delay_spin.setValue(500)
        self.delay_spin.setSuffix(" 毫秒")
        delay_layout.addWidget(self.delay_spin)
        delay_layout.addStretch()
        trigger_layout.addLayout(delay_layout)
        
        layout.addWidget(trigger_group)
        
        # 连接信号
        self._connect_signals()
    
    def _connect_signals(self):
        """连接信号"""
        self.temperature_slider.valueChanged.connect(self._emit_settings_changed)
        self.length_spin.valueChanged.connect(self._emit_settings_changed)
        self.auto_trigger.toggled.connect(self._emit_settings_changed)
        self.delay_spin.valueChanged.connect(self._emit_settings_changed)
    
    def _emit_settings_changed(self):
        """发送设置变化信号"""
        settings = self.get_settings()
        self.settingsChanged.emit(settings)
    
    def _toggle_expanded(self):
        """切换展开状态"""
        self._expanded = not self._expanded
        self.settings_widget.setVisible(self._expanded)
        
        if self._expanded:
            self.toggle_btn.setText("🔧 高级设置 ▼")
        else:
            self.toggle_btn.setText("🔧 高级设置 ▶")
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "temperature": self.temperature_slider.value() / 10.0,
            "max_length": self.length_spin.value(),
            "auto_trigger": self.auto_trigger.isChecked(),
            "trigger_delay": self.delay_spin.value()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        if "temperature" in settings:
            self.temperature_slider.setValue(int(settings["temperature"] * 10))
        if "max_length" in settings:
            self.length_spin.setValue(settings["max_length"])
        if "auto_trigger" in settings:
            self.auto_trigger.setChecked(settings["auto_trigger"])
        if "trigger_delay" in settings:
            self.delay_spin.setValue(settings["trigger_delay"])


class SimplifiedPromptWidget(QWidget):
    """简化的提示词配置主组件"""
    
    # 信号
    configChanged = pyqtSignal(dict)  # 配置变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()
        self._current_config = {}
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)
        
        # 主标题
        title = QLabel("AI写作助手")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 描述
        desc = QLabel("选择适合您创作风格的设置，AI将为您提供智能补全建议")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 12px; margin-bottom: 20px;")
        layout.addWidget(desc)
        
        # 主要设置区域
        main_settings = QFrame()
        main_settings.setFrameStyle(QFrame.Shape.Box)
        main_settings.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        main_layout = QVBoxLayout(main_settings)
        main_layout.setSpacing(20)
        
        # 上下文模式选择
        self.context_selector = ContextModeSelector()
        main_layout.addWidget(self.context_selector)
        
        # 分割线
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("color: #ddd;")
        main_layout.addWidget(line1)
        
        # 文体风格选择
        self.style_selector = GenreStyleSelector()
        main_layout.addWidget(self.style_selector)
        
        layout.addWidget(main_settings)
        
        # 高级设置
        self.advanced_settings = AdvancedSettings()
        layout.addWidget(self.advanced_settings)
        
        # 预设方案快速选择
        self._create_preset_section(layout)
        
        # 按钮区域
        self._create_button_section(layout)
        
        layout.addStretch()
    
    def _create_preset_section(self, parent_layout):
        """创建预设方案快速选择"""
        preset_group = QGroupBox("快速预设")
        preset_layout = QHBoxLayout(preset_group)
        
        presets = [
            ("新手推荐", {"context": "balanced", "styles": ["简洁明快"], "temp": 0.7}),
            ("文学创作", {"context": "full", "styles": ["诗意抒情", "华丽辞藻"], "temp": 0.9}),
            ("网文快写", {"context": "fast", "styles": ["口语化", "轻松幽默"], "temp": 0.8}),
            ("传统文学", {"context": "full", "styles": ["文言古风", "深沉内敛"], "temp": 0.6})
        ]
        
        for name, config in presets:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, cfg=config: self._apply_preset(cfg))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    border-color: #adb5bd;
                }
            """)
            preset_layout.addWidget(btn)
        
        preset_layout.addStretch()
        parent_layout.addWidget(preset_group)
    
    def _create_button_section(self, parent_layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        # 测试按钮
        test_btn = QPushButton("🧪 测试设置")
        test_btn.clicked.connect(self._test_settings)
        button_layout.addWidget(test_btn)
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置默认")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 应用按钮
        apply_btn = QPushButton("✅ 应用设置")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        apply_btn.clicked.connect(self._apply_settings)
        button_layout.addWidget(apply_btn)
        
        parent_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.context_selector.modeChanged.connect(self._on_config_changed)
        self.style_selector.styleChanged.connect(self._on_config_changed)
        self.advanced_settings.settingsChanged.connect(self._on_config_changed)
    
    def _on_config_changed(self):
        """配置变化处理"""
        self._current_config = self.get_config()
        self.configChanged.emit(self._current_config)
    
    def _apply_preset(self, preset_config: Dict[str, Any]):
        """应用预设配置"""
        # 设置上下文模式
        if "context" in preset_config:
            self.context_selector.set_current_mode(preset_config["context"])
        
        # 设置风格标签
        if "styles" in preset_config:
            self.style_selector.set_selected_tags(preset_config["styles"])
        
        # 设置高级参数
        if "temp" in preset_config:
            advanced_settings = self.advanced_settings.get_settings()
            advanced_settings["temperature"] = preset_config["temp"]
            self.advanced_settings.set_settings(advanced_settings)
        
        self._on_config_changed()
    
    def _test_settings(self):
        """测试当前设置"""
        config = self.get_config()
        QMessageBox.information(
            self, "测试设置",
            f"当前配置：\n"
            f"上下文模式: {config['context_mode']}\n"
            f"风格标签: {', '.join(config['style_tags']) if config['style_tags'] else '无'}\n"
            f"创意度: {config['temperature']}\n"
            f"补全长度: {config['max_length']} 字符"
        )
    
    def _reset_to_defaults(self):
        """重置为默认设置"""
        # 重置上下文模式
        self.context_selector.set_current_mode("balanced")
        
        # 清空风格标签
        self.style_selector.set_selected_tags([])
        
        # 重置高级设置
        default_advanced = {
            "temperature": 0.8,
            "max_length": 80,
            "auto_trigger": True,
            "trigger_delay": 500
        }
        self.advanced_settings.set_settings(default_advanced)
        
        self._on_config_changed()
    
    def _apply_settings(self):
        """应用设置"""
        config = self.get_config()
        self.configChanged.emit(config)
        QMessageBox.information(self, "成功", "设置已应用！")
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        advanced = self.advanced_settings.get_settings()
        
        return {
            "context_mode": self.context_selector.get_current_mode(),
            "style_tags": self.style_selector.get_selected_tags(),
            "temperature": advanced["temperature"],
            "max_length": advanced["max_length"],
            "auto_trigger": advanced["auto_trigger"],
            "trigger_delay": advanced["trigger_delay"]
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        if "context_mode" in config:
            self.context_selector.set_current_mode(config["context_mode"])
        
        if "style_tags" in config:
            self.style_selector.set_selected_tags(config["style_tags"])
        
        # 设置高级配置
        advanced_config = {
            "temperature": config.get("temperature", 0.8),
            "max_length": config.get("max_length", 80),
            "auto_trigger": config.get("auto_trigger", True),
            "trigger_delay": config.get("trigger_delay", 500)
        }
        self.advanced_settings.set_settings(advanced_config)
        
        self._current_config = config.copy()