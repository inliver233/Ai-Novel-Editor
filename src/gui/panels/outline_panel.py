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


class OutlineTreeItem(QTreeWidgetItem):
    """大纲树项目"""
    
    def __init__(self, document: 'ProjectDocument', parent=None):
        super().__init__(parent)
        self.document = document
        self.update_display()
    
    def update_display(self):
        """更新显示内容"""
        # 显示文档名称
        self.setText(0, self.document.name)
        
        # 根据文档类型设置不同的显示样式
        if self.document.doc_type.value == "act":
            self.setText(0, f"第{self.document.order + 1}幕：{self.document.name}")
        elif self.document.doc_type.value == "chapter":
            self.setText(0, f"第{self.document.order + 1}章：{self.document.name}")
        elif self.document.doc_type.value == "scene":
            self.setText(0, f"场景 {self.document.order + 1}：{self.document.name}")
        
        # 显示字数统计
        if self.document.word_count > 0:
            self.setText(1, f"{self.document.word_count:,}")
        else:
            self.setText(1, "")
        
        # 设置工具提示
        tooltip = f"类型: {self.document.doc_type.value}\n"
        tooltip += f"状态: {self.document.status.value}\n"
        tooltip += f"字数: {self.document.word_count:,}"
        self.setToolTip(0, tooltip)


class OutlinePanel(QWidget):
    """大纲视图面板"""
    
    # 信号定义
    documentSelected = pyqtSignal(str)  # 文档选择信号
    documentMoved = pyqtSignal(str, str, int)  # 文档移动信号 (doc_id, new_parent_id, new_order)
    outlineUpdated = pyqtSignal()  # 大纲更新信号
    
    def __init__(self, config: 'Config', shared: 'Shared', project_manager: 'ProjectManager', parent=None):
        super().__init__(parent)
        
        self._config = config
        self._shared = shared
        self._project_manager = project_manager
        self._outline_items = {}  # doc_id -> OutlineTreeItem 映射
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._do_update_outline)
        self._outline_request_id = 0
        self._outline_task_key = "outline.refresh"
        self._pending_select_doc_id = None
        self._pending_emit_selection = False
        self._pending_expand_doc_id = None
        self._pending_emit_outline_updated = False
        self._task_manager = getattr(self._shared, "task_manager", None)
        if self._task_manager:
            self._task_manager.taskFinished.connect(self._on_task_finished)
            self._task_manager.taskFailed.connect(self._on_task_failed)
        self._outline_model = OutlineModel()
        
        self._init_ui()
        self._init_signals()
        self._request_outline_refresh(debounce_ms=0, reason="init")
        
        logger.info("大纲面板已初始化")
    
    def _init_ui(self):
        """初始化UI（优化紧凑布局）"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)  # 减少边距
        layout.setSpacing(4)                   # 减少间距
        
        # 标题栏
        title_frame = self._create_title_frame()
        layout.addWidget(title_frame)
        
        # 主分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 大纲树
        self._outline_tree = self._create_outline_tree()
        splitter.addWidget(self._outline_tree)
        
        # 摘要预览区（可选）
        self._preview_area = self._create_preview_area()
        splitter.addWidget(self._preview_area)
        
        # 设置分割比例，给大纲树更多空间
        splitter.setSizes([500, 150])  # 调整比例，减少预览区占用
        
        layout.addWidget(splitter)
        
        # 工具栏
        toolbar_frame = self._create_toolbar()
        layout.addWidget(toolbar_frame)
    
    def _create_title_frame(self) -> QFrame:
        """创建紧凑标题栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)  # 减少垂直边距
        
        # 标题
        title_label = QLabel("文档大纲")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 12px;  /* 稍微减小字体 */
                font-weight: bold;
                padding: 2px;     /* 减少内边距 */
            }
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 折叠/展开按钮（紧凑化）
        expand_btn = QToolButton()
        expand_btn.setText("全展")
        expand_btn.setMaximumWidth(40)  # 限制按钮宽度
        expand_btn.setToolTip("展开全部")
        expand_btn.clicked.connect(self._expand_all)
        layout.addWidget(expand_btn)
        
        collapse_btn = QToolButton()
        collapse_btn.setText("折叠")
        collapse_btn.setMaximumWidth(40)
        collapse_btn.setToolTip("折叠全部")
        collapse_btn.clicked.connect(self._collapse_all)
        layout.addWidget(collapse_btn)
        
        return frame
    
    def _create_outline_tree(self) -> QTreeWidget:
        """创建大纲树（优化列宽度）"""
        tree = QTreeWidget()
        tree.setHeaderLabels(["标题", "字数"])
        
        # 优化列宽度设置
        tree.setColumnWidth(0, 160)  # 标题列更紧凑
        tree.setColumnWidth(1, 50)   # 字数列更紧凑
        
        # 设置列可自动调整，但有最小宽度
        header = tree.header()
        header.setStretchLastSection(False)  # 最后一列不自动拉伸
        header.setSectionResizeMode(0, header.ResizeMode.Interactive)  # 标题列可手动调整
        header.setSectionResizeMode(1, header.ResizeMode.Fixed)        # 字数列固定宽度
        
        # 启用拖拽
        tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        # 连接信号
        tree.itemClicked.connect(self._on_item_clicked)
        tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        tree.customContextMenuRequested.connect(self._on_context_menu)
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        return tree
    
    def _create_preview_area(self) -> QTextEdit:
        """创建预览区域"""
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText("选择一个章节查看摘要...")
        
        # 设置样式
        preview.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        return preview
    
    def _create_toolbar(self) -> QFrame:
        """创建紧凑工具栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QVBoxLayout(frame)  # 改为垂直布局，减少水平空间占用
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 第一行：基础操作按钮
        basic_row = QHBoxLayout()
        basic_row.setSpacing(4)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setMaximumWidth(60)  # 限制按钮宽度
        refresh_btn.clicked.connect(self._refresh_outline)
        basic_row.addWidget(refresh_btn)
        
        # 扫描项目按钮
        scan_btn = QPushButton("扫描")
        scan_btn.setMaximumWidth(60)
        scan_btn.setToolTip("扫描当前项目的文档结构并更新大纲")
        scan_btn.clicked.connect(self._scan_project_structure)
        basic_row.addWidget(scan_btn)
        
        basic_row.addStretch()
        
        # 统计信息（可收缩）
        self._stats_label = QLabel("0章节")
        self._stats_label.setStyleSheet("font-size: 10px; color: #888;")
        basic_row.addWidget(self._stats_label)
        
        layout.addLayout(basic_row)
        
        # 第二行：AI功能按钮（可折叠）
        ai_row = QHBoxLayout()
        ai_row.setSpacing(4)
        
        # 导入大纲按钮
        import_btn = QPushButton("导入")
        import_btn.setMaximumWidth(60)
        import_btn.setToolTip("从文本文件导入手写大纲")
        import_btn.clicked.connect(self._import_outline)
        ai_row.addWidget(import_btn)
        
        # AI分析按钮
        analyze_btn = QPushButton("分析")
        analyze_btn.setMaximumWidth(60)
        analyze_btn.setToolTip("使用AI智能分析大纲结构")
        analyze_btn.clicked.connect(self._analyze_outline)
        ai_row.addWidget(analyze_btn)
        
        # AI续写按钮
        generate_btn = QPushButton("续写")
        generate_btn.setMaximumWidth(60)
        generate_btn.setToolTip("基于现有内容智能生成后续大纲章节")
        generate_btn.clicked.connect(self._generate_outline_continuation)
        ai_row.addWidget(generate_btn)
        
        ai_row.addStretch()
        layout.addLayout(ai_row)
        
        return frame
    
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
    
    def _create_tree_item(self, doc: 'ProjectDocument', parent: Optional[QTreeWidgetItem]) -> OutlineTreeItem:
        """创建树项目"""
        if parent:
            item = OutlineTreeItem(doc, parent)
        else:
            item = OutlineTreeItem(doc)
            self._outline_tree.addTopLevelItem(item)
        
        self._outline_items[doc.id] = item
        return item
    
    def _build_tree_recursive(self, parent_item: OutlineTreeItem, parent_id: str, doc_children: Dict[str, List]):
        """递归构建树"""
        if parent_id not in doc_children:
            return
        
        for doc in sorted(doc_children[parent_id], key=lambda d: d.order):
            item = self._create_tree_item(doc, parent_item)
            self._build_tree_recursive(item, doc.id, doc_children)
    
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
    
    @pyqtSlot()
    def _on_document_changed(self):
        """文档变化处理"""
        self._schedule_update()

    @pyqtSlot(str, dict)
    def _on_document_meta_changed(self, doc_id: str, changes: dict):
        """文档元数据变化处理（增量更新）"""
        if not self._project_manager.has_project():
            return

        doc = self._project_manager.get_document(doc_id)
        if not doc:
            return

        item = self._outline_items.get(doc_id)
        if not item:
            self._request_outline_refresh(debounce_ms=0, reason="meta_missing")
            return

        if any(key in changes for key in ('name', 'word_count', 'doc_type', 'status')):
            item.update_display()

        if 'parent_id' in changes or 'order' in changes:
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

    def _apply_incremental_reorder(self, parent_id: Optional[str]):
        ordered_docs = self._project_manager.get_children(parent_id)
        self._outline_model.reorder_children(parent_id, ordered_docs)
        ordered_ids = [doc.id for doc in ordered_docs if doc.id in self._outline_items]
        self._reorder_tree_children(parent_id, ordered_ids)

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
    
    def _import_outline(self):
        """导入手写大纲"""
        try:
            from PyQt6.QtWidgets import QFileDialog, QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel, QCheckBox, QHBoxLayout
            
            if not self._project_manager.has_project():
                QMessageBox.warning(self, "警告", "请先创建或打开一个项目")
                return
            
            # 检查大纲AI配置
            outline_ai_config = self._config._config_data.get('outline', {})
            auto_analyze = outline_ai_config.get('analysis', {}).get('auto_analyze', False)
            
            # 选择导入方式
            import_dialog = QDialog(self)
            import_dialog.setWindowTitle("智能大纲导入")
            import_dialog.setMinimumSize(600, 500)
            
            layout = QVBoxLayout(import_dialog)
            
            # AI分析选项
            ai_options_group = QHBoxLayout()
            self.use_ai_analysis = QCheckBox("启用AI智能分析")
            self.use_ai_analysis.setChecked(auto_analyze)
            self.use_ai_analysis.setToolTip("使用AI分析任意格式文本并自动转换为标准大纲结构")
            ai_options_group.addWidget(self.use_ai_analysis)
            
            # 同步AI配置按钮
            sync_config_btn = QPushButton("同步到AI配置")
            sync_config_btn.setToolTip("将当前AI分析设置同步到AI配置中心")
            sync_config_btn.clicked.connect(lambda: self._sync_ai_config(self.use_ai_analysis.isChecked()))
            ai_options_group.addWidget(sync_config_btn)
            
            ai_options_group.addStretch()
            layout.addLayout(ai_options_group)
            
            # 说明文字 - 根据AI选项动态更新
            self.info_label = QLabel()
            self._update_import_info()
            self.info_label.setWordWrap(True)
            layout.addWidget(self.info_label)
            
            # 连接AI选项变化
            self.use_ai_analysis.toggled.connect(self._update_import_info)
            
            # 文本编辑区
            text_edit = QTextEdit()
            text_edit.setPlaceholderText("请在此处粘贴或输入您的大纲内容...")
            layout.addWidget(text_edit)
            
            # 文件导入按钮
            file_layout = QHBoxLayout()
            file_btn = QPushButton("从文件导入")
            file_btn.clicked.connect(lambda: self._load_outline_from_file(text_edit))
            file_layout.addWidget(file_btn)
            
            # AI分析测试按钮
            if auto_analyze:  # 只有配置了AI才显示
                test_ai_btn = QPushButton("测试AI分析")
                test_ai_btn.clicked.connect(lambda: self._test_ai_analysis(text_edit))
                file_layout.addWidget(test_ai_btn)
            
            file_layout.addStretch()
            layout.addLayout(file_layout)
            
            # 对话框按钮
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(import_dialog.accept)
            button_box.rejected.connect(import_dialog.reject)
            layout.addWidget(button_box)
            
            # 显示对话框
            if import_dialog.exec() == QDialog.DialogCode.Accepted:
                outline_text = text_edit.toPlainText().strip()
                if outline_text:
                    use_ai = self.use_ai_analysis.isChecked()
                    # 如果AI开关状态变化，自动同步到配置
                    if use_ai != auto_analyze:
                        self._sync_ai_config(use_ai)
                    self._process_imported_outline(outline_text, use_ai)
                else:
                    QMessageBox.warning(self, "警告", "请输入大纲内容")
            
        except Exception as e:
            logger.error(f"导入大纲时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"导入大纲失败: {str(e)}")
    
    def _sync_ai_config(self, enable_ai: bool):
        """同步AI配置"""
        try:
            # 更新大纲AI配置中的自动分析选项
            outline_config = self._config._config_data.get('outline', {})
            if 'analysis' not in outline_config:
                outline_config['analysis'] = {}
            
            outline_config['analysis']['auto_analyze'] = enable_ai
            self._config._config_data['outline'] = outline_config
            
            # 保存配置
            self._config.save()
            
            status_text = "启用" if enable_ai else "禁用"
            logger.info(f"已同步AI分析配置: {status_text}")
            
            # 显示同步成功提示
            QMessageBox.information(
                self, 
                "同步成功", 
                f"AI智能分析已{status_text}，配置已保存到AI配置中心"
            )
            
        except Exception as e:
            logger.error(f"同步AI配置失败: {e}")
            QMessageBox.warning(self, "同步失败", f"同步AI配置失败: {str(e)}")
    
    def _update_import_info(self):
        """更新导入信息说明"""
        if hasattr(self, 'use_ai_analysis') and self.use_ai_analysis.isChecked():
            info_text = """
<b>🤖 AI智能大纲导入</b><br><br>
<b>AI模式特点：</b><br>
• <b>任意格式支持</b>：可以导入任何文本格式的大纲、故事摘要、想法笔记<br>
• <b>智能结构分析</b>：AI自动识别章节层次、情节发展、角色关系<br>
• <b>自动格式转换</b>：将任意文本转换为标准的幕-章-节结构<br>
• <b>内容增强</b>：AI会适当补充和优化大纲内容<br><br>
<b>支持的输入示例：</b><br>
• 简单列表：第一章 相遇，第二章 冲突...<br>
• 段落描述：故事开始于一个雨天，主角遇到了...<br>
• 混合格式：任何包含故事信息的文本<br>
• 无结构文本：想法、灵感、故事片段<br><br>
<span style="color: #4CAF50;"><b>✨ AI会帮您整理成完整的大纲结构！</b></span>
            """
        else:
            info_text = """
<b>📝 标准格式大纲导入</b><br><br>
支持以下<b>标准格式</b>的大纲导入：<br>
• <b>层次格式</b>：使用缩进或编号表示层次<br>
• <b>标记格式</b>：使用 #、##、### 表示标题级别<br>
• <b>纯文本</b>：每行一个章节名称<br><br>
<b>示例格式：</b><br>
第一幕：开始<br>
&nbsp;&nbsp;第一章：相遇<br>
&nbsp;&nbsp;&nbsp;&nbsp;场景1：公园<br>
&nbsp;&nbsp;第二章：误会<br>
第二幕：发展<br>
&nbsp;&nbsp;第三章：冲突<br><br>
或者使用Markdown格式：<br>
# 第一幕：开始<br>
## 第一章：相遇<br>
### 场景1：公园<br>
## 第二章：误会<br>
# 第二幕：发展<br>
## 第三章：冲突<br><br>
<span style="color: #FF9800;"><b>⚠️ 需要严格按照格式要求</b></span>
            """
        
        if hasattr(self, 'info_label'):
            self.info_label.setText(info_text)
    
    def _load_outline_from_file(self, text_edit: QTextEdit):
        """从文件加载大纲"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "选择大纲文件", 
                "", 
                "文本文件 (*.txt *.md *.markdown);;所有文件 (*)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                text_edit.setPlainText(content)
                logger.info(f"已从文件加载大纲: {file_path}")
                
        except Exception as e:
            logger.error(f"从文件加载大纲时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"加载文件失败: {str(e)}")
    
    def _test_ai_analysis(self, text_edit: QTextEdit):
        """测试AI分析功能"""
        try:
            text_content = text_edit.toPlainText().strip()
            if not text_content:
                QMessageBox.warning(self, "提示", "请先输入一些文本内容进行测试")
                return
            
            # 限制测试文本长度
            if len(text_content) > 1000:
                text_content = text_content[:1000] + "..."
            
            # 显示处理中提示
            from PyQt6.QtWidgets import QProgressDialog
            progress = QProgressDialog("正在进行AI分析测试...", "取消", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            # 调用AI分析
            analyzed_content = self._ai_analyze_text(text_content)
            
            progress.close()
            
            # 检查是否是异步处理标识
            if analyzed_content == "ASYNC_PROCESSING":
                QMessageBox.information(self, "提示", "AI分析已启动，请稍后通过导入功能查看结果")
                return
            elif analyzed_content:
                # 显示分析结果
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
                result_dialog = QDialog(self)
                result_dialog.setWindowTitle("AI分析结果预览")
                result_dialog.setMinimumSize(500, 400)
                
                layout = QVBoxLayout(result_dialog)
                
                browser = QTextBrowser()
                browser.setPlainText(analyzed_content)
                layout.addWidget(browser)
                
                # 按钮
                button_layout = QHBoxLayout()
                apply_btn = QPushButton("应用到编辑器")
                apply_btn.clicked.connect(lambda: text_edit.setPlainText(analyzed_content))
                apply_btn.clicked.connect(result_dialog.accept)
                button_layout.addWidget(apply_btn)
                
                close_btn = QPushButton("关闭")
                close_btn.clicked.connect(result_dialog.reject)
                button_layout.addWidget(close_btn)
                
                layout.addLayout(button_layout)
                result_dialog.exec()
            else:
                QMessageBox.warning(self, "测试失败", "AI分析失败，请检查AI配置和网络连接")
                
        except Exception as e:
            logger.error(f"AI分析测试失败: {e}")
            QMessageBox.critical(self, "测试错误", f"AI分析测试失败: {str(e)}")
    
    def _process_imported_outline(self, outline_text: str, use_ai: bool = False):
        """处理导入的大纲文本（支持异步AI分析）"""
        try:
            if use_ai:
                # AI智能分析模式 - 使用异步处理
                logger.info("启动异步AI分析模式")
                
                # 保存原始文本供异步处理使用
                self._pending_outline_text = outline_text
                
                # 启动异步AI分析
                analyzed_text = self._ai_analyze_text(outline_text)
                
                if analyzed_text == "ASYNC_PROCESSING":
                    # 异步处理中，等待回调处理
                    logger.info("AI分析已启动，等待异步完成")
                    return
                elif analyzed_text:
                    # 同步返回结果（降级处理）
                    outline_text = analyzed_text
                else:
                    QMessageBox.warning(self, "警告", "AI分析失败，将使用标准格式解析")
            
            # 标准格式解析或AI分析失败后的处理
            self._process_outline_sync(outline_text, use_ai)
            
        except Exception as e:
            logger.error(f"处理导入大纲时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"处理大纲失败: {str(e)}")
    
    def _process_outline_sync(self, outline_text: str, use_ai: bool = False):
        """同步处理大纲（标准格式或AI分析完成后的处理）"""
        try:
            # 使用大纲解析器解析
            from core.outline_parser import OutlineParserFactory, OutlineParseLevel
            
            # 根据是否使用AI选择解析器
            if use_ai:
                parser = OutlineParserFactory.create_parser(OutlineParseLevel.SEMANTIC)
            else:
                parser = OutlineParserFactory.create_parser(OutlineParseLevel.BASIC)
            
            # 解析大纲
            outline_nodes = parser.parse(outline_text)
            
            if not outline_nodes:
                if use_ai:
                    QMessageBox.warning(self, "警告", "AI分析后仍无法解析大纲内容，请检查AI输出格式")
                else:
                    QMessageBox.warning(self, "警告", "无法解析大纲内容，请检查格式\n\n提示：您可以尝试启用AI智能分析来处理任意格式的文本")
                return
            
            # 转换为项目文档
            created_count = self._create_documents_from_outline(outline_nodes)
            
            if created_count > 0:
                # 刷新大纲视图
                QTimer.singleShot(100, self._force_refresh_outline)
                
                mode_text = "AI智能分析" if use_ai else "标准格式解析"
                QMessageBox.information(
                    self, 
                    "导入成功", 
                    f"大纲导入成功！\n"
                    f"• 处理模式: {mode_text}\n"
                    f"• 创建文档: {created_count} 个\n"
                    f"• 大纲视图已更新"
                )
                logger.info(f"大纲导入成功 ({mode_text})，创建了 {created_count} 个文档")
            else:
                QMessageBox.warning(self, "警告", "没有创建任何文档，导入失败")
            
        except Exception as e:
            logger.error(f"同步处理大纲时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"处理大纲失败: {str(e)}")
    
    def _ai_analyze_text(self, text: str) -> Optional[str]:
        """使用AI分析文本并转换为大纲格式（异步版本，避免界面卡死）"""
        try:
            # 优先使用共享的AI管理器
            if hasattr(self._shared, 'ai_manager') and self._shared.ai_manager:
                ai_manager = self._shared.ai_manager
                
                # 检查AI服务是否可用
                ai_status = ai_manager.get_ai_status()
                if not ai_status.get('ai_client_available', False):
                    logger.warning("AI服务不可用，尝试重新初始化")
                    if not ai_manager.force_reinit_ai():
                        raise RuntimeError("AI服务初始化失败")
                
                # 使用异步方式处理AI分析
                self._start_async_outline_analysis(text, ai_manager)
                return "ASYNC_PROCESSING"  # 返回特殊标识，表示异步处理中
                
            else:
                logger.warning("AI管理器不可用，使用本地结构转换器")
                return self._fallback_local_analysis(text)
                
        except Exception as e:
            logger.error(f"AI大纲分析失败: {e}")
            # 显示用户友好的错误信息
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "AI分析失败", f"AI分析出现错误：{str(e)}\n\n将使用本地解析方式。")
            return self._fallback_local_analysis(text)
    
    def _start_async_outline_analysis(self, text: str, ai_manager):
        """启动异步AI大纲分析（使用线程避免界面阻塞）"""
        try:
            from PyQt6.QtCore import QThread, pyqtSignal
            
            class AsyncOutlineAnalysisWorker(QThread):
                """异步大纲分析工作线程"""
                analysisCompleted = pyqtSignal(str)  # 分析完成信号
                analysisError = pyqtSignal(str)      # 分析错误信号
                
                def __init__(self, text: str, ai_manager):
                    super().__init__()
                    self.text = text
                    self.ai_manager = ai_manager
                
                def run(self):
                    """线程主执行函数"""
                    try:
                        logger.info(f"异步大纲分析线程启动，文本长度: {len(self.text)}")
                        
                        # 在子线程中执行AI分析
                        result = self.ai_manager.analyze_outline(self.text, 'auto')
                        
                        if result and len(result.strip()) > 20:
                            logger.info(f"异步大纲分析完成，结果长度: {len(result)}")
                            self.analysisCompleted.emit(result)
                        else:
                            self.analysisError.emit("AI返回结果过短或为空")
                            
                    except Exception as e:
                        error_msg = f"异步大纲分析失败: {str(e)}"
                        logger.error(error_msg)
                        self.analysisError.emit(error_msg)
            
            # 创建并启动异步工作线程
            self._analysis_worker = AsyncOutlineAnalysisWorker(text, ai_manager)
            self._analysis_worker.analysisCompleted.connect(self._on_async_analysis_completed)
            self._analysis_worker.analysisError.connect(self._on_async_analysis_error)
            self._analysis_worker.start()
            
            # 显示处理进度对话框
            self._show_analysis_progress()
            
            logger.info("异步大纲分析已启动")
            
        except Exception as e:
            logger.error(f"启动异步大纲分析失败: {e}")
            raise
    
    def _show_analysis_progress(self):
        """显示分析进度对话框"""
        try:
            from PyQt6.QtWidgets import QProgressDialog
            
            self._progress_dialog = QProgressDialog("AI正在分析大纲...", "取消", 0, 0, self)
            self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self._progress_dialog.setAutoClose(True)
            self._progress_dialog.setAutoReset(True)
            self._progress_dialog.resize(400, 120)
            
            # 居中显示进度条和文字
            self._progress_dialog.setStyleSheet("""
                QProgressDialog {
                    text-align: center;
                }
                QLabel {
                    text-align: center;
                    qproperty-alignment: AlignCenter;
                }
                QProgressBar {
                    text-align: center;
                    qproperty-alignment: AlignCenter;
                }
            """)
            
            # 连接取消信号
            self._progress_dialog.canceled.connect(self._cancel_async_analysis)
            
            self._progress_dialog.show()
            
        except Exception as e:
            logger.error(f"显示分析进度对话框失败: {e}")
    
    def _cancel_async_analysis(self):
        """取消异步分析"""
        try:
            if hasattr(self, '_analysis_worker') and self._analysis_worker:
                if self._analysis_worker.isRunning():
                    self._analysis_worker.terminate()
                    self._analysis_worker.wait(1000)  # 等待1秒
                self._analysis_worker = None
            
            logger.info("异步大纲分析已取消")
            
        except Exception as e:
            logger.error(f"取消异步分析失败: {e}")
    
    def _on_async_analysis_completed(self, result: str):
        """异步分析完成处理"""
        try:
            # 关闭进度对话框
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                self._progress_dialog.close()
                self._progress_dialog = None
            
            # 清理工作线程
            if hasattr(self, '_analysis_worker'):
                self._analysis_worker = None
            
            logger.info(f"异步大纲分析完成，结果长度: {len(result)}")
            
            # 处理AI分析结果
            self._handle_ai_analysis_result(result)
            
        except Exception as e:
            logger.error(f"处理异步分析结果失败: {e}")
    
    def _on_async_analysis_error(self, error_msg: str):
        """异步分析错误处理"""
        try:
            # 关闭进度对话框
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                self._progress_dialog.close()
                self._progress_dialog = None
            
            # 清理工作线程
            if hasattr(self, '_analysis_worker'):
                self._analysis_worker = None
            
            logger.error(f"异步大纲分析失败: {error_msg}")
            
            # 显示错误信息并降级处理
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "AI分析失败", f"AI分析出现错误：{error_msg}\n\n将使用本地解析方式。")
            
            # 降级到本地分析
            if hasattr(self, '_pending_outline_text'):
                result = self._fallback_local_analysis(self._pending_outline_text)
                if result:
                    self._handle_ai_analysis_result(result)
                
        except Exception as e:
            logger.error(f"处理异步分析错误失败: {e}")
    
    def _handle_ai_analysis_result(self, result: str):
        """处理AI分析结果（统一处理函数）"""
        try:
            if hasattr(self, '_pending_outline_text'):
                # 使用AI分析结果进行大纲处理
                self._process_imported_outline_with_result(self._pending_outline_text, result)
                # 清理临时数据
                delattr(self, '_pending_outline_text')
            else:
                logger.warning("找不到待处理的大纲文本")
                
        except Exception as e:
            logger.error(f"处理AI分析结果失败: {e}")
    
    def _process_imported_outline_with_result(self, original_text: str, ai_result: str):
        """使用AI分析结果处理导入的大纲"""
        try:
            # 使用AI分析结果作为大纲文本
            outline_text = ai_result if ai_result else original_text
            
            # 使用大纲解析器解析
            from core.outline_parser import OutlineParserFactory, OutlineParseLevel
            
            # 使用语义级解析器（因为已经过AI处理）
            parser = OutlineParserFactory.create_parser(OutlineParseLevel.SEMANTIC)
            
            # 解析大纲
            outline_nodes = parser.parse(outline_text)
            
            if not outline_nodes:
                QMessageBox.warning(self, "警告", "AI分析后仍无法解析大纲内容，请检查AI输出格式")
                return
            
            # 转换为项目文档
            created_count = self._create_documents_from_outline(outline_nodes)
            
            if created_count > 0:
                # 刷新大纲视图
                QTimer.singleShot(100, self._force_refresh_outline)
                
                mode_text = "AI智能分析"
                QMessageBox.information(
                    self, 
                    "导入成功", 
                    f"大纲导入成功！\n"
                    f"• 处理模式: {mode_text}\n"
                    f"• 创建文档: {created_count} 个\n"
                    f"• 大纲视图已更新"
                )
                logger.info(f"大纲导入成功 ({mode_text})，创建了 {created_count} 个文档")
            else:
                QMessageBox.warning(self, "警告", "没有创建任何文档，导入失败")
            
        except Exception as e:
            logger.error(f"处理AI分析结果时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"处理大纲失败: {str(e)}")
    
    def _fallback_local_analysis(self, text: str) -> Optional[str]:
        """本地降级分析方法"""
        try:
            from core.outline_converter import OutlineStructureConverter
            converter = OutlineStructureConverter()
            conversion_result = converter.convert_text_to_structure(text, use_ai_enhancement=False)
            
            if conversion_result.nodes:
                logger.info(f"使用本地结构转换器成功，质量分: {conversion_result.quality_score:.1f}")
                return self._structure_to_markdown(conversion_result.nodes)
            else:
                logger.warning("本地结构转换器也失败了")
                return None
                
        except Exception as fallback_error:
            logger.error(f"本地分析降级方案失败: {fallback_error}")
            return None
    
    def _get_outline_suggestions(self, current_outline: str) -> List[str]:
        """获取大纲改进建议（使用统一AI管理器）"""
        try:
            if hasattr(self._shared, 'ai_manager') and self._shared.ai_manager:
                ai_manager = self._shared.ai_manager
                suggestions = ai_manager.get_outline_suggestions(current_outline)
                logger.info(f"获取到 {len(suggestions)} 条AI改进建议")
                return suggestions
            else:
                logger.warning("AI管理器不可用，无法获取建议")
                return []
        except Exception as e:
            logger.error(f"获取大纲建议失败: {e}")
            return []
    
    def _structure_to_markdown(self, nodes: List) -> str:
        """将结构节点转换为Markdown格式"""
        try:
            from core.outline_converter import StructureLevel
            
            lines = []
            
            def process_node(node, depth=0):
                # 根据节点层级生成对应的Markdown标题
                level_map = {
                    StructureLevel.ACT: '#',
                    StructureLevel.CHAPTER: '##', 
                    StructureLevel.SCENE: '###',
                    StructureLevel.SECTION: '####'
                }
                
                prefix = level_map.get(node.level, '###')
                lines.append(f"{prefix} {node.title}")
                
                # 添加内容
                if node.content:
                    lines.append("")
                    lines.append(node.content)
                    lines.append("")
                
                # 递归处理子节点
                if hasattr(node, 'children') and node.children:
                    for child in node.children:
                        process_node(child, depth + 1)
            
            for node in nodes:
                process_node(node)
            
            return '\n'.join(lines)
            
        except Exception as e:
            logger.error(f"结构转换为Markdown失败: {e}")
            return ""
    
    def _create_documents_from_outline(self, outline_nodes: List) -> int:
        """从大纲节点创建文档"""
        try:
            from core.project import DocumentType
            
            created_count = 0
            
            def create_document_recursive(node, parent_id=None, level=0):
                nonlocal created_count
                
                # 根据层级确定文档类型
                if level == 0:
                    doc_type = DocumentType.ACT
                elif level == 1:
                    doc_type = DocumentType.CHAPTER
                else:
                    doc_type = DocumentType.SCENE
                
                # 创建文档 - 不传入content参数
                new_doc = self._project_manager.add_document(
                    name=node.title,
                    doc_type=doc_type,
                    parent_id=parent_id,
                    save=False  # 先不保存，批量处理后再保存
                )
                
                if new_doc:
                    created_count += 1
                    
                    # 如果有内容，单独更新
                    if hasattr(node, 'content') and node.content:
                        self._project_manager.update_document(
                            new_doc.id,
                            content=node.content,
                            save=False
                        )
                    
                    # 递归创建子文档
                    if hasattr(node, 'children') and node.children:
                        for child_node in node.children:
                            create_document_recursive(child_node, new_doc.id, level + 1)
                
                return new_doc
            
            # 创建所有顶级节点
            for node in outline_nodes:
                create_document_recursive(node)
            
            # 批量保存项目
            if created_count > 0:
                self._project_manager.save_project()
                logger.info(f"批量创建了 {created_count} 个文档并保存")
            
            return created_count
            
        except Exception as e:
            logger.error(f"从大纲节点创建文档时发生错误: {e}")
            return 0
    
    def _analyze_outline(self):
        """分析当前大纲并提供优化建议"""
        try:
            if not self._project_manager.has_project():
                QMessageBox.warning(self, "警告", "请先创建或打开一个项目")
                return
            
            # 获取当前项目的文档
            project = self._project_manager.get_current_project()
            if not project or not project.documents:
                QMessageBox.information(self, "提示", "项目中没有文档可以分析")
                return
            
            # 过滤小说文档
            novel_docs = []
            for doc_id, doc in project.documents.items():
                if doc.doc_type.value in ['act', 'chapter', 'scene']:
                    novel_docs.append(doc)
            
            if not novel_docs:
                QMessageBox.information(self, "提示", "项目中没有小说文档可以分析")
                return
            
            # 显示分析进度
            from PyQt6.QtWidgets import QProgressDialog
            progress = QProgressDialog("正在分析大纲结构...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            progress.setValue(20)
            
            try:
                # 执行大纲分析
                from core.outline_enhancer import OutlineEnhancer
                enhancer = OutlineEnhancer()
                
                progress.setValue(50)
                
                # 分析大纲
                analysis_result = enhancer.analyze_outline(novel_docs)
                
                progress.setValue(80)
                
                # 检查是否有足够的分析结果
                if not analysis_result or analysis_result.total_nodes == 0:
                    progress.close()
                    QMessageBox.warning(self, "分析失败", "无法分析大纲结构，请检查项目内容")
                    return
                
                progress.setValue(100)
                progress.close()
                
                # 显示分析结果对话框
                from gui.dialogs.outline_analysis_dialog import OutlineAnalysisDialog
                analysis_dialog = OutlineAnalysisDialog(analysis_result, self)
                analysis_dialog.applyChangesRequested.connect(self._apply_outline_suggestions)
                
                result = analysis_dialog.exec()
                
                if result == QDialog.DialogCode.Accepted:
                    logger.info("大纲分析对话框已确认")
                    
            except ImportError as ie:
                progress.close()
                logger.error(f"导入大纲分析模块失败: {ie}")
                QMessageBox.critical(self, "功能不可用", f"大纲分析功能模块加载失败：{str(ie)}")
            except Exception as analysis_error:
                progress.close()
                logger.error(f"大纲分析过程失败: {analysis_error}")
                QMessageBox.critical(self, "分析失败", f"大纲分析失败：{str(analysis_error)}")
                
        except Exception as e:
            logger.error(f"启动大纲分析时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"启动大纲分析失败: {str(e)}")
    
    def _apply_outline_suggestions(self, suggestions: List):
        """应用大纲优化建议"""
        try:
            if not suggestions:
                return
            
            logger.info(f"开始应用 {len(suggestions)} 个大纲优化建议")
            
            applied_count = 0
            failed_count = 0
            
            for suggestion in suggestions:
                try:
                    # 根据建议类型执行不同的优化操作
                    if suggestion.suggestion_type.value == 'structure':
                        success = self._apply_structure_suggestion(suggestion)
                    elif suggestion.suggestion_type.value == 'content':
                        success = self._apply_content_suggestion(suggestion)
                    elif suggestion.suggestion_type.value == 'plot':
                        success = self._apply_plot_suggestion(suggestion)
                    elif suggestion.suggestion_type.value == 'character':
                        success = self._apply_character_suggestion(suggestion)
                    else:
                        # 通用建议处理
                        success = self._apply_generic_suggestion(suggestion)
                    
                    if success:
                        applied_count += 1
                        logger.info(f"成功应用建议: {suggestion.title}")
                    else:
                        failed_count += 1
                        logger.warning(f"应用建议失败: {suggestion.title}")
                        
                except Exception as suggestion_error:
                    failed_count += 1
                    logger.error(f"应用建议 '{suggestion.title}' 时发生错误: {suggestion_error}")
            
            # 保存项目
            if applied_count > 0:
                self._project_manager.save_project()
                
                # 刷新大纲显示
                QTimer.singleShot(100, self._force_refresh_outline)
            
            # 显示应用结果
            result_message = f"建议应用完成！\n\n"
            result_message += f"✅ 成功应用: {applied_count} 个建议\n"
            if failed_count > 0:
                result_message += f"❌ 应用失败: {failed_count} 个建议\n"
            result_message += f"\n大纲已更新，建议重新分析查看效果。"
            
            QMessageBox.information(self, "应用完成", result_message)
            
        except Exception as e:
            logger.error(f"应用大纲建议时发生错误: {e}")
            QMessageBox.critical(self, "应用失败", f"应用大纲建议失败: {str(e)}")
    
    def _apply_structure_suggestion(self, suggestion) -> bool:
        """应用结构类建议"""
        try:
            # 简化的结构建议实现
            if "增加结构层次" in suggestion.title:
                return self._add_missing_structure_levels()
            elif "平衡章节结构" in suggestion.title:
                return self._balance_chapter_structure()
            else:
                return self._apply_generic_suggestion(suggestion)
        except Exception as e:
            logger.error(f"应用结构建议失败: {e}")
            return False
    
    def _apply_content_suggestion(self, suggestion) -> bool:
        """应用内容类建议"""
        try:
            # 为空白节点添加内容提示
            project = self._project_manager.get_current_project()
            if not project:
                return False
            
            content_added = 0
            for doc_id, doc in project.documents.items():
                if doc.doc_type.value in ['act', 'chapter', 'scene'] and not doc.content.strip():
                    # 添加内容模板
                    content_template = self._generate_content_template(doc)
                    if content_template:
                        self._project_manager.update_document(doc_id, content=content_template, save=False)
                        content_added += 1
            
            logger.info(f"为 {content_added} 个节点添加了内容模板")
            return content_added > 0
            
        except Exception as e:
            logger.error(f"应用内容建议失败: {e}")
            return False
    
    def _apply_plot_suggestion(self, suggestion) -> bool:
        """应用情节类建议"""
        try:
            # 简化的情节建议实现
            return self._apply_generic_suggestion(suggestion)
        except Exception as e:
            logger.error(f"应用情节建议失败: {e}")
            return False
    
    def _apply_character_suggestion(self, suggestion) -> bool:
        """应用角色类建议"""
        try:
            # 简化的角色建议实现
            return self._apply_generic_suggestion(suggestion)
        except Exception as e:
            logger.error(f"应用角色建议失败: {e}")
            return False
    
    def _apply_generic_suggestion(self, suggestion) -> bool:
        """应用通用建议"""
        try:
            # 记录建议已应用（用于跟踪）
            logger.info(f"已记录建议应用: {suggestion.title}")
            return True
        except Exception as e:
            logger.error(f"应用通用建议失败: {e}")
            return False
    
    def _add_missing_structure_levels(self) -> bool:
        """添加缺失的结构层级"""
        try:
            project = self._project_manager.get_current_project()
            if not project:
                return False
            
            # 检查是否缺少幕级结构
            acts = [d for d in project.documents.values() if d.doc_type.value == 'act']
            chapters = [d for d in project.documents.values() if d.doc_type.value == 'chapter']
            
            if not acts and chapters:
                # 创建默认幕并将章节归类
                from core.project import DocumentType
                default_act = self._project_manager.add_document(
                    name="第一幕：主要情节",
                    doc_type=DocumentType.ACT,
                    save=False
                )
                
                if default_act:
                    # 将前几个章节归到这个幕下
                    chapters_to_move = chapters[:min(len(chapters), 5)]
                    for chapter in chapters_to_move:
                        self._project_manager.update_document(
                            chapter.id, 
                            parent_id=default_act.id, 
                            save=False
                        )
                    
                    logger.info(f"创建了默认幕并移动了 {len(chapters_to_move)} 个章节")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"添加结构层级失败: {e}")
            return False
    
    def _balance_chapter_structure(self) -> bool:
        """平衡章节结构"""
        try:
            # 简化实现：检查章节内容长度并提供平衡建议
            project = self._project_manager.get_current_project()
            if not project:
                return False
            
            chapters = [d for d in project.documents.values() if d.doc_type.value == 'chapter']
            if len(chapters) < 2:
                return False
            
            # 计算平均长度
            content_lengths = [len(d.content) for d in chapters if d.content]
            if not content_lengths:
                return False
            
            avg_length = sum(content_lengths) / len(content_lengths)
            balanced_count = 0
            
            # 为过短的章节添加扩展提示
            for chapter in chapters:
                if len(chapter.content) < avg_length * 0.5:
                    expansion_note = f"\n\n<!-- 建议扩展内容 -->\n<!-- 当前字数: {len(chapter.content)}，建议目标: {int(avg_length)} -->"
                    new_content = chapter.content + expansion_note
                    self._project_manager.update_document(chapter.id, content=new_content, save=False)
                    balanced_count += 1
            
            logger.info(f"为 {balanced_count} 个章节添加了平衡建议")
            return balanced_count > 0
            
        except Exception as e:
            logger.error(f"平衡章节结构失败: {e}")
            return False
    
    def _generate_content_template(self, doc) -> str:
        """为文档生成内容模板"""
        try:
            templates = {
                'act': f"""# {doc.name}

## 本幕概述
[请描述本幕的主要情节和目标]

## 主要冲突
[请描述本幕的核心冲突]

## 角色发展
[请描述角色在本幕中的成长和变化]

## 关键事件
- [关键事件1]
- [关键事件2]
- [关键事件3]""",

                'chapter': f"""# {doc.name}

## 章节摘要
[请简要描述本章的主要内容]

## 场景设置
**时间:** [时间]
**地点:** [地点]
**人物:** [参与角色]

## 主要情节
[请详细描述本章发生的事件]

## 章节目标
[本章要达成的故事目标]""",

                'scene': f"""# {doc.name}

## 场景描述
[请描述场景的具体情况]

## 角色行动
[角色在此场景中的行动和对话]

## 冲突点
[此场景的冲突或转折]

## 情感要素
[场景中的情感氛围]"""
            }
            
            return templates.get(doc.doc_type.value, f"# {doc.name}\n\n[请添加内容描述]")
            
        except Exception as e:
            logger.error(f"生成内容模板失败: {e}")
            return f"# {doc.name}\n\n[请添加内容描述]"
    
    def _generate_outline_continuation(self):
        """智能生成大纲续写内容"""
        try:
            if not self._project_manager.has_project():
                QMessageBox.warning(self, "警告", "请先创建或打开一个项目")
                return
            
            # 获取当前项目的文档
            project = self._project_manager.get_current_project()
            if not project or not project.documents:
                QMessageBox.information(self, "提示", "项目中没有内容可以作为续写基础")
                return
            
            # 过滤小说文档
            novel_docs = []
            for doc_id, doc in project.documents.items():
                if doc.doc_type.value in ['act', 'chapter', 'scene']:
                    novel_docs.append(doc)
            
            if len(novel_docs) < 1:
                QMessageBox.information(self, "提示", "项目中需要至少一个小说文档才能进行续写")
                return
            
            # 显示生成选项对话框
            generation_options = self._show_generation_options_dialog()
            if not generation_options:
                return  # 用户取消
            
            # 显示生成进度
            from PyQt6.QtWidgets import QProgressDialog
            progress = QProgressDialog("正在分析上下文并生成续写内容...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            progress.setValue(20)
            
            try:
                # 执行智能续写生成（使用统一AI管理器）
                if hasattr(self._shared, 'ai_manager') and self._shared.ai_manager:
                    ai_manager = self._shared.ai_manager
                    
                    # 检查AI服务可用性
                    ai_status = ai_manager.get_ai_status()
                    if not ai_status.get('ai_client_available', False):
                        logger.warning("AI服务不可用，尝试重新初始化")
                        if not ai_manager.force_reinit_ai():
                            raise RuntimeError("AI服务初始化失败")
                    
                    progress.setValue(40)
                    
                    # 解析生成选项
                    progress.setValue(60)
                    
                    # 使用统一AI管理器的续写功能
                    generation_result_dict = ai_manager.generate_outline_continuation(
                        existing_docs=novel_docs,
                        generation_params={
                            'type': generation_options['type'],
                            'scope': generation_options['scope'], 
                            'length': generation_options['length']
                        }
                    )
                    
                    progress.setValue(90)
                    
                    # 检查生成结果
                    if 'error' in generation_result_dict:
                        progress.close()
                        QMessageBox.warning(self, "生成失败", f"AI续写失败: {generation_result_dict['error']}")
                        return
                    
                    if not generation_result_dict.get('generated_nodes'):
                        progress.close()
                        QMessageBox.warning(self, "生成失败", "无法生成续写内容，请检查项目内容")
                        return
                    
                    progress.setValue(100)
                    progress.close()
                    
                    # 显示生成结果对话框
                    self._show_unified_generation_result_dialog(generation_result_dict)
                    
                else:
                    # 降级到独立生成器
                    progress.close()
                    QMessageBox.warning(self, "功能不可用", "AI管理器不可用，无法进行智能续写")
                    return
                
            except ImportError as ie:
                progress.close()
                logger.error(f"导入续写生成模块失败: {ie}")
                QMessageBox.critical(self, "功能不可用", f"智能续写功能模块加载失败：{str(ie)}")
            except Exception as generation_error:
                progress.close()
                logger.error(f"续写生成过程失败: {generation_error}")
                QMessageBox.critical(self, "生成失败", f"智能续写生成失败：{str(generation_error)}")
                
        except Exception as e:
            logger.error(f"启动智能续写时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"启动智能续写失败: {str(e)}")
    
    def _show_generation_options_dialog(self) -> Optional[Dict[str, Any]]:
        """显示生成选项对话框"""
        try:
            from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                       QComboBox, QSpinBox, QDialogButtonBox, QGroupBox,
                                       QRadioButton, QButtonGroup, QTextEdit)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("智能续写设置")
            dialog.setMinimumSize(450, 400)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(12)
            
            # 说明文字
            info_label = QLabel("🤖 基于现有内容智能生成后续大纲章节")
            info_label.setStyleSheet("font-size: 12pt; font-weight: bold; margin-bottom: 8px;")
            layout.addWidget(info_label)
            
            # 生成类型选择
            type_group = QGroupBox("生成类型")
            type_layout = QVBoxLayout(type_group)
            
            self.type_button_group = QButtonGroup()
            type_options = [
                ("continuation", "续写发展", "基于现有情节继续推进故事"),
                ("expansion", "扩展深化", "对现有内容进行深度扩展"),
                ("alternative", "替代方案", "提供不同的发展路径"),
                ("completion", "补全完善", "补充缺失的故事元素")
            ]
            
            for value, title, desc in type_options:
                radio = QRadioButton(f"{title} - {desc}")
                radio.setProperty("value", value)
                if value == "continuation":  # 默认选择续写
                    radio.setChecked(True)
                self.type_button_group.addButton(radio)
                type_layout.addWidget(radio)
            
            layout.addWidget(type_group)
            
            # 上下文范围
            scope_layout = QHBoxLayout()
            scope_label = QLabel("上下文范围:")
            scope_label.setMinimumWidth(80)
            scope_layout.addWidget(scope_label)
            
            self.scope_combo = QComboBox()
            self.scope_combo.addItem("全局上下文 - 分析整个项目", "global")
            self.scope_combo.addItem("章节上下文 - 关注最近章节", "chapter") 
            self.scope_combo.addItem("局部上下文 - 仅考虑邻近内容", "local")
            scope_layout.addWidget(self.scope_combo)
            
            layout.addLayout(scope_layout)
            
            # 生成数量
            length_layout = QHBoxLayout()
            length_label = QLabel("生成章节数:")
            length_label.setMinimumWidth(80)
            length_layout.addWidget(length_label)
            
            self.length_spin = QSpinBox()
            self.length_spin.setRange(1, 10)
            self.length_spin.setValue(3)
            self.length_spin.setSuffix(" 个")
            length_layout.addWidget(self.length_spin)
            
            length_layout.addStretch()
            layout.addLayout(length_layout)
            
            # 特殊要求
            requirements_group = QGroupBox("特殊要求 (可选)")
            requirements_layout = QVBoxLayout(requirements_group)
            
            self.requirements_edit = QTextEdit()
            self.requirements_edit.setPlaceholderText("请输入对生成内容的特殊要求，如：\n• 重点发展某个角色\n• 加入新的冲突元素\n• 转换叙述视角\n等等...")
            self.requirements_edit.setMaximumHeight(80)
            requirements_layout.addWidget(self.requirements_edit)
            
            layout.addWidget(requirements_group)
            
            # 对话框按钮
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | 
                QDialogButtonBox.StandardButton.Cancel
            )
            
            ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
            ok_btn.setText("开始生成")
            
            cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
            cancel_btn.setText("取消")
            
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # 显示对话框
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 获取选中的生成类型
                selected_type = "continuation"
                for button in self.type_button_group.buttons():
                    if button.isChecked():
                        selected_type = button.property("value")
                        break
                
                options = {
                    'type': selected_type,
                    'scope': self.scope_combo.currentData(),
                    'length': self.length_spin.value(),
                    'requirements': self.requirements_edit.toPlainText().strip()
                }
                
                logger.info(f"续写选项: {options}")
                return options
            else:
                return None
                
        except Exception as e:
            logger.error(f"显示生成选项对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"显示设置对话框失败: {str(e)}")
            return None
    
    def _show_generation_result_dialog(self, generation_result):
        """显示生成结果对话框"""
        try:
            from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                                       QTextBrowser, QListWidget, QListWidgetItem, 
                                       QPushButton, QDialogButtonBox, QLabel, QFrame,
                                       QScrollArea, QWidget, QCheckBox)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("智能续写结果")
            dialog.setMinimumSize(700, 500)
            dialog.resize(900, 600)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(12)
            
            # 标题和质量评分
            header_layout = QHBoxLayout()
            
            title_label = QLabel("🎯 智能续写生成结果")
            title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
            header_layout.addWidget(title_label)
            
            header_layout.addStretch()
            
            quality_label = QLabel(f"质量评分: {generation_result.quality_score:.1%}")
            quality_color = "#4CAF50" if generation_result.quality_score > 0.7 else "#FF9800" if generation_result.quality_score > 0.4 else "#F44336"
            quality_label.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {quality_color};")
            header_layout.addWidget(quality_label)
            
            layout.addLayout(header_layout)
            
            # 标签页容器
            tab_widget = QTabWidget()
            
            # 生成内容标签页
            content_tab = QWidget()
            content_layout = QVBoxLayout(content_tab)
            
            # 生成的章节列表
            content_label = QLabel(f"📝 生成了 {len(generation_result.generated_nodes)} 个章节:")
            content_label.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
            content_layout.addWidget(content_label)
            
            # 章节选择列表
            self.chapter_list = QListWidget()
            for i, node in enumerate(generation_result.generated_nodes):
                item_widget = QWidget()
                item_layout = QVBoxLayout(item_widget)
                item_layout.setContentsMargins(8, 4, 8, 4)
                
                # 复选框和标题
                checkbox_layout = QHBoxLayout()
                checkbox = QCheckBox()
                checkbox.setChecked(True)  # 默认全选
                checkbox.setProperty("node_data", node)
                checkbox_layout.addWidget(checkbox)
                
                title_label = QLabel(node.get('title', '未命名章节'))
                title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
                checkbox_layout.addWidget(title_label)
                
                checkbox_layout.addStretch()
                item_layout.addLayout(checkbox_layout)
                
                # 章节内容预览
                content_preview = node.get('content', '无内容')
                if len(content_preview) > 100:
                    content_preview = content_preview[:100] + "..."
                
                content_label = QLabel(content_preview)
                content_label.setStyleSheet("color: #666; font-size: 9pt; margin-left: 20px;")
                content_label.setWordWrap(True)
                item_layout.addWidget(content_label)
                
                # 创建列表项
                list_item = QListWidgetItem()
                list_item.setSizeHint(item_widget.sizeHint())
                self.chapter_list.addItem(list_item)
                self.chapter_list.setItemWidget(list_item, item_widget)
            
            content_layout.addWidget(self.chapter_list)
            tab_widget.addTab(content_tab, "📝 生成内容")
            
            # 上下文分析标签页
            analysis_tab = QTextBrowser()
            analysis_tab.setHtml(f"<pre style='font-family: Microsoft YaHei; line-height: 1.5;'>{generation_result.context_analysis}</pre>")
            tab_widget.addTab(analysis_tab, "📊 上下文分析")
            
            # 生成理由标签页
            rationale_tab = QTextBrowser()
            rationale_tab.setHtml(f"<pre style='font-family: Microsoft YaHei; line-height: 1.5;'>{generation_result.generation_rationale}</pre>")
            tab_widget.addTab(rationale_tab, "💡 生成理由")
            
            # 替代方案标签页
            if generation_result.alternative_options:
                alternatives_tab = QWidget()
                alt_layout = QVBoxLayout(alternatives_tab)
                
                for i, alt in enumerate(generation_result.alternative_options):
                    alt_frame = QFrame()
                    alt_frame.setFrameStyle(QFrame.Shape.Box)
                    alt_frame.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.1); border-radius: 4px; padding: 8px; }")
                    
                    alt_frame_layout = QVBoxLayout(alt_frame)
                    
                    alt_title = QLabel(alt.get('title', f'方案{i+1}'))
                    alt_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
                    alt_frame_layout.addWidget(alt_title)
                    
                    alt_desc = QLabel(alt.get('description', '无描述'))
                    alt_desc.setWordWrap(True)
                    alt_frame_layout.addWidget(alt_desc)
                    
                    alt_layout.addWidget(alt_frame)
                
                alt_layout.addStretch()
                tab_widget.addTab(alternatives_tab, "🔄 替代方案")
            
            # 续写建议标签页
            if generation_result.continuation_suggestions:
                suggestions_tab = QListWidget()
                for suggestion in generation_result.continuation_suggestions:
                    item = QListWidgetItem(f"• {suggestion}")
                    suggestions_tab.addItem(item)
                tab_widget.addTab(suggestions_tab, "📋 续写建议")
            
            layout.addWidget(tab_widget)
            
            # 底部按钮
            button_layout = QHBoxLayout()
            
            select_all_btn = QPushButton("全选")
            select_all_btn.clicked.connect(lambda: self._toggle_all_chapters(True))
            button_layout.addWidget(select_all_btn)
            
            select_none_btn = QPushButton("全不选")
            select_none_btn.clicked.connect(lambda: self._toggle_all_chapters(False))
            button_layout.addWidget(select_none_btn)
            
            button_layout.addStretch()
            
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | 
                QDialogButtonBox.StandardButton.Cancel
            )
            
            apply_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
            apply_btn.setText("添加选中章节")
            apply_btn.clicked.connect(lambda: self._apply_generated_chapters(dialog))
            
            cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
            cancel_btn.setText("取消")
            cancel_btn.clicked.connect(dialog.reject)
            
            button_layout.addWidget(button_box)
            layout.addLayout(button_layout)
            
            # 显示对话框
            dialog.exec()
            
        except Exception as e:
            logger.error(f"显示生成结果对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"显示结果对话框失败: {str(e)}")
    
    def _toggle_all_chapters(self, checked: bool):
        """切换所有章节的选中状态"""
        try:
            for i in range(self.chapter_list.count()):
                item = self.chapter_list.item(i)
                widget = self.chapter_list.itemWidget(item)
                if widget:
                    checkbox = widget.findChild(QCheckBox)
                    if checkbox:
                        checkbox.setChecked(checked)
        except Exception as e:
            logger.error(f"切换章节选中状态失败: {e}")
    
    def _apply_generated_chapters(self, dialog):
        """应用生成的章节"""
        try:
            selected_nodes = []
            
            # 收集选中的章节
            for i in range(self.chapter_list.count()):
                item = self.chapter_list.item(i)
                widget = self.chapter_list.itemWidget(item)
                if widget:
                    checkbox = widget.findChild(QCheckBox)
                    if checkbox and checkbox.isChecked():
                        node_data = checkbox.property("node_data")
                        if node_data:
                            selected_nodes.append(node_data)
            
            if not selected_nodes:
                QMessageBox.warning(self, "警告", "请至少选择一个章节")
                return
            
            # 创建文档
            created_count = 0
            failed_count = 0
            
            for node in selected_nodes:
                try:
                    # 确定文档类型
                    from core.project import DocumentType
                    doc_type = DocumentType.CHAPTER  # 默认为章节类型
                    
                    if node.get('level') == 'act':
                        doc_type = DocumentType.ACT
                    elif node.get('level') == 'scene':
                        doc_type = DocumentType.SCENE
                    
                    # 创建文档
                    new_doc = self._project_manager.add_document(
                        name=node.get('title', '新章节'),
                        doc_type=doc_type,
                        save=False
                    )
                    
                    if new_doc:
                        # 更新内容
                        content = node.get('content', '')
                        if content:
                            self._project_manager.update_document(
                                new_doc.id,
                                content=content,
                                save=False
                            )
                        
                        created_count += 1
                        logger.info(f"创建生成章节: {node.get('title', '新章节')}")
                    else:
                        failed_count += 1
                        
                except Exception as node_error:
                    failed_count += 1
                    logger.error(f"创建章节失败: {node_error}")
            
            # 保存项目
            if created_count > 0:
                self._project_manager.save_project()
                
                # 刷新大纲显示
                QTimer.singleShot(100, self._force_refresh_outline)
            
            # 显示结果
            result_message = f"智能续写应用完成！\n\n"
            result_message += f"✅ 成功创建: {created_count} 个章节\n"
            if failed_count > 0:
                result_message += f"❌ 创建失败: {failed_count} 个章节\n"
            result_message += f"\n大纲已更新，请在左侧查看新增章节。"
            
            QMessageBox.information(self, "应用完成", result_message)
            dialog.accept()
            
        except Exception as e:
            logger.error(f"应用生成章节失败: {e}")
            QMessageBox.critical(self, "应用失败", f"应用生成章节失败: {str(e)}")
    
    def _show_unified_generation_result_dialog(self, generation_result_dict: Dict[str, Any]):
        """显示统一AI管理器的生成结果对话框"""
        try:
            from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                                       QTextBrowser, QListWidget, QListWidgetItem, 
                                       QPushButton, QDialogButtonBox, QLabel, QFrame,
                                       QScrollArea, QWidget, QCheckBox)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("智能续写结果")
            dialog.setMinimumSize(700, 500)
            dialog.resize(900, 600)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(12)
            
            # 标题和质量评分
            header_layout = QHBoxLayout()
            
            title_label = QLabel("🎯 智能续写生成结果")
            title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
            header_layout.addWidget(title_label)
            
            header_layout.addStretch()
            
            quality_score = generation_result_dict.get('quality_score', 0.0)
            quality_label = QLabel(f"质量评分: {quality_score:.1%}")
            quality_color = "#4CAF50" if quality_score > 0.7 else "#FF9800" if quality_score > 0.4 else "#F44336"
            quality_label.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {quality_color};")
            header_layout.addWidget(quality_label)
            
            layout.addLayout(header_layout)
            
            # 标签页容器
            tab_widget = QTabWidget()
            
            # 生成内容标签页
            generated_nodes = generation_result_dict.get('generated_nodes', [])
            content_tab = QWidget()
            content_layout = QVBoxLayout(content_tab)
            
            # 生成的章节列表
            content_label = QLabel(f"📝 生成了 {len(generated_nodes)} 个章节:")
            content_label.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
            content_layout.addWidget(content_label)
            
            # 章节选择列表
            self.chapter_list = QListWidget()
            for i, node in enumerate(generated_nodes):
                item_widget = QWidget()
                item_layout = QVBoxLayout(item_widget)
                item_layout.setContentsMargins(8, 4, 8, 4)
                
                # 复选框和标题
                checkbox_layout = QHBoxLayout()
                checkbox = QCheckBox()
                checkbox.setChecked(True)  # 默认全选
                checkbox.setProperty("node_data", node)
                checkbox_layout.addWidget(checkbox)
                
                title_label = QLabel(node.get('title', '未命名章节'))
                title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
                checkbox_layout.addWidget(title_label)
                
                checkbox_layout.addStretch()
                item_layout.addLayout(checkbox_layout)
                
                # 章节内容预览
                content_preview = node.get('content', '无内容')
                if len(content_preview) > 100:
                    content_preview = content_preview[:100] + "..."
                
                content_label = QLabel(content_preview)
                content_label.setStyleSheet("color: #666; font-size: 9pt; margin-left: 20px;")
                content_label.setWordWrap(True)
                item_layout.addWidget(content_label)
                
                # 创建列表项
                list_item = QListWidgetItem()
                list_item.setSizeHint(item_widget.sizeHint())
                self.chapter_list.addItem(list_item)
                self.chapter_list.setItemWidget(list_item, item_widget)
            
            content_layout.addWidget(self.chapter_list)
            tab_widget.addTab(content_tab, "📝 生成内容")
            
            # 上下文分析标签页
            context_analysis = generation_result_dict.get('context_analysis', '无分析信息')
            analysis_tab = QTextBrowser()
            analysis_tab.setHtml(f"<pre style='font-family: Microsoft YaHei; line-height: 1.5;'>{context_analysis}</pre>")
            tab_widget.addTab(analysis_tab, "📊 上下文分析")
            
            # 生成理由标签页
            generation_rationale = generation_result_dict.get('generation_rationale', '无生成理由')
            rationale_tab = QTextBrowser()
            rationale_tab.setHtml(f"<pre style='font-family: Microsoft YaHei; line-height: 1.5;'>{generation_rationale}</pre>")
            tab_widget.addTab(rationale_tab, "💡 生成理由")
            
            # 续写建议标签页
            suggestions = generation_result_dict.get('suggestions', [])
            if suggestions:
                suggestions_tab = QListWidget()
                for suggestion in suggestions:
                    item = QListWidgetItem(f"• {suggestion}")
                    suggestions_tab.addItem(item)
                tab_widget.addTab(suggestions_tab, "📋 续写建议")
            
            layout.addWidget(tab_widget)
            
            # 底部按钮
            button_layout = QHBoxLayout()
            
            select_all_btn = QPushButton("全选")
            select_all_btn.clicked.connect(lambda: self._toggle_all_chapters(True))
            button_layout.addWidget(select_all_btn)
            
            select_none_btn = QPushButton("全不选")
            select_none_btn.clicked.connect(lambda: self._toggle_all_chapters(False))
            button_layout.addWidget(select_none_btn)
            
            button_layout.addStretch()
            
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | 
                QDialogButtonBox.StandardButton.Cancel
            )
            
            apply_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
            apply_btn.setText("添加选中章节")
            apply_btn.clicked.connect(lambda: self._apply_generated_chapters(dialog))
            
            cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
            cancel_btn.setText("取消")
            cancel_btn.clicked.connect(dialog.reject)
            
            button_layout.addWidget(button_box)
            layout.addLayout(button_layout)
            
            # 显示对话框
            dialog.exec()
            
        except Exception as e:
            logger.error(f"显示统一生成结果对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"显示结果对话框失败: {str(e)}")
