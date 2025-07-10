"""
RAG配置对话框 - 用于配置向量搜索和重排序模型
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTextEdit, QMessageBox, QTabWidget, QWidget,
    QCheckBox, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import json
import asyncio
import aiohttp
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RAGConfigWidget(QWidget):
    """RAG配置组件"""
    
    configChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = self._get_default_config()
        self._init_ui()
        self._load_config()
        
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": False,
            "provider": "siliconflow",
            "api_key": "",
            "base_url": "https://api.siliconflow.cn/v1",
            "embedding": {
                "model": "BAAI/bge-large-zh-v1.5",
                "dimension": 1024,
                "batch_size": 32
            },
            "rerank": {
                "model": "BAAI/bge-reranker-v2-m3",
                "enabled": True,
                "top_k": 5
            },
            "search": {
                "chunk_size": 500,
                "chunk_overlap": 50,
                "max_results": 10,
                "min_similarity": 0.5
            }
        }
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 启用/禁用RAG
        self.enable_check = QCheckBox("启用智能向量搜索 (RAG)")
        self.enable_check.stateChanged.connect(self._on_enable_changed)
        layout.addWidget(self.enable_check)
        
        # 主配置区域
        self.config_widget = QWidget()
        config_layout = QVBoxLayout(self.config_widget)
        
        # API配置组
        api_group = QGroupBox("API配置")
        api_layout = QVBoxLayout()
        
        # 提供商选择
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("提供商:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["siliconflow", "custom"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()
        api_layout.addLayout(provider_layout)
        
        # API Key
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_layout.addWidget(self.api_key_edit)
        api_layout.addLayout(key_layout)
        
        # Base URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Base URL:"))
        self.base_url_edit = QLineEdit()
        url_layout.addWidget(self.base_url_edit)
        api_layout.addLayout(url_layout)
        
        # 测试连接按钮
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        api_layout.addWidget(self.test_btn)
        
        api_group.setLayout(api_layout)
        config_layout.addWidget(api_group)
        
        # Embedding配置组
        embedding_group = QGroupBox("向量模型配置")
        embedding_layout = QVBoxLayout()
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型:"))
        self.embedding_model_combo = QComboBox()
        self.embedding_model_combo.setEditable(True)
        self.embedding_model_combo.addItems([
            "BAAI/bge-large-zh-v1.5",
            "BAAI/bge-m3",
            "text-embedding-ada-002"
        ])
        model_layout.addWidget(self.embedding_model_combo)
        embedding_layout.addLayout(model_layout)
        
        # 向量维度
        dim_layout = QHBoxLayout()
        dim_layout.addWidget(QLabel("向量维度:"))
        self.dimension_spin = QSpinBox()
        self.dimension_spin.setRange(128, 4096)
        self.dimension_spin.setValue(1024)
        dim_layout.addWidget(self.dimension_spin)
        dim_layout.addStretch()
        embedding_layout.addLayout(dim_layout)
        
        # 批处理大小
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("批处理大小:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100)
        self.batch_size_spin.setValue(32)
        batch_layout.addWidget(self.batch_size_spin)
        batch_layout.addStretch()
        embedding_layout.addLayout(batch_layout)
        
        embedding_group.setLayout(embedding_layout)
        config_layout.addWidget(embedding_group)
        
        # Rerank配置组
        rerank_group = QGroupBox("重排序配置")
        rerank_layout = QVBoxLayout()
        
        self.rerank_check = QCheckBox("启用重排序")
        rerank_layout.addWidget(self.rerank_check)
        
        # 重排序模型
        rerank_model_layout = QHBoxLayout()
        rerank_model_layout.addWidget(QLabel("模型:"))
        self.rerank_model_combo = QComboBox()
        self.rerank_model_combo.setEditable(True)
        self.rerank_model_combo.addItems([
            "BAAI/bge-reranker-v2-m3",
            "rerank-english-v2.0"
        ])
        rerank_model_layout.addWidget(self.rerank_model_combo)
        rerank_layout.addLayout(rerank_model_layout)
        
        # Top K
        topk_layout = QHBoxLayout()
        topk_layout.addWidget(QLabel("返回前K个结果:"))
        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 50)
        self.topk_spin.setValue(5)
        topk_layout.addWidget(self.topk_spin)
        topk_layout.addStretch()
        rerank_layout.addLayout(topk_layout)
        
        rerank_group.setLayout(rerank_layout)
        config_layout.addWidget(rerank_group)
        
        # 搜索配置组
        search_group = QGroupBox("搜索配置")
        search_layout = QVBoxLayout()
        
        # 分块大小
        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("分块大小:"))
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(100, 2000)
        self.chunk_size_spin.setValue(500)
        self.chunk_size_spin.setSuffix(" 字符")
        chunk_layout.addWidget(self.chunk_size_spin)
        chunk_layout.addStretch()
        search_layout.addLayout(chunk_layout)
        
        # 重叠大小
        overlap_layout = QHBoxLayout()
        overlap_layout.addWidget(QLabel("重叠大小:"))
        self.overlap_spin = QSpinBox()
        self.overlap_spin.setRange(0, 500)
        self.overlap_spin.setValue(50)
        self.overlap_spin.setSuffix(" 字符")
        overlap_layout.addWidget(self.overlap_spin)
        overlap_layout.addStretch()
        search_layout.addLayout(overlap_layout)
        
        # 最大结果数
        max_results_layout = QHBoxLayout()
        max_results_layout.addWidget(QLabel("最大结果数:"))
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 50)
        self.max_results_spin.setValue(10)
        max_results_layout.addWidget(self.max_results_spin)
        max_results_layout.addStretch()
        search_layout.addLayout(max_results_layout)
        
        # 最小相似度
        min_sim_layout = QHBoxLayout()
        min_sim_layout.addWidget(QLabel("最小相似度:"))
        self.min_similarity_spin = QDoubleSpinBox()
        self.min_similarity_spin.setRange(0.0, 1.0)
        self.min_similarity_spin.setSingleStep(0.1)
        self.min_similarity_spin.setValue(0.5)
        min_sim_layout.addWidget(self.min_similarity_spin)
        min_sim_layout.addStretch()
        search_layout.addLayout(min_sim_layout)
        
        search_group.setLayout(search_layout)
        config_layout.addWidget(search_group)
        
        # 测试结果区域
        self.test_result = QTextEdit()
        self.test_result.setReadOnly(True)
        self.test_result.setMaximumHeight(150)
        config_layout.addWidget(QLabel("测试结果:"))
        config_layout.addWidget(self.test_result)
        
        config_layout.addStretch()
        layout.addWidget(self.config_widget)
        
        # 连接信号
        self._connect_signals()
        
    def _connect_signals(self):
        """连接信号"""
        # 配置变化信号
        self.api_key_edit.textChanged.connect(self._on_config_changed)
        self.base_url_edit.textChanged.connect(self._on_config_changed)
        self.embedding_model_combo.currentTextChanged.connect(self._on_config_changed)
        self.dimension_spin.valueChanged.connect(self._on_config_changed)
        self.batch_size_spin.valueChanged.connect(self._on_config_changed)
        self.rerank_check.stateChanged.connect(self._on_config_changed)
        self.rerank_model_combo.currentTextChanged.connect(self._on_config_changed)
        self.topk_spin.valueChanged.connect(self._on_config_changed)
        self.chunk_size_spin.valueChanged.connect(self._on_config_changed)
        self.overlap_spin.valueChanged.connect(self._on_config_changed)
        self.max_results_spin.valueChanged.connect(self._on_config_changed)
        self.min_similarity_spin.valueChanged.connect(self._on_config_changed)
        
    def _on_enable_changed(self, state):
        """启用状态改变"""
        enabled = state == Qt.CheckState.Checked.value
        self.config_widget.setEnabled(enabled)
        self._on_config_changed()
        
    def _on_provider_changed(self, provider):
        """提供商改变"""
        if provider == "siliconflow":
            self.base_url_edit.setText("https://api.siliconflow.cn/v1")
            self.embedding_model_combo.setCurrentText("BAAI/bge-large-zh-v1.5")
            self.rerank_model_combo.setCurrentText("BAAI/bge-reranker-v2-m3")
        self._on_config_changed()
        
    def _on_config_changed(self):
        """配置改变"""
        self.config = self.get_config()
        self.configChanged.emit(self.config)
        
    def _load_config(self):
        """加载配置"""
        # 从配置系统加载
        # TODO: 集成到现有配置系统
        self._apply_config(self.config)
        
    def _apply_config(self, config: Dict[str, Any]):
        """应用配置"""
        self.enable_check.setChecked(config.get("enabled", False))
        self.provider_combo.setCurrentText(config.get("provider", "siliconflow"))
        self.api_key_edit.setText(config.get("api_key", ""))
        self.base_url_edit.setText(config.get("base_url", ""))
        
        embedding = config.get("embedding", {})
        self.embedding_model_combo.setCurrentText(embedding.get("model", ""))
        self.dimension_spin.setValue(embedding.get("dimension", 1024))
        self.batch_size_spin.setValue(embedding.get("batch_size", 32))
        
        rerank = config.get("rerank", {})
        self.rerank_check.setChecked(rerank.get("enabled", True))
        self.rerank_model_combo.setCurrentText(rerank.get("model", ""))
        self.topk_spin.setValue(rerank.get("top_k", 5))
        
        search = config.get("search", {})
        self.chunk_size_spin.setValue(search.get("chunk_size", 500))
        self.overlap_spin.setValue(search.get("chunk_overlap", 50))
        self.max_results_spin.setValue(search.get("max_results", 10))
        self.min_similarity_spin.setValue(search.get("min_similarity", 0.5))
        
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        # 保存API密钥到安全存储
        api_key = self.api_key_edit.text()
        provider = self.provider_combo.currentText().lower()
        
        if api_key:
            try:
                from core.secure_key_manager import get_secure_key_manager
                key_manager = get_secure_key_manager()
                key_manager.store_api_key(provider, api_key)
            except ImportError:
                pass  # 如果安全密钥管理器不可用，保持兼容性
        
        return {
            "enabled": self.enable_check.isChecked(),
            "provider": provider,
            "has_api_key": bool(api_key),
            "base_url": self.base_url_edit.text(),
            "embedding": {
                "model": self.embedding_model_combo.currentText(),
                "dimension": self.dimension_spin.value(),
                "batch_size": self.batch_size_spin.value()
            },
            "rerank": {
                "model": self.rerank_model_combo.currentText(),
                "enabled": self.rerank_check.isChecked(),
                "top_k": self.topk_spin.value()
            },
            "search": {
                "chunk_size": self.chunk_size_spin.value(),
                "chunk_overlap": self.overlap_spin.value(),
                "max_results": self.max_results_spin.value(),
                "min_similarity": self.min_similarity_spin.value()
            }
        }
        
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self.config = config
        self._apply_config(config)
        
        # 从安全存储加载API密钥
        provider = config.get("provider", "openai")
        try:
            from core.secure_key_manager import get_secure_key_manager
            key_manager = get_secure_key_manager()
            api_key = key_manager.retrieve_api_key(provider)
            if api_key:
                self.api_key_edit.setText(api_key)
        except ImportError:
            # 如果安全密钥管理器不可用，尝试从配置中获取（兼容性）
            api_key = config.get("api_key", "")
            if api_key:
                self.api_key_edit.setText(api_key)
        
    async def _test_connection_async(self):
        """异步测试连接"""
        config = self.get_config()
        results = []
        
        # 获取API密钥
        api_key = self.api_key_edit.text()
        if not api_key:
            self.test_result.setText("❌ 请先设置API密钥")
            return
        
        async with aiohttp.ClientSession() as session:
            # 测试Embedding API
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                # 测试向量模型
                embedding_url = f"{config['base_url']}/embeddings"
                embedding_data = {
                    "model": config['embedding']['model'],
                    "input": "测试文本"
                }
                
                async with session.post(
                    embedding_url, 
                    headers=headers, 
                    json=embedding_data
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embedding_len = len(data.get('data', [{}])[0].get('embedding', []))
                        results.append(f"✓ Embedding API连接成功")
                        results.append(f"  模型: {config['embedding']['model']}")
                        results.append(f"  向量维度: {embedding_len}")
                    else:
                        error_text = await resp.text()
                        results.append(f"✗ Embedding API连接失败: {resp.status}")
                        results.append(f"  错误: {error_text}")
                        
            except Exception as e:
                results.append(f"✗ Embedding API连接异常: {str(e)}")
                
            # 测试Rerank API
            if config['rerank']['enabled']:
                try:
                    rerank_url = f"{config['base_url']}/rerank"
                    rerank_data = {
                        "model": config['rerank']['model'],
                        "query": "测试查询",
                        "documents": ["文档1", "文档2"]
                    }
                    
                    async with session.post(
                        rerank_url, 
                        headers=headers, 
                        json=rerank_data
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results.append(f"\n✓ Rerank API连接成功")
                            results.append(f"  模型: {config['rerank']['model']}")
                        else:
                            error_text = await resp.text()
                            results.append(f"\n✗ Rerank API连接失败: {resp.status}")
                            results.append(f"  错误: {error_text}")
                            
                except Exception as e:
                    results.append(f"\n✗ Rerank API连接异常: {str(e)}")
                    
        return "\n".join(results)
        
    def _test_connection(self):
        """测试连接"""
        self.test_btn.setEnabled(False)
        self.test_result.setText("正在测试连接...")
        
        try:
            # 运行异步测试
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._test_connection_async())
            self.test_result.setText(result)
        except Exception as e:
            self.test_result.setText(f"测试失败: {str(e)}")
        finally:
            self.test_btn.setEnabled(True)


class RAGConfigDialog(QDialog):
    """RAG配置对话框"""
    
    def __init__(self, config=None, shared=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.shared = shared
        self.setWindowTitle("RAG向量搜索配置")
        self.setModal(True)
        self.resize(800, 700)
        
        self._init_ui()
        self._load_config()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 说明文本
        info_label = QLabel(
            "配置向量搜索（RAG）功能，实现智能的上下文检索和补全增强。\n"
            "支持硅基流动等第三方向量模型API。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # RAG配置组件
        self.rag_widget = RAGConfigWidget()
        self.rag_widget.configChanged.connect(self._on_config_changed)
        layout.addWidget(self.rag_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def _load_config(self):
        """加载配置"""
        if self.config:
            rag_config = self.config.get("rag", self.rag_widget._get_default_config())
            self.rag_widget.set_config(rag_config)
            
    def _on_config_changed(self, config):
        """配置改变"""
        # 可以在这里添加实时保存逻辑
        pass
        
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self.rag_widget.get_config()
        
    def accept(self):
        """保存配置"""
        if self.config:
            rag_config = self.get_config()
            self.config.set("rag", rag_config)
            self.config.save()
            
        super().accept()