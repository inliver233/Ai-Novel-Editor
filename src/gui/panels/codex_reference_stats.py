"""
Codex引用统计组件
显示每个Codex条目的引用次数、位置和详细统计信息
"""

import logging
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QPushButton, QComboBox, QFrame, QHeaderView,
    QSplitter, QTextEdit, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush

logger = logging.getLogger(__name__)


class CodexReferenceStatsWidget(QWidget):
    """Codex引用统计组件"""
    
    # 信号定义
    entrySelected = pyqtSignal(str)  # 选择条目时发出
    locationClicked = pyqtSignal(str, int)  # 点击位置时发出（文档ID，位置）
    
    def __init__(self, codex_manager=None, parent=None):
        super().__init__(parent)
        self._codex_manager = codex_manager
        self._reference_data: Dict[str, List] = {}
        
        self._init_ui()
        self._refresh_stats()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 控制栏
        control_bar = self._create_control_bar()
        layout.addWidget(control_bar)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 统计树
        self._stats_tree = self._create_stats_tree()
        splitter.addWidget(self._stats_tree)
        
        # 详情面板
        self._detail_panel = self._create_detail_panel()
        splitter.addWidget(self._detail_panel)
        
        # 设置分割比例
        splitter.setSizes([300, 150])
        
        layout.addWidget(splitter)
    
    def _create_control_bar(self) -> QWidget:
        """创建控制栏"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 排序选项
        layout.addWidget(QLabel("排序:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItems([
            "按名称",
            "按引用次数",
            "按类型",
            "按最近使用"
        ])
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        layout.addWidget(self._sort_combo)
        
        layout.addStretch()
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_stats)
        layout.addWidget(refresh_btn)
        
        return widget
    
    def _create_stats_tree(self) -> QTreeWidget:
        """创建统计树"""
        tree = QTreeWidget()
        tree.setHeaderLabels(["条目", "类型", "引用次数", "文档数"])
        
        # 设置列宽
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 80)
        header.resizeSection(2, 80)
        header.resizeSection(3, 60)
        
        # 设置样式
        tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #BDC3C7;
                border-radius: 4px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 2px;
            }
            QTreeWidget::item:selected {
                background-color: #3498DB;
                color: white;
            }
            QTreeWidget::branch {
                background: white;
            }
        """)
        
        # 连接信号
        tree.itemSelectionChanged.connect(self._on_selection_changed)
        tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        return tree
    
    def _create_detail_panel(self) -> QWidget:
        """创建详情面板"""
        group = QGroupBox("引用详情")
        layout = QVBoxLayout(group)
        
        # 详情文本
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setMaximumHeight(150)
        self._detail_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #BDC3C7;
                border-radius: 4px;
                font-size: 11px;
                padding: 4px;
            }
        """)
        
        layout.addWidget(self._detail_text)
        
        return group
    
    def _refresh_stats(self):
        """刷新统计数据"""
        if not self._codex_manager:
            return
        
        self._stats_tree.clear()
        self._reference_data.clear()
        
        # 获取所有条目
        entries = self._codex_manager.get_all_entries()
        
        # 创建类型分组
        type_items = {}
        
        for entry in entries:
            # 获取该条目的引用
            references = self._codex_manager.get_references_for_entry(entry.id)
            
            # 统计文档数
            doc_ids = set(ref.document_id for ref in references)
            
            # 存储引用数据
            self._reference_data[entry.id] = references
            
            # 获取或创建类型节点
            type_name = entry.entry_type.value
            if type_name not in type_items:
                type_item = QTreeWidgetItem(self._stats_tree)
                type_item.setText(0, self._get_type_display_name(type_name))
                type_item.setExpanded(True)
                
                # 设置类型节点样式
                font = QFont()
                font.setBold(True)
                type_item.setFont(0, font)
                type_item.setBackground(0, QBrush(QColor(236, 240, 241)))
                
                type_items[type_name] = type_item
            
            # 创建条目节点
            item = QTreeWidgetItem(type_items[type_name])
            item.setText(0, entry.title)
            item.setText(1, self._get_type_icon(type_name))
            item.setText(2, str(len(references)))
            item.setText(3, str(len(doc_ids)))
            item.setData(0, Qt.ItemDataRole.UserRole, entry.id)
            
            # 根据引用次数设置颜色
            if len(references) > 10:
                item.setForeground(2, QBrush(QColor(231, 76, 60)))  # 红色，热门
            elif len(references) > 5:
                item.setForeground(2, QBrush(QColor(241, 196, 15)))  # 黄色，常用
            else:
                item.setForeground(2, QBrush(QColor(52, 152, 219)))  # 蓝色，普通
        
        # 更新类型节点的统计
        for type_name, type_item in type_items.items():
            child_count = type_item.childCount()
            total_refs = sum(
                int(type_item.child(i).text(2)) 
                for i in range(child_count)
            )
            type_item.setText(2, f"({total_refs})")
            type_item.setText(3, f"({child_count})")
        
        self._apply_current_sort()
    
    def _get_type_display_name(self, type_name: str) -> str:
        """获取类型显示名称"""
        type_names = {
            "CHARACTER": "角色",
            "LOCATION": "地点",
            "OBJECT": "物品",
            "LORE": "传说",
            "SUBPLOT": "子情节",
            "OTHER": "其他"
        }
        return type_names.get(type_name, type_name)
    
    def _get_type_icon(self, type_name: str) -> str:
        """获取类型图标"""
        type_icons = {
            "CHARACTER": "👤",
            "LOCATION": "📍",
            "OBJECT": "📦",
            "LORE": "📜",
            "SUBPLOT": "📖",
            "OTHER": "📎"
        }
        return type_icons.get(type_name, "📎")
    
    def _on_sort_changed(self, index: int):
        """排序方式变化"""
        self._apply_current_sort()
    
    def _apply_current_sort(self):
        """应用当前排序"""
        sort_index = self._sort_combo.currentIndex()
        
        # 对每个类型组内的项目进行排序
        for i in range(self._stats_tree.topLevelItemCount()):
            type_item = self._stats_tree.topLevelItem(i)
            self._sort_type_children(type_item, sort_index)
    
    def _sort_type_children(self, type_item: QTreeWidgetItem, sort_method: int):
        """排序类型节点的子项"""
        # 提取所有子项
        children = []
        while type_item.childCount() > 0:
            children.append(type_item.takeChild(0))
        
        # 根据排序方法排序
        if sort_method == 0:  # 按名称
            children.sort(key=lambda x: x.text(0))
        elif sort_method == 1:  # 按引用次数
            children.sort(key=lambda x: int(x.text(2)), reverse=True)
        elif sort_method == 2:  # 按类型（已经按类型分组了）
            pass
        elif sort_method == 3:  # 按最近使用
            # TODO: 实现按最近使用排序
            pass
        
        # 重新添加子项
        for child in children:
            type_item.addChild(child)
    
    def _on_selection_changed(self):
        """选择变化处理"""
        items = self._stats_tree.selectedItems()
        if not items:
            self._detail_text.clear()
            return
        
        item = items[0]
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not entry_id:
            self._detail_text.clear()
            return
        
        # 显示引用详情
        self._show_reference_details(entry_id)
        
        # 发送信号
        self.entrySelected.emit(entry_id)
    
    def _show_reference_details(self, entry_id: str):
        """显示引用详情"""
        references = self._reference_data.get(entry_id, [])
        if not references:
            self._detail_text.setPlainText("暂无引用")
            return
        
        # 按文档分组
        doc_refs = {}
        for ref in references:
            if ref.document_id not in doc_refs:
                doc_refs[ref.document_id] = []
            doc_refs[ref.document_id].append(ref)
        
        # 生成详情文本
        details = []
        for doc_id, refs in doc_refs.items():
            details.append(f"📄 文档: {doc_id}")
            details.append(f"   引用次数: {len(refs)}")
            
            # 显示前3个引用的上下文
            for i, ref in enumerate(refs[:3]):
                context = f"{ref.context_before}【{ref.reference_text}】{ref.context_after}"
                details.append(f"   {i+1}. {context.strip()}")
            
            if len(refs) > 3:
                details.append(f"   ... 还有 {len(refs) - 3} 处引用")
            
            details.append("")
        
        self._detail_text.setPlainText("\n".join(details))
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """双击条目处理"""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if entry_id:
            # 可以在这里实现跳转到第一个引用的功能
            references = self._reference_data.get(entry_id, [])
            if references:
                first_ref = references[0]
                self.locationClicked.emit(first_ref.document_id, first_ref.position_start)
    
    def set_codex_manager(self, codex_manager):
        """设置Codex管理器"""
        self._codex_manager = codex_manager
        self._refresh_stats()
    
    def refresh(self):
        """刷新统计"""
        self._refresh_stats()