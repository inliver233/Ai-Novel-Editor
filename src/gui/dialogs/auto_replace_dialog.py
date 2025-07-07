"""
自动替换设置对话框
允许用户配置自动替换规则
"""

import logging
from typing import List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QCheckBox,
    QLabel, QLineEdit, QTextEdit, QGroupBox, QMessageBox,
    QHeaderView, QAbstractItemView, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont

from core.auto_replace import get_auto_replace_engine, ReplaceType, ReplaceRule

logger = logging.getLogger(__name__)


class AutoReplaceDialog(QDialog):
    """自动替换设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自动替换设置")
        self.setModal(True)
        self.resize(800, 600)
        
        self._auto_replace_engine = get_auto_replace_engine()
        self._init_ui()
        self._load_settings()
        
        logger.debug("Auto replace dialog initialized")
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 主要启用开关
        self._enable_checkbox = QCheckBox("启用自动替换")
        self._enable_checkbox.setChecked(self._auto_replace_engine.is_enabled())
        self._enable_checkbox.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self._enable_checkbox)
        
        # 标签页
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)
        
        # 创建各个标签页
        self._create_quotes_tab()
        self._create_dashes_tab()
        self._create_symbols_tab()
        self._create_custom_tab()
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self._test_btn = QPushButton("测试")
        self._test_btn.clicked.connect(self._test_replacements)
        button_layout.addWidget(self._test_btn)
        
        button_layout.addStretch()
        
        self._reset_btn = QPushButton("重置")
        self._reset_btn.clicked.connect(self._reset_settings)
        button_layout.addWidget(self._reset_btn)
        
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)
        
        self._ok_btn = QPushButton("确定")
        self._ok_btn.clicked.connect(self._apply_settings)
        self._ok_btn.setDefault(True)
        button_layout.addWidget(self._ok_btn)
        
        layout.addLayout(button_layout)
    
    def _create_quotes_tab(self):
        """创建引号标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("智能引号会自动将直引号转换为弯引号")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 规则表格
        self._quotes_table = self._create_rules_table()
        layout.addWidget(self._quotes_table)
        
        self._tab_widget.addTab(widget, "智能引号")
    
    def _create_dashes_tab(self):
        """创建破折号标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("自动将连字符转换为适当的破折号")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 规则表格
        self._dashes_table = self._create_rules_table()
        layout.addWidget(self._dashes_table)
        
        self._tab_widget.addTab(widget, "破折号")
    
    def _create_symbols_tab(self):
        """创建符号标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("自动替换常用符号和特殊字符")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 规则表格
        self._symbols_table = self._create_rules_table()
        layout.addWidget(self._symbols_table)
        
        self._tab_widget.addTab(widget, "符号")
    
    def _create_custom_tab(self):
        """创建自定义规则标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # 自定义规则表格
        rules_widget = QWidget()
        rules_layout = QVBoxLayout(rules_widget)
        
        rules_layout.addWidget(QLabel("自定义替换规则:"))
        self._custom_table = self._create_rules_table()
        rules_layout.addWidget(self._custom_table)
        
        # 添加/删除按钮
        button_layout = QHBoxLayout()
        self._add_rule_btn = QPushButton("添加规则")
        self._add_rule_btn.clicked.connect(self._add_custom_rule)
        button_layout.addWidget(self._add_rule_btn)
        
        self._remove_rule_btn = QPushButton("删除规则")
        self._remove_rule_btn.clicked.connect(self._remove_custom_rule)
        button_layout.addWidget(self._remove_rule_btn)
        
        button_layout.addStretch()
        rules_layout.addLayout(button_layout)
        
        splitter.addWidget(rules_widget)
        
        # 规则编辑区域
        edit_widget = QWidget()
        edit_layout = QVBoxLayout(edit_widget)
        
        edit_layout.addWidget(QLabel("新建规则:"))
        
        form_layout = QVBoxLayout()
        
        form_layout.addWidget(QLabel("匹配模式 (正则表达式):"))
        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText("例如: \\b(c)\\b")
        form_layout.addWidget(self._pattern_edit)
        
        form_layout.addWidget(QLabel("替换文本:"))
        self._replacement_edit = QLineEdit()
        self._replacement_edit.setPlaceholderText("例如: ©")
        form_layout.addWidget(self._replacement_edit)
        
        form_layout.addWidget(QLabel("描述:"))
        self._description_edit = QLineEdit()
        self._description_edit.setPlaceholderText("例如: 版权符号")
        form_layout.addWidget(self._description_edit)
        
        edit_layout.addLayout(form_layout)
        
        splitter.addWidget(edit_widget)
        splitter.setSizes([400, 200])
        
        self._tab_widget.addTab(widget, "自定义")
    
    def _create_rules_table(self) -> QTableWidget:
        """创建规则表格"""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["启用", "描述", "匹配", "替换"])
        
        # 设置列宽
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        table.setColumnWidth(0, 60)
        
        # 设置选择模式
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        return table
    
    def _load_settings(self):
        """加载设置"""
        # 加载各类型的规则
        self._load_rules_to_table(self._quotes_table, ReplaceType.SMART_QUOTES)
        self._load_rules_to_table(self._dashes_table, ReplaceType.DASHES)
        self._load_rules_to_table(self._symbols_table, ReplaceType.SYMBOLS)
        self._load_rules_to_table(self._custom_table, ReplaceType.CUSTOM)
    
    def _load_rules_to_table(self, table: QTableWidget, rule_type: ReplaceType):
        """加载规则到表格"""
        rules = self._auto_replace_engine.get_rules(rule_type)
        table.setRowCount(len(rules))
        
        for row, rule in enumerate(rules):
            # 启用复选框
            checkbox = QCheckBox()
            checkbox.setChecked(rule.enabled)
            table.setCellWidget(row, 0, checkbox)
            
            # 描述
            table.setItem(row, 1, QTableWidgetItem(rule.description))
            
            # 匹配模式
            table.setItem(row, 2, QTableWidgetItem(rule.pattern))
            
            # 替换文本
            table.setItem(row, 3, QTableWidgetItem(rule.replacement))
    
    @pyqtSlot(bool)
    def _on_enable_toggled(self, enabled: bool):
        """启用状态切换"""
        self._tab_widget.setEnabled(enabled)
        self._test_btn.setEnabled(enabled)
    
    @pyqtSlot()
    def _add_custom_rule(self):
        """添加自定义规则"""
        pattern = self._pattern_edit.text().strip()
        replacement = self._replacement_edit.text().strip()
        description = self._description_edit.text().strip()
        
        if not pattern or not replacement or not description:
            QMessageBox.warning(self, "警告", "请填写完整的规则信息")
            return
        
        # 验证正则表达式
        try:
            import re
            re.compile(pattern)
        except re.error as e:
            QMessageBox.critical(self, "错误", f"无效的正则表达式: {e}")
            return
        
        # 添加到表格
        row = self._custom_table.rowCount()
        self._custom_table.insertRow(row)
        
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        self._custom_table.setCellWidget(row, 0, checkbox)
        
        self._custom_table.setItem(row, 1, QTableWidgetItem(description))
        self._custom_table.setItem(row, 2, QTableWidgetItem(pattern))
        self._custom_table.setItem(row, 3, QTableWidgetItem(replacement))
        
        # 清空输入框
        self._pattern_edit.clear()
        self._replacement_edit.clear()
        self._description_edit.clear()
    
    @pyqtSlot()
    def _remove_custom_rule(self):
        """删除自定义规则"""
        current_row = self._custom_table.currentRow()
        if current_row >= 0:
            self._custom_table.removeRow(current_row)
    
    @pyqtSlot()
    def _test_replacements(self):
        """测试替换功能"""
        # TODO: 实现测试对话框
        QMessageBox.information(self, "测试", "测试功能将在后续版本中实现")
    
    @pyqtSlot()
    def _reset_settings(self):
        """重置设置"""
        reply = QMessageBox.question(
            self, "确认重置", 
            "确定要重置所有自动替换设置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 重新初始化引擎
            self._auto_replace_engine._rules.clear()
            self._auto_replace_engine._init_default_rules()
            self._load_settings()
    
    @pyqtSlot()
    def _apply_settings(self):
        """应用设置"""
        try:
            # 设置引擎启用状态
            self._auto_replace_engine.set_enabled(self._enable_checkbox.isChecked())
            
            # 应用规则启用状态
            self._apply_table_settings(self._quotes_table, ReplaceType.SMART_QUOTES)
            self._apply_table_settings(self._dashes_table, ReplaceType.DASHES)
            self._apply_table_settings(self._symbols_table, ReplaceType.SYMBOLS)
            self._apply_custom_rules()
            
            self.accept()
            
        except Exception as e:
            logger.error(f"Failed to apply auto replace settings: {e}")
            QMessageBox.critical(self, "错误", f"应用设置失败: {str(e)}")
    
    def _apply_table_settings(self, table: QTableWidget, rule_type: ReplaceType):
        """应用表格设置"""
        rules = self._auto_replace_engine.get_rules(rule_type)
        
        for row in range(table.rowCount()):
            if row < len(rules):
                checkbox = table.cellWidget(row, 0)
                if checkbox:
                    rules[row].enabled = checkbox.isChecked()
    
    def _apply_custom_rules(self):
        """应用自定义规则"""
        # 先删除所有自定义规则
        custom_rules = self._auto_replace_engine.get_rules(ReplaceType.CUSTOM)
        for rule in custom_rules[:]:
            self._auto_replace_engine.remove_rule(rule.description)
        
        # 添加表格中的自定义规则
        for row in range(self._custom_table.rowCount()):
            checkbox = self._custom_table.cellWidget(row, 0)
            description_item = self._custom_table.item(row, 1)
            pattern_item = self._custom_table.item(row, 2)
            replacement_item = self._custom_table.item(row, 3)
            
            if checkbox and description_item and pattern_item and replacement_item:
                if checkbox.isChecked():
                    self._auto_replace_engine.add_custom_rule(
                        pattern_item.text(),
                        replacement_item.text(),
                        description_item.text()
                    )
