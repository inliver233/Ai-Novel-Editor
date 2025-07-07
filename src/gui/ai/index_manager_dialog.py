"""
RAG索引管理对话框
"""
import logging
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QLabel, QPushButton, QProgressBar, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QSplitter, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette

logger = logging.getLogger(__name__)


class IndexRebuildWorker(QThread):
    """索引重建工作线程"""
    
    progressChanged = pyqtSignal(int)  # 进度变化
    statusChanged = pyqtSignal(str)    # 状态变化
    finished = pyqtSignal(bool)        # 完成信号
    
    def __init__(self, ai_manager, documents: Dict[str, str]):
        super().__init__()
        self.ai_manager = ai_manager
        self.documents = documents
        self._should_stop = False
    
    def run(self):
        """执行索引重建"""
        try:
            total = len(self.documents)
            if total == 0:
                self.finished.emit(True)
                return
            
            self.statusChanged.emit("正在清理旧索引...")
            self.progressChanged.emit(0)
            
            # 清理旧索引
            if not self.ai_manager.clear_all_indexes():
                self.statusChanged.emit("清理旧索引失败")
                self.finished.emit(False)
                return
            
            self.statusChanged.emit("正在重建索引...")
            
            # 逐个处理文档并更新进度
            success_count = 0
            for i, (doc_id, content) in enumerate(self.documents.items()):
                if self._should_stop:
                    break
                    
                try:
                    self.statusChanged.emit(f"正在索引文档 {i+1}/{total}: {doc_id[:20]}...")
                    logger.info(f"[WORKER] 开始索引文档 {i+1}/{total}: {doc_id}")
                    logger.info(f"[WORKER] 文档内容长度: {len(content)} 字符")
                    
                    # 检查AI管理器类型
                    logger.info(f"[WORKER] AI管理器类型: {type(self.ai_manager)}")
                    logger.info(f"[WORKER] 是否有index_document_sync方法: {hasattr(self.ai_manager, 'index_document_sync')}")
                    
                    # 索引单个文档
                    logger.info(f"[WORKER] 调用index_document_sync方法...")
                    result = self.ai_manager.index_document_sync(doc_id, content)
                    logger.info(f"[WORKER] index_document_sync返回结果: {result}")
                    
                    if result:
                        success_count += 1
                        logger.info(f"[WORKER] 文档索引成功: {doc_id}")
                    else:
                        logger.warning(f"[WORKER] 文档索引失败: {doc_id}")
                    
                    # 更新进度
                    progress = int((i + 1) * 100 / total)
                    self.progressChanged.emit(progress)
                    
                except Exception as e:
                    logger.error(f"索引文档 {doc_id} 时出错: {e}")
                    continue
            
            # 完成处理
            if success_count > 0:
                self.progressChanged.emit(100)
                self.statusChanged.emit(f"索引重建完成，成功处理了 {success_count}/{total} 个文档")
                self.finished.emit(True)
            else:
                self.statusChanged.emit("索引重建失败，没有文档被成功索引")
                self.finished.emit(False)
            
        except Exception as e:
            logger.error(f"索引重建过程中出错: {e}")
            self.statusChanged.emit(f"索引重建出错: {str(e)}")
            self.finished.emit(False)
    
    def stop(self):
        """停止工作"""
        self._should_stop = True


class IndexManagerDialog(QDialog):
    """索引管理对话框"""
    
    def __init__(self, parent=None, ai_manager=None, project_manager=None):
        super().__init__(parent)
        self.ai_manager = ai_manager
        self.project_manager = project_manager
        self._rebuild_worker = None
        
        self.setWindowTitle("RAG索引管理")
        self.setMinimumSize(800, 600)
        
        self._init_ui()
        self._init_signals()
        self._refresh_stats()
        
        # 自动刷新定时器
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_stats)
        self._refresh_timer.start(5000)  # 每5秒刷新一次
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题
        title_label = QLabel("RAG索引管理")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 主内容区域
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(main_splitter)
        
        # 统计信息区域
        stats_group = self._create_stats_group()
        main_splitter.addWidget(stats_group)
        
        # 已索引文档列表
        docs_group = self._create_docs_group()
        main_splitter.addWidget(docs_group)
        
        # 操作区域
        actions_group = self._create_actions_group()
        main_splitter.addWidget(actions_group)
        
        # 设置分割器比例
        main_splitter.setSizes([200, 200, 150])
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_stats_group(self) -> QGroupBox:
        """创建统计信息组"""
        group = QGroupBox("索引统计")
        layout = QVBoxLayout(group)
        
        # 创建统计标签
        self.stats_labels = {
            'total_documents': QLabel("总文档数: --"),
            'total_chunks': QLabel("总文本块数: --"),
            'index_size': QLabel("索引大小: --"),
            'last_updated': QLabel("最后更新: --"),
            'search_count': QLabel("搜索次数: --"),
            'avg_search_time': QLabel("平均搜索时间: --")
        }
        
        # 添加到布局
        for label in self.stats_labels.values():
            label.setStyleSheet("QLabel { padding: 4px; }")
            layout.addWidget(label)
        
        return group
    
    def _create_docs_group(self) -> QGroupBox:
        """创建已索引文档组"""
        group = QGroupBox("已索引文档")
        layout = QVBoxLayout(group)
        
        # 创建表格
        self.docs_table = QTableWidget()
        self.docs_table.setColumnCount(2)
        self.docs_table.setHorizontalHeaderLabels(["文档ID", "索引状态"])
        
        # 设置表格属性
        header = self.docs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        self.docs_table.setAlternatingRowColors(True)
        self.docs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.docs_table)
        
        return group
    
    def _create_actions_group(self) -> QGroupBox:
        """创建操作区域组"""
        group = QGroupBox("操作")
        layout = QVBoxLayout(group)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新统计")
        self.refresh_btn.clicked.connect(self._force_refresh_stats)
        button_layout.addWidget(self.refresh_btn)
        
        # 重新初始化RAG按钮
        self.reinit_btn = QPushButton("重新初始化RAG")
        self.reinit_btn.setToolTip("强制重新初始化RAG服务")
        self.reinit_btn.clicked.connect(self._reinit_rag)
        button_layout.addWidget(self.reinit_btn)
        
        # 重建索引按钮
        self.rebuild_btn = QPushButton("重建所有索引")
        self.rebuild_btn.clicked.connect(self._rebuild_indexes)
        button_layout.addWidget(self.rebuild_btn)
        
        # 批量索引按钮
        self.batch_index_btn = QPushButton("批量索引未索引文档")
        self.batch_index_btn.setToolTip("仅对有内容但未索引的文档建立索引")
        self.batch_index_btn.clicked.connect(self._batch_index_unindexed)
        button_layout.addWidget(self.batch_index_btn)
        
        # 清空索引按钮
        self.clear_btn = QPushButton("清空所有索引")
        self.clear_btn.clicked.connect(self._clear_indexes)
        button_layout.addWidget(self.clear_btn)
        
        # 缓存管理按钮
        self.clear_cache_btn = QPushButton("清空缓存")
        self.clear_cache_btn.setToolTip("清空RAG缓存以节省内存")
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        button_layout.addWidget(self.clear_cache_btn)
        
        self.cleanup_cache_btn = QPushButton("清理缓存")
        self.cleanup_cache_btn.setToolTip("清理过期的缓存条目")
        self.cleanup_cache_btn.clicked.connect(self._cleanup_cache)
        button_layout.addWidget(self.cleanup_cache_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        return group
    
    def _init_signals(self):
        """初始化信号连接"""
        pass
    
    def _refresh_stats(self):
        """刷新统计信息"""
        try:
            logger.info("开始刷新索引统计信息")
            
            if not self.ai_manager:
                logger.warning("AI管理器不可用")
                self._set_stats_unavailable()
                return
            
            # 如果RAG服务不可用，尝试重新初始化
            if not self.ai_manager.rag_service:
                logger.info("RAG服务不可用，尝试重新初始化...")
                if self.ai_manager.force_reinit_rag():
                    logger.info("RAG服务重新初始化成功")
                else:
                    logger.warning("RAG服务重新初始化失败")
                    self._set_stats_unavailable()
                    return
            
            # 获取索引统计
            stats = self.ai_manager.get_index_stats()
            logger.info(f"获取到的统计信息: {stats}")
            
            if stats:
                self.stats_labels['total_documents'].setText(f"总文档数: {stats.total_documents}")
                self.stats_labels['total_chunks'].setText(f"总文本块数: {stats.total_chunks}")
                self.stats_labels['index_size'].setText(f"索引大小: {stats.index_size_mb:.2f} MB")
                self.stats_labels['last_updated'].setText(f"最后更新: {stats.last_updated}")
                
                # 更新文档列表
                self._update_docs_table(stats.indexed_documents)
                
            else:
                logger.warning("未获取到统计信息")
                self._set_stats_unavailable()
                
        except Exception as e:
            logger.error(f"刷新统计信息失败: {e}", exc_info=True)
            self._set_stats_unavailable()
    
    def _force_refresh_stats(self):
        """强制刷新统计信息（手动点击）"""
        logger.info("用户手动触发刷新统计信息")
        self._refresh_stats()
    
    def _reinit_rag(self):
        """重新初始化RAG服务"""
        if not self.ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器不可用")
            return
        
        try:
            # 禁用按钮
            self.reinit_btn.setEnabled(False)
            self.rebuild_btn.setEnabled(False)
            self.batch_index_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            
            self.status_label.setText("正在重新初始化RAG服务...")
            
            success = self.ai_manager.force_reinit_rag()
            
            if success:
                self.status_label.setText("RAG服务重新初始化成功")
                QMessageBox.information(self, "成功", "RAG服务已重新初始化！")
            else:
                self.status_label.setText("RAG服务重新初始化失败")
                QMessageBox.warning(self, "失败", "RAG服务重新初始化失败，请检查配置和日志。")
            
            # 刷新统计
            self._refresh_stats()
            
        except Exception as e:
            logger.error(f"重新初始化RAG失败: {e}")
            QMessageBox.critical(self, "错误", f"重新初始化RAG时出错：{str(e)}")
        finally:
            # 重新启用按钮
            self.reinit_btn.setEnabled(True)
            self.rebuild_btn.setEnabled(True)
            self.batch_index_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
    
    def _set_stats_unavailable(self):
        """设置统计信息不可用"""
        for key, label in self.stats_labels.items():
            if key == 'total_documents':
                label.setText("总文档数: 不可用")
            elif key == 'total_chunks':
                label.setText("总文本块数: 不可用")
            elif key == 'index_size':
                label.setText("索引大小: 不可用")
            elif key == 'last_updated':
                label.setText("最后更新: 不可用")
            elif key == 'search_count':
                label.setText("搜索次数: 不可用")
            elif key == 'avg_search_time':
                label.setText("平均搜索时间: 不可用")
        
        self.docs_table.setRowCount(0)
    
    def _update_docs_table(self, indexed_docs):
        """更新文档表格"""
        logger.info(f"更新文档表格，已索引文档: {indexed_docs}")
        
        # 获取项目中的所有文档
        all_docs = {}
        if self.project_manager and self.project_manager.get_current_project():
            project = self.project_manager.get_current_project()
            for doc_id, doc in project.documents.items():
                all_docs[doc_id] = doc.name
        
        logger.info(f"项目中的所有文档: {list(all_docs.keys())}")
        
        # 设置表格行数
        self.docs_table.setRowCount(len(all_docs))
        
        # 填充表格
        row = 0
        for doc_id, doc_name in all_docs.items():
            # 文档ID列
            name_item = QTableWidgetItem(f"{doc_name} ({doc_id})")
            self.docs_table.setItem(row, 0, name_item)
            
            # 检查文档内容以确定状态
            is_indexed = doc_id in indexed_docs
            
            # 获取文档内容来判断是否为空
            doc_has_content = False
            if self.project_manager and self.project_manager.get_current_project():
                project = self.project_manager.get_current_project()
                if doc_id in project.documents:
                    doc = project.documents[doc_id]
                    doc_has_content = bool(doc.content and doc.content.strip())
            
            # 确定状态文本
            if is_indexed:
                status = "已索引"
                color_role = QPalette.ColorRole.Link
            elif not doc_has_content:
                status = "空文档"
                color_role = QPalette.ColorRole.PlaceholderText
            else:
                status = "未索引"
                color_role = QPalette.ColorRole.WindowText
            
            status_item = QTableWidgetItem(status)
            status_item.setForeground(self.palette().color(color_role))
            
            logger.info(f"文档 '{doc_name}' (ID: {doc_id[:8]}...) 状态: {status} (有内容: {doc_has_content})")
            
            self.docs_table.setItem(row, 1, status_item)
            row += 1
    
    def _batch_index_unindexed(self):
        """批量索引未索引的文档"""
        if not self.ai_manager or not self.project_manager:
            QMessageBox.warning(self, "警告", "AI管理器或项目管理器不可用")
            return
        
        # 获取当前索引状态
        stats = self.ai_manager.get_index_stats()
        if not stats:
            QMessageBox.warning(self, "警告", "无法获取索引状态")
            return
        
        indexed_docs = set(stats.indexed_documents)
        
        # 获取所有有内容但未索引的文档
        project = self.project_manager.get_current_project()
        if not project:
            QMessageBox.warning(self, "警告", "没有打开的项目")
            return
        
        unindexed_docs = {}
        unindexed_count = 0
        
        for doc_id, doc in project.documents.items():
            # 检查文档是否有内容且未索引
            if doc.content and doc.content.strip() and doc_id not in indexed_docs:
                unindexed_docs[doc_id] = doc.content
                unindexed_count += 1
        
        if not unindexed_docs:
            QMessageBox.information(self, "提示", "没有找到需要索引的文档。\n所有有内容的文档都已经建立了索引。")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认", 
            f"发现 {unindexed_count} 个有内容但未索引的文档。\n确定要为这些文档建立索引吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        # 启动批量索引工作线程
        self._start_batch_index_worker(unindexed_docs)
    
    def _start_batch_index_worker(self, documents: Dict[str, str]):
        """启动批量索引工作线程"""
        # 禁用按钮
        self.batch_index_btn.setEnabled(False)
        self.rebuild_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 创建工作线程（复用重建索引的工作线程）
        self._rebuild_worker = IndexRebuildWorker(self.ai_manager, documents)
        self._rebuild_worker.progressChanged.connect(self.progress_bar.setValue)
        self._rebuild_worker.statusChanged.connect(self.status_label.setText)
        self._rebuild_worker.finished.connect(self._on_batch_index_finished)
        
        # 启动工作线程
        self._rebuild_worker.start()
    
    def _on_batch_index_finished(self, success: bool):
        """批量索引完成处理"""
        # 重新启用按钮
        self.batch_index_btn.setEnabled(True)
        self.rebuild_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 清理工作线程
        if self._rebuild_worker:
            self._rebuild_worker.deleteLater()
            self._rebuild_worker = None
        
        # 延迟刷新统计，确保数据已写入
        QTimer.singleShot(1000, self._refresh_stats)
        
        # 显示结果
        if success:
            QMessageBox.information(self, "成功", "批量索引完成！")
        else:
            QMessageBox.critical(self, "失败", "批量索引失败，请查看日志获取详细信息。")

    def _rebuild_indexes(self):
        """重建索引"""
        if not self.ai_manager or not self.project_manager:
            QMessageBox.warning(self, "警告", "AI管理器或项目管理器不可用")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认", 
            "重建索引将删除所有现有索引并重新创建。\n这可能需要较长时间，确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        # 获取所有文档
        project = self.project_manager.get_current_project()
        if not project:
            QMessageBox.warning(self, "警告", "没有打开的项目")
            return
        
        documents = {}
        for doc_id, doc in project.documents.items():
            if doc.content:  # 只处理有内容的文档
                documents[doc_id] = doc.content
        
        if not documents:
            QMessageBox.information(self, "提示", "没有找到需要索引的文档")
            return
        
        # 启动重建工作线程
        self._start_rebuild_worker(documents)
    
    def _start_rebuild_worker(self, documents: Dict[str, str]):
        """启动重建工作线程"""
        # 禁用按钮
        self.rebuild_btn.setEnabled(False)
        self.batch_index_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 创建工作线程
        self._rebuild_worker = IndexRebuildWorker(self.ai_manager, documents)
        self._rebuild_worker.progressChanged.connect(self.progress_bar.setValue)
        self._rebuild_worker.statusChanged.connect(self.status_label.setText)
        self._rebuild_worker.finished.connect(self._on_rebuild_finished)
        
        # 启动工作线程
        self._rebuild_worker.start()
    
    def _on_rebuild_finished(self, success: bool):
        """重建完成处理"""
        # 重新启用按钮
        self.rebuild_btn.setEnabled(True)
        self.batch_index_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 清理工作线程
        if self._rebuild_worker:
            self._rebuild_worker.deleteLater()
            self._rebuild_worker = None
        
        # 延迟刷新统计，确保数据已写入
        QTimer.singleShot(1000, self._refresh_stats)
        
        # 显示结果
        if success:
            QMessageBox.information(self, "成功", "索引重建完成！")
        else:
            QMessageBox.critical(self, "失败", "索引重建失败，请查看日志获取详细信息。")
    
    def _clear_indexes(self):
        """清空索引"""
        if not self.ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器不可用")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认", 
            "确定要清空所有索引吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        # 清空索引
        try:
            success = self.ai_manager.clear_all_indexes()
            
            if success:
                self.status_label.setText("所有索引已清空")
                self._refresh_stats()
                QMessageBox.information(self, "成功", "所有索引已清空！")
            else:
                QMessageBox.critical(self, "失败", "清空索引失败，请查看日志获取详细信息。")
                
        except Exception as e:
            logger.error(f"清空索引失败: {e}")
            QMessageBox.critical(self, "错误", f"清空索引时出错：{str(e)}")
    
    def _clear_cache(self):
        """清空缓存"""
        if not self.ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器不可用")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认", 
            "确定要清空所有RAG缓存吗？\n这将删除所有缓存的嵌入向量和重排序结果。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        try:
            self.ai_manager.clear_cache()
            self.status_label.setText("缓存已清空")
            QMessageBox.information(self, "成功", "RAG缓存已清空！")
            
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            QMessageBox.critical(self, "错误", f"清空缓存时出错：{str(e)}")
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        if not self.ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器不可用")
            return
        
        try:
            # 获取清理前的缓存统计
            stats_before = self.ai_manager.get_cache_stats()
            
            self.ai_manager.cleanup_cache()
            
            # 获取清理后的缓存统计
            stats_after = self.ai_manager.get_cache_stats()
            
            # 计算清理的条目数
            if stats_before.get('enabled') and stats_after.get('enabled'):
                memory_before = stats_before.get('memory_cache', {}).get('count', 0)
                memory_after = stats_after.get('memory_cache', {}).get('count', 0)
                disk_before = stats_before.get('disk_cache', {}).get('count', 0)
                disk_after = stats_after.get('disk_cache', {}).get('count', 0)
                
                total_cleaned = (memory_before - memory_after) + (disk_before - disk_after)
                message = f"过期缓存清理完成！\n清理了 {total_cleaned} 个过期条目。"
            else:
                message = "过期缓存清理完成！"
            
            self.status_label.setText("过期缓存已清理")
            QMessageBox.information(self, "成功", message)
            
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            QMessageBox.critical(self, "错误", f"清理缓存时出错：{str(e)}")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止刷新定时器
        if hasattr(self, '_refresh_timer'):
            self._refresh_timer.stop()
        
        # 停止工作线程
        if self._rebuild_worker and self._rebuild_worker.isRunning():
            self._rebuild_worker.stop()
            self._rebuild_worker.wait(3000)  # 等待3秒
        
        event.accept()