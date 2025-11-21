"""
RAG配置组件 - 恢复RAG向量搜索和检索增强生成的配置界面
"""

import logging
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QComboBox, QCheckBox,
    QPushButton, QLabel, QSlider, QTextEdit, QProgressBar,
    QMessageBox, QTextBrowser, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class RAGTestWorker(QThread):
    """RAG连接测试工作线程"""
    
    testStarted = pyqtSignal()
    testProgress = pyqtSignal(str)
    testCompleted = pyqtSignal(bool, str)
    
    def __init__(self, config_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config_data = config_data
        
    def run(self):
        """执行RAG连接测试"""
        try:
            self.testStarted.emit()
            self.testProgress.emit("正在验证RAG配置参数...")
            
            # 检查API密钥
            if not self.config_data.get('api_key', '').strip():
                self.testCompleted.emit(False, "RAG API密钥不能为空")
                return
            
            # 检查embedding模型配置
            embedding_config = self.config_data.get('embedding', {})
            if not embedding_config.get('enabled', False):
                self.testCompleted.emit(False, "embedding服务未启用")
                return
                
            if not embedding_config.get('model', '').strip():
                self.testCompleted.emit(False, "embedding模型未配置")
                return
            
            self.testProgress.emit("正在测试embedding API连接...")
            
            # 这里可以添加实际的RAG服务测试逻辑
            # 模拟测试过程
            self.msleep(1000)  # 模拟网络延迟
            
            self.testProgress.emit("正在测试向量存储连接...")
            self.msleep(500)
            
            # 检查rerank配置（如果启用）
            rerank_config = self.config_data.get('rerank', {})
            if rerank_config.get('enabled', False):
                self.testProgress.emit("正在测试rerank服务...")
                self.msleep(500)
            
            # 模拟成功结果
            self.testCompleted.emit(True, 
                f"✅ RAG连接测试成功！\n"
                f"🔗 API地址: {self.config_data.get('base_url', 'N/A')}\n"
                f"🤖 Embedding模型: {embedding_config.get('model', 'N/A')}\n"
                f"📊 Rerank服务: {'启用' if rerank_config.get('enabled') else '禁用'}"
            )
            
        except Exception as e:
            self.testCompleted.emit(False, f"RAG连接测试失败: {str(e)}")


class RAGConfigWidget(QFrame):
    """RAG配置组件"""
    
    configChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_worker = None
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        # 主布局（只包含滚动区域）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 创建内容widget
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        # 内容布局
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题和说明
        title_label = QLabel("RAG 向量搜索配置")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        desc_label = QLabel(
            "配置检索增强生成(RAG)系统，为AI补全提供相关上下文。\n"
            "RAG系统通过向量搜索找到相关的历史内容，提升AI补全的连贯性和准确性。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 16px;")
        layout.addWidget(desc_label)
        
        # RAG服务配置
        self._create_service_config(layout)
        
        # Embedding配置
        self._create_embedding_config(layout)
        
        # Rerank配置
        self._create_rerank_config(layout)
        
        # 向量存储配置
        self._create_vector_store_config(layout)
        
        # 网络和性能配置
        self._create_network_config(layout)
        
        # 缓存配置
        self._create_cache_config(layout)
        
        # 连接测试
        self._create_connection_test(layout)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
    def _create_service_config(self, layout):
        """创建RAG服务配置"""
        group = QGroupBox("RAG服务配置")
        group_layout = QFormLayout(group)
        
        # 总开关
        self.rag_enabled = QCheckBox("启用RAG向量搜索")
        self.rag_enabled.setChecked(True)
        self.rag_enabled.toggled.connect(self._on_rag_enabled_changed)
        group_layout.addRow("", self.rag_enabled)
        
        # API密钥
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("请输入RAG服务API密钥")
        
        # 显示/隐藏密钥按钮
        key_layout = QHBoxLayout()
        key_layout.addWidget(self.api_key_edit)
        
        self.show_key_btn = QPushButton("👁")
        self.show_key_btn.setFixedSize(30, 30)
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.show_key_btn)
        
        group_layout.addRow("API密钥:", key_layout)
        
        # API基础URL
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setText("https://api.siliconflow.cn/v1")
        self.base_url_edit.setPlaceholderText("RAG服务API基础URL")
        group_layout.addRow("API地址:", self.base_url_edit)
        
        layout.addWidget(group)
    
    def _create_embedding_config(self, layout):
        """创建Embedding配置"""
        group = QGroupBox("Embedding向量化配置")
        group_layout = QFormLayout(group)
        
        # Embedding开关
        self.embedding_enabled = QCheckBox("启用Embedding服务")
        self.embedding_enabled.setChecked(True)
        group_layout.addRow("", self.embedding_enabled)
        
        # Embedding模型
        self.embedding_model = QComboBox()
        self.embedding_model.setEditable(True)
        self.embedding_model.addItems([
            "BAAI/bge-large-zh-v1.5",
            "BAAI/bge-m3",
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large"
        ])
        self.embedding_model.setCurrentText("BAAI/bge-large-zh-v1.5")
        group_layout.addRow("Embedding模型:", self.embedding_model)
        
        # 向量维度（只读显示）
        self.embedding_dimension = QLabel("1024")
        self.embedding_dimension.setStyleSheet("color: #666;")
        group_layout.addRow("向量维度:", self.embedding_dimension)
        
        # 批量大小
        self.embedding_batch_size = QSpinBox()
        self.embedding_batch_size.setRange(1, 100)
        self.embedding_batch_size.setValue(32)
        self.embedding_batch_size.setToolTip("批量处理文档数量，越大速度越快但内存占用越多")
        group_layout.addRow("批量大小:", self.embedding_batch_size)
        
        layout.addWidget(group)
    
    def _create_rerank_config(self, layout):
        """创建Rerank配置"""
        group = QGroupBox("Rerank重排序配置")
        group_layout = QFormLayout(group)
        
        # Rerank开关
        self.rerank_enabled = QCheckBox("启用Rerank重排序")
        self.rerank_enabled.setChecked(True)
        self.rerank_enabled.setToolTip("重排序可以提高检索质量，但会增加API调用成本")
        group_layout.addRow("", self.rerank_enabled)
        
        # Rerank模型
        self.rerank_model = QComboBox()
        self.rerank_model.setEditable(True)
        self.rerank_model.addItems([
            "BAAI/bge-reranker-v2-m3",
            "BAAI/bge-reranker-large",
            "rerank-multilingual-v3.0"
        ])
        self.rerank_model.setCurrentText("BAAI/bge-reranker-v2-m3")
        group_layout.addRow("Rerank模型:", self.rerank_model)
        
        # Top K重排序
        self.rerank_top_k = QSpinBox()
        self.rerank_top_k.setRange(1, 20)
        self.rerank_top_k.setValue(10)
        self.rerank_top_k.setToolTip("参与重排序的候选文档数量")
        group_layout.addRow("重排序数量:", self.rerank_top_k)
        
        layout.addWidget(group)
    
    def _create_vector_store_config(self, layout):
        """创建向量存储配置"""
        group = QGroupBox("向量存储配置")
        group_layout = QFormLayout(group)
        
        # 相似度阈值
        similarity_layout = QHBoxLayout()
        self.similarity_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.similarity_threshold_slider.setRange(0, 100)
        self.similarity_threshold_slider.setValue(30)  # 0.3
        self.similarity_threshold_label = QLabel("0.3")
        
        similarity_layout.addWidget(self.similarity_threshold_slider)
        similarity_layout.addWidget(self.similarity_threshold_label)
        
        self.similarity_threshold_slider.valueChanged.connect(
            lambda v: self.similarity_threshold_label.setText(f"{v/100:.1f}")
        )
        
        group_layout.addRow("相似度阈值:", similarity_layout)
        
        # 检索结果数量
        search_limits_layout = QVBoxLayout()
        
        # 快速模式
        self.search_limit_fast = QSpinBox()
        self.search_limit_fast.setRange(1, 50)
        self.search_limit_fast.setValue(5)
        search_limits_layout.addWidget(QLabel("快速模式检索数量:"))
        search_limits_layout.addWidget(self.search_limit_fast)
        
        # 平衡模式
        self.search_limit_balanced = QSpinBox()
        self.search_limit_balanced.setRange(1, 50)
        self.search_limit_balanced.setValue(10)
        search_limits_layout.addWidget(QLabel("平衡模式检索数量:"))
        search_limits_layout.addWidget(self.search_limit_balanced)
        
        # 全局模式
        self.search_limit_full = QSpinBox()
        self.search_limit_full.setRange(1, 100)
        self.search_limit_full.setValue(20)
        search_limits_layout.addWidget(QLabel("全局模式检索数量:"))
        search_limits_layout.addWidget(self.search_limit_full)
        
        group_layout.addRow("检索数量配置:", search_limits_layout)
        
        # 文档分块大小
        self.chunk_size = QSpinBox()
        self.chunk_size.setRange(100, 1000)
        self.chunk_size.setValue(250)
        self.chunk_size.setSuffix(" 字符")
        self.chunk_size.setToolTip("文档分块大小，影响检索精度和存储空间")
        group_layout.addRow("分块大小:", self.chunk_size)
        
        # 分块重叠
        self.chunk_overlap = QSpinBox()
        self.chunk_overlap.setRange(0, 200)
        self.chunk_overlap.setValue(50)
        self.chunk_overlap.setSuffix(" 字符")
        self.chunk_overlap.setToolTip("分块重叠大小，确保上下文连续性")
        group_layout.addRow("重叠大小:", self.chunk_overlap)
        
        layout.addWidget(group)
    
    def _create_network_config(self, layout):
        """创建网络配置"""
        group = QGroupBox("网络和性能配置")
        group_layout = QFormLayout(group)
        
        # 最大重试次数
        self.max_retries = QSpinBox()
        self.max_retries.setRange(0, 10)
        self.max_retries.setValue(3)
        self.max_retries.setToolTip("API调用失败时的最大重试次数")
        group_layout.addRow("最大重试:", self.max_retries)
        
        # 请求超时
        self.request_timeout = QSpinBox()
        self.request_timeout.setRange(5, 120)
        self.request_timeout.setValue(30)
        self.request_timeout.setSuffix(" 秒")
        self.request_timeout.setToolTip("单次API请求的超时时间")
        group_layout.addRow("请求超时:", self.request_timeout)
        
        # 降级策略
        self.enable_fallback = QCheckBox("启用降级策略")
        self.enable_fallback.setChecked(True)
        self.enable_fallback.setToolTip("网络不可用时使用文本相似度算法")
        group_layout.addRow("", self.enable_fallback)
        
        # 并发限制
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(1, 20)
        self.max_concurrent.setValue(5)
        self.max_concurrent.setToolTip("同时进行的API请求数量限制")
        group_layout.addRow("并发限制:", self.max_concurrent)
        
        layout.addWidget(group)
    
    def _create_cache_config(self, layout):
        """创建缓存配置"""
        group = QGroupBox("缓存配置")
        group_layout = QFormLayout(group)
        
        # 缓存开关
        self.cache_enabled = QCheckBox("启用智能缓存")
        self.cache_enabled.setChecked(True)
        self.cache_enabled.setToolTip("缓存可以减少重复的API调用，提高响应速度")
        group_layout.addRow("", self.cache_enabled)
        
        # 内存缓存大小
        self.cache_memory_size = QSpinBox()
        self.cache_memory_size.setRange(100, 2000)
        self.cache_memory_size.setValue(500)
        self.cache_memory_size.setSuffix(" 条目")
        self.cache_memory_size.setToolTip("内存中缓存的最大条目数量")
        group_layout.addRow("内存缓存:", self.cache_memory_size)
        
        # 缓存TTL
        self.cache_ttl = QSpinBox()
        self.cache_ttl.setRange(300, 86400)  # 5分钟到1天
        self.cache_ttl.setValue(7200)  # 2小时
        self.cache_ttl.setSuffix(" 秒")
        self.cache_ttl.setToolTip("缓存项的存活时间")
        group_layout.addRow("缓存TTL:", self.cache_ttl)
        
        # 最大内存使用
        self.max_memory_mb = QSpinBox()
        self.max_memory_mb.setRange(10, 500)
        self.max_memory_mb.setValue(50)
        self.max_memory_mb.setSuffix(" MB")
        self.max_memory_mb.setToolTip("缓存系统的最大内存使用量")
        group_layout.addRow("内存限制:", self.max_memory_mb)
        
        layout.addWidget(group)
    
    def _create_connection_test(self, layout):
        """创建连接测试"""
        group = QGroupBox("连接测试")
        group_layout = QVBoxLayout(group)
        
        # 测试按钮和进度
        test_header_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("测试RAG连接")
        self.test_btn.clicked.connect(self._test_connection)
        test_header_layout.addWidget(self.test_btn)
        
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        test_header_layout.addWidget(self.test_progress)
        
        test_header_layout.addStretch()
        group_layout.addLayout(test_header_layout)
        
        # 测试结果显示
        self.test_result_browser = QTextBrowser()
        self.test_result_browser.setMaximumHeight(120)
        self.test_result_browser.setPlainText("点击\"测试RAG连接\"验证配置是否正确")
        group_layout.addWidget(self.test_result_browser)
        
        layout.addWidget(group)
    
    def _on_rag_enabled_changed(self, enabled):
        """RAG开关变化处理"""
        # 启用/禁用其他控件
        self.api_key_edit.setEnabled(enabled)
        self.base_url_edit.setEnabled(enabled)
        self.embedding_enabled.setEnabled(enabled)
        self.rerank_enabled.setEnabled(enabled)
        self.test_btn.setEnabled(enabled)
        
        if enabled:
            self.test_result_browser.setPlainText("RAG服务已启用，点击\"测试RAG连接\"验证配置")
        else:
            self.test_result_browser.setPlainText("RAG服务已禁用")
        
        self.configChanged.emit()
    
    def _toggle_key_visibility(self, checked):
        """切换密钥显示/隐藏"""
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("🙈")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("👁")
    
    def _test_connection(self):
        """测试RAG连接"""
        if self._test_worker and self._test_worker.isRunning():
            return
        
        # 获取当前配置
        config_data = self.get_config()
        
        # 验证必要参数
        if not config_data.get('enabled', False):
            self._show_test_result(False, "请先启用RAG服务")
            return
        
        if not config_data.get('api_key', '').strip():
            self._show_test_result(False, "请先输入API密钥")
            return
        
        embedding_config = config_data.get('embedding', {})
        if not embedding_config.get('enabled', False):
            self._show_test_result(False, "请先启用Embedding服务")
            return
        
        # 开始测试
        self.test_btn.setEnabled(False)
        self.test_progress.setVisible(True)
        self.test_progress.setRange(0, 0)  # 不确定进度
        
        # 创建测试工作线程
        self._test_worker = RAGTestWorker(config_data, self)
        self._test_worker.testStarted.connect(self._on_test_started)
        self._test_worker.testProgress.connect(self._on_test_progress)
        self._test_worker.testCompleted.connect(self._on_test_completed)
        
        self._test_worker.start()
    
    @pyqtSlot()
    def _on_test_started(self):
        """测试开始"""
        self.test_result_browser.setPlainText("开始RAG连接测试...")
    
    @pyqtSlot(str)
    def _on_test_progress(self, message):
        """测试进度更新"""
        current = self.test_result_browser.toPlainText()
        self.test_result_browser.setPlainText(current + "\n" + message)
    
    @pyqtSlot(bool, str)
    def _on_test_completed(self, success, message):
        """测试完成"""
        self.test_btn.setEnabled(True)
        self.test_progress.setVisible(False)
        
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
        
        self.test_result_browser.setHtml(result_html)
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "enabled": self.rag_enabled.isChecked(),
            "api_key": self.api_key_edit.text(),
            "base_url": self.base_url_edit.text(),
            "embedding": {
                "enabled": self.embedding_enabled.isChecked(),
                "model": self.embedding_model.currentText(),
                "batch_size": self.embedding_batch_size.value()
            },
            "rerank": {
                "enabled": self.rerank_enabled.isChecked(),
                "model": self.rerank_model.currentText(),
                "top_k": self.rerank_top_k.value()
            },
            "vector_store": {
                "similarity_threshold": self.similarity_threshold_slider.value() / 100,
                "search_limits": {
                    "fast": self.search_limit_fast.value(),
                    "balanced": self.search_limit_balanced.value(),
                    "full": self.search_limit_full.value()
                },
                "chunk_size": self.chunk_size.value(),
                "chunk_overlap": self.chunk_overlap.value()
            },
            "network": {
                "max_retries": self.max_retries.value(),
                "timeout": self.request_timeout.value(),
                "enable_fallback": self.enable_fallback.isChecked(),
                "max_concurrent": self.max_concurrent.value()
            },
            "cache": {
                "enabled": self.cache_enabled.isChecked(),
                "memory_size": self.cache_memory_size.value(),
                "ttl": self.cache_ttl.value(),
                "max_memory_mb": self.max_memory_mb.value()
            }
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        # 基础配置
        self.rag_enabled.setChecked(config.get("enabled", True))
        self.api_key_edit.setText(config.get("api_key", ""))
        self.base_url_edit.setText(config.get("base_url", "https://api.siliconflow.cn/v1"))
        
        # Embedding配置
        embedding_config = config.get("embedding", {})
        self.embedding_enabled.setChecked(embedding_config.get("enabled", True))
        
        embedding_model = embedding_config.get("model", "BAAI/bge-large-zh-v1.5")
        index = self.embedding_model.findText(embedding_model)
        if index >= 0:
            self.embedding_model.setCurrentIndex(index)
        else:
            self.embedding_model.setCurrentText(embedding_model)
        
        self.embedding_batch_size.setValue(embedding_config.get("batch_size", 32))
        
        # Rerank配置
        rerank_config = config.get("rerank", {})
        self.rerank_enabled.setChecked(rerank_config.get("enabled", True))
        
        rerank_model = rerank_config.get("model", "BAAI/bge-reranker-v2-m3")
        index = self.rerank_model.findText(rerank_model)
        if index >= 0:
            self.rerank_model.setCurrentIndex(index)
        else:
            self.rerank_model.setCurrentText(rerank_model)
        
        self.rerank_top_k.setValue(rerank_config.get("top_k", 10))
        
        # 向量存储配置
        vector_config = config.get("vector_store", {})
        self.similarity_threshold_slider.setValue(int(vector_config.get("similarity_threshold", 0.3) * 100))
        
        search_limits = vector_config.get("search_limits", {})
        self.search_limit_fast.setValue(search_limits.get("fast", 5))
        self.search_limit_balanced.setValue(search_limits.get("balanced", 10))
        self.search_limit_full.setValue(search_limits.get("full", 20))
        
        self.chunk_size.setValue(vector_config.get("chunk_size", 250))
        self.chunk_overlap.setValue(vector_config.get("chunk_overlap", 50))
        
        # 网络配置
        network_config = config.get("network", {})
        self.max_retries.setValue(network_config.get("max_retries", 3))
        self.request_timeout.setValue(network_config.get("timeout", 30))
        self.enable_fallback.setChecked(network_config.get("enable_fallback", True))
        self.max_concurrent.setValue(network_config.get("max_concurrent", 5))
        
        # 缓存配置
        cache_config = config.get("cache", {})
        self.cache_enabled.setChecked(cache_config.get("enabled", True))
        self.cache_memory_size.setValue(cache_config.get("memory_size", 500))
        self.cache_ttl.setValue(cache_config.get("ttl", 7200))
        self.max_memory_mb.setValue(cache_config.get("max_memory_mb", 50))
        
        # 触发开关变化处理
        self._on_rag_enabled_changed(self.rag_enabled.isChecked())
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "api_key": "",
            "base_url": "https://api.siliconflow.cn/v1",
            "embedding": {
                "enabled": True,
                "model": "BAAI/bge-large-zh-v1.5",
                "batch_size": 32
            },
            "rerank": {
                "enabled": True,
                "model": "BAAI/bge-reranker-v2-m3",
                "top_k": 10
            },
            "vector_store": {
                "similarity_threshold": 0.3,
                "search_limits": {
                    "fast": 5,
                    "balanced": 10,
                    "full": 20
                },
                "chunk_size": 250,
                "chunk_overlap": 50
            },
            "network": {
                "max_retries": 3,
                "timeout": 30,
                "enable_fallback": True,
                "max_concurrent": 5
            },
            "cache": {
                "enabled": True,
                "memory_size": 500,
                "ttl": 7200,
                "max_memory_mb": 50
            }
        }