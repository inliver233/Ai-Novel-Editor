"""
大纲AI配置组件
专门用于配置大纲分析的AI参数，支持使用独立API或共享现有配置
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                            QCheckBox, QTextEdit, QPushButton, QTabWidget, QWidget,
                            QGroupBox, QButtonGroup, QRadioButton, QMessageBox,
                            QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import logging
from typing import Dict, Any, Optional

from core.outline_prompts import OutlinePromptManager, PromptType


logger = logging.getLogger(__name__)


class OutlineAIConfigWidget(QWidget):
    """大纲AI配置组件（嵌入式）"""
    
    configChanged = pyqtSignal(dict)  # 配置变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompt_manager = OutlinePromptManager()
        self._init_ui()
        self._load_default_config()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # API使用模式
        mode_group = QGroupBox("API使用模式")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_group = QButtonGroup()
        
        self.shared_mode = QRadioButton("使用共享AI配置（推荐）")
        self.shared_mode.setToolTip("使用与智能补全、RAG等功能相同的AI配置")
        self.shared_mode.setChecked(True)
        self.mode_group.addButton(self.shared_mode, 0)
        mode_layout.addWidget(self.shared_mode)
        
        self.independent_mode = QRadioButton("使用独立API配置")
        self.independent_mode.setToolTip("为大纲分析单独配置API，可使用不同的模型")
        self.mode_group.addButton(self.independent_mode, 1)
        mode_layout.addWidget(self.independent_mode)
        
        layout.addWidget(mode_group)
        
        # 独立配置区域
        self.independent_config_frame = self._create_independent_config()
        layout.addWidget(self.independent_config_frame)
        
        # 大纲分析设置
        analysis_group = QGroupBox("分析设置")
        analysis_layout = QFormLayout(analysis_group)
        
        self.auto_analyze_check = QCheckBox("导入大纲时自动分析")
        analysis_layout.addRow(self.auto_analyze_check)
        
        self.analysis_depth_combo = QComboBox()
        self.analysis_depth_combo.addItems(["basic", "standard", "detailed"])
        self.analysis_depth_combo.setCurrentText("standard")
        analysis_layout.addRow("分析深度:", self.analysis_depth_combo)
        
        self.confidence_threshold_spin = QDoubleSpinBox()
        self.confidence_threshold_spin.setRange(0.0, 1.0)
        self.confidence_threshold_spin.setSingleStep(0.1)
        self.confidence_threshold_spin.setValue(0.7)
        analysis_layout.addRow("置信度阈值:", self.confidence_threshold_spin)
        
        layout.addWidget(analysis_group)
        
        # 连接信号
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        self.mode_group.buttonClicked.connect(self._emit_config_changed)
        self.auto_analyze_check.toggled.connect(self._emit_config_changed)
        self.analysis_depth_combo.currentTextChanged.connect(self._emit_config_changed)
        self.confidence_threshold_spin.valueChanged.connect(self._emit_config_changed)
        
        # 初始状态
        self._on_mode_changed()
    
    def _create_independent_config(self) -> QWidget:
        """创建独立配置区域"""
        frame = QGroupBox("独立API配置")
        layout = QFormLayout(frame)
        
        # AI提供商选择
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "custom"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.provider_combo.currentTextChanged.connect(self._emit_config_changed)
        layout.addRow("AI提供商:", self.provider_combo)
        
        # API配置
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("输入API密钥")
        self.api_key_edit.textChanged.connect(self._emit_config_changed)
        layout.addRow("API密钥:", self.api_key_edit)
        
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("API基础URL（可选）")
        self.base_url_edit.textChanged.connect(self._emit_config_changed)
        layout.addRow("基础URL:", self.base_url_edit)
        
        # 模型选择
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.currentTextChanged.connect(self._emit_config_changed)
        layout.addRow("模型:", self.model_combo)
        
        # 参数配置
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.valueChanged.connect(self._emit_config_changed)
        layout.addRow("Temperature:", self.temperature_spin)
        
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 8000)
        self.max_tokens_spin.setValue(2000)
        self.max_tokens_spin.valueChanged.connect(self._emit_config_changed)
        layout.addRow("最大Token数:", self.max_tokens_spin)
        
        return frame
    
    def _load_default_config(self):
        """加载默认配置"""
        # 设置默认值
        self.shared_mode.setChecked(True)
        self.provider_combo.setCurrentText("openai")
        self.temperature_spin.setValue(0.7)
        self.max_tokens_spin.setValue(2000)
        self.auto_analyze_check.setChecked(False)
        self.analysis_depth_combo.setCurrentText("standard")
        self.confidence_threshold_spin.setValue(0.7)
        
        # 更新模型选项
        self._on_provider_changed()
    
    def _on_mode_changed(self):
        """API使用模式变化"""
        use_shared = self.shared_mode.isChecked()
        self.independent_config_frame.setVisible(not use_shared)
    
    def _on_provider_changed(self):
        """AI提供商变化时更新模型选项"""
        provider = self.provider_combo.currentText()
        self.model_combo.clear()
        
        if provider == "openai":
            models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"]
        elif provider == "anthropic":
            models = ["claude-3-haiku", "claude-3-sonnet", "claude-3-opus"]
        else:
            models = ["custom-model"]
        
        self.model_combo.addItems(models)
    
    def _emit_config_changed(self):
        """发出配置变化信号"""
        config = self.get_config()
        self.configChanged.emit(config)
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "outline": {
                "use_shared_api": self.shared_mode.isChecked(),
                "api": {
                    "provider": self.provider_combo.currentText(),
                    "api_key": self.api_key_edit.text(),
                    "base_url": self.base_url_edit.text(),
                    "model": self.model_combo.currentText(),
                    "temperature": self.temperature_spin.value(),
                    "max_tokens": self.max_tokens_spin.value()
                },
                "analysis": {
                    "auto_analyze": self.auto_analyze_check.isChecked(),
                    "analysis_depth": self.analysis_depth_combo.currentText(),
                    "confidence_threshold": self.confidence_threshold_spin.value()
                }
            }
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        outline_config = config.get("outline", {})
        
        # API模式
        use_shared = outline_config.get("use_shared_api", True)
        if use_shared:
            self.shared_mode.setChecked(True)
        else:
            self.independent_mode.setChecked(True)
        
        # 独立API配置
        api_config = outline_config.get("api", {})
        if api_config:
            self.provider_combo.setCurrentText(api_config.get("provider", "openai"))
            self.api_key_edit.setText(api_config.get("api_key", ""))
            self.base_url_edit.setText(api_config.get("base_url", ""))
            self.model_combo.setCurrentText(api_config.get("model", ""))
            self.temperature_spin.setValue(api_config.get("temperature", 0.7))
            self.max_tokens_spin.setValue(api_config.get("max_tokens", 2000))
        
        # 分析设置
        analysis_config = outline_config.get("analysis", {})
        self.auto_analyze_check.setChecked(analysis_config.get("auto_analyze", False))
        self.analysis_depth_combo.setCurrentText(analysis_config.get("analysis_depth", "standard"))
        self.confidence_threshold_spin.setValue(analysis_config.get("confidence_threshold", 0.7))
        
        # 触发模式变化
        self._on_mode_changed()


class OutlineAIConfigDialog(QDialog):
    """大纲AI配置对话框（独立版本）"""
    
    configSaved = pyqtSignal(dict)  # 配置保存信号
    
    def __init__(self, parent=None, current_config: Dict[str, Any] = None, shared_ai_config: Dict[str, Any] = None):
        super().__init__(parent)
        self.current_config = current_config or {}
        self.shared_ai_config = shared_ai_config or {}
        
        self.setWindowTitle("大纲AI配置")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self._init_ui()
        self._load_config()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 配置组件
        self.config_widget = OutlineAIConfigWidget()
        layout.addWidget(self.config_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self._save_config)
        self.save_btn.setDefault(True)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
    
    def _load_config(self):
        """加载配置"""
        self.config_widget.set_config(self.current_config)
    
    def _test_connection(self):
        """测试API连接"""
        # TODO: 实现API测试
        QMessageBox.information(self, "测试", "API连接测试功能待实现")
    
    def _save_config(self):
        """保存配置"""
        try:
            config = self.config_widget.get_config()
            self.configSaved.emit(config)
            self.accept()
        except Exception as e:
            logger.error(f"保存大纲AI配置失败: {e}")
            QMessageBox.critical(self, "保存失败", f"配置保存失败：{str(e)}")