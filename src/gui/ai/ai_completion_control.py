"""
AI补全控制面板
提供AI补全功能的开关、设置和状态控制
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QCheckBox, QSlider, QSpinBox, QGroupBox, QPushButton,
                            QComboBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon

logger = logging.getLogger(__name__)


class AICompletionControlPanel(QWidget):
    """AI补全控制面板"""
    
    # 信号
    completionEnabledChanged = pyqtSignal(bool)
    autoTriggerEnabledChanged = pyqtSignal(bool)
    triggerDelayChanged = pyqtSignal(int)
    completionModeChanged = pyqtSignal(str)
    punctuationAssistChanged = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_settings()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("AI补全控制")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 主要开关
        self._create_main_controls(layout)
        
        # 触发设置
        self._create_trigger_settings(layout)
        
        # 补全模式
        self._create_completion_modes(layout)
        
        # 高级设置
        self._create_advanced_settings(layout)
        
        # 状态显示
        self._create_status_display(layout)
        
        # 操作按钮
        self._create_action_buttons(layout)
        
    def _create_main_controls(self, layout):
        """创建主要控制开关"""
        group = QGroupBox("基本控制")
        group_layout = QVBoxLayout(group)
        
        # AI补全总开关
        self.completion_enabled = QCheckBox("启用AI补全")
        self.completion_enabled.setChecked(True)
        self.completion_enabled.toggled.connect(self.completionEnabledChanged.emit)
        group_layout.addWidget(self.completion_enabled)
        
        # 自动触发开关
        self.auto_trigger_enabled = QCheckBox("自动触发补全")
        self.auto_trigger_enabled.setChecked(True)
        self.auto_trigger_enabled.toggled.connect(self.autoTriggerEnabledChanged.emit)
        group_layout.addWidget(self.auto_trigger_enabled)
        
        # 标点符号辅助
        self.punctuation_assist = QCheckBox("智能标点符号补全")
        self.punctuation_assist.setChecked(True)
        self.punctuation_assist.toggled.connect(self.punctuationAssistChanged.emit)
        group_layout.addWidget(self.punctuation_assist)
        
        layout.addWidget(group)
        
    def _create_trigger_settings(self, layout):
        """创建触发设置"""
        group = QGroupBox("触发设置")
        group_layout = QVBoxLayout(group)
        
        # 触发延迟
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("触发延迟:"))
        
        self.trigger_delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.trigger_delay_slider.setRange(100, 2000)  # 100ms - 2s
        self.trigger_delay_slider.setValue(500)
        self.trigger_delay_slider.valueChanged.connect(self._on_delay_changed)
        
        self.delay_label = QLabel("500ms")
        self.delay_label.setMinimumWidth(60)
        
        delay_layout.addWidget(self.trigger_delay_slider)
        delay_layout.addWidget(self.delay_label)
        group_layout.addLayout(delay_layout)
        
        # 触发条件说明
        info_label = QLabel("• 句子结束后自动触发\n• 换行后自动触发\n• 手动Ctrl+Space触发")
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        group_layout.addWidget(info_label)
        
        layout.addWidget(group)
        
    def _create_completion_modes(self, layout):
        """创建补全模式设置"""
        group = QGroupBox("补全模式")
        group_layout = QVBoxLayout(group)
        
        # 补全模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("模式:"))
        
        self.completion_mode = QComboBox()
        self.completion_mode.addItems([
            "自动AI补全",
            "手动AI补全",
            "禁用补全"
        ])
        self.completion_mode.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.completion_mode)

        group_layout.addLayout(mode_layout)

        # 模式说明
        self.mode_description = QLabel("自动AI补全：自动识别并触发AI补全")
        self.mode_description.setStyleSheet("color: #666; font-size: 11px;")
        self.mode_description.setWordWrap(True)
        group_layout.addWidget(self.mode_description)
        
        layout.addWidget(group)
        
    def _create_advanced_settings(self, layout):
        """创建高级设置"""
        group = QGroupBox("高级设置")
        group_layout = QVBoxLayout(group)
        
        # 上下文长度
        context_layout = QHBoxLayout()
        context_layout.addWidget(QLabel("上下文长度:"))
        
        self.context_length = QSpinBox()
        self.context_length.setRange(100, 1000)
        self.context_length.setValue(500)
        self.context_length.setSuffix(" 字符")
        context_layout.addWidget(self.context_length)
        
        group_layout.addLayout(context_layout)
        
        # 补全长度限制
        length_layout = QHBoxLayout()
        length_layout.addWidget(QLabel("补全长度限制:"))
        
        self.completion_length = QSpinBox()
        self.completion_length.setRange(20, 200)
        self.completion_length.setValue(80)
        self.completion_length.setSuffix(" 字符")
        length_layout.addWidget(self.completion_length)
        
        group_layout.addLayout(length_layout)
        
        layout.addWidget(group)
        
    def _create_status_display(self, layout):
        """创建状态显示"""
        group = QGroupBox("状态信息")
        group_layout = QVBoxLayout(group)
        
        # 当前状态
        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        group_layout.addWidget(self.status_label)
        
        # 统计信息
        self.stats_label = QLabel("今日补全: 0 次 | 接受率: 0%")
        self.stats_label.setStyleSheet("color: #666; font-size: 11px;")
        group_layout.addWidget(self.stats_label)
        
        layout.addWidget(group)
        
    def _create_action_buttons(self, layout):
        """创建操作按钮"""
        button_layout = QHBoxLayout()
        
        # 手动触发按钮
        self.manual_trigger_btn = QPushButton("手动触发补全")
        self.manual_trigger_btn.clicked.connect(self._manual_trigger)
        button_layout.addWidget(self.manual_trigger_btn)
        
        # 清除补全按钮
        self.clear_completion_btn = QPushButton("清除当前补全")
        self.clear_completion_btn.clicked.connect(self._clear_completion)
        button_layout.addWidget(self.clear_completion_btn)
        
        layout.addLayout(button_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # 重置按钮
        reset_layout = QHBoxLayout()
        self.reset_btn = QPushButton("重置为默认设置")
        self.reset_btn.clicked.connect(self._reset_settings)
        reset_layout.addWidget(self.reset_btn)
        
        layout.addLayout(reset_layout)
        
    def _on_delay_changed(self, value):
        """触发延迟改变"""
        self.delay_label.setText(f"{value}ms")
        self.triggerDelayChanged.emit(value)
        
    def _on_mode_changed(self, mode_text):
        """补全模式改变"""
        mode_descriptions = {
            "自动AI补全": "自动AI补全：自动识别并触发AI补全",
            "手动AI补全": "手动AI补全：按Tab键手动触发AI补全",
            "禁用补全": "禁用补全：完全关闭AI补全功能"
        }

        self.mode_description.setText(mode_descriptions.get(mode_text, ""))

        # 映射到内部模式名称
        mode_mapping = {
            "自动AI补全": "auto_ai",
            "手动AI补全": "manual_ai",
            "禁用补全": "disabled"
        }

        mode = mode_mapping.get(mode_text, "auto_ai")
        self.completionModeChanged.emit(mode)
        
    def _manual_trigger(self):
        """手动触发补全"""
        # 发送手动触发信号
        if hasattr(self.parent(), '_ai_manager'):
            self.parent()._ai_manager.request_completion('manual')
            
    def _clear_completion(self):
        """清除当前补全"""
        # 发送清除信号
        if hasattr(self.parent(), '_current_editor'):
            editor = self.parent()._current_editor
            if hasattr(editor, 'clear_ghost_text'):
                editor.clear_ghost_text()
                
    def _reset_settings(self):
        """重置设置"""
        self.completion_enabled.setChecked(True)
        self.auto_trigger_enabled.setChecked(True)
        self.punctuation_assist.setChecked(True)
        self.trigger_delay_slider.setValue(500)
        self.completion_mode.setCurrentIndex(0)
        self.context_length.setValue(500)
        self.completion_length.setValue(80)
        
    def _load_settings(self):
        """加载设置"""
        # TODO: 从配置文件加载设置
        pass
        
    def _save_settings(self):
        """保存设置"""
        # TODO: 保存设置到配置文件
        pass
        
    def update_status(self, status: str, color: str = "#28a745"):
        """更新状态显示"""
        self.status_label.setText(f"状态: {status}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        
    def update_stats(self, completions: int, acceptance_rate: float):
        """更新统计信息"""
        self.stats_label.setText(f"今日补全: {completions} 次 | 接受率: {acceptance_rate:.1f}%")
        
    def get_settings(self) -> dict:
        """获取当前设置"""
        return {
            'completion_enabled': self.completion_enabled.isChecked(),
            'auto_trigger_enabled': self.auto_trigger_enabled.isChecked(),
            'punctuation_assist': self.punctuation_assist.isChecked(),
            'trigger_delay': self.trigger_delay_slider.value(),
            'completion_mode': self.completion_mode.currentText(),
            'context_length': self.context_length.value(),
            'completion_length': self.completion_length.value()
        }
        
    def set_settings(self, settings: dict):
        """设置配置"""
        if 'completion_enabled' in settings:
            self.completion_enabled.setChecked(settings['completion_enabled'])
        if 'auto_trigger_enabled' in settings:
            self.auto_trigger_enabled.setChecked(settings['auto_trigger_enabled'])
        if 'punctuation_assist' in settings:
            self.punctuation_assist.setChecked(settings['punctuation_assist'])
        if 'trigger_delay' in settings:
            self.trigger_delay_slider.setValue(settings['trigger_delay'])
        if 'completion_mode' in settings:
            index = self.completion_mode.findText(settings['completion_mode'])
            if index >= 0:
                self.completion_mode.setCurrentIndex(index)
        if 'context_length' in settings:
            self.context_length.setValue(settings['context_length'])
        if 'completion_length' in settings:
            self.completion_length.setValue(settings['completion_length'])
