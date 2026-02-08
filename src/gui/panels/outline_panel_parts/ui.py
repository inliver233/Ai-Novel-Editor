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




class OutlinePanelUIMixin:
    """OutlinePanel mixin."""
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

