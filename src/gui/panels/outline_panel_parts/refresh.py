"""
大纲视图面板
提供文档大纲的专门视图，支持快速导航、编辑和重组
"""

import logging
import time
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMenu, QMessageBox, QToolButton,
    QFrame, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QAction, QCursor

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config
    from core.shared import Shared
    from core.project import ProjectManager, ProjectDocument, DocumentType
from gui.models.outline_model import OutlineModel

logger = logging.getLogger(__name__)




class OutlinePanelRefreshMixin:
    """OutlinePanel mixin."""
    def _load_outline(self):
        """加载大纲"""
        self._outline_tree.clear()
        self._outline_items.clear()
        
        if not self._project_manager.has_project():
            return
        
        try:
            # 获取所有文档
            project = self._project_manager.get_current_project()
            if not project:
                return

            docs_for_outline = [
                doc for doc in project.documents.values()
                if doc.doc_type.value in ['act', 'chapter', 'scene']
            ]
            self._outline_model.rebuild(docs_for_outline)
            
            # 构建文档树
            root_docs = []
            doc_children = {}
            
            for doc_id, doc in project.documents.items():
                # 只显示小说内容类型的文档
                if doc.doc_type.value in ['act', 'chapter', 'scene']:
                    if doc.parent_id:
                        if doc.parent_id not in doc_children:
                            doc_children[doc.parent_id] = []
                        doc_children[doc.parent_id].append(doc)
                    else:
                        root_docs.append(doc)
            
            # 递归构建树
            for doc in sorted(root_docs, key=lambda d: d.order):
                item = self._create_tree_item(doc, None)
                self._build_tree_recursive(item, doc.id, doc_children)
            
            # 展开第一层
            self._outline_tree.expandToDepth(0)
            
            # 更新统计信息
            self._update_statistics()
            self._apply_pending_post_refresh()
            
        except Exception as e:
            logger.error(f"加载大纲失败: {e}")

    def _snapshot_outline_docs(self):
        """采集用于大纲计算的快照数据（避免在worker访问UI对象）"""
        if not self._project_manager.has_project():
            return None

        project = self._project_manager.get_current_project()
        if not project:
            return None

        docs_snapshot = []
        for doc in project.documents.values():
            if doc.doc_type.value in ['act', 'chapter', 'scene']:
                docs_snapshot.append({
                    'id': doc.id,
                    'parent_id': doc.parent_id,
                    'order': doc.order,
                })

        return docs_snapshot

    def _compute_outline_model(self, docs_snapshot, token, request_id):
        """后台线程计算大纲结构（不触碰UI）"""
        if token.cancelled or docs_snapshot is None:
            return None

        children = {}
        roots = []
        for doc in docs_snapshot:
            parent_id = doc['parent_id']
            if parent_id:
                children.setdefault(parent_id, []).append(doc)
            else:
                roots.append(doc)

        for doc_list in children.values():
            doc_list.sort(key=lambda d: d['order'])
        roots.sort(key=lambda d: d['order'])

        def build(node_doc):
            if token.cancelled:
                return None
            node = {'id': node_doc['id'], 'children': []}
            for child_doc in children.get(node_doc['id'], []):
                child_node = build(child_doc)
                if child_node is not None:
                    node['children'].append(child_node)
            return node

        model = []
        for root_doc in roots:
            node = build(root_doc)
            if node is not None:
                model.append(node)

        return {'request_id': request_id, 'model': model}

    def _apply_outline_model(self, payload):
        if not payload:
            return
        if payload.get('request_id') != self._outline_request_id:
            return
        model = payload.get('model')
        if model is None:
            return

        start_time = time.perf_counter()
        self._outline_tree.clear()
        self._outline_items.clear()

        project = self._project_manager.get_current_project()
        if not project:
            self._update_statistics()
            return

        docs = project.documents
        docs_for_outline = [
            doc for doc in docs.values()
            if doc.doc_type.value in ['act', 'chapter', 'scene']
        ]
        self._outline_model.rebuild(docs_for_outline)

        def apply_node(node, parent_item=None):
            doc = docs.get(node['id'])
            if not doc:
                return
            item = self._create_tree_item(doc, parent_item)
            for child in node.get('children', []):
                apply_node(child, item)

        for root in model:
            apply_node(root, None)

        self._outline_tree.expandToDepth(0)
        self._update_statistics()
        self._apply_pending_post_refresh()

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "outline refresh: full rebuild applied in %.1fms (items=%d)",
            elapsed_ms,
            len(self._outline_items),
        )

    def _apply_pending_post_refresh(self):
        if self._pending_expand_doc_id:
            item = self._outline_items.get(self._pending_expand_doc_id)
            if item:
                item.setExpanded(True)
            self._pending_expand_doc_id = None

        if self._pending_select_doc_id:
            self._select_document(self._pending_select_doc_id)
            if self._pending_emit_selection:
                self.documentSelected.emit(self._pending_select_doc_id)
            self._pending_select_doc_id = None
            self._pending_emit_selection = False

        if self._pending_emit_outline_updated:
            self.outlineUpdated.emit()
            self._pending_emit_outline_updated = False

    def _queue_post_refresh_actions(
        self,
        *,
        select_doc_id: Optional[str] = None,
        emit_selection: bool = False,
        expand_doc_id: Optional[str] = None,
        emit_outline_updated: bool = False
    ):
        if select_doc_id:
            self._pending_select_doc_id = select_doc_id
            self._pending_emit_selection = emit_selection
        if expand_doc_id:
            self._pending_expand_doc_id = expand_doc_id
        if emit_outline_updated:
            self._pending_emit_outline_updated = True

    def _request_outline_refresh(self, debounce_ms: int = 500, *, clear: bool = False, reason: str = ""):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "outline refresh requested: reason=%s debounce_ms=%s clear=%s task_manager=%s",
                reason,
                debounce_ms,
                clear,
                bool(self._task_manager),
            )

        if clear:
            self._outline_tree.clear()
            self._outline_items.clear()

        if not self._project_manager.has_project():
            self._outline_tree.clear()
            self._outline_items.clear()
            self._update_statistics()
            return

        if self._task_manager:
            self._outline_request_id += 1
            request_id = self._outline_request_id
            docs_snapshot = self._snapshot_outline_docs()
            if docs_snapshot is None:
                self._outline_tree.clear()
                self._outline_items.clear()
                self._update_statistics()
                return

            def runner(token, snapshot=docs_snapshot, req_id=request_id):
                return self._compute_outline_model(snapshot, token, req_id)

            description = f"outline refresh {reason}".strip()
            self._task_manager.submit(
                self._outline_task_key,
                runner,
                cancel_previous=True,
                coalesce=True,
                throttle_ms=max(debounce_ms, 0),
                description=description or None,
            )
            return

        self._update_timer.stop()
        if debounce_ms <= 0:
            self._load_outline()
        else:
            self._update_timer.start(debounce_ms)

    @pyqtSlot(str, object)
    def _on_task_finished(self, key: str, result: object):
        if key != self._outline_task_key:
            return
        self._apply_outline_model(result)

    @pyqtSlot(str, str, dict)
    def _on_task_failed(self, key: str, error: str, details: dict):
        if key != self._outline_task_key:
            return
        logger.warning(f"大纲刷新任务失败: {error}")

    def _update_statistics(self):
        """更新统计信息（紧凑显示）"""
        total_docs = 0
        total_words = 0
        
        for doc_id, item in self._outline_items.items():
            total_docs += 1
            total_words += item.document.word_count
        
        # 紧凑显示格式
        if total_words > 10000:
            word_text = f"{total_words//1000}k字"
        elif total_words > 0:
            word_text = f"{total_words}字"
        else:
            word_text = "0字"
            
        self._stats_label.setText(f"{total_docs}章节,{word_text}")

    def _refresh_outline(self):
        """刷新大纲"""
        self._request_outline_refresh(debounce_ms=0, reason="manual")

    def _force_refresh_outline(self):
        """强制刷新大纲（用于扫描后的更新）"""
        try:
            # 清空当前显示
            self._request_outline_refresh(debounce_ms=0, clear=True, reason="force")
            
            logger.info("强制刷新大纲完成")
            
        except Exception as e:
            logger.error(f"强制刷新大纲时发生错误: {e}")
            # 降级到普通刷新
            self._load_outline()

    def _schedule_update(self):
        """计划更新大纲（延迟执行）"""
        self._request_outline_refresh(debounce_ms=500, reason="debounce")

    def _do_update_outline(self):
        """执行大纲更新"""
        self._load_outline()

    def _apply_incremental_reorder(self, parent_id: Optional[str]):
        start_time = time.perf_counter()
        ordered_docs = self._project_manager.get_children(parent_id)
        self._outline_model.reorder_children(parent_id, ordered_docs)
        ordered_ids = [doc.id for doc in ordered_docs if doc.id in self._outline_items]
        self._reorder_tree_children(parent_id, ordered_ids)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "incremental update: reorder parent=%s took %.1fms (children=%d)",
            parent_id,
            elapsed_ms,
            len(ordered_ids),
        )

    def _reorder_tree_children(self, parent_id: Optional[str], ordered_ids: List[str]):
        if not ordered_ids:
            return

        if parent_id:
            parent_item = self._outline_items.get(parent_id)
            if not parent_item:
                return

            for doc_id in ordered_ids:
                item = self._outline_items.get(doc_id)
                if item:
                    idx = parent_item.indexOfChild(item)
                    if idx != -1:
                        parent_item.takeChild(idx)

            for idx, doc_id in enumerate(ordered_ids):
                item = self._outline_items.get(doc_id)
                if item:
                    parent_item.insertChild(idx, item)
            return

        for doc_id in ordered_ids:
            item = self._outline_items.get(doc_id)
            if item:
                idx = self._outline_tree.indexOfTopLevelItem(item)
                if idx != -1:
                    self._outline_tree.takeTopLevelItem(idx)

        for idx, doc_id in enumerate(ordered_ids):
            item = self._outline_items.get(doc_id)
            if item:
                self._outline_tree.insertTopLevelItem(idx, item)

    def _move_tree_item(self, doc_id: str, old_parent_id: Optional[str], new_parent_id: Optional[str]):
        item = self._outline_items.get(doc_id)
        if not item:
            return

        if old_parent_id:
            old_parent_item = self._outline_items.get(old_parent_id)
            if old_parent_item:
                idx = old_parent_item.indexOfChild(item)
                if idx != -1:
                    old_parent_item.takeChild(idx)
            else:
                idx = self._outline_tree.indexOfTopLevelItem(item)
                if idx != -1:
                    self._outline_tree.takeTopLevelItem(idx)
        else:
            idx = self._outline_tree.indexOfTopLevelItem(item)
            if idx != -1:
                self._outline_tree.takeTopLevelItem(idx)

        if new_parent_id:
            new_parent_item = self._outline_items.get(new_parent_id)
            if new_parent_item:
                new_parent_item.addChild(item)
            else:
                self._outline_tree.addTopLevelItem(item)
        else:
            self._outline_tree.addTopLevelItem(item)

