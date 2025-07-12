"""
增强提示词配置组件 - 为AI配置对话框提供完整的提示词配置功能

集成标签化操作、上下文模式选择和高级提示词设置
"""

import logging
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QPushButton, QButtonGroup, QRadioButton,
    QTextEdit, QSlider, QSpinBox, QCheckBox, QFrame,
    QScrollArea, QGridLayout, QSizePolicy, QMessageBox,
    QFormLayout, QLineEdit
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


class EnhancedPromptConfigWidget(QFrame):
    """增强提示词配置组件"""
    
    # 信号定义
    contextModeChanged = pyqtSignal(str)
    styleTagsChanged = pyqtSignal(list)
    configChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_available_tags()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题和说明
        title_label = QLabel("智能提示词配置")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        desc_label = QLabel(
            "配置AI补全的提示词生成策略，选择合适的上下文模式和风格标签以获得最佳补全效果。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 16px;")
        layout.addWidget(desc_label)
        
        # 上下文模式配置
        self._create_context_mode_config(layout)
        
        # 风格标签配置
        self._create_style_tags_config(layout)
        
        # 高级提示词设置
        self._create_advanced_prompt_settings(layout)
        
        # 预设方案管理
        self._create_preset_management(layout)
        
    def _create_context_mode_config(self, layout):
        """创建上下文模式配置"""
        group = QGroupBox("上下文模式")
        group_layout = QVBoxLayout(group)
        
        # 模式说明
        desc_label = QLabel("选择AI补全的上下文深度，影响生成质量和响应速度：")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 8px;")
        group_layout.addWidget(desc_label)
        
        # 模式选择按钮
        modes_layout = QHBoxLayout()
        self.context_mode_group = QButtonGroup(self)
        
        modes = [
            ("快速模式", "fast", "轻量级上下文，最快响应\n适合：快速草稿、简单续写"),
            ("平衡模式", "balanced", "适中上下文，平衡质量与速度\n适合：日常写作、一般补全"),
            ("深度模式", "full", "完整上下文，最佳质量\n适合：精细创作、复杂情节")
        ]
        
        for i, (text, mode, tooltip) in enumerate(modes):
            btn = QRadioButton(text)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, m=mode: self._on_context_mode_changed(m))
            self.context_mode_group.addButton(btn, i)
            modes_layout.addWidget(btn)
        
        # 默认选择平衡模式
        self.context_mode_group.button(1).setChecked(True)
        self._current_context_mode = "balanced"
        
        modes_layout.addStretch()
        group_layout.addLayout(modes_layout)
        
        # 模式详细说明
        self.context_mode_desc = QLabel("平衡模式：在效果与成本间取得平衡，适合日常写作")
        self.context_mode_desc.setStyleSheet("color: #0066cc; font-style: italic; margin-top: 8px;")
        self.context_mode_desc.setWordWrap(True)
        group_layout.addWidget(self.context_mode_desc)
        
        layout.addWidget(group)
    
    def _create_style_tags_config(self, layout):
        """创建风格标签配置"""
        group = QGroupBox("风格标签")
        group_layout = QVBoxLayout(group)
        
        # 标签说明
        desc_label = QLabel("选择写作风格标签，AI将根据这些标签调整生成内容的风格和语调：")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 12px;")
        group_layout.addWidget(desc_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(200)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        
        # 创建标签按钮组
        self.tag_buttons = {}
        self.selected_tags = []
        
        # 添加标签分类
        self._add_tag_category(scroll_layout, "文体风格", [
            "科幻", "武侠", "都市", "奇幻", "历史", "悬疑", "浪漫", "恐怖"
        ])
        
        self._add_tag_category(scroll_layout, "情感风格", [
            "轻松幽默", "严肃深沉", "温馨治愈", "紧张刺激", "忧郁沉重", "激昂热血"
        ])
        
        self._add_tag_category(scroll_layout, "叙述风格", [
            "第一人称", "第三人称", "全知视角", "细腻描写", "简洁明快", "诗意表达"
        ])
        
        self._add_tag_category(scroll_layout, "内容类型", [
            "对话", "动作", "描写", "心理", "情节推进", "场景转换"
        ])
        
        scroll_area.setWidget(scroll_widget)
        group_layout.addWidget(scroll_area)
        
        # 已选标签显示
        selected_layout = QHBoxLayout()
        selected_layout.addWidget(QLabel("已选择:"))
        
        self.selected_tags_label = QLabel("无")
        self.selected_tags_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        self.selected_tags_label.setWordWrap(True)
        selected_layout.addWidget(self.selected_tags_label)
        
        selected_layout.addStretch()
        
        clear_btn = QPushButton("清除全部")
        clear_btn.clicked.connect(self._clear_all_tags)
        clear_btn.setFixedWidth(80)
        selected_layout.addWidget(clear_btn)
        
        group_layout.addLayout(selected_layout)
        
        layout.addWidget(group)
    
    def _add_tag_category(self, layout, category_name, tags):
        """添加标签分类"""
        # 分类标题
        category_label = QLabel(category_name)
        category_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        category_label.setStyleSheet("color: #333; margin: 8px 0 4px 0;")
        layout.addWidget(category_label)
        
        # 标签按钮
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(8)
        
        for tag in tags:
            btn = StyleTagButton(tag)
            btn.clicked.connect(lambda checked, t=tag: self._on_tag_clicked(t, checked))
            self.tag_buttons[tag] = btn
            tags_layout.addWidget(btn)
        
        tags_layout.addStretch()
        layout.addLayout(tags_layout)
    
    def _create_advanced_prompt_settings(self, layout):
        """创建高级提示词设置"""
        group = QGroupBox("高级设置")
        group_layout = QFormLayout(group)
        
        # 自定义提示词前缀
        self.custom_prefix_edit = QTextEdit()
        self.custom_prefix_edit.setFixedHeight(60)
        self.custom_prefix_edit.setPlaceholderText("可选：添加自定义提示词前缀")
        group_layout.addRow("自定义前缀:", self.custom_prefix_edit)
        
        # 续写长度偏好
        length_layout = QHBoxLayout()
        self.length_slider = QSlider(Qt.Orientation.Horizontal)
        self.length_slider.setRange(50, 500)
        self.length_slider.setValue(200)
        self.length_label = QLabel("200字")
        
        self.length_slider.valueChanged.connect(
            lambda v: self.length_label.setText(f"{v}字")
        )
        
        length_layout.addWidget(self.length_slider)
        length_layout.addWidget(self.length_label)
        group_layout.addRow("续写长度:", length_layout)
        
        # 创造性调节
        creativity_layout = QHBoxLayout()
        self.creativity_slider = QSlider(Qt.Orientation.Horizontal)
        self.creativity_slider.setRange(0, 100)
        self.creativity_slider.setValue(70)
        self.creativity_label = QLabel("0.7")
        
        self.creativity_slider.valueChanged.connect(
            lambda v: self.creativity_label.setText(f"{v/100:.1f}")
        )
        
        creativity_layout.addWidget(self.creativity_slider)
        creativity_layout.addWidget(self.creativity_label)
        group_layout.addRow("创造性:", creativity_layout)
        
        # 上下文长度
        self.context_length_spin = QSpinBox()
        self.context_length_spin.setRange(200, 2000)
        self.context_length_spin.setValue(800)
        self.context_length_spin.setSuffix(" 字符")
        group_layout.addRow("上下文长度:", self.context_length_spin)
        
        layout.addWidget(group)
    
    def _create_preset_management(self, layout):
        """创建预设方案管理"""
        group = QGroupBox("预设方案")
        group_layout = QVBoxLayout(group)
        
        # 预设选择
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("快速方案:"))
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "默认设置",
            "创意写作",
            "学术写作",
            "商务写作",
            "小说创作",
            "诗歌散文"
        ])
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo)
        
        # 保存预设按钮
        save_preset_btn = QPushButton("保存当前设置")
        save_preset_btn.clicked.connect(self._save_current_preset)
        preset_layout.addWidget(save_preset_btn)
        
        preset_layout.addStretch()
        group_layout.addLayout(preset_layout)
        
        # 预设说明
        self.preset_desc = QLabel("默认设置：适合一般写作场景的平衡配置")
        self.preset_desc.setStyleSheet("color: #666; font-style: italic;")
        self.preset_desc.setWordWrap(True)
        group_layout.addWidget(self.preset_desc)
        
        layout.addWidget(group)
    
    def _on_context_mode_changed(self, mode):
        """上下文模式变化处理"""
        self._current_context_mode = mode
        
        # 更新说明文字
        mode_descriptions = {
            "fast": "快速模式：轻量级上下文，最快响应，适合快速草稿",
            "balanced": "平衡模式：在效果与成本间取得平衡，适合日常写作",
            "full": "深度模式：完整项目上下文，最佳效果，适合精细创作"
        }
        
        self.context_mode_desc.setText(mode_descriptions.get(mode, ""))
        
        # 发送信号
        self.contextModeChanged.emit(mode)
        self.configChanged.emit()
    
    def _on_tag_clicked(self, tag, checked):
        """标签点击处理"""
        if checked:
            if tag not in self.selected_tags:
                self.selected_tags.append(tag)
        else:
            if tag in self.selected_tags:
                self.selected_tags.remove(tag)
        
        # 更新已选标签显示
        if self.selected_tags:
            self.selected_tags_label.setText(", ".join(self.selected_tags))
        else:
            self.selected_tags_label.setText("无")
        
        # 发送信号
        self.styleTagsChanged.emit(self.selected_tags.copy())
        self.configChanged.emit()
    
    def _clear_all_tags(self):
        """清除所有标签"""
        for tag, btn in self.tag_buttons.items():
            btn.setChecked(False)
        
        self.selected_tags.clear()
        self.selected_tags_label.setText("无")
        
        # 发送信号
        self.styleTagsChanged.emit([])
        self.configChanged.emit()
    
    def _on_preset_changed(self, preset_name):
        """预设方案变化处理"""
        presets = {
            "默认设置": {
                "context_mode": "balanced",
                "tags": [],
                "length": 200,
                "creativity": 70,
                "context_length": 800,
                "description": "适合一般写作场景的平衡配置"
            },
            "创意写作": {
                "context_mode": "full",
                "tags": ["奇幻", "创意表达", "诗意表达"],
                "length": 300,
                "creativity": 85,
                "context_length": 1200,
                "description": "高创造性设置，适合创意写作和想象力创作"
            },
            "学术写作": {
                "context_mode": "balanced",
                "tags": ["严肃深沉", "简洁明快"],
                "length": 150,
                "creativity": 40,
                "context_length": 600,
                "description": "严谨准确的学术写作风格"
            },
            "小说创作": {
                "context_mode": "full",
                "tags": ["第三人称", "细腻描写", "情节推进"],
                "length": 250,
                "creativity": 75,
                "context_length": 1000,
                "description": "适合小说创作的丰富上下文配置"
            }
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            self.apply_preset(preset)
            self.preset_desc.setText(preset["description"])
    
    def _save_current_preset(self):
        """保存当前设置为预设"""
        from PyQt6.QtWidgets import QInputDialog
        
        text, ok = QInputDialog.getText(self, "保存预设", "请输入预设名称:")
        if ok and text.strip():
            # 这里可以实现保存预设的逻辑
            QMessageBox.information(self, "成功", f"预设 '{text}' 已保存")
    
    def _load_available_tags(self):
        """加载可用的标签"""
        # 这里可以从配置文件或AI管理器加载标签
        # 当前使用硬编码的标签
        pass
    
    def apply_preset(self, preset_config):
        """应用预设配置"""
        # 设置上下文模式
        context_mode = preset_config.get("context_mode", "balanced")
        mode_index = {"fast": 0, "balanced": 1, "full": 2}.get(context_mode, 1)
        self.context_mode_group.button(mode_index).setChecked(True)
        self._on_context_mode_changed(context_mode)
        
        # 清除并设置标签
        self._clear_all_tags()
        for tag in preset_config.get("tags", []):
            if tag in self.tag_buttons:
                self.tag_buttons[tag].setChecked(True)
                self.selected_tags.append(tag)
        
        if self.selected_tags:
            self.selected_tags_label.setText(", ".join(self.selected_tags))
        
        # 设置其他参数
        self.length_slider.setValue(preset_config.get("length", 200))
        self.creativity_slider.setValue(preset_config.get("creativity", 70))
        self.context_length_spin.setValue(preset_config.get("context_length", 800))
        
        # 发送信号
        self.styleTagsChanged.emit(self.selected_tags.copy())
        self.configChanged.emit()
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "context_mode": self._current_context_mode,
            "style_tags": self.selected_tags.copy(),
            "custom_prefix": self.custom_prefix_edit.toPlainText(),
            "preferred_length": self.length_slider.value(),
            "creativity": self.creativity_slider.value() / 100,
            "context_length": self.context_length_spin.value(),
            "preset": self.preset_combo.currentText()
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        # 设置上下文模式
        context_mode = config.get("context_mode", "balanced")
        mode_index = {"fast": 0, "balanced": 1, "full": 2}.get(context_mode, 1)
        self.context_mode_group.button(mode_index).setChecked(True)
        self._on_context_mode_changed(context_mode)
        
        # 设置风格标签
        self._clear_all_tags()
        for tag in config.get("style_tags", []):
            if tag in self.tag_buttons:
                self.tag_buttons[tag].setChecked(True)
                self.selected_tags.append(tag)
        
        if self.selected_tags:
            self.selected_tags_label.setText(", ".join(self.selected_tags))
        
        # 设置其他配置
        self.custom_prefix_edit.setPlainText(config.get("custom_prefix", ""))
        self.length_slider.setValue(config.get("preferred_length", 200))
        self.creativity_slider.setValue(int(config.get("creativity", 0.7) * 100))
        self.context_length_spin.setValue(config.get("context_length", 800))
        
        # 设置预设
        preset = config.get("preset", "默认设置")
        index = self.preset_combo.findText(preset)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
    
    def get_current_context_mode(self) -> str:
        """获取当前上下文模式"""
        return self._current_context_mode
    
    def get_selected_tags(self) -> List[str]:
        """获取选中的标签"""
        return self.selected_tags.copy()