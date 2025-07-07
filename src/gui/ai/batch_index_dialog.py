"""
批量索引对话框
允许用户对现有项目文档批量建立RAG索引
"""

import logging
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QProgressBar, QTextEdit, QCheckBox,
    QGroupBox, QSplitter, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class BatchIndexWorker(QThread):
    """批量索引工作线程"""
    
    progressChanged = pyqtSignal(int, int, str)  # current, total, current_doc
    statusChanged = pyqtSignal(str)  # status message
    documentIndexed = pyqtSignal(str, bool, str)  # doc_id, success, message
    finished = pyqtSignal(int, int)  # success_count, total_count
    
    def __init__(self, ai_manager, documents: Dict[str, str]):
        super().__init__()
        self.ai_manager = ai_manager
        self.documents = documents
        self.should_stop = False
        
    def run(self):
        """执行批量索引"""
        try:
            total_count = len(self.documents)
            success_count = 0
            
            self.statusChanged.emit("开始批量索引...")
            
            for i, (doc_id, content) in enumerate(self.documents.items()):
                if self.should_stop:
                    break
                
                self.progressChanged.emit(i, total_count, doc_id)
                
                try:
                    # 执行索引
                    self.ai_manager.index_document_sync(doc_id, content)
                    success_count += 1
                    self.documentIndexed.emit(doc_id, True, "索引成功")
                    
                except Exception as e:
                    error_msg = f"索引失败: {str(e)}"
                    logger.error(f"批量索引文档失败: {doc_id}, 错误: {e}")
                    self.documentIndexed.emit(doc_id, False, error_msg)
                
                # 添加小延迟，避免API过载
                self.msleep(100)
            
            self.finished.emit(success_count, total_count)
            
        except Exception as e:
            logger.error(f"批量索引工作线程异常: {e}")
            self.statusChanged.emit(f"批量索引失败: {str(e)}")
    
    def stop(self):
        """停止索引"""
        self.should_stop = True


class BatchIndexDialog(QDialog):
    """批量索引对话框"""
    
    def __init__(self, parent=None, ai_manager=None, project_manager=None):
        super().__init__(parent)
        
        self.ai_manager = ai_manager
        self.project_manager = project_manager
        self.worker = None
        
        self._init_ui()
        self._load_documents()
        
        # 设置对话框属性
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        self.setWindowTitle("批量索引管理")
        
        logger.debug("批量索引对话框已初始化")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题和说明
        title_label = QLabel("批量索引管理")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        desc_label = QLabel("为项目中的文档批量建立RAG向量索引，提升AI补全效果")
        desc_label.setStyleSheet("color: #666; margin-bottom: 8px;")
        layout.addWidget(desc_label)
        
        # 主要内容分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # 文档选择区域
        self._create_document_selection(splitter)
        
        # 索引进度区域
        self._create_progress_area(splitter)
        
        # 日志区域
        self._create_log_area(splitter)
        
        # 设置分割器比例
        splitter.setSizes([300, 100, 200])
        
        # 按钮区域
        self._create_button_area(layout)
    
    def _create_document_selection(self, parent):
        """创建文档选择区域"""
        group = QGroupBox("选择要索引的文档")
        layout = QVBoxLayout(group)
        
        # 全选/取消全选按钮
        select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all_documents)
        select_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("取消全选")
        self.select_none_btn.clicked.connect(self._select_no_documents)
        select_layout.addWidget(self.select_none_btn)
        
        select_layout.addStretch()
        
        # 只索引未索引的文档选项
        self.only_unindexed_cb = QCheckBox("只索引未索引的文档")
        self.only_unindexed_cb.setChecked(True)
        self.only_unindexed_cb.toggled.connect(self._filter_documents)
        select_layout.addWidget(self.only_unindexed_cb)
        
        layout.addLayout(select_layout)
        
        # 文档树
        self.document_tree = QTreeWidget()
        self.document_tree.setHeaderLabels(["文档名称", "状态", "字数", "类型"])
        self.document_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.document_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.document_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.document_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.document_tree)
        
        parent.addWidget(group)
    
    def _create_progress_area(self, parent):
        """创建进度区域"""
        group = QGroupBox("索引进度")
        layout = QVBoxLayout(group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        parent.addWidget(group)
    
    def _create_log_area(self, parent):
        """创建日志区域"""
        group = QGroupBox("索引日志")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        font = QFont("Consolas", 9)
        self.log_text.setFont(font)
        layout.addWidget(self.log_text)
        
        parent.addWidget(group)
    
    def _create_button_area(self, layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        # 统计信息
        self.stats_label = QLabel("选择了 0 个文档")
        button_layout.addWidget(self.stats_label)
        
        button_layout.addStretch()
        
        # 开始索引按钮
        self.start_btn = QPushButton("开始索引")
        self.start_btn.clicked.connect(self._start_indexing)
        button_layout.addWidget(self.start_btn)
        
        # 停止索引按钮
        self.stop_btn = QPushButton("停止索引")
        self.stop_btn.clicked.connect(self._stop_indexing)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_documents(self):
        """加载项目文档"""
        if not self.project_manager:
            return
        
        try:
            current_project = self.project_manager.get_current_project()
            if not current_project:
                self.log_text.append("⚠️ 没有打开的项目")
                return
            
            self.document_tree.clear()
            
            # 获取索引统计信息
            index_stats = {}
            if self.ai_manager and hasattr(self.ai_manager, '_vector_store'):
                try:
                    stats = self.ai_manager._vector_store.get_stats()
                    index_stats = stats.get('documents', {})
                except:
                    pass
            
            # 添加文档到树
            for doc_id, document in current_project.documents.items():
                item = QTreeWidgetItem()
                item.setText(0, document.name or "未命名文档")
                
                # 检查索引状态
                is_indexed = doc_id in index_stats
                item.setText(1, "已索引" if is_indexed else "未索引")
                
                # 字数统计
                word_count = len(document.content) if document.content else 0
                item.setText(2, f"{word_count:,}")
                
                # 文档类型
                doc_type = document.document_type.value if hasattr(document.document_type, 'value') else str(document.document_type)
                item.setText(3, doc_type)
                
                # 设置复选框
                item.setCheckState(0, Qt.CheckState.Unchecked)
                
                # 存储文档信息
                item.setData(0, Qt.ItemDataRole.UserRole, {
                    'doc_id': doc_id,
                    'content': document.content or "",
                    'is_indexed': is_indexed
                })
                
                # 设置样式
                if is_indexed:
                    item.setForeground(1, item.foreground(1).color().lighter(150))
                
                self.document_tree.addTopLevelItem(item)
            
            # 应用过滤
            self._filter_documents()
            
            self.log_text.append(f"✅ 加载了 {self.document_tree.topLevelItemCount()} 个文档")
            
        except Exception as e:
            logger.error(f"加载文档失败: {e}")
            self.log_text.append(f"❌ 加载文档失败: {str(e)}")
    
    def _filter_documents(self):
        """根据过滤条件显示/隐藏文档"""
        only_unindexed = self.only_unindexed_cb.isChecked()
        
        for i in range(self.document_tree.topLevelItemCount()):
            item = self.document_tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            
            if only_unindexed:
                # 只显示未索引的文档
                should_show = not data.get('is_indexed', False)
                item.setHidden(not should_show)
                
                # 自动选中未索引的文档
                if should_show and data.get('content', '').strip():
                    item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
            else:
                # 显示所有文档
                item.setHidden(False)
        
        self._update_stats()
    
    def _select_all_documents(self):
        """全选文档"""
        for i in range(self.document_tree.topLevelItemCount()):
            item = self.document_tree.topLevelItem(i)
            if not item.isHidden():
                item.setCheckState(0, Qt.CheckState.Checked)
        self._update_stats()
    
    def _select_no_documents(self):
        """取消全选"""
        for i in range(self.document_tree.topLevelItemCount()):
            item = self.document_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)
        self._update_stats()
    
    def _update_stats(self):
        """更新统计信息"""
        selected_count = 0
        total_words = 0
        
        for i in range(self.document_tree.topLevelItemCount()):
            item = self.document_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected_count += 1
                data = item.data(0, Qt.ItemDataRole.UserRole)
                content = data.get('content', '')
                total_words += len(content)
        
        self.stats_label.setText(f"选择了 {selected_count} 个文档，共 {total_words:,} 字符")
        self.start_btn.setEnabled(selected_count > 0)
    
    def _get_selected_documents(self) -> Dict[str, str]:
        """获取选中的文档"""
        selected_docs = {}
        
        for i in range(self.document_tree.topLevelItemCount()):
            item = self.document_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                doc_id = data.get('doc_id')
                content = data.get('content', '')
                
                if doc_id and content.strip():
                    selected_docs[doc_id] = content
        
        return selected_docs
    
    def _start_indexing(self):
        """开始批量索引"""
        if not self.ai_manager:
            QMessageBox.warning(self, "错误", "AI管理器未初始化")
            return
        
        selected_docs = self._get_selected_documents()
        if not selected_docs:
            QMessageBox.information(self, "提示", "请选择要索引的文档")
            return
        
        # 检查RAG服务状态
        if not self.ai_manager._rag_service:
            QMessageBox.warning(self, "RAG服务不可用", 
                              "RAG服务未初始化，请检查配置。\n" +
                              "您可以通过AI配置对话框进行设置。")
            return
        
        # 禁用UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.only_unindexed_cb.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_docs))
        self.progress_bar.setValue(0)
        
        # 清空日志
        self.log_text.clear()
        self.log_text.append(f"🚀 开始批量索引 {len(selected_docs)} 个文档...")
        
        # 启动工作线程
        self.worker = BatchIndexWorker(self.ai_manager, selected_docs)
        self.worker.progressChanged.connect(self._on_progress_changed)
        self.worker.statusChanged.connect(self._on_status_changed)
        self.worker.documentIndexed.connect(self._on_document_indexed)
        self.worker.finished.connect(self._on_indexing_finished)
        self.worker.start()
    
    def _stop_indexing(self):
        """停止索引"""
        if self.worker:
            self.worker.stop()
            self.status_label.setText("正在停止...")
            self.stop_btn.setEnabled(False)
    
    @pyqtSlot(int, int, str)
    def _on_progress_changed(self, current, total, current_doc):
        """进度更新"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在索引: {current_doc} ({current + 1}/{total})")
    
    @pyqtSlot(str)
    def _on_status_changed(self, status):
        """状态更新"""
        self.status_label.setText(status)
        self.log_text.append(f"ℹ️ {status}")
    
    @pyqtSlot(str, bool, str)
    def _on_document_indexed(self, doc_id, success, message):
        """文档索引完成"""
        icon = "✅" if success else "❌"
        self.log_text.append(f"{icon} {doc_id}: {message}")
        
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    @pyqtSlot(int, int)
    def _on_indexing_finished(self, success_count, total_count):
        """索引完成"""
        # 恢复UI
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_all_btn.setEnabled(True)
        self.select_none_btn.setEnabled(True)
        self.only_unindexed_cb.setEnabled(True)
        
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 显示完成信息
        if success_count == total_count:
            self.status_label.setText(f"✅ 索引完成！成功索引 {success_count} 个文档")
            self.log_text.append(f"🎉 批量索引完成！成功 {success_count}/{total_count}")
        else:
            self.status_label.setText(f"⚠️ 索引完成，成功 {success_count}/{total_count}")
            self.log_text.append(f"⚠️ 批量索引完成，成功 {success_count}/{total_count}")
        
        # 重新加载文档状态
        self._load_documents()
        
        # 清理工作线程
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭",
                "索引正在进行中，确定要关闭对话框吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop()
                self.worker.wait(3000)  # 等待最多3秒
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()