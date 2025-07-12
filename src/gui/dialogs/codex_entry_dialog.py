"""
Codex条目编辑对话框
支持创建和编辑Codex条目，包括高级特性如别名、关系和进展追踪
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QPushButton, QListWidget, QListWidgetItem,
    QTabWidget, QWidget, QLabel, QGroupBox,
    QDialogButtonBox, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from core.codex_manager import CodexEntry, CodexEntryType

logger = logging.getLogger(__name__)


class CodexEntryDialog(QDialog):
    """Codex条目编辑对话框"""
    
    # 信号定义
    entryUpdated = pyqtSignal(str)  # 条目更新信号
    
    def __init__(self, codex_manager=None, entry_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._codex_manager = codex_manager
        self._entry_id = entry_id
        self._entry: Optional[CodexEntry] = None
        
        # 如果是编辑模式，加载条目
        if entry_id and codex_manager:
            self._entry = codex_manager.get_entry(entry_id)
        
        self._init_ui()
        self._load_entry_data()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("编辑Codex条目" if self._entry else "新建Codex条目")
        self.setModal(True)
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self._tabs = QTabWidget()
        
        # 基本信息标签页
        basic_tab = self._create_basic_tab()
        self._tabs.addTab(basic_tab, "基本信息")
        
        # 别名管理标签页
        aliases_tab = self._create_aliases_tab()
        self._tabs.addTab(aliases_tab, "别名管理")
        
        # 关系网络标签页
        relations_tab = self._create_relations_tab()
        self._tabs.addTab(relations_tab, "关系网络")
        
        # 进展追踪标签页
        progression_tab = self._create_progression_tab()
        self._tabs.addTab(progression_tab, "进展追踪")
        
        layout.addWidget(self._tabs)
        
        # 按钮栏
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_entry)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_basic_tab(self) -> QWidget:
        """创建基本信息标签页"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 标题
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("输入条目标题...")
        layout.addRow("标题:", self._title_edit)
        
        # 类型
        self._type_combo = QComboBox()
        for entry_type in CodexEntryType:
            self._type_combo.addItem(
                self._get_type_display_name(entry_type.value),
                entry_type
            )
        layout.addRow("类型:", self._type_combo)
        
        # 描述
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("输入条目描述...")
        self._desc_edit.setMaximumHeight(150)
        layout.addRow("描述:", self._desc_edit)
        
        # 选项
        self._global_check = QCheckBox("全局条目（自动包含在AI上下文中）")
        layout.addRow(self._global_check)
        
        self._track_check = QCheckBox("追踪引用（在文本中检测和高亮）")
        self._track_check.setChecked(True)
        layout.addRow(self._track_check)
        
        return widget
    
    def _create_aliases_tab(self) -> QWidget:
        """创建别名管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("别名可以帮助系统识别同一条目的不同称呼")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 别名列表
        self._aliases_list = QListWidget()
        self._aliases_list.setAlternatingRowColors(True)
        layout.addWidget(self._aliases_list)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self._alias_edit = QLineEdit()
        self._alias_edit.setPlaceholderText("输入新别名...")
        button_layout.addWidget(self._alias_edit)
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_alias)
        button_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("删除")
        remove_btn.clicked.connect(self._remove_alias)
        button_layout.addWidget(remove_btn)
        
        layout.addLayout(button_layout)
        
        return widget
    
    def _create_relations_tab(self) -> QWidget:
        """创建关系网络标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("定义此条目与其他条目之间的关系")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 关系表格
        self._relations_table = QTableWidget()
        self._relations_table.setColumnCount(3)
        self._relations_table.setHorizontalHeaderLabels(["目标条目", "关系类型", "描述"])
        
        header = self._relations_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(1, 120)
        
        layout.addWidget(self._relations_table)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        add_relation_btn = QPushButton("添加关系")
        add_relation_btn.clicked.connect(self._add_relation)
        button_layout.addWidget(add_relation_btn)
        
        remove_relation_btn = QPushButton("删除关系")
        remove_relation_btn.clicked.connect(self._remove_relation)
        button_layout.addWidget(remove_relation_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return widget
    
    def _create_progression_tab(self) -> QWidget:
        """创建进展追踪标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("记录条目在故事中的发展和变化")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 进展列表
        self._progression_list = QListWidget()
        self._progression_list.itemSelectionChanged.connect(self._on_progression_selected)
        splitter.addWidget(self._progression_list)
        
        # 进展详情
        detail_group = QGroupBox("进展详情")
        detail_layout = QVBoxLayout(detail_group)
        
        self._progression_detail = QTextEdit()
        self._progression_detail.setReadOnly(True)
        detail_layout.addWidget(self._progression_detail)
        
        splitter.addWidget(detail_group)
        
        layout.addWidget(splitter)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        add_prog_btn = QPushButton("添加进展")
        add_prog_btn.clicked.connect(self._add_progression)
        button_layout.addWidget(add_prog_btn)
        
        edit_prog_btn = QPushButton("编辑进展")
        edit_prog_btn.clicked.connect(self._edit_progression)
        button_layout.addWidget(edit_prog_btn)
        
        remove_prog_btn = QPushButton("删除进展")
        remove_prog_btn.clicked.connect(self._remove_progression)
        button_layout.addWidget(remove_prog_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return widget
    
    def _get_type_display_name(self, type_value: str) -> str:
        """获取类型显示名称"""
        type_names = {
            "CHARACTER": "👤 角色",
            "LOCATION": "📍 地点",
            "OBJECT": "📦 物品",
            "LORE": "📜 传说",
            "SUBPLOT": "📖 子情节",
            "OTHER": "📎 其他"
        }
        return type_names.get(type_value, type_value)
    
    def _load_entry_data(self):
        """加载条目数据"""
        if not self._entry:
            return
        
        # 基本信息
        self._title_edit.setText(self._entry.title)
        
        # 查找并设置类型
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i) == self._entry.entry_type:
                self._type_combo.setCurrentIndex(i)
                break
        
        self._desc_edit.setPlainText(self._entry.description)
        self._global_check.setChecked(self._entry.is_global)
        self._track_check.setChecked(self._entry.track_references)
        
        # 别名
        self._aliases_list.clear()
        for alias in self._entry.aliases:
            self._aliases_list.addItem(alias)
        
        # 关系
        self._relations_table.setRowCount(len(self._entry.relationships))
        for i, relation in enumerate(self._entry.relationships):
            self._relations_table.setItem(i, 0, QTableWidgetItem(relation.get("target", "")))
            self._relations_table.setItem(i, 1, QTableWidgetItem(relation.get("type", "")))
            self._relations_table.setItem(i, 2, QTableWidgetItem(relation.get("description", "")))
        
        # 进展
        self._progression_list.clear()
        for prog in self._entry.progression:
            item = QListWidgetItem(f"{prog.get('date', '未知时间')} - {prog.get('title', '未命名')}")
            item.setData(Qt.ItemDataRole.UserRole, prog)
            self._progression_list.addItem(item)
    
    @pyqtSlot()
    def _add_alias(self):
        """添加别名"""
        alias = self._alias_edit.text().strip()
        if alias:
            # 检查重复
            items = [self._aliases_list.item(i).text() 
                    for i in range(self._aliases_list.count())]
            if alias not in items:
                self._aliases_list.addItem(alias)
                self._alias_edit.clear()
    
    @pyqtSlot()
    def _remove_alias(self):
        """删除别名"""
        current = self._aliases_list.currentRow()
        if current >= 0:
            self._aliases_list.takeItem(current)
    
    @pyqtSlot()
    def _add_relation(self):
        """添加关系"""
        row = self._relations_table.rowCount()
        self._relations_table.insertRow(row)
        self._relations_table.setItem(row, 0, QTableWidgetItem(""))
        self._relations_table.setItem(row, 1, QTableWidgetItem(""))
        self._relations_table.setItem(row, 2, QTableWidgetItem(""))
    
    @pyqtSlot()
    def _remove_relation(self):
        """删除关系"""
        current = self._relations_table.currentRow()
        if current >= 0:
            self._relations_table.removeRow(current)
    
    @pyqtSlot()
    def _add_progression(self):
        """添加进展"""
        from .progression_dialog import ProgressionDialog
        dialog = ProgressionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            prog_data = dialog.get_progression_data()
            item = QListWidgetItem(f"{prog_data['date']} - {prog_data['title']}")
            item.setData(Qt.ItemDataRole.UserRole, prog_data)
            self._progression_list.addItem(item)
    
    @pyqtSlot()
    def _edit_progression(self):
        """编辑进展"""
        current = self._progression_list.currentItem()
        if current:
            prog_data = current.data(Qt.ItemDataRole.UserRole)
            from .progression_dialog import ProgressionDialog
            dialog = ProgressionDialog(self, prog_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_data = dialog.get_progression_data()
                current.setText(f"{new_data['date']} - {new_data['title']}")
                current.setData(Qt.ItemDataRole.UserRole, new_data)
    
    @pyqtSlot()
    def _remove_progression(self):
        """删除进展"""
        current = self._progression_list.currentRow()
        if current >= 0:
            self._progression_list.takeItem(current)
    
    @pyqtSlot()
    def _on_progression_selected(self):
        """进展选择变化"""
        current = self._progression_list.currentItem()
        if current:
            prog_data = current.data(Qt.ItemDataRole.UserRole)
            detail_text = f"标题: {prog_data.get('title', '未命名')}\n"
            detail_text += f"时间: {prog_data.get('date', '未知')}\n"
            detail_text += f"章节: {prog_data.get('chapter', '')}\n\n"
            detail_text += f"描述:\n{prog_data.get('description', '')}"
            self._progression_detail.setPlainText(detail_text)
        else:
            self._progression_detail.clear()
    
    @pyqtSlot()
    def _save_entry(self):
        """保存条目"""
        # 验证输入
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "警告", "请输入条目标题")
            return
        
        # 收集数据
        entry_type = self._type_combo.currentData()
        description = self._desc_edit.toPlainText()
        is_global = self._global_check.isChecked()
        track_references = self._track_check.isChecked()
        
        # 收集别名
        aliases = []
        for i in range(self._aliases_list.count()):
            aliases.append(self._aliases_list.item(i).text())
        
        # 收集关系
        relationships = []
        for i in range(self._relations_table.rowCount()):
            target = self._relations_table.item(i, 0).text() if self._relations_table.item(i, 0) else ""
            rel_type = self._relations_table.item(i, 1).text() if self._relations_table.item(i, 1) else ""
            desc = self._relations_table.item(i, 2).text() if self._relations_table.item(i, 2) else ""
            
            if target:  # 至少要有目标
                relationships.append({
                    "target": target,
                    "type": rel_type,
                    "description": desc
                })
        
        # 收集进展
        progression = []
        for i in range(self._progression_list.count()):
            item = self._progression_list.item(i)
            progression.append(item.data(Qt.ItemDataRole.UserRole))
        
        # 保存到Codex管理器
        if self._codex_manager:
            try:
                if self._entry_id:
                    # 更新现有条目
                    success = self._codex_manager.update_entry(
                        self._entry_id,
                        title=title,
                        entry_type=entry_type,
                        description=description,
                        is_global=is_global,
                        track_references=track_references,
                        aliases=aliases,
                        relationships=relationships,
                        progression=progression
                    )
                    
                    if success:
                        self.entryUpdated.emit(self._entry_id)
                        self.accept()
                    else:
                        QMessageBox.warning(self, "错误", "更新条目失败")
                else:
                    # 创建新条目
                    entry_id = self._codex_manager.add_entry(
                        title=title,
                        entry_type=entry_type,
                        description=description,
                        is_global=is_global,
                        aliases=aliases
                    )
                    
                    # 更新关系和进展
                    if entry_id:
                        self._codex_manager.update_entry(
                            entry_id,
                            relationships=relationships,
                            progression=progression,
                            track_references=track_references
                        )
                        self.entryUpdated.emit(entry_id)
                        self.accept()
                    else:
                        QMessageBox.warning(self, "错误", "创建条目失败")
                        
            except Exception as e:
                logger.error(f"保存条目失败: {e}")
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
        else:
            # 没有Codex管理器，只返回数据
            self.accept()
    
    def get_entry_data(self) -> Dict[str, Any]:
        """获取条目数据（用于没有Codex管理器的情况）"""
        return {
            "title": self._title_edit.text().strip(),
            "entry_type": self._type_combo.currentData(),
            "description": self._desc_edit.toPlainText(),
            "is_global": self._global_check.isChecked(),
            "track_references": self._track_check.isChecked(),
            "aliases": [self._aliases_list.item(i).text() 
                       for i in range(self._aliases_list.count())],
            "relationships": self._get_relationships_data(),
            "progression": self._get_progression_data()
        }
    
    def _get_relationships_data(self) -> List[Dict[str, str]]:
        """获取关系数据"""
        relationships = []
        for i in range(self._relations_table.rowCount()):
            target = self._relations_table.item(i, 0).text() if self._relations_table.item(i, 0) else ""
            rel_type = self._relations_table.item(i, 1).text() if self._relations_table.item(i, 1) else ""
            desc = self._relations_table.item(i, 2).text() if self._relations_table.item(i, 2) else ""
            
            if target:
                relationships.append({
                    "target": target,
                    "type": rel_type,
                    "description": desc
                })
        return relationships
    
    def _get_progression_data(self) -> List[Dict[str, Any]]:
        """获取进展数据"""
        progression = []
        for i in range(self._progression_list.count()):
            item = self._progression_list.item(i)
            progression.append(item.data(Qt.ItemDataRole.UserRole))
        return progression