"""
大纲视图面板
提供文档大纲的专门视图，支持快速导航、编辑和重组
"""

import logging
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


from .ui import OutlineTreeItem



class OutlinePanelActionsMixin:
    """OutlinePanel mixin."""
    def _init_signals(self):
        """初始化信号连接"""
        # 连接共享信号
        self._shared.documentChanged.connect(self._on_document_changed)
        self._shared.projectChanged.connect(self._on_project_changed)
        if hasattr(self._shared, 'documentMetaChanged'):
            self._shared.documentMetaChanged.connect(self._on_document_meta_changed)
        
        # 连接项目管理器信号
        if hasattr(self._project_manager, 'documentUpdated'):
            self._project_manager.documentUpdated.connect(self._schedule_update)

    def _on_item_clicked(self, item: OutlineTreeItem, column: int):
        """项目点击处理"""
        if isinstance(item, OutlineTreeItem):
            # 更新预览
            self._update_preview(item.document)

    def _on_item_double_clicked(self, item: OutlineTreeItem, column: int):
        """项目双击处理"""
        if isinstance(item, OutlineTreeItem):
            # 发送文档选择信号
            self.documentSelected.emit(item.document.id)

    def _update_preview(self, document: 'ProjectDocument'):
        """更新预览内容"""
        if not document.content:
            self._preview_area.setPlainText("（无内容）")
            return
        
        # 提取前200个字符作为预览
        preview_text = document.content[:200]
        if len(document.content) > 200:
            preview_text += "..."
        
        self._preview_area.setPlainText(preview_text)

    def _on_context_menu(self, pos):
        """显示右键菜单"""
        item = self._outline_tree.itemAt(pos)
        if not isinstance(item, OutlineTreeItem):
            return
        
        menu = QMenu(self)
        
        # 编辑动作
        edit_action = QAction("编辑章节", self)
        edit_action.triggered.connect(lambda: self.documentSelected.emit(item.document.id))
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        # 添加子章节
        if item.document.doc_type.value in ['act', 'chapter']:
            add_child_action = QAction("添加子章节", self)
            add_child_action.triggered.connect(lambda: self._add_child_document(item.document))
            menu.addAction(add_child_action)
        
        menu.addSeparator()
        
        # 上移/下移
        move_up_action = QAction("上移", self)
        move_up_action.triggered.connect(lambda: self._move_document(item.document, -1))
        menu.addAction(move_up_action)
        
        move_down_action = QAction("下移", self)
        move_down_action.triggered.connect(lambda: self._move_document(item.document, 1))
        menu.addAction(move_down_action)
        
        menu.addSeparator()
        
        # 删除文档
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self._delete_document(item.document))
        menu.addAction(delete_action)
        
        menu.exec(QCursor.pos())

    def _delete_document(self, doc: 'ProjectDocument'):
        """删除文档"""
        try:
            # 确认对话框
            confirm_msg = f"确定要删除文档「{doc.name}」吗？"
            
            # 检查是否有子文档
            project = self._project_manager.get_current_project()
            if project:
                child_docs = [d for d in project.documents.values() if d.parent_id == doc.id]
                if child_docs:
                    confirm_msg += f"\n\n注意：该文档下有 {len(child_docs)} 个子文档，删除后子文档也将被删除。"
            
            reply = QMessageBox.question(
                self, "确认删除", confirm_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 记住文档名称用于日志
                doc_name = doc.name
                doc_type = doc.doc_type.value
                
                # 调用项目管理器删除文档
                success = self._project_manager.remove_document(doc.id)
                
                if success:
                    # 刷新大纲视图（debounce + worker）
                    self._queue_post_refresh_actions(emit_outline_updated=True)
                    self._request_outline_refresh(debounce_ms=0, reason="delete")
                    
                    logger.info(f"成功删除文档: {doc_name} (类型: {doc_type})")
                    
                    # 显示成功消息
                    QMessageBox.information(
                        self, "删除成功", 
                        f"文档「{doc_name}」已成功删除"
                    )
                else:
                    QMessageBox.critical(
                        self, "删除失败", 
                        f"删除文档「{doc_name}」失败，请检查文档是否被其他进程占用"
                    )
                    
        except Exception as e:
            logger.error(f"删除文档时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"删除文档失败: {str(e)}")

    def _add_child_document(self, parent_doc: 'ProjectDocument'):
        """添加子文档"""
        try:
            from core.project import DocumentType
            
            # 定义文档类型层次映射
            child_type_map = {
                DocumentType.ACT: DocumentType.CHAPTER,
                DocumentType.CHAPTER: DocumentType.SCENE
            }
            
            # 获取子文档类型
            child_type = child_type_map.get(parent_doc.doc_type)
            if not child_type:
                QMessageBox.warning(self, "警告", f"{parent_doc.doc_type.value}类型文档不能添加子文档")
                return
            
            # 确定新文档名称
            type_names = {
                DocumentType.CHAPTER: "章节",
                DocumentType.SCENE: "场景"
            }
            type_name = type_names.get(child_type, child_type.value)
            
            # 获取同级文档数量来确定序号
            siblings = [d for d in self._project_manager.get_current_project().documents.values() 
                       if d.parent_id == parent_doc.id and d.doc_type == child_type]
            next_order = len(siblings) + 1
            
            new_name = f"新{type_name}{next_order}"
            
            # 创建新文档
            new_doc = self._project_manager.add_document(
                name=new_name,
                doc_type=child_type,
                parent_id=parent_doc.id
            )
            
            if new_doc:
                # 刷新大纲视图（debounce + worker）
                self._queue_post_refresh_actions(
                    select_doc_id=new_doc.id,
                    emit_selection=True,
                    expand_doc_id=parent_doc.id,
                )
                self._request_outline_refresh(debounce_ms=0, reason="add_child")
                
                logger.info(f"成功添加子文档: {new_name} (类型: {child_type.value})")
            else:
                QMessageBox.critical(self, "错误", "创建子文档失败")
                
        except Exception as e:
            logger.error(f"添加子文档时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"添加子文档失败: {str(e)}")

    def _move_document(self, doc: 'ProjectDocument', direction: int):
        """移动文档顺序"""
        try:
            # 调用项目管理器的移动方法
            success = self._project_manager.move_document(doc.id, direction)
            
            if success:
                # 记住当前选中的文档ID
                current_doc_id = doc.id
                
                # 增量更新顺序（不全量重建）
                self._apply_incremental_reorder(doc.parent_id)
                self._select_document(current_doc_id)
                self.outlineUpdated.emit()
                
                direction_text = "上移" if direction == -1 else "下移"
                logger.info(f"成功{direction_text}文档: {doc.name}")
            else:
                # 根据情况显示不同的提示信息
                siblings = self._project_manager.get_children(doc.parent_id)
                if len(siblings) <= 1:
                    QMessageBox.information(self, "提示", "只有一个同级文档，无法移动")
                else:
                    direction_text = "上移" if direction == -1 else "下移"
                    QMessageBox.information(self, "提示", f"无法{direction_text}，已到达边界")
                
        except Exception as e:
            logger.error(f"移动文档时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"移动文档失败: {str(e)}")

    def _select_document(self, doc_id: str):
        """选中指定文档"""
        try:
            item = self._outline_items.get(doc_id)
            if item:
                self._outline_tree.setCurrentItem(item)
                self._outline_tree.scrollToItem(item)
                logger.debug(f"已选中文档: {doc_id}")
        except Exception as e:
            logger.error(f"选中文档时发生错误: {e}")

    def _expand_all(self):
        """展开全部"""
        self._outline_tree.expandAll()

    def _collapse_all(self):
        """折叠全部"""
        self._outline_tree.collapseAll()

    @pyqtSlot()
    def _on_document_changed(self):
        """文档变化处理"""
        self._schedule_update()

    @pyqtSlot(str, dict)
    def _on_document_meta_changed(self, doc_id: str, changes: dict):
        """文档元数据变化处理（增量更新）"""
        if not self._project_manager.has_project():
            return

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("outline meta changed: doc_id=%s keys=%s", doc_id, list(changes.keys()))

        doc = self._project_manager.get_document(doc_id)
        if not doc:
            return

        item = self._outline_items.get(doc_id)
        if not item:
            logger.debug("incremental update fallback: item missing; doing full refresh (doc_id=%s)", doc_id)
            self._request_outline_refresh(debounce_ms=0, reason="meta_missing")
            return

        if any(key in changes for key in ('name', 'word_count', 'doc_type', 'status')):
            item.update_display()

        if 'parent_id' in changes or 'order' in changes:
            logger.debug("incremental update: move/reorder doc_id=%s", doc_id)
            old_parent, new_parent, changed_parent = self._outline_model.update_node(doc)
            if changed_parent:
                self._move_tree_item(doc_id, old_parent, new_parent)
                if old_parent != new_parent:
                    self._apply_incremental_reorder(old_parent)
            self._apply_incremental_reorder(new_parent)

    @pyqtSlot()
    def _on_project_changed(self):
        """项目变化处理"""
        self._request_outline_refresh(debounce_ms=300, reason="project_changed")

    def _scan_project_structure(self):
        """扫描项目结构并更新大纲"""
        try:
            if not self._project_manager.has_project():
                QMessageBox.warning(self, "警告", "当前没有打开的项目")
                return
            
            # 获取当前项目
            project = self._project_manager.get_current_project()
            if not project or not project.documents:
                QMessageBox.information(self, "提示", "项目中没有文档")
                return
            
            # 统计扫描结果
            total_docs = len(project.documents)
            novel_docs = []
            other_docs = []
            
            for doc_id, doc in project.documents.items():
                if doc.doc_type.value in ['act', 'chapter', 'scene']:
                    novel_docs.append(doc)
                else:
                    other_docs.append(doc)
            
            # 自动重新组织文档结构
            reorganized_result = self._reorganize_documents_with_stats(novel_docs)
            
            # 强制刷新大纲显示 - 使用延迟确保数据已更新
            QTimer.singleShot(100, self._force_refresh_outline)
            
            # 显示扫描结果
            if reorganized_result['total_changes'] > 0:
                optimization_text = f"""🔧 结构优化:
• 调整了 {reorganized_result['total_changes']} 个文档的结构
• 修复了 {reorganized_result['hierarchy_fixes']} 个层次关系
• 重新排序了 {reorganized_result['order_fixes']} 个文档顺序
• 创建了 {reorganized_result['created_docs']} 个默认结构节点
• 大纲视图已更新"""
            else:
                optimization_text = """✅ 结构检查:
• 项目结构完整，层次关系正确
• 文档顺序合理，无需调整
• 大纲显示已刷新"""
            
            result_message = f"""项目结构扫描完成！
            
📊 扫描统计:
• 总文档数: {total_docs}
• 小说文档: {len(novel_docs)} (幕/章/节)  
• 其他文档: {len(other_docs)} (角色/地点等)

{optimization_text}

💡 提示: 如果需要进一步调整结构，可以使用右键菜单移动文档"""
            
            QMessageBox.information(self, "扫描完成", result_message)
            logger.info(f"项目结构扫描完成: {len(novel_docs)}个小说文档, {len(other_docs)}个其他文档")
            
        except Exception as e:
            logger.error(f"扫描项目结构时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"扫描项目结构失败: {str(e)}")

    def _reorganize_documents_with_stats(self, novel_docs: List['ProjectDocument']) -> Dict[str, int]:
        """重新组织文档结构（带详细统计）"""
        try:
            stats = {
                'total_changes': 0,
                'order_fixes': 0,
                'hierarchy_fixes': 0,
                'created_docs': 0
            }
            
            # 按类型分组
            acts = [d for d in novel_docs if d.doc_type.value == 'act']
            chapters = [d for d in novel_docs if d.doc_type.value == 'chapter']
            scenes = [d for d in novel_docs if d.doc_type.value == 'scene']
            
            logger.info(f"文档分组: {len(acts)}个幕, {len(chapters)}个章节, {len(scenes)}个场景")
            
            # 排序文档（按创建时间或名称）
            acts.sort(key=lambda d: (d.order, d.created_at, d.name))
            chapters.sort(key=lambda d: (d.order, d.created_at, d.name))
            scenes.sort(key=lambda d: (d.order, d.created_at, d.name))
            
            # 重新分配order - 确保连续编号
            for i, act in enumerate(acts):
                if act.order != i:
                    old_order = act.order
                    self._project_manager.update_document(act.id, order=i, save=False)
                    stats['order_fixes'] += 1
                    stats['total_changes'] += 1
                    logger.debug(f"更新幕 {act.name} 顺序: {old_order} -> {i}")
            
            for i, chapter in enumerate(chapters):
                if chapter.order != i:
                    old_order = chapter.order
                    self._project_manager.update_document(chapter.id, order=i, save=False)
                    stats['order_fixes'] += 1
                    stats['total_changes'] += 1
                    logger.debug(f"更新章节 {chapter.name} 顺序: {old_order} -> {i}")
            
            for i, scene in enumerate(scenes):
                if scene.order != i:
                    old_order = scene.order
                    self._project_manager.update_document(scene.id, order=i, save=False)
                    stats['order_fixes'] += 1
                    stats['total_changes'] += 1
                    logger.debug(f"更新场景 {scene.name} 顺序: {old_order} -> {i}")
            
            # 自动建立层次关系
            # 1. 如果章节没有父级，分配到第一个幕下
            orphan_chapters = [c for c in chapters if not c.parent_id]
            if orphan_chapters and acts:
                target_act = acts[0]
                for chapter in orphan_chapters:
                    old_parent = chapter.parent_id
                    self._project_manager.update_document(chapter.id, parent_id=target_act.id, save=False)
                    stats['hierarchy_fixes'] += 1
                    stats['total_changes'] += 1
                    logger.debug(f"设置章节 {chapter.name} 父级: {old_parent} -> {target_act.id}")
            
            # 2. 如果场景没有父级，分配到第一个章节下
            orphan_scenes = [s for s in scenes if not s.parent_id]
            if orphan_scenes and chapters:
                target_chapter = chapters[0]
                for scene in orphan_scenes:
                    old_parent = scene.parent_id
                    self._project_manager.update_document(scene.id, parent_id=target_chapter.id, save=False)
                    stats['hierarchy_fixes'] += 1
                    stats['total_changes'] += 1
                    logger.debug(f"设置场景 {scene.name} 父级: {old_parent} -> {target_chapter.id}")
            
            # 3. 如果没有幕但有章节，创建默认幕
            if not acts and chapters:
                logger.info("没有幕文档，创建默认幕")
                from core.project import DocumentType
                default_act = self._project_manager.add_document(
                    name="第一幕：主要情节",
                    doc_type=DocumentType.ACT,
                    save=False
                )
                if default_act:
                    stats['created_docs'] += 1
                    stats['total_changes'] += 1
                    # 将所有章节移到默认幕下
                    for chapter in chapters:
                        if not chapter.parent_id:
                            self._project_manager.update_document(chapter.id, parent_id=default_act.id, save=False)
                            stats['hierarchy_fixes'] += 1
                            stats['total_changes'] += 1
                    logger.info(f"创建默认幕并分配了 {len(chapters)} 个章节")
            
            # 4. 如果没有章节但有场景，创建默认章节
            if not chapters and scenes:
                logger.info("没有章节文档，创建默认章节")
                from core.project import DocumentType
                # 确保有幕
                if not acts:
                    default_act = self._project_manager.add_document(
                        name="第一幕：主要情节",
                        doc_type=DocumentType.ACT,
                        save=False
                    )
                    stats['created_docs'] += 1
                    stats['total_changes'] += 1
                    parent_id = default_act.id if default_act else None
                else:
                    parent_id = acts[0].id
                
                default_chapter = self._project_manager.add_document(
                    name="第一章：开始",
                    doc_type=DocumentType.CHAPTER,
                    parent_id=parent_id,
                    save=False
                )
                if default_chapter:
                    stats['created_docs'] += 1
                    stats['total_changes'] += 1
                    # 将所有场景移到默认章节下
                    for scene in scenes:
                        if not scene.parent_id:
                            self._project_manager.update_document(scene.id, parent_id=default_chapter.id, save=False)
                            stats['hierarchy_fixes'] += 1
                            stats['total_changes'] += 1
                    logger.info(f"创建默认章节并分配了 {len(scenes)} 个场景")
            
            # 强制保存项目
            if stats['total_changes'] > 0:
                self._project_manager.save_project()
                logger.info(f"项目结构重组完成，保存了 {stats['total_changes']} 个更改")
            else:
                logger.info("项目结构已经是最优状态，无需重组")
            
            return stats
            
        except Exception as e:
            logger.error(f"重新组织文档结构时发生错误: {e}")
            return {'total_changes': 0, 'order_fixes': 0, 'hierarchy_fixes': 0, 'created_docs': 0}

    def _reorganize_documents(self, novel_docs: List['ProjectDocument']) -> int:
        """重新组织文档结构"""
        try:
            reorganized_count = 0
            
            # 按类型分组
            acts = [d for d in novel_docs if d.doc_type.value == 'act']
            chapters = [d for d in novel_docs if d.doc_type.value == 'chapter']
            scenes = [d for d in novel_docs if d.doc_type.value == 'scene']
            
            logger.info(f"文档分组: {len(acts)}个幕, {len(chapters)}个章节, {len(scenes)}个场景")
            
            # 排序文档（按创建时间或名称）
            acts.sort(key=lambda d: (d.order, d.created_at, d.name))
            chapters.sort(key=lambda d: (d.order, d.created_at, d.name))
            scenes.sort(key=lambda d: (d.order, d.created_at, d.name))
            
            # 重新分配order - 确保连续编号
            for i, act in enumerate(acts):
                if act.order != i:
                    old_order = act.order
                    self._project_manager.update_document(act.id, order=i, save=False)
                    reorganized_count += 1
                    logger.debug(f"更新幕 {act.name} 顺序: {old_order} -> {i}")
            
            for i, chapter in enumerate(chapters):
                if chapter.order != i:
                    old_order = chapter.order
                    self._project_manager.update_document(chapter.id, order=i, save=False)
                    reorganized_count += 1
                    logger.debug(f"更新章节 {chapter.name} 顺序: {old_order} -> {i}")
            
            for i, scene in enumerate(scenes):
                if scene.order != i:
                    old_order = scene.order
                    self._project_manager.update_document(scene.id, order=i, save=False)
                    reorganized_count += 1
                    logger.debug(f"更新场景 {scene.name} 顺序: {old_order} -> {i}")
            
            # 自动建立层次关系
            # 1. 如果章节没有父级，分配到第一个幕下
            orphan_chapters = [c for c in chapters if not c.parent_id]
            if orphan_chapters and acts:
                target_act = acts[0]
                for chapter in orphan_chapters:
                    old_parent = chapter.parent_id
                    self._project_manager.update_document(chapter.id, parent_id=target_act.id, save=False)
                    reorganized_count += 1
                    logger.debug(f"设置章节 {chapter.name} 父级: {old_parent} -> {target_act.id}")
            
            # 2. 如果场景没有父级，分配到第一个章节下
            orphan_scenes = [s for s in scenes if not s.parent_id]
            if orphan_scenes and chapters:
                target_chapter = chapters[0]
                for scene in orphan_scenes:
                    old_parent = scene.parent_id
                    self._project_manager.update_document(scene.id, parent_id=target_chapter.id, save=False)
                    reorganized_count += 1
                    logger.debug(f"设置场景 {scene.name} 父级: {old_parent} -> {target_chapter.id}")
            
            # 3. 如果没有幕但有章节，创建默认幕
            if not acts and chapters:
                logger.info("没有幕文档，创建默认幕")
                from core.project import DocumentType
                default_act = self._project_manager.add_document(
                    name="第一幕：主要情节",
                    doc_type=DocumentType.ACT,
                    save=False
                )
                if default_act:
                    # 将所有章节移到默认幕下
                    for chapter in chapters:
                        if not chapter.parent_id:
                            self._project_manager.update_document(chapter.id, parent_id=default_act.id, save=False)
                            reorganized_count += 1
                    logger.info(f"创建默认幕并分配了 {len(chapters)} 个章节")
            
            # 4. 如果没有章节但有场景，创建默认章节
            if not chapters and scenes:
                logger.info("没有章节文档，创建默认章节")
                from core.project import DocumentType
                # 确保有幕
                if not acts:
                    default_act = self._project_manager.add_document(
                        name="第一幕：主要情节",
                        doc_type=DocumentType.ACT,
                        save=False
                    )
                    parent_id = default_act.id if default_act else None
                else:
                    parent_id = acts[0].id
                
                default_chapter = self._project_manager.add_document(
                    name="第一章：开始",
                    doc_type=DocumentType.CHAPTER,
                    parent_id=parent_id,
                    save=False
                )
                if default_chapter:
                    # 将所有场景移到默认章节下
                    for scene in scenes:
                        if not scene.parent_id:
                            self._project_manager.update_document(scene.id, parent_id=default_chapter.id, save=False)
                            reorganized_count += 1
                    logger.info(f"创建默认章节并分配了 {len(scenes)} 个场景")
            
            # 强制保存项目
            if reorganized_count > 0:
                self._project_manager.save_project()
                logger.info(f"项目结构重组完成，保存了 {reorganized_count} 个更改")
            else:
                logger.info("项目结构已经是最优状态，无需重组")
            
            return reorganized_count
            
        except Exception as e:
            logger.error(f"重新组织文档结构时发生错误: {e}")
            return 0

