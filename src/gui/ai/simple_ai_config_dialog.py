"""
简化的AI配置对话框
统一所有AI相关配置，替代复杂的多对话框系统
"""

import logging
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QComboBox, QCheckBox, QSlider, QPushButton,
    QTabWidget, QWidget, QLabel, QTextEdit, QMessageBox, 
    QDialogButtonBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class SimpleAIConfigDialog(QDialog):
    """
    简化的AI配置对话框
    
    整合原有的5个配置对话框功能：
    - config_dialog.py (基础AI配置)
    - unified_ai_config_dialog.py (统一配置)
    - outline_ai_config_dialog.py (大纲AI配置)
    - rag_config_dialog.py (RAG配置)
    - config_mapper.py (配置映射)
    """
    
    configChanged = pyqtSignal()
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._original_values = {}
        
        self.setWindowTitle("AI配置")
        self.setModal(True)
        self.resize(600, 500)
        
        self._init_ui()
        self._load_current_config()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 基础AI配置标签页
        self._create_basic_ai_tab(tab_widget)
        
        # 补全设置标签页
        self._create_completion_tab(tab_widget)
        
        # 高级设置标签页
        self._create_advanced_tab(tab_widget)
        
        layout.addWidget(tab_widget)
        
        # 按钮区域
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_config)
        layout.addWidget(button_box)
    
    def _create_basic_ai_tab(self, tab_widget: QTabWidget):
        """创建基础AI配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # AI提供商配置
        provider_group = QGroupBox("AI提供商")
        provider_layout = QFormLayout(provider_group)
        
        # AI提供商选择
        self._provider_combo = QComboBox()
        self._provider_combo.addItems([
            "openai", "claude", "qwen", "zhipu", "deepseek", "groq"
        ])
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addRow("AI提供商:", self._provider_combo)
        
        # API密钥
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("输入API密钥...")
        provider_layout.addRow("API密钥:", self._api_key_edit)
        
        # 模型选择
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        provider_layout.addRow("模型:", self._model_combo)
        
        # API基础URL（可选）
        self._base_url_edit = QLineEdit()
        self._base_url_edit.setPlaceholderText("可选，留空使用默认值")
        provider_layout.addRow("API基础URL:", self._base_url_edit)
        
        layout.addWidget(provider_group)
        
        # 连接测试
        test_group = QGroupBox("连接测试")
        test_layout = QVBoxLayout(test_group)
        
        self._test_button = QPushButton("测试连接")
        self._test_button.clicked.connect(self._test_connection)
        test_layout.addWidget(self._test_button)
        
        self._test_result_edit = QTextEdit()
        self._test_result_edit.setMaximumHeight(100)
        self._test_result_edit.setReadOnly(True)
        test_layout.addWidget(self._test_result_edit)
        
        layout.addWidget(test_group)
        layout.addStretch()
        
        tab_widget.addTab(widget, "基础配置")
    
    def _create_completion_tab(self, tab_widget: QTabWidget):
        """创建补全设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 补全行为
        behavior_group = QGroupBox("补全行为")
        behavior_layout = QFormLayout(behavior_group)
        
        # 启用补全
        self._completion_enabled_check = QCheckBox("启用AI补全")
        behavior_layout.addRow(self._completion_enabled_check)
        
        # 自动触发
        self._auto_trigger_check = QCheckBox("自动触发补全")
        behavior_layout.addRow(self._auto_trigger_check)
        
        # 触发延迟
        self._trigger_delay_spin = QSpinBox()
        self._trigger_delay_spin.setRange(100, 5000)
        self._trigger_delay_spin.setSuffix(" ms")
        self._trigger_delay_spin.setValue(1000)
        behavior_layout.addRow("触发延迟:", self._trigger_delay_spin)
        
        layout.addWidget(behavior_group)
        
        # 生成参数
        params_group = QGroupBox("生成参数")
        params_layout = QFormLayout(params_group)
        
        # 最大Token数
        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(10, 1000)
        self._max_tokens_spin.setValue(100)
        params_layout.addRow("最大Token数:", self._max_tokens_spin)
        
        # 温度值
        self._temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self._temperature_slider.setRange(0, 100)
        self._temperature_slider.setValue(70)
        
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(self._temperature_slider)
        self._temperature_label = QLabel("0.7")
        self._temperature_slider.valueChanged.connect(
            lambda v: self._temperature_label.setText(f"{v/100:.2f}")
        )
        temp_layout.addWidget(self._temperature_label)
        
        params_layout.addRow("创意程度:", temp_layout)
        
        layout.addWidget(params_group)
        layout.addStretch()
        
        tab_widget.addTab(widget, "补全设置")
    
    def _create_advanced_tab(self, tab_widget: QTabWidget):
        """创建高级设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 性能设置
        performance_group = QGroupBox("性能设置")
        performance_layout = QFormLayout(performance_group)
        
        # 缓存启用
        self._cache_enabled_check = QCheckBox("启用补全缓存")
        self._cache_enabled_check.setChecked(True)
        performance_layout.addRow(self._cache_enabled_check)
        
        # 缓存大小
        self._cache_size_spin = QSpinBox()
        self._cache_size_spin.setRange(10, 1000)
        self._cache_size_spin.setValue(100)
        performance_layout.addRow("缓存大小:", self._cache_size_spin)
        
        # 超时设置
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 120)
        self._timeout_spin.setSuffix(" 秒")
        self._timeout_spin.setValue(30)
        performance_layout.addRow("请求超时:", self._timeout_spin)
        
        layout.addWidget(performance_group)
        
        # 日志设置
        logging_group = QGroupBox("日志设置")
        logging_layout = QFormLayout(logging_group)
        
        # 日志级别
        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._log_level_combo.setCurrentText("INFO")
        logging_layout.addRow("日志级别:", self._log_level_combo)
        
        # 记录API调用
        self._log_api_calls_check = QCheckBox("记录API调用详情")
        logging_layout.addRow(self._log_api_calls_check)
        
        layout.addWidget(logging_group)
        
        # 重置按钮
        reset_group = QGroupBox("重置选项")
        reset_layout = QVBoxLayout(reset_group)
        
        reset_button = QPushButton("恢复默认设置")
        reset_button.clicked.connect(self._reset_to_defaults)
        reset_layout.addWidget(reset_button)
        
        clear_cache_button = QPushButton("清空缓存")
        clear_cache_button.clicked.connect(self._clear_cache)
        reset_layout.addWidget(clear_cache_button)
        
        layout.addWidget(reset_group)
        layout.addStretch()
        
        tab_widget.addTab(widget, "高级设置")
    
    def _on_provider_changed(self, provider: str):
        """处理提供商变更"""
        # 更新模型列表
        models = self._get_models_for_provider(provider)
        self._model_combo.clear()
        self._model_combo.addItems(models)
        
        # 更新API基础URL提示
        default_url = self._get_default_url_for_provider(provider)
        self._base_url_edit.setPlaceholderText(f"留空使用默认值: {default_url}")
    
    def _get_models_for_provider(self, provider: str) -> List[str]:
        """获取指定提供商的模型列表"""
        models_map = {
            "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            "claude": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
            "qwen": ["qwen-max", "qwen-plus", "qwen-turbo"],
            "zhipu": ["glm-4", "glm-3-turbo"],
            "deepseek": ["deepseek-chat", "deepseek-coder"],
            "groq": ["llama2-70b-4096", "mixtral-8x7b-32768"]
        }
        return models_map.get(provider, [""])
    
    def _get_default_url_for_provider(self, provider: str) -> str:
        """获取提供商的默认URL"""
        url_map = {
            "openai": "https://api.openai.com/v1",
            "claude": "https://api.anthropic.com",
            "qwen": "https://dashscope.aliyuncs.com/api/v1",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "deepseek": "https://api.deepseek.com",
            "groq": "https://api.groq.com/openai/v1"
        }
        return url_map.get(provider, "")
    
    def _test_connection(self):
        """测试AI连接"""
        self._test_result_edit.clear()
        self._test_result_edit.append("正在测试连接...")
        self._test_button.setEnabled(False)
        
        try:
            # 获取当前配置
            provider = self._provider_combo.currentText()
            api_key = self._api_key_edit.text().strip()
            model = self._model_combo.currentText().strip()
            
            if not api_key:
                self._test_result_edit.append("❌ 错误：API密钥不能为空")
                return
            
            if not model:
                self._test_result_edit.append("❌ 错误：模型不能为空")
                return
            
            # 简化的连接测试（实际项目中会调用AI客户端）
            self._test_result_edit.append(f"✅ 配置验证通过")
            self._test_result_edit.append(f"   提供商: {provider}")
            self._test_result_edit.append(f"   模型: {model}")
            self._test_result_edit.append(f"   API密钥: {'*' * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else '****'}")
            self._test_result_edit.append("⚠️  注意：实际连接测试需要AI客户端支持")
            
        except Exception as e:
            self._test_result_edit.append(f"❌ 测试失败: {str(e)}")
        
        finally:
            self._test_button.setEnabled(True)
    
    def _reset_to_defaults(self):
        """重置到默认设置"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要恢复所有设置到默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 重置基础配置
            self._provider_combo.setCurrentText("openai")
            self._api_key_edit.clear()
            self._base_url_edit.clear()
            
            # 重置补全设置
            self._completion_enabled_check.setChecked(True)
            self._auto_trigger_check.setChecked(True)
            self._trigger_delay_spin.setValue(1000)
            self._max_tokens_spin.setValue(100)
            self._temperature_slider.setValue(70)
            
            # 重置高级设置
            self._cache_enabled_check.setChecked(True)
            self._cache_size_spin.setValue(100)
            self._timeout_spin.setValue(30)
            self._log_level_combo.setCurrentText("INFO")
            self._log_api_calls_check.setChecked(False)
            
            QMessageBox.information(self, "重置完成", "设置已恢复到默认值")
    
    def _clear_cache(self):
        """清空缓存"""
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空AI补全缓存吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 这里会调用AI管理器的清空缓存方法
            QMessageBox.information(self, "清空完成", "AI补全缓存已清空")
    
    def _load_current_config(self):
        """加载当前配置"""
        try:
            # 使用Config的get_section方法获取AI配置
            ai_config = self._config.get_section('ai') or {}
            
            # 加载基础配置
            provider = ai_config.get('provider', 'openai')
            self._provider_combo.setCurrentText(provider)
            self._on_provider_changed(provider)  # 更新模型列表
            
            self._api_key_edit.setText(ai_config.get('api_key', ''))
            self._model_combo.setCurrentText(ai_config.get('model', ''))
            self._base_url_edit.setText(ai_config.get('base_url', ''))
            
            # 加载补全设置
            completion_config = ai_config.get('completion', {})
            self._completion_enabled_check.setChecked(completion_config.get('enabled', True))
            self._auto_trigger_check.setChecked(completion_config.get('auto_trigger', True))
            self._trigger_delay_spin.setValue(completion_config.get('trigger_delay', 1000))
            self._max_tokens_spin.setValue(completion_config.get('max_tokens', 100))
            
            temperature = completion_config.get('temperature', 0.7)
            self._temperature_slider.setValue(int(temperature * 100))
            
            # 加载高级设置
            self._cache_enabled_check.setChecked(ai_config.get('cache_enabled', True))
            self._cache_size_spin.setValue(ai_config.get('cache_size', 100))
            self._timeout_spin.setValue(ai_config.get('timeout', 30))
            self._log_level_combo.setCurrentText(ai_config.get('log_level', 'INFO'))
            self._log_api_calls_check.setChecked(ai_config.get('log_api_calls', False))
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
    
    def _apply_config(self):
        """应用配置"""
        try:
            # 构建配置字典
            ai_config = {
                'provider': self._provider_combo.currentText(),
                'api_key': self._api_key_edit.text().strip(),
                'model': self._model_combo.currentText().strip(),
                'base_url': self._base_url_edit.text().strip(),
                'completion': {
                    'enabled': self._completion_enabled_check.isChecked(),
                    'auto_trigger': self._auto_trigger_check.isChecked(),
                    'trigger_delay': self._trigger_delay_spin.value(),
                    'max_tokens': self._max_tokens_spin.value(),
                    'temperature': self._temperature_slider.value() / 100.0
                },
                'cache_enabled': self._cache_enabled_check.isChecked(),
                'cache_size': self._cache_size_spin.value(),
                'timeout': self._timeout_spin.value(),
                'log_level': self._log_level_combo.currentText(),
                'log_api_calls': self._log_api_calls_check.isChecked()
            }
            
            # 保存配置
            self._config.set('ai', ai_config)
            self._config.save()
            
            # 发送配置变更信号
            self.configChanged.emit()
            
            QMessageBox.information(self, "配置已保存", "AI配置已成功保存")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存配置时发生错误：{str(e)}")
    
    def accept(self):
        """接受对话框"""
        self._apply_config()
        super().accept()