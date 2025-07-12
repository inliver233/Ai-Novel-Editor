"""
统一AI配置对话框
将API配置、补全设置和连接测试整合到一个界面中
"""

import logging
import json
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout,
    QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QLabel, QGroupBox, QCheckBox, QSlider, QFrame,
    QProgressBar, QTextBrowser, QPlainTextEdit, QSplitter, QMessageBox,
    QWidget, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QTextCharFormat, QColor

from core.ai_client import AIClient, AIConfig, AIProvider, AIClientError
from core.config import Config
from .rag_config_widget import RAGConfigWidget
from .enhanced_prompt_config_widget import EnhancedPromptConfigWidget

logger = logging.getLogger(__name__)


class APITestWorker(QThread):
    """API连接测试工作线程"""
    
    testStarted = pyqtSignal()
    testProgress = pyqtSignal(str)  # 进度信息
    testCompleted = pyqtSignal(bool, str)  # 成功/失败, 结果信息
    
    def __init__(self, config_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config_data = config_data
        
    def run(self):
        """执行API测试"""
        try:
            self.testStarted.emit()
            self.testProgress.emit("正在验证配置参数...")
            
            # 检查必要参数
            if not self.config_data.get('api_key', '').strip():
                self.testCompleted.emit(False, "API密钥不能为空")
                return
                
            if not self.config_data.get('model', '').strip():
                self.testCompleted.emit(False, "模型名称不能为空")
                return
                
            # 检查API地址（自定义API必须有地址）
            provider_name = self.config_data.get('provider', 'OpenAI')
            api_base = self.config_data.get('api_base', '').strip()
            
            if provider_name == '自定义API' and not api_base:
                self.testCompleted.emit(False, "自定义API必须设置API地址")
                return
            
            self.testProgress.emit("正在创建AI客户端...")
            
            # 创建AI配置
            provider_mapping = {
                'OpenAI': AIProvider.OPENAI,
                'Claude (Anthropic)': AIProvider.CLAUDE,
                '通义千问 (阿里云)': AIProvider.CUSTOM,
                '智谱AI': AIProvider.CUSTOM,
                'DeepSeek': AIProvider.CUSTOM,
                'Groq': AIProvider.CUSTOM,
                'Ollama (本地)': AIProvider.CUSTOM,
                '自定义API': AIProvider.CUSTOM
            }
            
            # 如果不在预定义列表中，默认为自定义
            provider = provider_mapping.get(provider_name, AIProvider.CUSTOM)
            
            # 根据服务商设置正确的endpoint URL
            endpoint_url = api_base
            if not endpoint_url and provider_name != '自定义API':
                endpoint_mapping = {
                    'OpenAI': 'https://api.openai.com/v1/chat/completions',
                    'Claude (Anthropic)': 'https://api.anthropic.com/v1/messages',
                    '通义千问 (阿里云)': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
                    '智谱AI': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                    'DeepSeek': 'https://api.deepseek.com/chat/completions',
                    'Groq': 'https://api.groq.com/openai/v1/chat/completions',
                    'Ollama (本地)': 'http://localhost:11434/v1/chat/completions'
                }
                endpoint_url = endpoint_mapping.get(provider_name, '')
            
            config = AIConfig(
                provider=provider,
                model=self.config_data['model'],
                endpoint_url=endpoint_url,
                temperature=self.config_data.get('temperature', 0.8),
                max_tokens=100,  # 测试时使用较小的token数
                timeout=15  # 缩短超时时间
            )
            
            # 设置API密钥
            api_key = self.config_data.get('api_key', '')
            if api_key:
                config.set_api_key(api_key)
            
            self.testProgress.emit("正在连接API服务...")
            
            # 创建AI客户端并测试
            client = AIClient(config)
            
            # 发送测试消息
            test_prompts = [
                "Hello, please respond with 'OK'.",
                "你好，请回复'确认'。",
                "Test message for AI connection."
            ]
            
            self.testProgress.emit("正在发送测试消息...")
            
            success = False
            response_text = ""
            
            for i, test_prompt in enumerate(test_prompts):
                try:
                    self.testProgress.emit(f"尝试测试消息 {i+1}/{len(test_prompts)}...")
                    response = client.complete(test_prompt, max_tokens=50)
                    
                    if response and len(response.strip()) > 0:
                        success = True
                        response_text = response
                        break
                    else:
                        continue  # 尝试下一个测试消息
                        
                except Exception as e:
                    if i == len(test_prompts) - 1:  # 最后一次尝试
                        raise e
                    continue  # 尝试下一个测试消息
            
            if success:
                self.testCompleted.emit(True, 
                    f"✅ 连接测试成功！\n"
                    f"📡 服务商: {provider_name}\n"
                    f"🤖 模型: {config.model}\n"
                    f"💬 测试响应: {response_text[:100]}..."
                )
            else:
                self.testCompleted.emit(False, "API响应为空或无效，请检查模型名称和配置")
                
        except AIClientError as e:
            self.testCompleted.emit(False, f"AI客户端错误: {str(e)}")
        except Exception as e:
            self.testCompleted.emit(False, f"连接测试失败: {str(e)}")


class UnifiedAPIConfigWidget(QFrame):
    """统一的API配置组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_worker = None
        self._provider_presets = {}  # 先初始化为空字典
        self._load_provider_presets()  # 加载预设配置
        self._init_ui()  # 然后创建UI
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 配置方案管理组
        self._create_config_schemes(layout)
        
        # API服务商配置组
        self._create_provider_config(layout)
        
        # API参数配置组
        self._create_api_params_config(layout)
        
        # 连接测试组
        self._create_connection_test(layout)
        
        # 在所有UI组件创建完成后连接信号和加载数据
        self._setup_signals_and_load_data()
    
    def _setup_signals_and_load_data(self):
        """设置信号连接并加载数据"""
        # 连接配置方案变化信号
        if hasattr(self, '_scheme_combo'):
            self._scheme_combo.currentTextChanged.connect(self._on_scheme_changed)
        
        # 连接服务商变化信号
        if hasattr(self, '_provider_combo'):
            self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        
        # 加载已保存的方案
        self._load_schemes()
    
    def _create_config_schemes(self, layout):
        """创建配置方案管理"""
        group = QGroupBox("配置方案")
        group_layout = QHBoxLayout(group)
        
        # 方案选择
        scheme_layout = QHBoxLayout()
        scheme_layout.addWidget(QLabel("方案:"))
        
        self._scheme_combo = QComboBox()
        self._scheme_combo.setEditable(True)
        self._scheme_combo.setPlaceholderText("选择或输入新方案名称")
        scheme_layout.addWidget(self._scheme_combo)
        
        # 保存方案按钮
        save_scheme_btn = QPushButton("保存方案")
        save_scheme_btn.clicked.connect(self._save_current_scheme)
        scheme_layout.addWidget(save_scheme_btn)
        
        # 删除方案按钮
        delete_scheme_btn = QPushButton("删除方案")
        delete_scheme_btn.clicked.connect(self._delete_current_scheme)
        scheme_layout.addWidget(delete_scheme_btn)
        
        # 导入/导出按钮
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._import_schemes)
        scheme_layout.addWidget(import_btn)
        
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_schemes)
        scheme_layout.addWidget(export_btn)
        
        group_layout.addLayout(scheme_layout)
        layout.addWidget(group)
        
    def _create_provider_config(self, layout):
        """创建服务商配置"""
        group = QGroupBox("API服务商")
        group_layout = QFormLayout(group)
        
        # 服务商选择
        self._provider_combo = QComboBox()
        self._provider_combo.addItems([
            "OpenAI",
            "Claude (Anthropic)", 
            "通义千问 (阿里云)",
            "智谱AI",
            "DeepSeek",
            "Groq",
            "Ollama (本地)",
            "自定义API"
        ])
        group_layout.addRow("服务商:", self._provider_combo)
        
        # API密钥
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("请输入API密钥")
        
        # 显示/隐藏密钥按钮
        key_layout = QHBoxLayout()
        key_layout.addWidget(self._api_key_edit)
        
        self._show_key_btn = QPushButton("👁")
        self._show_key_btn.setFixedSize(30, 30)
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_layout.addWidget(self._show_key_btn)
        
        group_layout.addRow("API密钥:", key_layout)
        
        # API基础URL
        self._api_base_edit = QLineEdit()
        self._api_base_edit.setPlaceholderText("API基础URL (如 https://api.openai.com/v1)")
        group_layout.addRow("API地址:", self._api_base_edit)
        
        # 模型名称
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setPlaceholderText("选择或输入模型名称")
        group_layout.addRow("模型:", self._model_combo)
        
        layout.addWidget(group)
        
    def _create_api_params_config(self, layout):
        """创建API参数配置"""
        group = QGroupBox("模型参数")
        group_layout = QFormLayout(group)
        
        # Temperature
        temp_layout = QHBoxLayout()
        self._temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self._temperature_slider.setRange(0, 100)
        self._temperature_slider.setValue(80)
        self._temperature_label = QLabel("0.8")
        
        temp_layout.addWidget(self._temperature_slider)
        temp_layout.addWidget(self._temperature_label)
        
        self._temperature_slider.valueChanged.connect(
            lambda v: self._temperature_label.setText(f"{v/100:.1f}")
        )
        
        group_layout.addRow("创造性 (Temperature):", temp_layout)
        
        # Top-p
        top_p_layout = QHBoxLayout()
        self._top_p_slider = QSlider(Qt.Orientation.Horizontal)
        self._top_p_slider.setRange(0, 100)
        self._top_p_slider.setValue(90)
        self._top_p_label = QLabel("0.9")
        
        top_p_layout.addWidget(self._top_p_slider)
        top_p_layout.addWidget(self._top_p_label)
        
        self._top_p_slider.valueChanged.connect(
            lambda v: self._top_p_label.setText(f"{v/100:.1f}")
        )
        
        group_layout.addRow("多样性 (Top-p):", top_p_layout)
        
        # Max Tokens
        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(50, 4000)
        self._max_tokens_spin.setValue(2000)
        self._max_tokens_spin.setSuffix(" tokens")
        group_layout.addRow("最大长度:", self._max_tokens_spin)
        
        # Timeout
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 600)  # 5秒到10分钟
        self._timeout_spin.setValue(30)
        self._timeout_spin.setSuffix(" 秒")
        self._timeout_spin.setMinimumWidth(120)  # 确保有足够宽度显示3位数
        group_layout.addRow("请求超时:", self._timeout_spin)
        
        layout.addWidget(group)
        
    def _create_connection_test(self, layout):
        """创建连接测试"""
        group = QGroupBox("连接测试")
        group_layout = QVBoxLayout(group)
        
        # 测试按钮和进度
        test_header_layout = QHBoxLayout()
        
        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._test_connection)
        test_header_layout.addWidget(self._test_btn)
        
        self._test_progress = QProgressBar()
        self._test_progress.setVisible(False)
        test_header_layout.addWidget(self._test_progress)
        
        test_header_layout.addStretch()
        group_layout.addLayout(test_header_layout)
        
        # 测试结果显示
        self._test_result_browser = QTextBrowser()
        self._test_result_browser.setMaximumHeight(120)
        self._test_result_browser.setPlainText("点击\"测试连接\"验证API配置是否正确")
        group_layout.addWidget(self._test_result_browser)
        
        layout.addWidget(group)
        
    def _load_provider_presets(self):
        """加载服务商预设配置"""
        self._provider_presets = {
            "OpenAI": {
                "api_base": "https://api.openai.com/v1",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo"],
                "help": "OpenAI官方API，需要OpenAI账户和API密钥"
            },
            "Claude (Anthropic)": {
                "api_base": "https://api.anthropic.com",
                "models": ["claude-3-5-sonnet-20241022", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
                "help": "Anthropic Claude API，需要Anthropic账户和API密钥"
            },
            "通义千问 (阿里云)": {
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "models": ["qwen-plus", "qwen-turbo", "qwen-max"],
                "help": "阿里云通义千问API，需要阿里云账户和API密钥"
            },
            "智谱AI": {
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
                "models": ["glm-4", "glm-3-turbo"],
                "help": "智谱AI API，需要智谱AI账户和API密钥"
            },
            "DeepSeek": {
                "api_base": "https://api.deepseek.com",
                "models": ["deepseek-chat", "deepseek-coder"],
                "help": "DeepSeek API，需要DeepSeek账户和API密钥"
            },
            "Groq": {
                "api_base": "https://api.groq.com/openai/v1",
                "models": ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768"],
                "help": "Groq API，需要Groq账户和API密钥，高速推理"
            },
            "Ollama (本地)": {
                "api_base": "http://localhost:11434/v1",
                "models": ["llama3.2", "qwen2.5", "gemma2"],
                "help": "本地Ollama服务，需要先安装并启动Ollama"
            },
            "自定义API": {
                "api_base": "",
                "models": [],
                "help": "兼容OpenAI格式的自定义API端点"
            }
        }
        
    def _on_provider_changed(self, provider: str):
        """服务商变化处理"""
        if not hasattr(self, '_provider_presets') or not self._provider_presets:
            logger.warning("Provider presets not loaded yet")
            return
            
        if provider in self._provider_presets:
            preset = self._provider_presets[provider]
            
            # 设置API基础URL
            if hasattr(self, '_api_base_edit'):
                self._api_base_edit.setText(preset["api_base"])
            
            # 更新模型列表
            if hasattr(self, '_model_combo'):
                self._model_combo.clear()
                self._model_combo.addItems(preset["models"])
                if preset["models"]:
                    self._model_combo.setCurrentIndex(0)
                
            # 更新帮助信息
            if hasattr(self, '_test_result_browser'):
                help_text = f"<b>{provider}</b><br>{preset['help']}"
                self._test_result_browser.setHtml(help_text)
            
    def _toggle_key_visibility(self, checked):
        """切换密钥显示/隐藏"""
        if checked:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("🙈")
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("👁")
            
    def _test_connection(self):
        """测试API连接"""
        if self._test_worker and self._test_worker.isRunning():
            return
            
        # 获取当前配置
        config_data = self.get_config()
        
        # 验证必要参数
        if not config_data['api_key'].strip():
            self._show_test_result(False, "请先输入API密钥")
            return
            
        if not config_data['model'].strip():
            self._show_test_result(False, "请先选择或输入模型名称")
            return
            
        # 开始测试
        self._test_btn.setEnabled(False)
        self._test_progress.setVisible(True)
        self._test_progress.setRange(0, 0)  # 不确定进度
        
        # 创建测试工作线程
        self._test_worker = APITestWorker(config_data, self)
        self._test_worker.testStarted.connect(self._on_test_started)
        self._test_worker.testProgress.connect(self._on_test_progress)
        self._test_worker.testCompleted.connect(self._on_test_completed)
        
        self._test_worker.start()
        
    @pyqtSlot()
    def _on_test_started(self):
        """测试开始"""
        self._test_result_browser.setPlainText("开始连接测试...")
        
    @pyqtSlot(str)
    def _on_test_progress(self, message):
        """测试进度更新"""
        current = self._test_result_browser.toPlainText()
        self._test_result_browser.setPlainText(current + "\n" + message)
        
    @pyqtSlot(bool, str)
    def _on_test_completed(self, success, message):
        """测试完成"""
        self._test_btn.setEnabled(True)
        self._test_progress.setVisible(False)
        
        self._show_test_result(success, message)
        
    def _show_test_result(self, success: bool, message: str):
        """显示测试结果"""
        if success:
            color = "#1a7f37"
            icon = "✅"
        else:
            color = "#d1242f"
            icon = "❌"
            
        result_html = f"""
        <div style="color: {color}; font-weight: bold;">
            {icon} {message}
        </div>
        """
        
        self._test_result_browser.setHtml(result_html)
        
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "provider": self._provider_combo.currentText(),
            "api_key": self._api_key_edit.text(),
            "api_base": self._api_base_edit.text(),
            "model": self._model_combo.currentText(),
            "temperature": self._temperature_slider.value() / 100,
            "top_p": self._top_p_slider.value() / 100,
            "max_tokens": self._max_tokens_spin.value(),
            "timeout": self._timeout_spin.value()
        }
        
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        # 检查必要的组件是否存在
        if not hasattr(self, '_provider_combo') or not self._provider_combo:
            logger.error("Provider combo not initialized")
            return
            
        # 设置服务商
        provider = config.get("provider", "OpenAI")
        index = self._provider_combo.findText(provider)
        if index >= 0:
            self._provider_combo.setCurrentIndex(index)
        
        # 设置其他配置
        if hasattr(self, '_api_key_edit'):
            self._api_key_edit.setText(config.get("api_key", ""))
        if hasattr(self, '_api_base_edit'):
            self._api_base_edit.setText(config.get("api_base", ""))
        
        # 设置模型（先触发provider变化，再设置模型）
        model = config.get("model", "")
        if model and hasattr(self, '_model_combo'):
            QTimer.singleShot(100, lambda: self._set_model_delayed(model))
            
        if hasattr(self, '_temperature_slider'):
            self._temperature_slider.setValue(int(config.get("temperature", 0.8) * 100))
        if hasattr(self, '_top_p_slider'):
            self._top_p_slider.setValue(int(config.get("top_p", 0.9) * 100))
        if hasattr(self, '_max_tokens_spin'):
            self._max_tokens_spin.setValue(config.get("max_tokens", 2000))
        if hasattr(self, '_timeout_spin'):
            self._timeout_spin.setValue(config.get("timeout", 30))
        
    def _set_model_delayed(self, model: str):
        """延迟设置模型（等待模型列表更新）"""
        self._model_combo.setCurrentText(model)
    
    def _save_current_scheme(self):
        """保存当前配置方案"""
        scheme_name = self._scheme_combo.currentText().strip()
        if not scheme_name:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "警告", "请输入方案名称")
            return
        
        # 获取当前配置
        current_config = self.get_config()
        
        # 加载现有方案
        schemes = self._load_saved_schemes()
        
        # 保存新方案
        schemes[scheme_name] = current_config
        
        # 写入配置文件
        self._save_schemes_to_file(schemes)
        
        # 更新下拉列表
        self._update_scheme_combo(schemes, scheme_name)
        
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "成功", f"配置方案 '{scheme_name}' 已保存")
        logger.info(f"配置方案已保存: {scheme_name}")
    
    def _delete_current_scheme(self):
        """删除当前配置方案"""
        scheme_name = self._scheme_combo.currentText().strip()
        if not scheme_name:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "警告", "请选择要删除的方案")
            return
        
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除配置方案 '{scheme_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 加载现有方案
            schemes = self._load_saved_schemes()
            
            if scheme_name in schemes:
                del schemes[scheme_name]
                
                # 保存更新后的方案
                self._save_schemes_to_file(schemes)
                
                # 更新下拉列表
                self._update_scheme_combo(schemes)
                
                QMessageBox.information(self, "成功", f"配置方案 '{scheme_name}' 已删除")
                logger.info(f"配置方案已删除: {scheme_name}")
            else:
                QMessageBox.warning(self, "错误", f"配置方案 '{scheme_name}' 不存在")
    
    def _load_schemes(self):
        """加载保存的配置方案"""
        schemes = self._load_saved_schemes()
        self._update_scheme_combo(schemes)
        logger.debug(f"已加载 {len(schemes)} 个配置方案")
    
    def _on_scheme_changed(self, scheme_name: str):
        """配置方案选择变化处理"""
        if not scheme_name.strip():
            return
        
        try:
            schemes = self._load_saved_schemes()
            if scheme_name in schemes:
                # 加载选中的方案配置
                scheme_config = schemes[scheme_name]
                self.set_config(scheme_config)
                logger.info(f"已加载配置方案: {scheme_name}")
        except Exception as e:
            logger.error(f"加载配置方案失败: {e}")
    
    def _import_schemes(self):
        """导入配置方案"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import json
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置方案", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_schemes = json.load(f)
                
                if not isinstance(imported_schemes, dict):
                    QMessageBox.warning(self, "错误", "导入文件格式不正确")
                    return
                
                # 加载现有方案
                current_schemes = self._load_saved_schemes()
                
                # 合并方案
                merged_count = 0
                for name, config in imported_schemes.items():
                    if isinstance(config, dict):
                        current_schemes[name] = config
                        merged_count += 1
                
                # 保存合并后的方案
                self._save_schemes_to_file(current_schemes)
                
                # 更新界面
                self._update_scheme_combo(current_schemes)
                
                QMessageBox.information(
                    self, "导入成功", 
                    f"成功导入 {merged_count} 个配置方案"
                )
                logger.info(f"导入了 {merged_count} 个配置方案")
                
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入配置方案失败：{str(e)}")
                logger.error(f"导入配置方案失败: {e}")
    
    def _export_schemes(self):
        """导出配置方案"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import json
        
        schemes = self._load_saved_schemes()
        if not schemes:
            QMessageBox.information(self, "提示", "没有可导出的配置方案")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置方案", "ai_config_schemes.json", 
            "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(schemes, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(
                    self, "导出成功", 
                    f"成功导出 {len(schemes)} 个配置方案到\n{file_path}"
                )
                logger.info(f"导出了 {len(schemes)} 个配置方案到 {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出配置方案失败：{str(e)}")
                logger.error(f"导出配置方案失败: {e}")
    
    def _load_saved_schemes(self) -> Dict[str, Any]:
        """从文件加载保存的配置方案"""
        import json
        import os
        
        schemes_file = self._get_schemes_file_path()
        
        if os.path.exists(schemes_file):
            try:
                with open(schemes_file, 'r', encoding='utf-8') as f:
                    schemes = json.load(f)
                return schemes if isinstance(schemes, dict) else {}
            except Exception as e:
                logger.warning(f"加载配置方案失败: {e}")
        
        return {}
    
    def _save_schemes_to_file(self, schemes: Dict[str, Any]):
        """保存配置方案到文件"""
        import json
        import os
        
        schemes_file = self._get_schemes_file_path()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(schemes_file), exist_ok=True)
        
        try:
            with open(schemes_file, 'w', encoding='utf-8') as f:
                json.dump(schemes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置方案失败: {e}")
            raise
    
    def _get_schemes_file_path(self) -> str:
        """获取配置方案文件路径"""
        import os
        from pathlib import Path
        
        # 使用用户配置目录
        config_dir = Path.home() / ".config" / "ai-novel-editor"
        return str(config_dir / "ai_config_schemes.json")
    
    def _update_scheme_combo(self, schemes: Dict[str, Any], selected_scheme: str = None):
        """更新配置方案下拉列表"""
        self._scheme_combo.clear()
        
        # 添加现有方案
        scheme_names = list(schemes.keys())
        scheme_names.sort()  # 按字母顺序排序
        
        self._scheme_combo.addItems(scheme_names)
        
        # 设置选中项
        if selected_scheme and selected_scheme in scheme_names:
            self._scheme_combo.setCurrentText(selected_scheme)
        elif scheme_names:
            self._scheme_combo.setCurrentText(scheme_names[0])


class CompletionSettingsWidget(QFrame):
    """补全设置组件"""
    
    # 信号
    completionEnabledChanged = pyqtSignal(bool)
    autoTriggerEnabledChanged = pyqtSignal(bool)
    triggerDelayChanged = pyqtSignal(int)
    completionModeChanged = pyqtSignal(str)
    contextModeChanged = pyqtSignal(str)  # 新增上下文模式信号
    punctuationAssistChanged = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 基本控制
        self._create_basic_controls(layout)
        
        # 补全模式
        self._create_completion_modes(layout)
        
        # 触发设置
        self._create_trigger_settings(layout)
        
        # 高级设置
        self._create_advanced_settings(layout)
        
    def _create_basic_controls(self, layout):
        """创建基本控制"""
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
        
        # 上下文模式选择
        context_layout = QHBoxLayout()
        context_layout.addWidget(QLabel("上下文:"))
        
        self.context_mode = QComboBox()
        self.context_mode.addItems([
            "快速模式 (<2K tokens)",
            "平衡模式 (2-8K tokens)",
            "全局模式 (200K+ tokens)"
        ])
        self.context_mode.setCurrentIndex(1)  # 默认平衡模式
        self.context_mode.currentTextChanged.connect(self._on_context_mode_changed)
        context_layout.addWidget(self.context_mode)
        
        group_layout.addLayout(context_layout)
        
        # 模式说明
        self.mode_description = QLabel("自动AI补全：自动识别并触发AI补全")
        self.mode_description.setStyleSheet("color: #cccccc; font-size: 11px;")
        self.mode_description.setWordWrap(True)
        group_layout.addWidget(self.mode_description)
        
        # 上下文模式说明
        self.context_description = QLabel("平衡模式：在效果与成本间取得平衡，适合日常写作")
        self.context_description.setStyleSheet("color: #cccccc; font-size: 11px;")
        self.context_description.setWordWrap(True)
        group_layout.addWidget(self.context_description)
        
        layout.addWidget(group)
        
    def _create_trigger_settings(self, layout):
        """创建触发设置"""
        group = QGroupBox("触发设置")
        group_layout = QFormLayout(group)
        
        # 触发延迟
        delay_layout = QHBoxLayout()
        self.trigger_delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.trigger_delay_slider.setRange(100, 2000)
        self.trigger_delay_slider.setValue(500)
        self.trigger_delay_slider.valueChanged.connect(self._on_delay_changed)
        
        self.delay_label = QLabel("500ms")
        delay_layout.addWidget(self.trigger_delay_slider)
        delay_layout.addWidget(self.delay_label)
        
        group_layout.addRow("触发延迟:", delay_layout)
        
        # 最小字符数
        self.min_chars_spin = QSpinBox()
        self.min_chars_spin.setRange(1, 10)
        self.min_chars_spin.setValue(3)
        group_layout.addRow("最小字符数:", self.min_chars_spin)
        
        layout.addWidget(group)
        
    def _create_advanced_settings(self, layout):
        """创建高级设置"""
        group = QGroupBox("高级设置")
        group_layout = QFormLayout(group)
        
        # 上下文长度
        self.context_length = QSpinBox()
        self.context_length.setRange(100, 1000)
        self.context_length.setValue(500)
        self.context_length.setSuffix(" 字符")
        group_layout.addRow("上下文长度:", self.context_length)
        
        # 补全长度限制
        self.completion_length = QSpinBox()
        self.completion_length.setRange(20, 200)
        self.completion_length.setValue(80)
        self.completion_length.setSuffix(" 字符")
        group_layout.addRow("补全长度限制:", self.completion_length)
        
        # 流式响应
        self.stream_response = QCheckBox("启用流式响应")
        self.stream_response.setChecked(True)
        group_layout.addRow("响应模式:", self.stream_response)
        
        # 显示置信度
        self.show_confidence = QCheckBox("显示AI置信度")
        self.show_confidence.setChecked(True)
        group_layout.addRow("界面选项:", self.show_confidence)
        
        layout.addWidget(group)
        
    def _on_delay_changed(self, value):
        """触发延迟改变"""
        self.delay_label.setText(f"{value}ms")
        self.triggerDelayChanged.emit(value)
        
    def _on_context_mode_changed(self, mode_text):
        """上下文模式改变"""
        context_descriptions = {
            "快速模式 (<2K tokens)": "快速模式：轻量级上下文，最快响应，适合简单补全",
            "平衡模式 (2-8K tokens)": "平衡模式：在效果与成本间取得平衡，适合日常写作",
            "全局模式 (200K+ tokens)": "全局模式：完整项目上下文，最佳效果，适合复杂场景"
        }
        
        self.context_description.setText(context_descriptions.get(mode_text, ""))
        
        # 映射到内部模式名称
        context_mapping = {
            "快速模式 (<2K tokens)": "fast",
            "平衡模式 (2-8K tokens)": "balanced", 
            "全局模式 (200K+ tokens)": "full"
        }
        
        context_mode = context_mapping.get(mode_text, "balanced")
        self.contextModeChanged.emit(context_mode)
        
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
        
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            'completion_enabled': self.completion_enabled.isChecked(),
            'auto_trigger_enabled': self.auto_trigger_enabled.isChecked(),
            'punctuation_assist': self.punctuation_assist.isChecked(),
            'trigger_delay': self.trigger_delay_slider.value(),
            'completion_mode': self.completion_mode.currentText(),
            'context_mode': self.context_mode.currentText(),  # 新增上下文模式
            'min_chars': self.min_chars_spin.value(),
            'context_length': self.context_length.value(),
            'completion_length': self.completion_length.value(),
            'stream_response': self.stream_response.isChecked(),
            'show_confidence': self.show_confidence.isChecked()
        }
        
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        self.completion_enabled.setChecked(settings.get('completion_enabled', True))
        self.auto_trigger_enabled.setChecked(settings.get('auto_trigger_enabled', True))
        self.punctuation_assist.setChecked(settings.get('punctuation_assist', True))
        self.trigger_delay_slider.setValue(settings.get('trigger_delay', 500))
        
        mode = settings.get('completion_mode', '自动AI补全')
        index = self.completion_mode.findText(mode)
        if index >= 0:
            self.completion_mode.setCurrentIndex(index)
        
        # 设置上下文模式
        context_mode = settings.get('context_mode', '平衡模式 (2-8K tokens)')
        context_index = self.context_mode.findText(context_mode)
        if context_index >= 0:
            self.context_mode.setCurrentIndex(context_index)
            
        self.min_chars_spin.setValue(settings.get('min_chars', 3))
        self.context_length.setValue(settings.get('context_length', 500))
        self.completion_length.setValue(settings.get('completion_length', 80))
        self.stream_response.setChecked(settings.get('stream_response', True))
        self.show_confidence.setChecked(settings.get('show_confidence', True))


class UnifiedAIConfigDialog(QDialog):
    """统一AI配置对话框"""
    
    configSaved = pyqtSignal(dict)  # 配置保存信号
    
    def __init__(self, parent=None, config: Optional[Config] = None):
        super().__init__(parent)
        
        self._config = config
        self._current_config = {}
        
        self._init_ui()
        self._load_config()
        
        # 设置对话框属性
        self.setModal(True)
        self.setMinimumSize(700, 700)
        self.resize(800, 800)
        self.setWindowTitle("AI配置中心")
        
        logger.debug("Unified AI config dialog initialized")
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建标签页
        self._tabs = QTabWidget()
        
        # API配置页
        self._api_widget = UnifiedAPIConfigWidget()
        self._tabs.addTab(self._api_widget, "🔧 API配置")
        
        # 补全设置页
        self._completion_widget = CompletionSettingsWidget()
        self._tabs.addTab(self._completion_widget, "⚡ 补全设置")
        
        # RAG配置页
        self._rag_widget = RAGConfigWidget()
        self._tabs.addTab(self._rag_widget, "🔍 RAG向量搜索")
        
        # 增强提示词配置页
        self._prompt_config_widget = EnhancedPromptConfigWidget()
        self._tabs.addTab(self._prompt_config_widget, "✨ 智能提示词")
        
        # 大纲AI配置页 (简化版本暂不提供)
        # TODO: 实现简化的大纲AI配置界面  
        # try:
        #     self._outline_widget = self._create_outline_widget()
        #     self._tabs.addTab(self._outline_widget, "📋 大纲AI")
        #     logger.debug("Successfully added outline AI config tab")
        # except Exception as e:
        #     logger.error(f"Failed to create outline AI config tab: {e}")
            
        # 提示词模板管理页
        try:
            self._template_widget = self._create_template_widget()
            self._tabs.addTab(self._template_widget, "✏️ 提示词模板")
            logger.debug("Successfully added template management tab")
        except Exception as e:
            logger.error(f"Failed to create template management widget: {e}")
            # 创建一个占位组件
            placeholder_widget = QWidget()
            placeholder_layout = QVBoxLayout(placeholder_widget)
            placeholder_layout.addWidget(QLabel("大纲AI配置暂时不可用"))
            self._outline_widget = placeholder_widget
            self._tabs.addTab(self._outline_widget, "📋 大纲AI")
        
        # 连接补全设置信号
        self._connect_completion_signals()
        
        layout.addWidget(self._tabs)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
        
    def _connect_completion_signals(self):
        """连接补全设置信号"""
        # 此方法暂时为空，可根据需要添加信号连接
        pass
        
    def _create_outline_widget(self):
        """创建大纲AI配置页面 (简化版本暂不实现)"""
        # TODO: 实现简化的大纲AI配置界面
        pass
    
    def _create_template_widget(self):
        """创建提示词模板管理页面"""
        try:
            widget = TemplateManagementWidget(self.parent())
            logger.debug("Successfully created TemplateManagementWidget")
            return widget
        except Exception as e:
            logger.error(f"Failed to create TemplateManagementWidget: {e}")
            raise
        
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)
        
        # 重置按钮
        reset_btn = QPushButton("重置默认")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        # 索引管理按钮
        index_btn = QPushButton("索引管理")
        index_btn.setToolTip("管理RAG向量索引")
        index_btn.clicked.connect(self._show_index_manager)
        layout.addWidget(index_btn)
        
        layout.addStretch()
        
        # 测试配置按钮
        test_btn = QPushButton("测试配置")
        test_btn.clicked.connect(self._test_full_config)
        layout.addWidget(test_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        # 保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._save_config)
        save_btn.setDefault(True)
        layout.addWidget(save_btn)
        
        return layout
        
    def _load_config(self):
        """加载配置"""
        if not self._config:
            return
            
        try:
            # 加载API配置
            ai_config = self._config.get_ai_config()
            if ai_config:
                # 映射内部标识到显示名称
                provider_reverse_mapping = {
                    'openai': 'OpenAI',
                    'claude': 'Claude (Anthropic)',
                    'qwen': '通义千问 (阿里云)',
                    'zhipu': '智谱AI',
                    'deepseek': 'DeepSeek',
                    'groq': 'Groq',
                    'ollama': 'Ollama (本地)',
                    'custom': '自定义API'
                }
                
                provider_internal = ai_config.provider.value if hasattr(ai_config.provider, 'value') else str(ai_config.provider)
                provider_display = provider_reverse_mapping.get(provider_internal, 'OpenAI')
                
                api_config = {
                    "provider": provider_display,
                    "api_key": ai_config.api_key,
                    "api_base": ai_config.endpoint_url or "",
                    "model": ai_config.model,
                    "temperature": ai_config.temperature,
                    "top_p": ai_config.top_p,
                    "max_tokens": ai_config.max_tokens,
                    "timeout": ai_config.timeout
                }
                self._api_widget.set_config(api_config)
                
            # 加载补全设置
            # 映射内部标识到显示名称
            mode_reverse_mapping = {
                'auto_ai': '自动AI补全',
                'manual_ai': '手动AI补全',
                'disabled': '禁用补全'
            }
            
            context_reverse_mapping = {
                'fast': '快速模式 (<2K tokens)',
                'balanced': '平衡模式 (2-8K tokens)',
                'full': '全局模式 (200K+ tokens)'
            }
            
            mode_internal = self._config.get('ai', 'completion_mode', 'auto_ai')
            mode_display = mode_reverse_mapping.get(mode_internal, '自动AI补全')
            
            context_internal = self._config.get('ai', 'context_mode', 'balanced')
            context_display = context_reverse_mapping.get(context_internal, '平衡模式 (2-8K tokens)')
            
            completion_settings = {
                'completion_enabled': self._config.get('ai', 'completion_enabled', True),
                'auto_trigger_enabled': self._config.get('ai', 'auto_suggestions', True),
                'punctuation_assist': self._config.get('ai', 'punctuation_assist', True),
                'trigger_delay': self._config.get('ai', 'completion_delay', 500),
                'completion_mode': mode_display,
                'context_mode': context_display,  # 新增上下文模式
                'min_chars': self._config.get('ai', 'min_chars', 3),
                'context_length': self._config.get('ai', 'context_length', 500),
                'completion_length': self._config.get('ai', 'completion_length', 80),
                'stream_response': self._config.get('ai', 'stream_response', True),
                'show_confidence': self._config.get('ai', 'show_confidence', True)
            }
            self._completion_widget.set_settings(completion_settings)
            
            # 加载RAG配置
            rag_config = self._config.get_section('rag')
            if not rag_config:
                rag_config = self._rag_widget._get_default_config()
            self._rag_widget.set_config(rag_config)
            
            # 加载增强提示词配置
            prompt_config = self._config.get_section('prompt')
            if not prompt_config:
                prompt_config = {
                    "context_mode": "balanced",
                    "style_tags": [],
                    "custom_prefix": "",
                    "preferred_length": 200,
                    "creativity": 0.7,
                    "context_length": 800,
                    "preset": "默认设置"
                }
            self._prompt_config_widget.set_config(prompt_config)
            
            # 加载大纲AI配置
            if hasattr(self, '_outline_widget') and hasattr(self._outline_widget, 'set_config'):
                try:
                    outline_config = self._config._config_data.get('outline', {})
                    if outline_config:
                        self._outline_widget.set_config(outline_config)
                        logger.debug("Successfully loaded outline AI config")
                except Exception as e:
                    logger.warning(f"Failed to load outline AI config: {e}")
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            
    def _save_config(self):
        """保存配置"""
        try:
            # 获取API配置
            api_config = self._api_widget.get_config()
            
            # 获取补全设置
            completion_settings = self._completion_widget.get_settings()
            
            # 获取RAG配置
            rag_config = self._rag_widget.get_config()
            
            # 获取增强提示词配置
            prompt_config = self._prompt_config_widget.get_config()
            
            # 获取大纲AI配置
            outline_config = {}
            if hasattr(self, '_outline_widget') and hasattr(self._outline_widget, 'get_config'):
                try:
                    outline_config = self._outline_widget.get_config()
                    logger.debug("Successfully got outline AI config")
                except Exception as e:
                    logger.warning(f"Failed to get outline AI config: {e}")
                    outline_config = {}
            
            # 合并配置
            full_config = {
                'api': api_config,
                'completion': completion_settings,
                'rag': rag_config,
                'prompt': prompt_config,
                'outline': outline_config
            }
            
            # 保存到配置文件
            if self._config:
                # 映射服务商名称到内部标识
                provider_mapping = {
                    'OpenAI': 'openai',
                    'Claude (Anthropic)': 'claude',
                    '通义千问 (阿里云)': 'qwen',
                    '智谱AI': 'zhipu',
                    'DeepSeek': 'deepseek',
                    'Groq': 'groq',
                    'Ollama (本地)': 'ollama',
                    '自定义API': 'custom'
                }
                
                provider_display = api_config.get('provider', 'OpenAI')
                provider_internal = provider_mapping.get(provider_display, 'custom')
                
                # 保存API配置
                self._config.set('ai', 'provider', provider_internal)
                self._config.set('ai', 'api_key', api_config.get('api_key', ''))
                self._config.set('ai', 'endpoint_url', api_config.get('api_base', ''))
                self._config.set('ai', 'model', api_config.get('model', ''))
                self._config.set('ai', 'temperature', api_config.get('temperature', 0.8))
                self._config.set('ai', 'top_p', api_config.get('top_p', 0.9))
                self._config.set('ai', 'max_tokens', api_config.get('max_tokens', 2000))
                self._config.set('ai', 'timeout', api_config.get('timeout', 30))
                
                # 保存补全设置
                # 映射补全模式到内部标识
                mode_mapping = {
                    '自动AI补全': 'auto_ai',
                    '手动AI补全': 'manual_ai',
                    '禁用补全': 'disabled'
                }
                
                context_mapping = {
                    '快速模式 (<2K tokens)': 'fast',
                    '平衡模式 (2-8K tokens)': 'balanced',
                    '全局模式 (200K+ tokens)': 'full'
                }
                
                mode_display = completion_settings.get('completion_mode', '自动AI补全')
                mode_internal = mode_mapping.get(mode_display, 'auto_ai')
                
                context_display = completion_settings.get('context_mode', '平衡模式 (2-8K tokens)')
                context_internal = context_mapping.get(context_display, 'balanced')
                
                self._config.set('ai', 'completion_enabled', completion_settings.get('completion_enabled', True))
                self._config.set('ai', 'auto_suggestions', completion_settings.get('auto_trigger_enabled', True))
                self._config.set('ai', 'punctuation_assist', completion_settings.get('punctuation_assist', True))
                self._config.set('ai', 'completion_delay', completion_settings.get('trigger_delay', 500))
                self._config.set('ai', 'completion_mode', mode_internal)
                self._config.set('ai', 'context_mode', context_internal)  # 新增上下文模式
                self._config.set('ai', 'min_chars', completion_settings.get('min_chars', 3))
                self._config.set('ai', 'context_length', completion_settings.get('context_length', 500))
                self._config.set('ai', 'completion_length', completion_settings.get('completion_length', 80))
                self._config.set('ai', 'stream_response', completion_settings.get('stream_response', True))
                self._config.set('ai', 'show_confidence', completion_settings.get('show_confidence', True))
                
                # 保存RAG配置
                self._config.set_section('rag', rag_config)
                
                # 保存增强提示词配置
                self._config.set_section('prompt', prompt_config)
                
                # 保存大纲AI配置
                if outline_config:
                    self._config._config_data['outline'] = outline_config
                    logger.debug("Saved outline AI config to config file")
                
                # 保存配置文件
                self._config.save()
                
                # 同步更新RAG配置的API key
                api_config = full_config.get('api', {})
                if api_config.get('api_key'):
                    rag_config = self._config.get_section('rag')
                    if not rag_config:
                        rag_config = {}
                    rag_config['api_key'] = api_config['api_key']
                    self._config.set_section('rag', rag_config)
                    self._config.save()
                    logger.info("同步更新RAG配置的API key")
                
            # 发送配置保存信号
            self.configSaved.emit(full_config)
            
            # 通知AI管理器重新加载配置
            self._notify_ai_manager_config_changed()
            
            # 显示成功消息
            QMessageBox.information(self, "成功", "AI配置已保存并应用！")
            
            self.accept()
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败：{str(e)}")
    
    def _notify_ai_manager_config_changed(self):
        """通知AI管理器配置已更改"""
        try:
            # 尝试从父窗口获取AI管理器
            parent = self.parent()
            if parent and hasattr(parent, '_ai_manager'):
                ai_manager = parent._ai_manager
                if ai_manager and hasattr(ai_manager, 'reload_config'):
                    ai_manager.reload_config()
                    logger.info("AI管理器配置重新加载成功")
                else:
                    logger.warning("AI管理器不支持配置重新加载")
            else:
                logger.warning("无法找到AI管理器实例")
                
            # 同时尝试通过shared对象通知
            if parent and hasattr(parent, '_shared'):
                shared = parent._shared
                if shared and hasattr(shared, 'ai_manager'):
                    ai_manager = shared.ai_manager
                    if ai_manager and hasattr(ai_manager, 'reload_config'):
                        ai_manager.reload_config()
                        logger.info("通过shared对象重新加载AI管理器配置成功")
                        
        except Exception as e:
            logger.error(f"通知AI管理器配置更改失败: {e}")
            
    def _reset_to_defaults(self):
        """重置为默认设置"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要将所有设置重置为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 重置API配置
            default_api_config = {
                "provider": "OpenAI",
                "api_key": "",
                "api_base": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo",
                "temperature": 0.8,
                "top_p": 0.9,
                "max_tokens": 2000,
                "timeout": 30
            }
            self._api_widget.set_config(default_api_config)
            
            # 重置补全设置
            default_completion_settings = {
                'completion_enabled': True,
                'auto_trigger_enabled': True,
                'punctuation_assist': True,
                'trigger_delay': 500,
                'completion_mode': '自动AI补全',
                'context_mode': '平衡模式 (2-8K tokens)',  # 新增上下文模式默认值
                'min_chars': 3,
                'context_length': 500,
                'completion_length': 80,
                'stream_response': True,
                'show_confidence': True
            }
            self._completion_widget.set_settings(default_completion_settings)
            
            # 重置RAG配置
            self._rag_widget.set_config(self._rag_widget._get_default_config())
            
            # 重置增强提示词配置
            default_prompt_config = {
                "context_mode": "balanced",
                "style_tags": [],
                "custom_prefix": "",
                "preferred_length": 200,
                "creativity": 0.7,
                "context_length": 800,
                "preset": "默认设置"
            }
            self._prompt_config_widget.set_config(default_prompt_config)
            
    def _test_full_config(self):
        """测试完整配置"""
        # 直接调用API配置页面的测试功能
        self._tabs.setCurrentIndex(0)  # 切换到API配置页
        self._api_widget._test_connection()
    
    def _show_index_manager(self):
        """显示索引管理对话框"""
        try:
            # 获取AI管理器和项目管理器引用
            ai_manager = None
            project_manager = None
            
            # 尝试从父窗口获取
            parent = self.parent()
            if parent:
                if hasattr(parent, '_ai_manager'):
                    ai_manager = parent._ai_manager
                if hasattr(parent, '_project_manager'):
                    project_manager = parent._project_manager
            
            if not ai_manager:
                QMessageBox.warning(self, "警告", "AI管理器不可用")
                return
            
            # 显示索引管理对话框
            ai_manager.show_index_manager(parent=self, project_manager=project_manager)
            
        except Exception as e:
            logger.error(f"显示索引管理对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开索引管理对话框：{str(e)}")
        
    def get_completion_widget(self):
        """获取补全设置组件"""
        return self._completion_widget
        
    def get_api_widget(self):
        """获取API配置组件"""
        return self._api_widget


class TemplateManagementWidget(QWidget):
    """提示词模板管理组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ai_manager = None
        self._init_ui()
        self._setup_connections()
        
        # 获取AI管理器
        if parent and hasattr(parent, '_ai_manager'):
            self._ai_manager = parent._ai_manager
            self._load_templates()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题和说明
        title_label = QLabel("提示词模板管理")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        desc_label = QLabel("选择和管理AI补全的提示词模板，不同模式可以使用不同的模板来获得最佳效果。")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 16px;")
        layout.addWidget(desc_label)
        
        # 模式模板选择区域
        modes_group = QGroupBox("模式模板选择")
        modes_layout = QFormLayout(modes_group)
        
        # 快速模式
        self._fast_combo = QComboBox()
        self._fast_combo.setToolTip("快速模式：15-30字符的简短补全，注重速度和流畅性")
        modes_layout.addRow("快速模式模板:", self._fast_combo)
        
        # 平衡模式  
        self._balanced_combo = QComboBox()
        self._balanced_combo.setToolTip("平衡模式：50-120字符的中等补全，平衡质量和速度")
        modes_layout.addRow("平衡模式模板:", self._balanced_combo)
        
        # 全局模式
        self._full_combo = QComboBox()
        self._full_combo.setToolTip("全局模式：150-400字符的深度创作，追求最高文学质量")
        modes_layout.addRow("全局模式模板:", self._full_combo)
        
        layout.addWidget(modes_group)
        
        # 模板列表和预览
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：模板列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        list_label = QLabel("可用模板")
        list_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        left_layout.addWidget(list_label)
        
        self._template_list = QListWidget()
        self._template_list.setMinimumWidth(300)
        left_layout.addWidget(self._template_list)
        
        # 模板操作按钮
        buttons_layout = QHBoxLayout()
        self._edit_btn = QPushButton("编辑模板")
        self._edit_btn.setEnabled(False)
        self._duplicate_btn = QPushButton("复制模板")
        self._duplicate_btn.setEnabled(False)
        self._delete_btn = QPushButton("删除模板")
        self._delete_btn.setEnabled(False)
        
        buttons_layout.addWidget(self._edit_btn)
        buttons_layout.addWidget(self._duplicate_btn)
        buttons_layout.addWidget(self._delete_btn)
        buttons_layout.addStretch()
        
        left_layout.addLayout(buttons_layout)
        
        # 右侧：模板预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_label = QLabel("模板预览")
        preview_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        right_layout.addWidget(preview_label)
        
        self._preview_text = QTextBrowser()
        self._preview_text.setMinimumWidth(400)
        self._preview_text.setMaximumHeight(300)
        right_layout.addWidget(self._preview_text)
        
        # 模板信息
        info_group = QGroupBox("模板信息")
        info_layout = QFormLayout(info_group)
        
        self._info_name = QLabel()
        self._info_category = QLabel()
        self._info_description = QLabel()
        self._info_builtin = QLabel()
        
        info_layout.addRow("名称:", self._info_name)
        info_layout.addRow("类别:", self._info_category)
        info_layout.addRow("描述:", self._info_description)
        info_layout.addRow("内置模板:", self._info_builtin)
        
        right_layout.addWidget(info_group)
        right_layout.addStretch()
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 500])
        
        layout.addWidget(splitter)
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        
        self._new_template_btn = QPushButton("新建模板")
        self._import_btn = QPushButton("导入模板")
        self._export_btn = QPushButton("导出模板")
        
        bottom_layout.addWidget(self._new_template_btn)
        bottom_layout.addWidget(self._import_btn)
        bottom_layout.addWidget(self._export_btn)
        bottom_layout.addStretch()
        
        self._apply_btn = QPushButton("应用设置")
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d7377;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14a085;
            }
            QPushButton:pressed {
                background-color: #0a5d61;
            }
        """)
        bottom_layout.addWidget(self._apply_btn)
        
        layout.addLayout(bottom_layout)
    
    def _setup_connections(self):
        """设置信号连接"""
        # 模板列表选择变化
        self._template_list.currentItemChanged.connect(self._on_template_selected)
        
        # 下拉框变化
        self._fast_combo.currentTextChanged.connect(self._on_template_combo_changed)
        self._balanced_combo.currentTextChanged.connect(self._on_template_combo_changed)
        self._full_combo.currentTextChanged.connect(self._on_template_combo_changed)
        
        # 按钮点击
        self._edit_btn.clicked.connect(self._edit_template)
        self._duplicate_btn.clicked.connect(self._duplicate_template)
        self._delete_btn.clicked.connect(self._delete_template)
        self._new_template_btn.clicked.connect(self._new_template)
        self._import_btn.clicked.connect(self._import_template)
        self._export_btn.clicked.connect(self._export_template)
        self._apply_btn.clicked.connect(self._apply_settings)
    
    def _load_templates(self):
        """加载模板列表"""
        if not self._ai_manager:
            return
            
        try:
            # 获取所有模板ID
            template_ids = self._ai_manager.get_available_templates()
            
            # 清空现有内容
            self._template_list.clear()
            self._fast_combo.clear()
            self._balanced_combo.clear()
            self._full_combo.clear()
            
            # 处理从SimpleAIManager返回的模板数据
            templates = []
            for template_data in template_ids:
                if isinstance(template_data, dict):
                    # SimpleAIManager返回的是字典格式
                    template_info = {
                        'id': template_data.get('id', ''),
                        'name': template_data.get('name', ''),
                        'description': template_data.get('description', ''),
                        'category': template_data.get('category', 'Template'),
                        'is_builtin': True,  # SimpleAIManager的模板都是内置的
                    }
                    templates.append(template_info)
                else:
                    # 兼容旧格式：字符串ID
                    templates.append({
                        'id': template_data,
                        'name': template_data.replace('_', ' ').title() if isinstance(template_data, str) else str(template_data),
                        'category': 'Template',
                        'is_builtin': True,
                        'description': ''
                    })
            
            # 添加模板到列表和下拉框
            for template in templates:
                # 添加到列表
                item = QListWidgetItem(f"{template['name']} ({template['category']})")
                item.setData(Qt.ItemDataRole.UserRole, template)
                if template['is_builtin']:
                    item.setForeground(QColor(100, 100, 100))  # 灰色表示内置
                self._template_list.addItem(item)
                
                # 添加到下拉框
                display_name = f"{template['name']} ({'内置' if template['is_builtin'] else '自定义'})"
                self._fast_combo.addItem(display_name, template['id'])
                self._balanced_combo.addItem(display_name, template['id'])
                self._full_combo.addItem(display_name, template['id'])
            
            # 设置当前选择
            self._set_current_selections()
            
            logger.info(f"已加载 {len(templates)} 个提示词模板")
            
        except Exception as e:
            logger.error(f"加载模板失败: {e}")
    
    def _set_current_selections(self):
        """设置当前选择的模板"""
        if not self._ai_manager:
            return
            
        try:
            # 获取当前模板ID
            fast_id = self._ai_manager.get_current_template_id('fast')
            balanced_id = self._ai_manager.get_current_template_id('balanced')
            full_id = self._ai_manager.get_current_template_id('full')
            
            # 设置下拉框选择
            self._set_combo_selection(self._fast_combo, fast_id)
            self._set_combo_selection(self._balanced_combo, balanced_id)
            self._set_combo_selection(self._full_combo, full_id)
            
        except Exception as e:
            logger.error(f"设置当前选择失败: {e}")
    
    def _set_combo_selection(self, combo, template_id):
        """设置下拉框的选择"""
        for i in range(combo.count()):
            if combo.itemData(i) == template_id:
                combo.setCurrentIndex(i)
                return
    
    def _on_template_selected(self, current, previous):
        """模板选择变化"""
        if not current:
            self._edit_btn.setEnabled(False)
            self._duplicate_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            self._preview_text.clear()
            self._info_name.clear()
            self._info_category.clear()
            self._info_description.clear()
            self._info_builtin.clear()
            return
        
        template = current.data(Qt.ItemDataRole.UserRole)
        if not template:
            return
        
        # 更新按钮状态
        is_builtin = template['is_builtin']
        self._edit_btn.setEnabled(True)
        self._duplicate_btn.setEnabled(True)
        self._delete_btn.setEnabled(not is_builtin)  # 内置模板不能删除
        
        # 更新预览和信息
        self._update_template_preview(template)
        self._update_template_info(template)
    
    def _update_template_preview(self, template):
        """更新模板预览"""
        # 这里可以显示模板的系统提示词预览
        preview_text = f"<h3>{template['name']}</h3>"
        preview_text += f"<p><b>类别:</b> {template['category']}</p>"
        preview_text += f"<p><b>描述:</b> {template['description']}</p>"
        preview_text += "<hr>"
        preview_text += "<p><i>模板内容预览功能开发中...</i></p>"
        
        self._preview_text.setHtml(preview_text)
    
    def _update_template_info(self, template):
        """更新模板信息"""
        self._info_name.setText(template['name'])
        self._info_category.setText(template['category'])
        self._info_description.setText(template['description'])
        self._info_builtin.setText("是" if template['is_builtin'] else "否")
    
    def _on_template_combo_changed(self):
        """模板下拉框变化"""
        # 实时应用更改
        pass
    
    def _edit_template(self):
        """编辑模板"""
        current = self._template_list.currentItem()
        if not current:
            return
        
        template = current.data(Qt.ItemDataRole.UserRole)
        if not template:
            return
        
        try:
            # 使用简化的提示词设置界面替代复杂编辑器
            from .simplified_prompt_dialog import SimplifiedPromptDialog
            dialog = SimplifiedPromptDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._load_templates()  # 重新加载模板列表
                
        except Exception as e:
            logger.error(f"打开简化提示词设置失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开提示词设置：{str(e)}")
    
    def _duplicate_template(self):
        """复制模板"""
        QMessageBox.information(self, "提示", "复制模板功能开发中...")
    
    def _delete_template(self):
        """删除模板"""
        current = self._template_list.currentItem()
        if not current:
            return
        
        template = current.data(Qt.ItemDataRole.UserRole)
        if not template or template['is_builtin']:
            QMessageBox.warning(self, "警告", "不能删除内置模板")
            return
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除模板 '{template['name']}' 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "提示", "删除模板功能开发中...")
    
    def _new_template(self):
        """新建模板"""
        try:
            # 使用简化的提示词设置界面替代复杂编辑器
            from .simplified_prompt_dialog import SimplifiedPromptDialog
            dialog = SimplifiedPromptDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._load_templates()  # 重新加载模板列表
                
        except Exception as e:
            logger.error(f"创建新模板失败: {e}")
            QMessageBox.warning(self, "错误", f"无法创建新模板：{str(e)}")
    
    def _import_template(self):
        """导入模板"""
        QMessageBox.information(self, "提示", "导入模板功能开发中...")
    
    def _export_template(self):
        """导出模板"""
        QMessageBox.information(self, "提示", "导出模板功能开发中...")
    
    def _apply_settings(self):
        """应用设置"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器不可用")
            return
        
        try:
            # 获取选择的模板ID
            fast_id = self._fast_combo.currentData()
            balanced_id = self._balanced_combo.currentData()
            full_id = self._full_combo.currentData()
            
            # 应用到AI管理器
            if fast_id:
                self._ai_manager.set_template_for_mode('fast', fast_id)
            if balanced_id:
                self._ai_manager.set_template_for_mode('balanced', balanced_id)
            if full_id:
                self._ai_manager.set_template_for_mode('full', full_id)
            
            QMessageBox.information(self, "成功", "模板设置已应用")
            
        except Exception as e:
            logger.error(f"应用模板设置失败: {e}")
            QMessageBox.warning(self, "错误", f"应用设置失败：{str(e)}")