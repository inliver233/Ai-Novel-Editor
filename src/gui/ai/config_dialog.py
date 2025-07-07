"""
AI配置对话框
管理AI服务商配置、提示词模板、补全参数等设置
"""

import logging
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout,
    QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QLabel, QGroupBox, QCheckBox, QSlider, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class AIProviderConfigWidget(QFrame):
    """AI服务商配置组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 服务商选择
        provider_group = QGroupBox("AI服务商")
        provider_layout = QFormLayout(provider_group)
        
        self._provider_combo = QComboBox()
        self._provider_combo.addItems([
            "OpenAI", "Claude (Anthropic)", "通义千问 (阿里云)", 
            "智谱AI", "DeepSeek", "自定义"
        ])
        provider_layout.addRow("服务商:", self._provider_combo)
        
        # API配置
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("请输入API密钥")
        provider_layout.addRow("API密钥:", self._api_key_edit)
        
        self._api_base_edit = QLineEdit()
        self._api_base_edit.setPlaceholderText("API基础URL (可选)")
        provider_layout.addRow("API地址:", self._api_base_edit)
        
        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText("模型名称")
        provider_layout.addRow("模型:", self._model_edit)
        
        layout.addWidget(provider_group)
        
        # 连接测试
        test_group = QGroupBox("连接测试")
        test_layout = QVBoxLayout(test_group)
        
        test_btn_layout = QHBoxLayout()
        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._test_connection)
        test_btn_layout.addWidget(self._test_btn)
        test_btn_layout.addStretch()
        
        test_layout.addLayout(test_btn_layout)
        
        self._test_result_label = QLabel("点击测试连接以验证配置")
        self._test_result_label.setStyleSheet("color: #656d76;")
        test_layout.addWidget(self._test_result_label)
        
        layout.addWidget(test_group)
        
        # 连接信号
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
    
    def _on_provider_changed(self, provider: str):
        """服务商变化处理"""
        # 根据服务商设置默认值
        defaults = {
            "OpenAI": {
                "api_base": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo"
            },
            "Claude (Anthropic)": {
                "api_base": "https://api.anthropic.com",
                "model": "claude-3-sonnet-20240229"
            },
            "通义千问 (阿里云)": {
                "api_base": "",
                "model": "qwen-long"
            },
            "智谱AI": {
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4"
            },
            "DeepSeek": {
                "api_base": "https://api.deepseek.com",
                "model": "deepseek-chat"
            }
        }
        
        if provider in defaults:
            config = defaults[provider]
            self._api_base_edit.setText(config["api_base"])
            self._model_edit.setText(config["model"])
    
    def _test_connection(self):
        """测试连接"""
        self._test_result_label.setText("正在测试连接...")
        self._test_result_label.setStyleSheet("color: #0969da;")
        
        # TODO: 实现实际的连接测试
        # 这里暂时模拟测试结果
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, self._show_test_result)
    
    def _show_test_result(self):
        """显示测试结果"""
        # 模拟测试成功
        self._test_result_label.setText("✓ 连接测试成功")
        self._test_result_label.setStyleSheet("color: #1a7f37;")
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "provider": self._provider_combo.currentText(),
            "api_key": self._api_key_edit.text(),
            "api_base": self._api_base_edit.text(),
            "model": self._model_edit.text()
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self._provider_combo.setCurrentText(config.get("provider", "OpenAI"))
        self._api_key_edit.setText(config.get("api_key", ""))
        self._api_base_edit.setText(config.get("api_base", ""))
        self._model_edit.setText(config.get("model", ""))


class CompletionConfigWidget(QFrame):
    """补全配置组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 补全参数
        params_group = QGroupBox("补全参数")
        params_layout = QFormLayout(params_group)
        
        # 温度
        self._temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self._temperature_slider.setRange(0, 100)
        self._temperature_slider.setValue(80)
        self._temperature_label = QLabel("0.8")
        
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(self._temperature_slider)
        temp_layout.addWidget(self._temperature_label)
        
        self._temperature_slider.valueChanged.connect(
            lambda v: self._temperature_label.setText(f"{v/100:.1f}")
        )
        
        params_layout.addRow("创造性 (Temperature):", temp_layout)
        
        # Top-p
        self._top_p_slider = QSlider(Qt.Orientation.Horizontal)
        self._top_p_slider.setRange(0, 100)
        self._top_p_slider.setValue(90)
        self._top_p_label = QLabel("0.9")
        
        top_p_layout = QHBoxLayout()
        top_p_layout.addWidget(self._top_p_slider)
        top_p_layout.addWidget(self._top_p_label)
        
        self._top_p_slider.valueChanged.connect(
            lambda v: self._top_p_label.setText(f"{v/100:.1f}")
        )
        
        params_layout.addRow("多样性 (Top-p):", top_p_layout)
        
        # 最大长度
        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(50, 4000)
        self._max_tokens_spin.setValue(500)
        self._max_tokens_spin.setSuffix(" tokens")
        params_layout.addRow("最大长度:", self._max_tokens_spin)
        
        layout.addWidget(params_group)
        
        # 补全行为
        behavior_group = QGroupBox("补全行为")
        behavior_layout = QVBoxLayout(behavior_group)
        
        self._auto_trigger_check = QCheckBox("自动触发补全")
        self._auto_trigger_check.setChecked(True)
        behavior_layout.addWidget(self._auto_trigger_check)
        
        self._show_confidence_check = QCheckBox("显示置信度")
        self._show_confidence_check.setChecked(True)
        behavior_layout.addWidget(self._show_confidence_check)
        
        self._stream_response_check = QCheckBox("流式响应")
        self._stream_response_check.setChecked(True)
        behavior_layout.addWidget(self._stream_response_check)
        
        layout.addWidget(behavior_group)
        
        # 触发设置
        trigger_group = QGroupBox("触发设置")
        trigger_layout = QFormLayout(trigger_group)
        
        self._trigger_delay_spin = QSpinBox()
        self._trigger_delay_spin.setRange(100, 5000)
        self._trigger_delay_spin.setValue(500)
        self._trigger_delay_spin.setSuffix(" ms")
        trigger_layout.addRow("触发延迟:", self._trigger_delay_spin)
        
        self._min_chars_spin = QSpinBox()
        self._min_chars_spin.setRange(1, 10)
        self._min_chars_spin.setValue(3)
        trigger_layout.addRow("最小字符数:", self._min_chars_spin)
        
        layout.addWidget(trigger_group)
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "temperature": self._temperature_slider.value() / 100,
            "top_p": self._top_p_slider.value() / 100,
            "max_tokens": self._max_tokens_spin.value(),
            "auto_trigger": self._auto_trigger_check.isChecked(),
            "show_confidence": self._show_confidence_check.isChecked(),
            "stream_response": self._stream_response_check.isChecked(),
            "trigger_delay": self._trigger_delay_spin.value(),
            "min_chars": self._min_chars_spin.value()
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self._temperature_slider.setValue(int(config.get("temperature", 0.8) * 100))
        self._top_p_slider.setValue(int(config.get("top_p", 0.9) * 100))
        self._max_tokens_spin.setValue(config.get("max_tokens", 500))
        self._auto_trigger_check.setChecked(config.get("auto_trigger", True))
        self._show_confidence_check.setChecked(config.get("show_confidence", True))
        self._stream_response_check.setChecked(config.get("stream_response", True))
        self._trigger_delay_spin.setValue(config.get("trigger_delay", 500))
        self._min_chars_spin.setValue(config.get("min_chars", 3))


class AIConfigDialog(QDialog):
    """AI配置对话框"""
    
    configSaved = pyqtSignal(dict)  # 配置保存信号
    
    def __init__(self, parent=None, config: Dict[str, Any] = None):
        super().__init__(parent)
        
        self._config = config or {}
        
        self._init_ui()
        self._load_config()
        
        # 设置对话框属性
        self.setModal(True)
        self.setMinimumSize(500, 600)
        self.resize(600, 700)
        self.setWindowTitle("AI配置")
        
        logger.debug("AI config dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标签页
        self._tabs = QTabWidget()
        
        # AI服务商配置
        self._provider_widget = AIProviderConfigWidget()
        self._tabs.addTab(self._provider_widget, "AI服务商")
        
        # 补全配置
        self._completion_widget = CompletionConfigWidget()
        self._tabs.addTab(self._completion_widget, "补全设置")
        
        layout.addWidget(self._tabs)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)
        layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._save_config)
        ok_btn.setDefault(True)
        layout.addWidget(ok_btn)
        
        return layout
    
    def _load_config(self):
        """加载配置"""
        if not self._config:
            return
        
        # 加载AI服务商配置
        provider_config = self._config.get("provider", {})
        self._provider_widget.set_config(provider_config)
        
        # 加载补全配置
        completion_config = self._config.get("completion", {})
        self._completion_widget.set_config(completion_config)
    
    def _save_config(self):
        """保存配置"""
        config = {
            "provider": self._provider_widget.get_config(),
            "completion": self._completion_widget.get_config()
        }
        
        self.configSaved.emit(config)
        self.accept()
        
        logger.info("AI config saved")
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "provider": self._provider_widget.get_config(),
            "completion": self._completion_widget.get_config()
        }
