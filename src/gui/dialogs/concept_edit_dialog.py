"""
概念编辑对话框
支持创建和编辑不同类型的概念（角色、地点、情节、设定等）
"""

import logging
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QLineEdit, QTextEdit, QSpinBox, QComboBox, QPushButton, QLabel,
    QGroupBox, QListWidget, QListWidgetItem, QMessageBox, QCheckBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.concepts import ConceptType, Concept, CharacterConcept, LocationConcept, PlotConcept


logger = logging.getLogger(__name__)


class ConceptEditDialog(QDialog):
    """概念编辑对话框"""
    
    conceptSaved = pyqtSignal(dict)  # 概念保存信号
    
    def __init__(self, parent=None, concept_type: ConceptType = ConceptType.CHARACTER, 
                 concept_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        
        self._concept_type = concept_type
        self._concept_data = concept_data or {}
        self._is_editing = bool(concept_data)
        
        self._init_ui()
        self._load_data()
        
        # 设置对话框属性
        self.setModal(True)
        self.setMinimumSize(500, 600)
        self.resize(600, 700)
        
        title = "编辑" if self._is_editing else "新建"
        type_name = self._get_type_display_name()
        self.setWindowTitle(f"{title}{type_name}")
        
        logger.debug(f"Concept edit dialog initialized: {concept_type.value}")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 基础信息区域
        basic_group = self._create_basic_info_group()
        layout.addWidget(basic_group)
        
        # 扩展信息标签页
        self._tabs = QTabWidget()
        
        # 基础属性标签页
        attributes_tab = self._create_attributes_tab()
        self._tabs.addTab(attributes_tab, "属性")
        
        # 类型特定标签页
        specific_tab = self._create_type_specific_tab()
        if specific_tab:
            type_name = self._get_type_display_name()
            self._tabs.addTab(specific_tab, f"{type_name}信息")
        
        layout.addWidget(self._tabs)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_basic_info_group(self) -> QGroupBox:
        """创建基础信息组"""
        group = QGroupBox("基础信息")
        layout = QFormLayout(group)
        
        # 名称
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("请输入概念名称")
        layout.addRow("名称*:", self._name_edit)
        
        # 描述
        self._description_edit = QTextEdit()
        self._description_edit.setPlaceholderText("请输入概念描述")
        self._description_edit.setMaximumHeight(100)
        layout.addRow("描述:", self._description_edit)
        
        return group
    
    def _create_attributes_tab(self) -> QWidget:
        """创建属性标签页"""
        from PyQt6.QtWidgets import QWidget
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 别名
        aliases_group = QGroupBox("别名")
        aliases_layout = QVBoxLayout(aliases_group)
        
        self._aliases_list = QListWidget()
        self._aliases_list.setMaximumHeight(100)
        aliases_layout.addWidget(self._aliases_list)
        
        aliases_btn_layout = QHBoxLayout()
        add_alias_btn = QPushButton("添加")
        add_alias_btn.clicked.connect(self._add_alias)
        remove_alias_btn = QPushButton("删除")
        remove_alias_btn.clicked.connect(self._remove_alias)
        
        aliases_btn_layout.addWidget(add_alias_btn)
        aliases_btn_layout.addWidget(remove_alias_btn)
        aliases_btn_layout.addStretch()
        aliases_layout.addLayout(aliases_btn_layout)
        
        layout.addWidget(aliases_group)
        
        # 标签
        tags_group = QGroupBox("标签")
        tags_layout = QVBoxLayout(tags_group)
        
        self._tags_list = QListWidget()
        self._tags_list.setMaximumHeight(100)
        tags_layout.addWidget(self._tags_list)
        
        tags_btn_layout = QHBoxLayout()
        add_tag_btn = QPushButton("添加")
        add_tag_btn.clicked.connect(self._add_tag)
        remove_tag_btn = QPushButton("删除")
        remove_tag_btn.clicked.connect(self._remove_tag)
        
        tags_btn_layout.addWidget(add_tag_btn)
        tags_btn_layout.addWidget(remove_tag_btn)
        tags_btn_layout.addStretch()
        tags_layout.addLayout(tags_btn_layout)
        
        layout.addWidget(tags_group)
        
        # 其他属性
        other_group = QGroupBox("其他属性")
        other_layout = QFormLayout(other_group)
        
        # 优先级
        self._priority_spin = QSpinBox()
        self._priority_spin.setRange(1, 10)
        self._priority_spin.setValue(5)
        other_layout.addRow("优先级:", self._priority_spin)
        
        # 自动检测
        self._auto_detect_check = QCheckBox("启用自动检测")
        self._auto_detect_check.setChecked(True)
        other_layout.addRow("", self._auto_detect_check)
        
        layout.addWidget(other_group)
        layout.addStretch()
        
        return widget
    
    def _create_type_specific_tab(self) -> Optional[QWidget]:
        """创建类型特定标签页"""
        if self._concept_type == ConceptType.CHARACTER:
            return self._create_character_tab()
        elif self._concept_type == ConceptType.LOCATION:
            return self._create_location_tab()
        elif self._concept_type == ConceptType.PLOT:
            return self._create_plot_tab()
        else:
            return None
    
    def _create_character_tab(self) -> QWidget:
        """创建角色标签页"""
        from PyQt6.QtWidgets import QWidget
        
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 年龄
        self._age_spin = QSpinBox()
        self._age_spin.setRange(0, 200)
        self._age_spin.setSpecialValueText("未设置")
        layout.addRow("年龄:", self._age_spin)
        
        # 性别
        self._gender_combo = QComboBox()
        self._gender_combo.addItems(["", "男", "女", "其他"])
        layout.addRow("性别:", self._gender_combo)
        
        # 职业
        self._occupation_edit = QLineEdit()
        self._occupation_edit.setPlaceholderText("请输入职业")
        layout.addRow("职业:", self._occupation_edit)
        
        # 外貌
        self._appearance_edit = QTextEdit()
        self._appearance_edit.setPlaceholderText("请描述外貌特征")
        self._appearance_edit.setMaximumHeight(80)
        layout.addRow("外貌:", self._appearance_edit)
        
        # 背景故事
        self._backstory_edit = QTextEdit()
        self._backstory_edit.setPlaceholderText("请输入背景故事")
        self._backstory_edit.setMaximumHeight(80)
        layout.addRow("背景:", self._backstory_edit)
        
        return widget
    
    def _create_location_tab(self) -> QWidget:
        """创建地点标签页"""
        from PyQt6.QtWidgets import QWidget
        
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 地点类型
        self._location_type_combo = QComboBox()
        self._location_type_combo.addItems([
            "general", "city", "building", "room", "outdoor", "virtual"
        ])
        layout.addRow("类型:", self._location_type_combo)
        
        # 氛围
        self._atmosphere_edit = QLineEdit()
        self._atmosphere_edit.setPlaceholderText("请描述氛围")
        layout.addRow("氛围:", self._atmosphere_edit)
        
        # 重要性
        self._significance_edit = QLineEdit()
        self._significance_edit.setPlaceholderText("请描述重要性")
        layout.addRow("重要性:", self._significance_edit)
        
        # 物理描述
        self._physical_desc_edit = QTextEdit()
        self._physical_desc_edit.setPlaceholderText("请描述物理特征")
        self._physical_desc_edit.setMaximumHeight(80)
        layout.addRow("物理描述:", self._physical_desc_edit)
        
        return widget
    
    def _create_plot_tab(self) -> QWidget:
        """创建情节标签页"""
        from PyQt6.QtWidgets import QWidget
        
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 情节类型
        self._plot_type_combo = QComboBox()
        self._plot_type_combo.addItems(["main", "subplot", "arc"])
        layout.addRow("类型:", self._plot_type_combo)
        
        # 状态
        self._status_combo = QComboBox()
        self._status_combo.addItems(["planned", "active", "resolved"])
        layout.addRow("状态:", self._status_combo)
        
        # 冲突类型
        self._conflict_type_edit = QLineEdit()
        self._conflict_type_edit.setPlaceholderText("请描述冲突类型")
        layout.addRow("冲突类型:", self._conflict_type_edit)
        
        # 解决方案
        self._resolution_edit = QTextEdit()
        self._resolution_edit.setPlaceholderText("请描述解决方案")
        self._resolution_edit.setMaximumHeight(80)
        layout.addRow("解决方案:", self._resolution_edit)
        
        return widget
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._save_concept)
        ok_btn.setDefault(True)
        layout.addWidget(ok_btn)
        
        return layout
    
    def _get_type_display_name(self) -> str:
        """获取类型显示名称"""
        type_names = {
            ConceptType.CHARACTER: "角色",
            ConceptType.LOCATION: "地点", 
            ConceptType.PLOT: "情节",
            ConceptType.SETTING: "设定",
            ConceptType.ITEM: "物品",
            ConceptType.EVENT: "事件"
        }
        return type_names.get(self._concept_type, "概念")
    
    def _load_data(self):
        """加载数据"""
        if not self._concept_data:
            return
        
        # 加载基础信息
        self._name_edit.setText(self._concept_data.get('name', ''))
        self._description_edit.setPlainText(self._concept_data.get('description', ''))
        
        # 加载别名
        aliases = self._concept_data.get('aliases', [])
        for alias in aliases:
            item = QListWidgetItem(alias)
            self._aliases_list.addItem(item)
        
        # 加载标签
        tags = self._concept_data.get('tags', [])
        for tag in tags:
            item = QListWidgetItem(tag)
            self._tags_list.addItem(item)
        
        # 加载其他属性
        self._priority_spin.setValue(self._concept_data.get('priority', 5))
        self._auto_detect_check.setChecked(self._concept_data.get('auto_detect', True))
        
        # 加载类型特定数据
        self._load_type_specific_data()
    
    def _load_type_specific_data(self):
        """加载类型特定数据"""
        if self._concept_type == ConceptType.CHARACTER:
            # 处理age字段，确保不为None
            age_value = self._concept_data.get('age', 0)
            if age_value is None:
                age_value = 0
            self._age_spin.setValue(age_value)

            self._gender_combo.setCurrentText(self._concept_data.get('gender', '') or '')
            self._occupation_edit.setText(self._concept_data.get('occupation', '') or '')
            self._appearance_edit.setPlainText(self._concept_data.get('appearance', '') or '')
            self._backstory_edit.setPlainText(self._concept_data.get('backstory', '') or '')
        
        elif self._concept_type == ConceptType.LOCATION:
            self._location_type_combo.setCurrentText(self._concept_data.get('location_type', 'general'))
            self._atmosphere_edit.setText(self._concept_data.get('atmosphere', ''))
            self._significance_edit.setText(self._concept_data.get('significance', ''))
            self._physical_desc_edit.setPlainText(self._concept_data.get('physical_description', ''))
        
        elif self._concept_type == ConceptType.PLOT:
            self._plot_type_combo.setCurrentText(self._concept_data.get('plot_type', 'main'))
            self._status_combo.setCurrentText(self._concept_data.get('status', 'planned'))
            self._conflict_type_edit.setText(self._concept_data.get('conflict_type', ''))
            self._resolution_edit.setPlainText(self._concept_data.get('resolution', ''))
    
    def _add_alias(self):
        """添加别名"""
        from PyQt6.QtWidgets import QInputDialog
        
        text, ok = QInputDialog.getText(self, "添加别名", "请输入别名:")
        if ok and text.strip():
            item = QListWidgetItem(text.strip())
            self._aliases_list.addItem(item)
    
    def _remove_alias(self):
        """删除别名"""
        current_item = self._aliases_list.currentItem()
        if current_item:
            self._aliases_list.takeItem(self._aliases_list.row(current_item))
    
    def _add_tag(self):
        """添加标签"""
        from PyQt6.QtWidgets import QInputDialog
        
        text, ok = QInputDialog.getText(self, "添加标签", "请输入标签:")
        if ok and text.strip():
            item = QListWidgetItem(text.strip())
            self._tags_list.addItem(item)
    
    def _remove_tag(self):
        """删除标签"""
        current_item = self._tags_list.currentItem()
        if current_item:
            self._tags_list.takeItem(self._tags_list.row(current_item))
    
    def _save_concept(self):
        """保存概念"""
        # 验证必填字段
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "验证错误", "请输入概念名称")
            return
        
        # 收集数据
        concept_data = self._collect_data()
        
        # 发出保存信号
        self.conceptSaved.emit(concept_data)
        self.accept()
    
    def _collect_data(self) -> Dict[str, Any]:
        """收集表单数据"""
        # 基础数据
        data = {
            'name': self._name_edit.text().strip(),
            'description': self._description_edit.toPlainText().strip(),
            'concept_type': self._concept_type,
            'priority': self._priority_spin.value(),
            'auto_detect': self._auto_detect_check.isChecked(),
        }
        
        # 如果是编辑模式，保留ID
        if self._is_editing and 'id' in self._concept_data:
            data['id'] = self._concept_data['id']
        
        # 收集别名
        aliases = []
        for i in range(self._aliases_list.count()):
            item = self._aliases_list.item(i)
            aliases.append(item.text())
        data['aliases'] = aliases
        
        # 收集标签
        tags = []
        for i in range(self._tags_list.count()):
            item = self._tags_list.item(i)
            tags.append(item.text())
        data['tags'] = tags
        
        # 收集类型特定数据
        type_specific_data = self._collect_type_specific_data()
        data.update(type_specific_data)
        
        return data
    
    def _collect_type_specific_data(self) -> Dict[str, Any]:
        """收集类型特定数据"""
        data = {}
        
        if self._concept_type == ConceptType.CHARACTER:
            age = self._age_spin.value()
            data.update({
                'age': age if age > 0 else None,
                'gender': self._gender_combo.currentText() or None,
                'occupation': self._occupation_edit.text().strip() or None,
                'appearance': self._appearance_edit.toPlainText().strip() or None,
                'backstory': self._backstory_edit.toPlainText().strip() or None,
            })
        
        elif self._concept_type == ConceptType.LOCATION:
            data.update({
                'location_type': self._location_type_combo.currentText(),
                'atmosphere': self._atmosphere_edit.text().strip() or None,
                'significance': self._significance_edit.text().strip() or None,
                'physical_description': self._physical_desc_edit.toPlainText().strip() or None,
            })
        
        elif self._concept_type == ConceptType.PLOT:
            data.update({
                'plot_type': self._plot_type_combo.currentText(),
                'status': self._status_combo.currentText(),
                'conflict_type': self._conflict_type_edit.text().strip() or None,
                'resolution': self._resolution_edit.toPlainText().strip() or None,
            })
        
        return data
