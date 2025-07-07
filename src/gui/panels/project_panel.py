from __future__ import annotations

"""
项目管理面板
基于novelWriter的项目树设计，实现Act-Chapter-Scene层次结构
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QMenu, QMessageBox, QSplitter,
    QGroupBox, QToolButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QMimeData
from PyQt6.QtGui import QAction, QIcon, QDrag, QPixmap
from typing import TYPE_CHECKING
from core.project import DocumentType, DocumentStatus

if TYPE_CHECKING:
    from core.config import Config
    from core.shared import Shared
    from core.project import ProjectManager


logger = logging.getLogger(__name__)


class ProjectPanel(QWidget):
    """项目管理面板"""
    
    # 信号定义
    documentSelected = pyqtSignal(str)  # 文档选择信号
    documentCreated = pyqtSignal(str, str)  # 文档创建信号 (类型, 名称)
    documentDeleted = pyqtSignal(str)  # 文档删除信号
    documentMoved = pyqtSignal(str, str)  # 文档移动信号 (from, to)
    
    def __init__(self, config: Config, shared: Shared, project_manager: ProjectManager, parent=None):
        super().__init__(parent)

        self._config = config
        self._shared = shared
        self._project_manager = project_manager

        self._init_ui()
        self._init_signals()
        self._load_project_tree()

        logger.info("Project panel initialized")
    
    def _init_ui(self):
        """初始化UI（优化紧凑布局）"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)  # 减少边距
        layout.setSpacing(4)                   # 减少间距
        
        # 标题栏
        title_frame = self._create_title_frame()
        layout.addWidget(title_frame)
        
        # 项目树
        self._project_tree = self._create_project_tree()
        layout.addWidget(self._project_tree)
        
        # 工具栏
        toolbar_frame = self._create_toolbar()
        layout.addWidget(toolbar_frame)
        
        # 设置样式
        # The stylesheet is now managed globally by the theme QSS files.
        # We only keep styles that are specific to this panel and not theme-dependent.
        self.setStyleSheet("""
            ProjectPanel {
                border-right: 1px solid #555555;
            }
        """)
    
    def _create_title_frame(self) -> QFrame:
        """创建紧凑标题栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)  # 减少垂直边距
        
        # 标题
        title_label = QLabel("项目结构")
        # Style is now managed globally by the theme QSS files.
        title_label.setStyleSheet("""
            QLabel {
                font-size: 12px;  /* 稍微减小字体 */
                font-weight: bold;
                padding: 2px;     /* 减少内边距 */
            }
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 折叠按钮（紧凑化）
        collapse_btn = QToolButton()
        collapse_btn.setText("折叠")
        collapse_btn.setMaximumWidth(40)  # 限制按钮宽度
        collapse_btn.setToolTip("折叠项目面板")
        collapse_btn.clicked.connect(lambda: self.parent().parent()._toggle_project_panel() if hasattr(self.parent().parent(), '_toggle_project_panel') else None)
        layout.addWidget(collapse_btn)
        
        return frame
        collapse_btn = QToolButton()
        collapse_btn.setText("−")
        collapse_btn.setFixedSize(20, 20)
        # Style is now managed globally by the theme QSS files.
        collapse_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(collapse_btn)
        
        return frame
    
    def _create_project_tree(self) -> QTreeWidget:
        """创建项目树"""
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(True)
        tree.setAlternatingRowColors(True)
        tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        
        # 设置样式
        # Style is now managed globally by the theme QSS files.
        # Specific branch/image styling might need to be adapted or moved if icons are theme-dependent
        tree.setStyleSheet("""
            QTreeWidget {
                outline: none;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                border: none;
                border-radius: 3px;
                margin: 1px;
            }
            /* Branch styles might need resource files for dark theme */
        """)
        
        # 项目树将在_load_project_tree中填充数据
        
        return tree
    
    def _load_project_tree(self):
        """加载项目树数据"""
        self._project_tree.clear()

        project = self._project_manager.get_current_project()
        if not project:
            # 显示空项目提示
            placeholder = QTreeWidgetItem(self._project_tree)
            placeholder.setText(0, "未打开项目")
            placeholder.setDisabled(True)
            return

        # 构建项目树
        tree_data = self._project_manager.get_document_tree()
        self._build_tree_items(tree_data, None)

    def _build_tree_items(self, tree_data, parent_item):
        """递归构建树项目"""
        for node in tree_data:
            document = node['document']

            # 创建树项目
            if parent_item:
                item = QTreeWidgetItem(parent_item)
            else:
                item = QTreeWidgetItem(self._project_tree)

            # 设置文本和数据
            item.setText(0, document.name)
            item.setData(0, Qt.ItemDataRole.UserRole, document.id)

            # 设置图标和样式
            self._set_item_style(item, document)

            # 递归添加子项目
            if node['children']:
                self._build_tree_items(node['children'], item)
                item.setExpanded(True)

    def _set_item_style(self, item: QTreeWidgetItem, document):
        """设置项目样式"""
        # 根据文档类型设置不同的样式
        # Colors are now inherited from the global dark_theme.qss
        # We only apply font weight changes here.
        if document.doc_type in [DocumentType.ROOT, DocumentType.ACT]:
            item.setFont(0, self._get_bold_font())

        # 根据状态设置样式
        if document.status == DocumentStatus.FINISHED:
            font = item.font(0)
            font.setStrikeOut(True)
            item.setFont(0, font)

    def _get_bold_font(self):
        """获取粗体字体"""
        from PyQt6.QtGui import QFont
        font = QFont()
        font.setBold(True)
        return font

    def _get_color(self, color_hex: str):
        """获取颜色"""
        from PyQt6.QtGui import QColor
        return QColor(color_hex)
    
    def _create_toolbar(self) -> QFrame:
        """创建工具栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 新建按钮
        new_btn = QPushButton("新建")
        new_btn.setFixedHeight(28)
        new_btn.setToolTip("新建文档 (Ctrl+N)")
        new_btn.clicked.connect(self._on_new_document)
        layout.addWidget(new_btn)

        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setFixedHeight(28)
        delete_btn.setToolTip("删除选中的文档")
        delete_btn.clicked.connect(self._on_delete_document)
        layout.addWidget(delete_btn)
        
        layout.addStretch()
        
        # 设置按钮样式
        # Button styles are now managed globally by the theme QSS files.
        # This ensures consistency and respects the selected theme.
        # The setStyleSheet calls are removed.
        pass
        
        return frame
    
    def _init_signals(self):
        """初始化信号连接"""
        self._project_tree.itemClicked.connect(self._on_item_clicked)
        self._project_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._project_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._project_tree.customContextMenuRequested.connect(self._show_context_menu)
    
    @pyqtSlot(QTreeWidgetItem, int)
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """项目点击处理"""
        if item:
            item_text = item.text(0)
            logger.debug(f"Item clicked: {item_text}")
            # 这里可以添加选择逻辑
    
    @pyqtSlot(QTreeWidgetItem, int)
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """项目双击处理"""
        if item:
            item_text = item.text(0)
            doc_id = item.data(0, Qt.ItemDataRole.UserRole)
            logger.info(f"Item double-clicked: {item_text}")
            # 发出文档选择信号，发送文档ID
            if doc_id:
                self.documentSelected.emit(doc_id)
            else:
                self.documentSelected.emit(item_text)  # 兼容性处理
    
    @pyqtSlot()
    def _on_new_document(self):
        """新建文档"""
        current_item = self._project_tree.currentItem()
        parent_id = None

        if current_item:
            parent_id = current_item.data(0, Qt.ItemDataRole.UserRole)

        # 显示新建对话框，让用户选择类型和名称
        result = self._show_new_document_dialog(parent_id)
        if result:
            doc_type, name = result
            doc_id = self._project_manager.add_document(name, doc_type, parent_id)
            if doc_id:
                self._load_project_tree()
                self.documentCreated.emit(doc_type.value, name)

    def _show_new_document_dialog(self, parent_id: Optional[str]) -> Optional[tuple]:
        """显示新建文档对话框"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("新建项目结构")
        dialog.setModal(True)
        dialog.resize(300, 150)

        layout = QVBoxLayout(dialog)

        # 名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("名称:"))
        name_edit = QLineEdit()
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)

        # 类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("类型:"))
        type_combo = QComboBox()

        # 根据父级类型确定可选的子类型
        available_types = self._get_available_types(parent_id)
        for doc_type, display_name in available_types:
            type_combo.addItem(display_name, doc_type)

        type_layout.addWidget(type_combo)
        layout.addLayout(type_layout)

        # 按钮
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")

        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        # 设置默认焦点
        name_edit.setFocus()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            if name:
                selected_type = type_combo.currentData()
                return (selected_type, name)

        return None

    def _get_available_types(self, parent_id: Optional[str]) -> List[tuple]:
        """获取可用的文档类型"""
        if not parent_id:
            # 顶级可以创建幕
            return [(DocumentType.ACT, "幕")]

        parent_doc = self._project_manager.get_document(parent_id)
        if not parent_doc:
            return [(DocumentType.SCENE, "场景")]

        if parent_doc.doc_type == DocumentType.ROOT:
            # 根据根目录的类型确定子类型
            if parent_doc.metadata and parent_doc.metadata.get("is_novel_root"):
                # 小说根目录下可以创建幕
                return [(DocumentType.ACT, "幕")]
            elif parent_doc.metadata and parent_doc.metadata.get("is_character_root"):
                # 角色根目录下可以创建角色
                return [(DocumentType.CHARACTER, "角色")]
            elif parent_doc.metadata and parent_doc.metadata.get("is_world_root"):
                # 世界观根目录下可以创建世界观元素
                return [
                    (DocumentType.LOCATION, "地点"),
                    (DocumentType.ITEM, "物品"),
                    (DocumentType.CONCEPT, "概念")
                ]
            else:
                # 默认创建幕
                return [(DocumentType.ACT, "幕")]
        elif parent_doc.doc_type == DocumentType.ACT:
            # 幕下可以创建章
            return [(DocumentType.CHAPTER, "章")]
        elif parent_doc.doc_type == DocumentType.CHAPTER:
            # 章下可以创建场景
            return [(DocumentType.SCENE, "场景")]
        elif parent_doc.doc_type == DocumentType.CHARACTER:
            # 角色下可以创建子角色
            return [(DocumentType.CHARACTER, "子角色")]
        else:
            # 其他情况默认创建场景
            return [(DocumentType.SCENE, "场景")]

    def _determine_document_type(self, parent_id: Optional[str]) -> Optional[DocumentType]:
        """根据父级确定文档类型"""
        if not parent_id:
            return DocumentType.ACT

        parent_doc = self._project_manager.get_document(parent_id)
        if not parent_doc:
            return DocumentType.SCENE

        if parent_doc.doc_type == DocumentType.ROOT:
            return DocumentType.ACT
        elif parent_doc.doc_type == DocumentType.ACT:
            return DocumentType.CHAPTER
        elif parent_doc.doc_type == DocumentType.CHAPTER:
            return DocumentType.SCENE
        else:
            return DocumentType.SCENE
    
    @pyqtSlot()
    def _on_delete_document(self):
        """删除文档"""
        current_item = self._project_tree.currentItem()
        if not current_item:
            return

        doc_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not doc_id:
            return

        document = self._project_manager.get_document(doc_id)
        if not document:
            return

        # 检查是否为根文档
        if document.doc_type == DocumentType.ROOT:
            QMessageBox.warning(self, "无法删除", "无法删除根文档")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 '{document.name}' 及其所有子文档吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._project_manager.remove_document(doc_id):
                self._load_project_tree()
                self.documentDeleted.emit(doc_id)
                logger.info(f"Document deleted: {document.name}")
    
    @pyqtSlot('QPoint')
    def _show_context_menu(self, position):
        """显示右键菜单"""
        item = self._project_tree.itemAt(position)
        if not item:
            return

        # 获取文档信息
        doc_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not doc_id:
            return

        document = self._project_manager.get_document(doc_id)
        if not document:
            return

        menu = QMenu(self)

        # 根据文档类型显示不同的菜单项
        if document.doc_type in [DocumentType.ROOT, DocumentType.ACT, DocumentType.CHAPTER]:
            # 新建子项
            new_action = QAction("新建子项", self)
            new_action.triggered.connect(lambda: self._add_child_item(item))
            menu.addAction(new_action)

        # 重命名（根目录不能重命名）
        if document.doc_type != DocumentType.ROOT:
            rename_action = QAction("重命名", self)
            rename_action.triggered.connect(lambda: self._rename_item(item))
            menu.addAction(rename_action)

        menu.addSeparator()

        # 删除（根目录不能删除）
        if document.doc_type != DocumentType.ROOT:
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self._delete_item(item))
            menu.addAction(delete_action)

        # 显示菜单
        global_pos = self._project_tree.mapToGlobal(position)
        menu.exec(global_pos)
    
    def _add_child_item(self, parent_item: QTreeWidgetItem):
        """添加子项"""
        parent_id = parent_item.data(0, Qt.ItemDataRole.UserRole) if parent_item else None

        # 显示新建对话框，让用户选择类型和名称
        result = self._show_new_document_dialog(parent_id)
        if result:
            doc_type, name = result
            doc_id = self._project_manager.add_document(name, doc_type, parent_id)
            if doc_id:
                self._load_project_tree()
                self.documentCreated.emit(doc_type.value, name)
    
    def _rename_item(self, item: QTreeWidgetItem):
        """重命名项目"""
        doc_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not doc_id:
            return

        current_name = item.text(0)

        # 获取新名称
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入新名称:", text=current_name)

        if ok and new_name.strip() and new_name.strip() != current_name:
            if self._project_manager.update_document(doc_id, name=new_name.strip()):
                self._load_project_tree()
                logger.info(f"Document renamed: {current_name} -> {new_name.strip()}")
            else:
                QMessageBox.warning(self, "重命名失败", "无法重命名文档")
    
    def _delete_item(self, item: QTreeWidgetItem):
        """删除项目"""
        doc_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not doc_id:
            return

        document = self._project_manager.get_document(doc_id)
        if not document:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 '{document.name}' 及其所有子项吗？\n\n此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._project_manager.remove_document(doc_id):
                self._load_project_tree()
                self.documentDeleted.emit(doc_id)
                logger.info(f"Document deleted: {document.name}")
            else:
                QMessageBox.warning(self, "删除失败", "无法删除文档")
    
    def get_selected_document(self) -> Optional[str]:
        """获取当前选中的文档"""
        current_item = self._project_tree.currentItem()
        return current_item.text(0) if current_item else None
    
    def expand_all(self):
        """展开所有项目"""
        self._project_tree.expandAll()
    
    def collapse_all(self):
        """折叠所有项目"""
        self._project_tree.collapseAll()

    def refresh_project_tree(self):
        """刷新项目树"""
        self._load_project_tree()

    def set_project(self, project_path: str):
        """设置当前项目"""
        if self._project_manager.open_project(project_path):
            self._load_project_tree()
        else:
            QMessageBox.warning(self, "打开项目失败", f"无法打开项目: {project_path}")
