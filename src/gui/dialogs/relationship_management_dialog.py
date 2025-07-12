"""
关系管理对话框
用于管理Codex条目之间的关系网络
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QGroupBox, QMessageBox,
    QDialogButtonBox, QInputDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QTabWidget,
    QWidget, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from core.codex_manager import CodexManager, CodexEntry, CodexEntryType

logger = logging.getLogger(__name__)


class RelationshipManagementDialog(QDialog):
    """关系管理对话框"""
    
    # 信号定义
    relationshipsUpdated = pyqtSignal(str)  # 关系更新信号
    
    # 预定义的关系类型
    RELATIONSHIP_TYPES = {
        CodexEntryType.CHARACTER: [
            "父子", "母子", "父女", "母女", "兄弟", "姐妹", "兄妹", "姐弟",
            "夫妻", "恋人", "朋友", "敌人", "师父", "弟子", "同门", "盟友",
            "上司", "下属", "同事", "竞争对手", "仇人", "救命恩人"
        ],
        CodexEntryType.LOCATION: [
            "包含", "邻接", "通往", "隶属于", "对立", "贸易伙伴", "联盟"
        ],
        CodexEntryType.OBJECT: [
            "拥有", "创造", "损坏", "修复", "使用", "收藏", "丢失", "寻找"
        ],
        CodexEntryType.LORE: [
            "起源", "影响", "关联", "冲突", "融合", "继承"
        ],
        CodexEntryType.SUBPLOT: [
            "前置", "后续", "平行", "冲突", "依赖", "影响"
        ]
    }
    
    def __init__(self, codex_manager: CodexManager, entry_id: str, parent=None):
        super().__init__(parent)
        self._codex_manager = codex_manager
        self._entry_id = entry_id
        self._entry: Optional[CodexEntry] = None
        
        # 加载条目
        if entry_id and codex_manager:
            self._entry = codex_manager.get_entry(entry_id)
        
        if not self._entry:
            raise ValueError(f"找不到条目: {entry_id}")
        
        self._init_ui()
        self._load_relationships()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"管理关系 - {self._entry.title}")
        self.setModal(True)
        self.resize(700, 500)
        
        layout = QVBoxLayout(self)
        
        # 条目信息区域
        info_group = QGroupBox("条目信息")
        info_layout = QFormLayout(info_group)
        
        self._title_label = QLabel(self._entry.title)
        self._title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        info_layout.addRow("标题:", self._title_label)
        
        self._type_label = QLabel(self._entry.entry_type.value)
        info_layout.addRow("类型:", self._type_label)
        
        layout.addWidget(info_group)
        
        # 标签页
        tab_widget = QTabWidget()
        
        # 关系管理标签页
        self._create_relationships_tab(tab_widget)
        
        # 关系网络视图标签页
        self._create_network_tab(tab_widget)
        
        layout.addWidget(tab_widget)
        
        # 对话框按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_relationships)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_relationships_tab(self, tab_widget: QTabWidget):
        """创建关系管理标签页"""
        relationships_widget = QWidget()
        layout = QVBoxLayout(relationships_widget)
        
        # 说明文本
        explanation = QLabel(
            "关系用于定义该条目与其他条目之间的连接。建立关系网络有助于创作时"
            "的上下文理解和情节一致性检查。"
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(explanation)
        
        # 关系表格
        self._relationships_table = QTableWidget()
        self._relationships_table.setColumnCount(4)
        self._relationships_table.setHorizontalHeaderLabels(["目标条目", "关系类型", "关系强度", "备注"])
        
        # 设置表格属性
        header = self._relationships_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self._relationships_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._relationships_table.setAlternatingRowColors(True)
        
        layout.addWidget(self._relationships_table)
        
        # 关系操作按钮
        button_layout = QHBoxLayout()
        
        self._add_relationship_btn = QPushButton("添加关系")
        self._add_relationship_btn.clicked.connect(self._add_relationship)
        button_layout.addWidget(self._add_relationship_btn)
        
        self._edit_relationship_btn = QPushButton("编辑关系")
        self._edit_relationship_btn.clicked.connect(self._edit_relationship)
        self._edit_relationship_btn.setEnabled(False)
        button_layout.addWidget(self._edit_relationship_btn)
        
        self._remove_relationship_btn = QPushButton("删除关系")
        self._remove_relationship_btn.clicked.connect(self._remove_relationship)
        self._remove_relationship_btn.setEnabled(False)
        button_layout.addWidget(self._remove_relationship_btn)
        
        button_layout.addStretch()
        
        self._quick_add_btn = QPushButton("快速添加")
        self._quick_add_btn.clicked.connect(self._quick_add_relationship)
        self._quick_add_btn.setToolTip("基于条目类型快速添加常见关系")
        button_layout.addWidget(self._quick_add_btn)
        
        layout.addLayout(button_layout)
        
        # 连接选择变化事件
        self._relationships_table.itemSelectionChanged.connect(self._on_relationship_selection_changed)
        
        tab_widget.addTab(relationships_widget, "关系管理")
    
    def _create_network_tab(self, tab_widget: QTabWidget):
        """创建关系网络视图标签页"""
        network_widget = QWidget()
        layout = QVBoxLayout(network_widget)
        
        # 网络统计
        stats_group = QGroupBox("关系统计")
        stats_layout = QFormLayout(stats_group)
        
        self._total_relationships_label = QLabel("0")
        stats_layout.addRow("总关系数:", self._total_relationships_label)
        
        self._relationship_types_label = QLabel("无")
        stats_layout.addRow("关系类型:", self._relationship_types_label)
        
        self._connected_entries_label = QLabel("0")
        stats_layout.addRow("连接的条目:", self._connected_entries_label)
        
        layout.addWidget(stats_group)
        
        # 关系网络文本视图
        network_group = QGroupBox("关系网络")
        network_layout = QVBoxLayout(network_group)
        
        self._network_view = QTextEdit()
        self._network_view.setReadOnly(True)
        self._network_view.setFont(QFont("Consolas", 10))
        network_layout.addWidget(self._network_view)
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        
        self._refresh_network_btn = QPushButton("刷新网络视图")
        self._refresh_network_btn.clicked.connect(self._update_network_view)
        refresh_layout.addWidget(self._refresh_network_btn)
        
        network_layout.addLayout(refresh_layout)
        layout.addWidget(network_group)
        
        tab_widget.addTab(network_widget, "网络视图")
    
    def _load_relationships(self):
        """加载当前关系"""
        self._relationships_table.setRowCount(0)
        
        relationships = self._entry.relationships or []
        
        for i, relationship in enumerate(relationships):
            self._add_relationship_row(relationship)
        
        self._update_network_view()
    
    def _add_relationship_row(self, relationship: Dict[str, Any]):
        """添加关系行到表格"""
        row = self._relationships_table.rowCount()
        self._relationships_table.insertRow(row)
        
        # 目标条目
        target_id = relationship.get('target_id', '')
        target_entry = self._codex_manager.get_entry(target_id) if target_id else None
        target_text = target_entry.title if target_entry else f"未知条目 ({target_id})"
        
        target_item = QTableWidgetItem(target_text)
        target_item.setData(Qt.ItemDataRole.UserRole, target_id)
        self._relationships_table.setItem(row, 0, target_item)
        
        # 关系类型
        rel_type = relationship.get('type', '')
        type_item = QTableWidgetItem(rel_type)
        self._relationships_table.setItem(row, 1, type_item)
        
        # 关系强度
        strength = relationship.get('strength', 1)
        strength_item = QTableWidgetItem(str(strength))
        self._relationships_table.setItem(row, 2, strength_item)
        
        # 备注
        notes = relationship.get('notes', '')
        notes_item = QTableWidgetItem(notes)
        self._relationships_table.setItem(row, 3, notes_item)
    
    def _on_relationship_selection_changed(self):
        """处理关系选择变化"""
        has_selection = bool(self._relationships_table.selectedItems())
        self._edit_relationship_btn.setEnabled(has_selection)
        self._remove_relationship_btn.setEnabled(has_selection)
    
    @pyqtSlot()
    def _add_relationship(self):
        """添加新关系"""
        dialog = RelationshipEditDialog(
            codex_manager=self._codex_manager,
            source_entry=self._entry,
            parent=self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            relationship = dialog.get_relationship()
            self._add_relationship_row(relationship)
            self._update_network_view()
    
    @pyqtSlot()
    def _edit_relationship(self):
        """编辑选中的关系"""
        current_row = self._relationships_table.currentRow()
        if current_row >= 0:
            # 获取当前关系数据
            target_item = self._relationships_table.item(current_row, 0)
            type_item = self._relationships_table.item(current_row, 1)
            strength_item = self._relationships_table.item(current_row, 2)
            notes_item = self._relationships_table.item(current_row, 3)
            
            relationship = {
                'target_id': target_item.data(Qt.ItemDataRole.UserRole),
                'type': type_item.text(),
                'strength': int(strength_item.text()) if strength_item.text().isdigit() else 1,
                'notes': notes_item.text()
            }
            
            dialog = RelationshipEditDialog(
                codex_manager=self._codex_manager,
                source_entry=self._entry,
                relationship=relationship,
                parent=self
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_relationship = dialog.get_relationship()
                
                # 更新表格
                target_entry = self._codex_manager.get_entry(new_relationship['target_id'])
                target_text = target_entry.title if target_entry else f"未知条目 ({new_relationship['target_id']})"
                
                target_item.setText(target_text)
                target_item.setData(Qt.ItemDataRole.UserRole, new_relationship['target_id'])
                type_item.setText(new_relationship['type'])
                strength_item.setText(str(new_relationship['strength']))
                notes_item.setText(new_relationship['notes'])
                
                self._update_network_view()
    
    @pyqtSlot()
    def _remove_relationship(self):
        """删除选中的关系"""
        current_row = self._relationships_table.currentRow()
        if current_row >= 0:
            target_item = self._relationships_table.item(current_row, 0)
            target_text = target_item.text()
            
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除与 '{target_text}' 的关系吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._relationships_table.removeRow(current_row)
                self._update_network_view()
    
    @pyqtSlot()
    def _quick_add_relationship(self):
        """快速添加关系"""
        # 获取当前条目类型的常见关系
        common_types = self.RELATIONSHIP_TYPES.get(self._entry.entry_type, [])
        
        if not common_types:
            QMessageBox.information(self, "快速添加", "该条目类型没有预定义的关系类型")
            return
        
        # 选择关系类型
        rel_type, ok = QInputDialog.getItem(
            self, "选择关系类型",
            f"为 '{self._entry.title}' 选择关系类型:",
            common_types, 0, False
        )
        
        if not ok:
            return
        
        # 获取可用的目标条目
        all_entries = self._codex_manager.get_all_entries()
        available_entries = [entry for entry in all_entries if entry.id != self._entry.id]
        
        if not available_entries:
            QMessageBox.information(self, "快速添加", "没有可用的目标条目")
            return
        
        # 选择目标条目
        entry_names = [f"{entry.title} ({entry.entry_type.value})" for entry in available_entries]
        target_name, ok = QInputDialog.getItem(
            self, "选择目标条目",
            f"选择与 '{self._entry.title}' 建立 '{rel_type}' 关系的条目:",
            entry_names, 0, False
        )
        
        if ok:
            # 找到选中的条目
            selected_index = entry_names.index(target_name)
            target_entry = available_entries[selected_index]
            
            # 创建关系
            relationship = {
                'target_id': target_entry.id,
                'type': rel_type,
                'strength': 3,  # 默认强度
                'notes': f"通过快速添加创建的{rel_type}关系"
            }
            
            self._add_relationship_row(relationship)
            self._update_network_view()
    
    def _update_network_view(self):
        """更新网络视图"""
        relationships = self._get_current_relationships()
        
        # 更新统计信息
        self._total_relationships_label.setText(str(len(relationships)))
        
        if relationships:
            types = list(set([rel['type'] for rel in relationships]))
            self._relationship_types_label.setText(", ".join(types))
            
            connected_entries = list(set([rel['target_id'] for rel in relationships]))
            self._connected_entries_label.setText(str(len(connected_entries)))
        else:
            self._relationship_types_label.setText("无")
            self._connected_entries_label.setText("0")
        
        # 生成网络视图文本
        network_text = self._generate_network_text(relationships)
        self._network_view.setPlainText(network_text)
    
    def _generate_network_text(self, relationships: List[Dict[str, Any]]) -> str:
        """生成网络视图文本"""
        if not relationships:
            return "该条目目前没有建立任何关系。"
        
        lines = [f"📍 {self._entry.title} ({self._entry.entry_type.value})", ""]
        
        # 按关系类型分组
        by_type = {}
        for rel in relationships:
            rel_type = rel['type']
            if rel_type not in by_type:
                by_type[rel_type] = []
            by_type[rel_type].append(rel)
        
        for rel_type, rels in by_type.items():
            lines.append(f"🔗 {rel_type} 关系:")
            
            for rel in rels:
                target_entry = self._codex_manager.get_entry(rel['target_id'])
                target_name = target_entry.title if target_entry else f"未知条目 ({rel['target_id']})"
                target_type = f"({target_entry.entry_type.value})" if target_entry else ""
                
                strength = "★" * rel.get('strength', 1)
                notes = f" - {rel['notes']}" if rel.get('notes') else ""
                
                lines.append(f"   └─ {target_name} {target_type} {strength}{notes}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _get_current_relationships(self) -> List[Dict[str, Any]]:
        """获取当前关系列表"""
        relationships = []
        
        for row in range(self._relationships_table.rowCount()):
            target_item = self._relationships_table.item(row, 0)
            type_item = self._relationships_table.item(row, 1)
            strength_item = self._relationships_table.item(row, 2)
            notes_item = self._relationships_table.item(row, 3)
            
            relationship = {
                'target_id': target_item.data(Qt.ItemDataRole.UserRole),
                'type': type_item.text(),
                'strength': int(strength_item.text()) if strength_item.text().isdigit() else 1,
                'notes': notes_item.text()
            }
            relationships.append(relationship)
        
        return relationships
    
    @pyqtSlot()
    def _save_relationships(self):
        """保存关系"""
        try:
            relationships = self._get_current_relationships()
            
            # 更新条目
            if self._codex_manager.update_entry(self._entry_id, relationships=relationships):
                self.relationshipsUpdated.emit(self._entry_id)
                self.accept()
                logger.info(f"关系已保存: {len(relationships)} 个关系")
            else:
                QMessageBox.critical(self, "保存失败", "无法保存关系，请重试")
                
        except Exception as e:
            logger.error(f"保存关系时出错: {e}")
            QMessageBox.critical(self, "保存错误", f"保存关系时发生错误: {str(e)}")


class RelationshipEditDialog(QDialog):
    """关系编辑对话框"""
    
    def __init__(self, codex_manager: CodexManager, source_entry: CodexEntry, 
                 relationship: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._codex_manager = codex_manager
        self._source_entry = source_entry
        self._relationship = relationship or {}
        
        self._init_ui()
        
        if relationship:
            self._load_relationship_data()
    
    def _init_ui(self):
        """初始化UI"""
        title = "编辑关系" if self._relationship else "添加关系"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 表单
        form_layout = QFormLayout()
        
        # 目标条目选择
        self._target_combo = QComboBox()
        self._target_combo.setEditable(False)
        
        # 填充目标条目
        all_entries = self._codex_manager.get_all_entries()
        available_entries = [entry for entry in all_entries if entry.id != self._source_entry.id]
        
        for entry in available_entries:
            self._target_combo.addItem(f"{entry.title} ({entry.entry_type.value})", entry.id)
        
        form_layout.addRow("目标条目:", self._target_combo)
        
        # 关系类型
        self._type_combo = QComboBox()
        self._type_combo.setEditable(True)
        
        # 根据源条目类型填充关系类型
        common_types = RelationshipManagementDialog.RELATIONSHIP_TYPES.get(
            self._source_entry.entry_type, []
        )
        
        for rel_type in common_types:
            self._type_combo.addItem(rel_type)
        
        form_layout.addRow("关系类型:", self._type_combo)
        
        # 关系强度
        self._strength_spin = QSpinBox()
        self._strength_spin.setRange(1, 5)
        self._strength_spin.setValue(3)
        self._strength_spin.setToolTip("1=弱关系, 3=一般关系, 5=强关系")
        form_layout.addRow("关系强度:", self._strength_spin)
        
        # 备注
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(80)
        self._notes_edit.setPlaceholderText("可选的关系描述或备注...")
        form_layout.addRow("备注:", self._notes_edit)
        
        layout.addLayout(form_layout)
        
        # 对话框按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_relationship_data(self):
        """加载关系数据"""
        # 设置目标条目
        target_id = self._relationship.get('target_id', '')
        for i in range(self._target_combo.count()):
            if self._target_combo.itemData(i) == target_id:
                self._target_combo.setCurrentIndex(i)
                break
        
        # 设置关系类型
        rel_type = self._relationship.get('type', '')
        self._type_combo.setCurrentText(rel_type)
        
        # 设置关系强度
        strength = self._relationship.get('strength', 3)
        self._strength_spin.setValue(strength)
        
        # 设置备注
        notes = self._relationship.get('notes', '')
        self._notes_edit.setPlainText(notes)
    
    def _validate_and_accept(self):
        """验证并接受"""
        if self._target_combo.currentIndex() == -1:
            QMessageBox.warning(self, "验证失败", "请选择目标条目")
            return
        
        if not self._type_combo.currentText().strip():
            QMessageBox.warning(self, "验证失败", "请输入关系类型")
            return
        
        self.accept()
    
    def get_relationship(self) -> Dict[str, Any]:
        """获取关系数据"""
        return {
            'target_id': self._target_combo.currentData(),
            'type': self._type_combo.currentText().strip(),
            'strength': self._strength_spin.value(),
            'notes': self._notes_edit.toPlainText().strip()
        }