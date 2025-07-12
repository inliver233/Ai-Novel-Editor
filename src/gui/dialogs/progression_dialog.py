"""
进展记录对话框
用于添加和编辑Codex条目的进展追踪记录
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QDateEdit,
    QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import Qt, QDate

logger = logging.getLogger(__name__)


class ProgressionDialog(QDialog):
    """进展记录对话框"""
    
    def __init__(self, parent=None, progression_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self._progression_data = progression_data or {}
        self._init_ui()
        self._load_data()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("编辑进展记录" if self._progression_data else "添加进展记录")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 标题
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("例如：初次登场、性格转变、重要事件...")
        form_layout.addRow("进展标题:", self._title_edit)
        
        # 日期
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("发生时间:", self._date_edit)
        
        # 章节
        self._chapter_edit = QLineEdit()
        self._chapter_edit.setPlaceholderText("例如：第一章、序章...")
        form_layout.addRow("所在章节:", self._chapter_edit)
        
        # 描述
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("详细描述这个进展的内容...")
        self._desc_edit.setMaximumHeight(150)
        form_layout.addRow("详细描述:", self._desc_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_data(self):
        """加载数据"""
        if self._progression_data:
            self._title_edit.setText(self._progression_data.get("title", ""))
            
            # 解析日期
            date_str = self._progression_data.get("date", "")
            if date_str:
                try:
                    date = QDate.fromString(date_str, "yyyy-MM-dd")
                    if date.isValid():
                        self._date_edit.setDate(date)
                except:
                    pass
            
            self._chapter_edit.setText(self._progression_data.get("chapter", ""))
            self._desc_edit.setPlainText(self._progression_data.get("description", ""))
    
    def _accept(self):
        """确认并验证输入"""
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "警告", "请输入进展标题")
            return
        
        self.accept()
    
    def get_progression_data(self) -> Dict[str, Any]:
        """获取进展数据"""
        return {
            "title": self._title_edit.text().strip(),
            "date": self._date_edit.date().toString("yyyy-MM-dd"),
            "chapter": self._chapter_edit.text().strip(),
            "description": self._desc_edit.toPlainText(),
            "created_at": datetime.now().isoformat()
        }