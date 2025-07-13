"""
RAG索引管理对话框
提供项目文档的向量索引管理功能
"""

import logging
from typing import Dict, Any, Optional, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QProgressBar, QTextBrowser, QSplitter,
    QGroupBox, QCheckBox, QSpinBox, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class IndexingWorker(QThread):
    """索引处理工作线程"""
    
    progressUpdated = pyqtSignal(int, str)  # 进度, 消息
    indexingCompleted = pyqtSignal(bool, str)  # 成功, 消息
    
    def __init__(self, ai_manager, documents: List[Dict], parent=None):
        super().__init__(parent)
        self.ai_manager = ai_manager
        self.documents = documents
        self._stopped = False
        
    def run(self):
        """执行索引处理"""
        try:
            total = len(self.documents)
            self.progressUpdated.emit(0, f"开始处理 {total} 个文档...")
            
            success_count = 0
            for i, doc in enumerate(self.documents):
                if self._stopped:
                    break
                    
                try:
                    # 模拟索引处理
                    doc_id = doc.get('id', f'doc_{i}')
                    title = doc.get('title', '未命名文档')
                    content = doc.get('content', '')
                    
                    self.progressUpdated.emit(
                        int((i + 1) / total * 100), 
                        f"正在索引: {title} ({len(content)} 字符)"
                    )
                    
                    # 如果有AI管理器，使用同步索引方法
                    if self.ai_manager:
                        if hasattr(self.ai_manager, 'index_document_sync'):
                            success = self.ai_manager.index_document_sync(doc_id, content)
                            if not success:
                                raise Exception("同步索引方法返回失败")
                        elif (hasattr(self.ai_manager, 'rag_service') and 
                              self.ai_manager.rag_service and 
                              hasattr(self.ai_manager.rag_service, 'index_document')):
                            # 直接使用RAG服务的index_document方法
                            success = self.ai_manager.rag_service.index_document(doc_id, content)
                            if not success:
                                raise Exception("RAG索引方法返回失败")
                        else:
                            raise Exception("没有可用的索引方法")
                    
                    success_count += 1
                    self.msleep(100)  # 模拟处理时间
                    
                except Exception as e:
                    logger.error(f"索引文档 {doc.get('title', 'unknown')} 失败: {e}")
                    
            if self._stopped:
                self.indexingCompleted.emit(False, "索引处理已被用户取消")
            else:
                self.indexingCompleted.emit(
                    True, 
                    f"索引处理完成！成功处理 {success_count}/{total} 个文档"
                )
                
        except Exception as e:
            self.indexingCompleted.emit(False, f"索引处理失败: {str(e)}")
    
    def stop(self):
        """停止处理"""
        self._stopped = True


class RAGIndexDialog(QDialog):
    """RAG索引管理对话框"""
    
    def __init__(self, ai_manager=None, project_manager=None, parent=None):
        super().__init__(parent)
        self.ai_manager = ai_manager
        self.project_manager = project_manager
        self.indexing_worker = None
        
        self.setWindowTitle("RAG向量索引管理")
        self.setModal(True)
        self.resize(900, 700)
        
        self._init_ui()
        self._load_document_list()
        
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题
        title_label = QLabel("RAG向量索引管理")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # 说明
        info_label = QLabel(
            "管理项目文档的向量索引。选择需要索引的文档，系统将为其创建向量表示以支持AI上下文检索。"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(info_label)
        
        # 主要内容区域
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)
        
        # 左侧：文档列表
        self._create_document_list(main_splitter)
        
        # 右侧：索引操作和日志
        self._create_index_controls(main_splitter)
        
        # 设置分割器比例
        main_splitter.setSizes([500, 400])
        
        # 底部按钮
        self._create_buttons(layout)
        
    def _create_document_list(self, parent):
        """创建文档列表"""
        # 文档列表组
        docs_group = QGroupBox("项目文档")
        docs_layout = QVBoxLayout(docs_group)
        
        # 操作按钮行
        ops_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all_documents)
        ops_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.clicked.connect(self._deselect_all_documents)
        ops_layout.addWidget(self.deselect_all_btn)
        
        ops_layout.addStretch()
        
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self._load_document_list)
        ops_layout.addWidget(self.refresh_btn)
        
        docs_layout.addLayout(ops_layout)
        
        # 文档表格
        self.docs_table = QTableWidget()
        self.docs_table.setColumnCount(4)
        self.docs_table.setHorizontalHeaderLabels(["选择", "文档标题", "字符数", "索引状态"])
        
        # 设置表格属性
        header = self.docs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        
        self.docs_table.setColumnWidth(0, 60)
        self.docs_table.setColumnWidth(2, 80)
        self.docs_table.setColumnWidth(3, 100)
        
        docs_layout.addWidget(self.docs_table)
        parent.addWidget(docs_group)
        
    def _create_index_controls(self, parent):
        """创建索引控制区域"""
        controls_group = QGroupBox("索引操作")
        controls_layout = QVBoxLayout(controls_group)
        
        # 索引配置
        config_group = QGroupBox("配置")
        config_layout = QVBoxLayout(config_group)
        
        self.batch_size_label = QLabel("批处理大小:")
        config_layout.addWidget(self.batch_size_label)
        
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 50)
        self.batch_size_spin.setValue(10)
        self.batch_size_spin.setToolTip("同时处理的文档数量")
        config_layout.addWidget(self.batch_size_spin)
        
        self.force_reindex = QCheckBox("强制重新索引已索引文档")
        self.force_reindex.setToolTip("即使文档已经被索引，也重新处理")
        config_layout.addWidget(self.force_reindex)
        
        controls_layout.addWidget(config_group)
        
        # 操作按钮
        self.start_index_btn = QPushButton("开始索引")
        self.start_index_btn.clicked.connect(self._start_indexing)
        controls_layout.addWidget(self.start_index_btn)
        
        self.stop_index_btn = QPushButton("停止索引")
        self.stop_index_btn.clicked.connect(self._stop_indexing)
        self.stop_index_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_index_btn)
        
        # 进度显示
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        controls_layout.addWidget(self.progress_bar)
        
        # 日志输出
        log_label = QLabel("处理日志:")
        controls_layout.addWidget(log_label)
        
        self.log_browser = QTextBrowser()
        self.log_browser.setMaximumHeight(200)
        controls_layout.addWidget(self.log_browser)
        
        controls_layout.addStretch()
        parent.addWidget(controls_group)
        
    def _create_buttons(self, layout):
        """创建底部按钮"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
    def _load_document_list(self):
        """加载文档列表"""
        try:
            self.docs_table.setRowCount(0)
            
            if not self.project_manager:
                self._log_message("项目管理器不可用")
                return
                
            # 获取所有文档 - 返回的是字典格式 {doc_id: {title, type, status}}
            documents_dict = {}
            try:
                if hasattr(self.project_manager, 'get_all_documents'):
                    documents_dict = self.project_manager.get_all_documents()
                else:
                    self._log_message("项目管理器不支持文档获取功能")
                    return
            except Exception as e:
                self._log_message(f"获取文档列表失败: {e}")
                return
                
            if not documents_dict:
                self._log_message("项目中没有找到文档")
                return
                
            # 填充表格
            self.docs_table.setRowCount(len(documents_dict))
            
            for row, (doc_id, doc_info) in enumerate(documents_dict.items()):
                # 选择框
                checkbox = QCheckBox()
                self.docs_table.setCellWidget(row, 0, checkbox)
                
                # 文档标题
                title = doc_info.get('title', '未命名文档')
                title_item = QTableWidgetItem(title)
                
                # 构建完整的文档数据用于后续处理
                doc_data = {
                    'id': doc_id,
                    'title': title,
                    'type': doc_info.get('type', 'SCENE'),
                    'status': doc_info.get('status', 'draft')
                }
                
                # 获取文档内容
                try:
                    if hasattr(self.project_manager, 'get_document_content'):
                        content = self.project_manager.get_document_content(doc_id) or ''
                        doc_data['content'] = content
                    else:
                        doc_data['content'] = ''
                except Exception as e:
                    logger.warning(f"获取文档 {doc_id} 内容失败: {e}")
                    doc_data['content'] = ''
                
                title_item.setData(Qt.ItemDataRole.UserRole, doc_data)  # 存储文档数据
                self.docs_table.setItem(row, 1, title_item)
                
                # 字符数
                content = doc_data['content']
                char_count = len(content)
                char_item = QTableWidgetItem(str(char_count))
                char_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.docs_table.setItem(row, 2, char_item)
                
                # 检查索引状态
                status_text = "未索引"
                status_color = None
                
                try:
                    # 检查文档是否已被索引
                    if (self.ai_manager and 
                        hasattr(self.ai_manager, 'rag_service') and 
                        self.ai_manager.rag_service and
                        hasattr(self.ai_manager.rag_service, '_vector_store') and
                        self.ai_manager.rag_service._vector_store):
                        
                        is_indexed = self.ai_manager.rag_service._vector_store.document_exists(doc_id)
                        if is_indexed:
                            status_text = "已索引"
                            from PyQt6.QtGui import QBrush, QColor
                            status_color = QBrush(QColor(144, 238, 144))  # lightgreen
                except Exception as e:
                    logger.debug(f"检查文档 {doc_id} 索引状态失败: {e}")
                
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if status_color:
                    status_item.setBackground(status_color)
                self.docs_table.setItem(row, 3, status_item)
                
            self._log_message(f"已加载 {len(documents_dict)} 个文档")
            
        except Exception as e:
            logger.error(f"加载文档列表失败: {e}")
            self._log_message(f"加载文档列表失败: {e}")
            
    def _select_all_documents(self):
        """全选文档"""
        for row in range(self.docs_table.rowCount()):
            checkbox = self.docs_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)
                
    def _deselect_all_documents(self):
        """取消全选文档"""
        for row in range(self.docs_table.rowCount()):
            checkbox = self.docs_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
                
    def _get_selected_documents(self) -> List[Dict]:
        """获取选中的文档"""
        selected_docs = []
        for row in range(self.docs_table.rowCount()):
            checkbox = self.docs_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                title_item = self.docs_table.item(row, 1)
                if title_item:
                    doc_data = title_item.data(Qt.ItemDataRole.UserRole)
                    if doc_data:
                        selected_docs.append(doc_data)
        return selected_docs
        
    def _start_indexing(self):
        """开始索引"""
        try:
            selected_docs = self._get_selected_documents()
            if not selected_docs:
                QMessageBox.warning(self, "警告", "请至少选择一个文档进行索引")
                return
                
            # 检查RAG服务
            rag_service = None
            if self.ai_manager and hasattr(self.ai_manager, 'rag_service'):
                rag_service = self.ai_manager.rag_service
                
            if not rag_service:
                self._log_message("RAG服务不可用，将模拟索引过程")
            else:
                self._log_message("RAG服务可用，开始实际索引")
                
            # 创建工作线程
            self.indexing_worker = IndexingWorker(self.ai_manager, selected_docs, self)
            self.indexing_worker.progressUpdated.connect(self._on_progress_updated)
            self.indexing_worker.indexingCompleted.connect(self._on_indexing_completed)
            
            # 更新UI状态
            self.start_index_btn.setEnabled(False)
            self.stop_index_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # 开始处理
            self.indexing_worker.start()
            self._log_message(f"开始索引 {len(selected_docs)} 个文档...")
            
        except Exception as e:
            logger.error(f"开始索引失败: {e}")
            self._log_message(f"开始索引失败: {e}")
            
    def _stop_indexing(self):
        """停止索引"""
        if self.indexing_worker and self.indexing_worker.isRunning():
            self.indexing_worker.stop()
            self._log_message("正在停止索引处理...")
            
    @pyqtSlot(int, str)
    def _on_progress_updated(self, progress: int, message: str):
        """处理进度更新"""
        self.progress_bar.setValue(progress)
        self._log_message(message)
        
    @pyqtSlot(bool, str)
    def _on_indexing_completed(self, success: bool, message: str):
        """处理索引完成"""
        self.start_index_btn.setEnabled(True)
        self.stop_index_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        self._log_message(message)
        
        if success:
            # 更新表格中的索引状态
            self._update_index_status()
            
    def _update_index_status(self):
        """更新索引状态显示"""
        # 重新加载文档列表以获取最新的索引状态
        self._log_message("正在刷新文档索引状态...")
        
        # 保存当前选中状态
        selected_docs = set()
        for row in range(self.docs_table.rowCount()):
            checkbox = self.docs_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                title_item = self.docs_table.item(row, 1)
                if title_item:
                    doc_data = title_item.data(Qt.ItemDataRole.UserRole)
                    if doc_data:
                        selected_docs.add(doc_data.get('id'))
        
        # 重新加载文档列表
        self._load_document_list()
        
        # 恢复选中状态
        for row in range(self.docs_table.rowCount()):
            title_item = self.docs_table.item(row, 1)
            if title_item:
                doc_data = title_item.data(Qt.ItemDataRole.UserRole)
                if doc_data and doc_data.get('id') in selected_docs:
                    checkbox = self.docs_table.cellWidget(row, 0)
                    if checkbox:
                        checkbox.setChecked(True)
        
        self._log_message("文档索引状态已刷新")
                    
    def _log_message(self, message: str):
        """添加日志消息"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_browser.append(f"[{timestamp}] {message}")
        
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.indexing_worker and self.indexing_worker.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭", 
                "索引处理正在进行中，确定要关闭对话框吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.indexing_worker.stop()
                self.indexing_worker.wait(3000)  # 等待3秒
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()