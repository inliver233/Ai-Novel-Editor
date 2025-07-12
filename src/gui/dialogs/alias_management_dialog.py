"""
别名管理对话框
用于管理Codex条目的别名和同义词
"""

import logging
from typing import Optional, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QGroupBox, QMessageBox,
    QDialogButtonBox, QInputDialog, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from core.codex_manager import CodexManager, CodexEntry

logger = logging.getLogger(__name__)


class AliasManagementDialog(QDialog):
    """别名管理对话框"""
    
    # 信号定义
    aliasesUpdated = pyqtSignal(str)  # 别名更新信号
    
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
        self._load_aliases()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"管理别名 - {self._entry.title}")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # 条目信息区域
        info_group = QGroupBox("条目信息")
        info_layout = QFormLayout(info_group)
        
        self._title_label = QLabel(self._entry.title)
        self._title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        info_layout.addRow("标题:", self._title_label)
        
        self._type_label = QLabel(self._entry.entry_type.value)
        info_layout.addRow("类型:", self._type_label)
        
        if self._entry.description:
            self._desc_label = QLabel(self._entry.description[:100] + "..." if len(self._entry.description) > 100 else self._entry.description)
            self._desc_label.setWordWrap(True)
            info_layout.addRow("描述:", self._desc_label)
        
        layout.addWidget(info_group)
        
        # 别名管理区域
        alias_group = QGroupBox("别名管理")
        alias_layout = QVBoxLayout(alias_group)
        
        # 说明文本
        explanation = QLabel(
            "别名是该条目的其他称呼或同义词。添加别名可以让系统在文本中检测到这些变体时"
            "也能正确识别为该条目的引用。"
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666; font-style: italic;")
        alias_layout.addWidget(explanation)
        
        # 别名列表和操作按钮
        list_layout = QHBoxLayout()
        
        # 别名列表
        list_container = QVBoxLayout()
        list_container.addWidget(QLabel("当前别名:"))
        self._alias_list = QListWidget()
        self._alias_list.setToolTip("双击别名可以编辑")
        self._alias_list.itemDoubleClicked.connect(self._edit_alias)
        list_container.addWidget(self._alias_list)
        
        # 操作按钮
        button_layout = QVBoxLayout()
        
        self._add_btn = QPushButton("添加别名")
        self._add_btn.clicked.connect(self._add_alias)
        button_layout.addWidget(self._add_btn)
        
        self._edit_btn = QPushButton("编辑选中")
        self._edit_btn.clicked.connect(self._edit_selected_alias)
        self._edit_btn.setEnabled(False)
        button_layout.addWidget(self._edit_btn)
        
        self._remove_btn = QPushButton("删除选中")
        self._remove_btn.clicked.connect(self._remove_alias)
        self._remove_btn.setEnabled(False)
        button_layout.addWidget(self._remove_btn)
        
        button_layout.addStretch()
        
        # 批量操作
        self._import_btn = QPushButton("批量导入")
        self._import_btn.clicked.connect(self._bulk_import)
        self._import_btn.setToolTip("从文本中批量导入别名，每行一个")
        button_layout.addWidget(self._import_btn)
        
        self._export_btn = QPushButton("导出别名")
        self._export_btn.clicked.connect(self._export_aliases)
        button_layout.addWidget(self._export_btn)
        
        list_layout.addLayout(list_container)
        list_layout.addLayout(button_layout)
        alias_layout.addLayout(list_layout)
        
        layout.addWidget(alias_group)
        
        # 预览区域
        preview_group = QGroupBox("引用检测预览")
        preview_layout = QVBoxLayout(preview_group)
        
        preview_layout.addWidget(QLabel("测试文本:"))
        self._test_input = QTextEdit()
        self._test_input.setMaximumHeight(60)
        self._test_input.setPlaceholderText("输入测试文本来预览引用检测效果...")
        self._test_input.textChanged.connect(self._update_preview)
        preview_layout.addWidget(self._test_input)
        
        preview_layout.addWidget(QLabel("检测结果:"))
        self._preview_result = QLabel("在上方输入文本进行测试")
        self._preview_result.setStyleSheet("border: 1px solid #ccc; padding: 5px; background: #f9f9f9;")
        self._preview_result.setWordWrap(True)
        self._preview_result.setMinimumHeight(40)
        preview_layout.addWidget(self._preview_result)
        
        layout.addWidget(preview_group)
        
        # 对话框按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_aliases)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # 连接选择变化事件
        self._alias_list.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_aliases(self):
        """加载当前别名"""
        self._alias_list.clear()
        for alias in self._entry.aliases:
            if alias.strip():  # 忽略空别名
                item = QListWidgetItem(alias.strip())
                self._alias_list.addItem(item)
    
    def _on_selection_changed(self):
        """处理选择变化"""
        has_selection = bool(self._alias_list.selectedItems())
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)
    
    @pyqtSlot()
    def _add_alias(self):
        """添加新别名"""
        text, ok = QInputDialog.getText(
            self, "添加别名", 
            f"为 '{self._entry.title}' 添加新别名:"
        )
        
        if ok and text.strip():
            alias = text.strip()
            
            # 检查是否已存在
            existing_aliases = [self._alias_list.item(i).text() for i in range(self._alias_list.count())]
            if alias in existing_aliases:
                QMessageBox.warning(self, "重复别名", f"别名 '{alias}' 已经存在！")
                return
            
            # 检查是否与主标题重复
            if alias == self._entry.title:
                QMessageBox.warning(self, "重复标题", "别名不能与主标题相同！")
                return
            
            # 添加到列表
            item = QListWidgetItem(alias)
            self._alias_list.addItem(item)
            self._alias_list.setCurrentItem(item)
            
            logger.info(f"添加别名: {alias}")
    
    @pyqtSlot()
    def _edit_selected_alias(self):
        """编辑选中的别名"""
        current_item = self._alias_list.currentItem()
        if current_item:
            self._edit_alias(current_item)
    
    @pyqtSlot(QListWidgetItem)
    def _edit_alias(self, item: QListWidgetItem):
        """编辑别名"""
        current_text = item.text()
        
        text, ok = QInputDialog.getText(
            self, "编辑别名",
            "编辑别名:",
            text=current_text
        )
        
        if ok and text.strip() and text.strip() != current_text:
            new_alias = text.strip()
            
            # 检查是否与其他别名重复
            existing_aliases = [self._alias_list.item(i).text() for i in range(self._alias_list.count())
                             if self._alias_list.item(i) != item]
            if new_alias in existing_aliases:
                QMessageBox.warning(self, "重复别名", f"别名 '{new_alias}' 已经存在！")
                return
            
            # 检查是否与主标题重复
            if new_alias == self._entry.title:
                QMessageBox.warning(self, "重复标题", "别名不能与主标题相同！")
                return
            
            item.setText(new_alias)
            logger.info(f"编辑别名: {current_text} -> {new_alias}")
    
    @pyqtSlot()
    def _remove_alias(self):
        """删除选中的别名"""
        current_item = self._alias_list.currentItem()
        if current_item:
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除别名 '{current_item.text()}' 吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                row = self._alias_list.row(current_item)
                self._alias_list.takeItem(row)
                logger.info(f"删除别名: {current_item.text()}")
    
    @pyqtSlot()
    def _bulk_import(self):
        """批量导入别名"""
        from .bulk_text_input_dialog import BulkTextInputDialog
        
        try:
            dialog = BulkTextInputDialog(
                title="批量导入别名",
                label="请输入别名列表（每行一个）:",
                placeholder="别名1\n别名2\n别名3",
                parent=self
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                lines = dialog.get_text().strip().split('\n')
                added_count = 0
                
                existing_aliases = [self._alias_list.item(i).text() for i in range(self._alias_list.count())]
                
                for line in lines:
                    alias = line.strip()
                    if alias and alias not in existing_aliases and alias != self._entry.title:
                        item = QListWidgetItem(alias)
                        self._alias_list.addItem(item)
                        existing_aliases.append(alias)
                        added_count += 1
                
                if added_count > 0:
                    QMessageBox.information(self, "导入完成", f"成功导入 {added_count} 个别名")
                else:
                    QMessageBox.warning(self, "导入结果", "没有新的别名被导入")
                    
        except ImportError:
            # 如果批量输入对话框不存在，使用简单的输入方式
            text, ok = QInputDialog.getMultiLineText(
                self, "批量导入别名",
                "请输入别名列表（每行一个）:"
            )
            
            if ok and text.strip():
                lines = text.strip().split('\n')
                added_count = 0
                
                existing_aliases = [self._alias_list.item(i).text() for i in range(self._alias_list.count())]
                
                for line in lines:
                    alias = line.strip()
                    if alias and alias not in existing_aliases and alias != self._entry.title:
                        item = QListWidgetItem(alias)
                        self._alias_list.addItem(item)
                        existing_aliases.append(alias)
                        added_count += 1
                
                if added_count > 0:
                    QMessageBox.information(self, "导入完成", f"成功导入 {added_count} 个别名")
    
    @pyqtSlot()
    def _export_aliases(self):
        """导出别名"""
        aliases = [self._alias_list.item(i).text() for i in range(self._alias_list.count())]
        
        if not aliases:
            QMessageBox.information(self, "导出结果", "没有别名可以导出")
            return
        
        text = '\n'.join(aliases)
        
        from PyQt6.QtWidgets import QTextEdit
        export_dialog = QDialog(self)
        export_dialog.setWindowTitle("导出别名")
        export_dialog.resize(400, 300)
        
        layout = QVBoxLayout(export_dialog)
        layout.addWidget(QLabel("别名列表（可复制）:"))
        
        text_edit = QTextEdit()
        text_edit.setPlainText(text)
        text_edit.selectAll()
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(export_dialog.reject)
        layout.addWidget(button_box)
        
        export_dialog.exec()
    
    @pyqtSlot()
    def _update_preview(self):
        """更新引用检测预览"""
        test_text = self._test_input.toPlainText().strip()
        
        if not test_text:
            self._preview_result.setText("在上方输入文本进行测试")
            return
        
        try:
            # 创建临时的别名列表进行测试
            current_aliases = [self._alias_list.item(i).text() for i in range(self._alias_list.count())]
            
            # 简单的引用检测预览（不依赖完整的检测器）
            found_refs = []
            
            # 检测主标题
            if self._entry.title.lower() in test_text.lower():
                found_refs.append(f"'{self._entry.title}' (主标题)")
            
            # 检测别名
            for alias in current_aliases:
                if alias.lower() in test_text.lower():
                    found_refs.append(f"'{alias}' (别名)")
            
            if found_refs:
                result_text = "检测到的引用: " + ", ".join(found_refs)
                self._preview_result.setStyleSheet("border: 1px solid #4CAF50; padding: 5px; background: #E8F5E8;")
            else:
                result_text = "未检测到任何引用"
                self._preview_result.setStyleSheet("border: 1px solid #FF9800; padding: 5px; background: #FFF3E0;")
            
            self._preview_result.setText(result_text)
            
        except Exception as e:
            self._preview_result.setText(f"预览错误: {str(e)}")
            self._preview_result.setStyleSheet("border: 1px solid #F44336; padding: 5px; background: #FFEBEE;")
    
    @pyqtSlot()
    def _save_aliases(self):
        """保存别名"""
        try:
            # 收集当前别名
            new_aliases = []
            for i in range(self._alias_list.count()):
                alias = self._alias_list.item(i).text().strip()
                if alias:  # 忽略空别名
                    new_aliases.append(alias)
            
            # 更新条目
            if self._codex_manager.update_entry(self._entry_id, aliases=new_aliases):
                self.aliasesUpdated.emit(self._entry_id)
                self.accept()
                logger.info(f"别名已保存: {new_aliases}")
            else:
                QMessageBox.critical(self, "保存失败", "无法保存别名，请重试")
                
        except Exception as e:
            logger.error(f"保存别名时出错: {e}")
            QMessageBox.critical(self, "保存错误", f"保存别名时发生错误: {str(e)}")