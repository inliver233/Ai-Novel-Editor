"""
进展管理对话框
用于管理Codex条目在故事中的发展轨迹和时间线
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QGroupBox, QMessageBox,
    QDialogButtonBox, QInputDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QTabWidget,
    QWidget, QSpinBox, QDateTimeEdit, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QDateTime
from PyQt6.QtGui import QFont

from core.codex_manager import CodexManager, CodexEntry, CodexEntryType

logger = logging.getLogger(__name__)


class ProgressionManagementDialog(QDialog):
    """进展管理对话框"""
    
    # 信号定义
    progressionUpdated = pyqtSignal(str)  # 进展更新信号
    
    # 进展事件类型
    PROGRESSION_TYPES = {
        CodexEntryType.CHARACTER: [
            "初次登场", "性格变化", "技能获得", "技能提升", "重要决定",
            "关系变化", "地位变化", "外观变化", "情感变化", "目标变化",
            "受伤", "恢复", "觉醒", "成长", "退场", "重要对话", "关键行动"
        ],
        CodexEntryType.LOCATION: [
            "初次出现", "环境变化", "重要事件", "战斗发生", "发现秘密",
            "建设完成", "遭到破坏", "人口变化", "统治者变更", "重要会议"
        ],
        CodexEntryType.OBJECT: [
            "初次出现", "被发现", "被获得", "被使用", "被损坏", "被修复",
            "能力觉醒", "能力提升", "丢失", "被盗", "转手", "重要作用"
        ],
        CodexEntryType.LORE: [
            "首次提及", "详细揭示", "新发现", "被证实", "被质疑",
            "影响扩大", "产生变化", "与其他传说结合"
        ],
        CodexEntryType.SUBPLOT: [
            "情节开始", "关键转折", "高潮", "解决", "影响其他情节",
            "新线索", "障碍出现", "角色加入", "角色离开"
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
        self._load_progression()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"管理进展 - {self._entry.title}")
        self.setModal(True)
        self.resize(800, 600)
        
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
        
        # 进展事件标签页
        self._create_events_tab(tab_widget)
        
        # 时间线视图标签页
        self._create_timeline_tab(tab_widget)
        
        # 统计分析标签页
        self._create_stats_tab(tab_widget)
        
        layout.addWidget(tab_widget)
        
        # 对话框按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_progression)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_events_tab(self, tab_widget: QTabWidget):
        """创建进展事件标签页"""
        events_widget = QWidget()
        layout = QVBoxLayout(events_widget)
        
        # 说明文本
        explanation = QLabel(
            "进展事件记录该条目在故事中的重要发展节点，有助于追踪角色成长、"
            "情节发展和世界观演变。"
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(explanation)
        
        # 进展事件表格
        self._events_table = QTableWidget()
        self._events_table.setColumnCount(6)
        self._events_table.setHorizontalHeaderLabels([
            "章节/场景", "事件类型", "事件描述", "重要性", "时间", "状态"
        ])
        
        # 设置表格属性
        header = self._events_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self._events_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._events_table.setAlternatingRowColors(True)
        self._events_table.setSortingEnabled(True)
        
        layout.addWidget(self._events_table)
        
        # 事件操作按钮
        button_layout = QHBoxLayout()
        
        self._add_event_btn = QPushButton("添加事件")
        self._add_event_btn.clicked.connect(self._add_event)
        button_layout.addWidget(self._add_event_btn)
        
        self._edit_event_btn = QPushButton("编辑事件")
        self._edit_event_btn.clicked.connect(self._edit_event)
        self._edit_event_btn.setEnabled(False)
        button_layout.addWidget(self._edit_event_btn)
        
        self._remove_event_btn = QPushButton("删除事件")
        self._remove_event_btn.clicked.connect(self._remove_event)
        self._remove_event_btn.setEnabled(False)
        button_layout.addWidget(self._remove_event_btn)
        
        button_layout.addStretch()
        
        self._quick_add_btn = QPushButton("快速添加")
        self._quick_add_btn.clicked.connect(self._quick_add_event)
        self._quick_add_btn.setToolTip("基于条目类型快速添加常见事件")
        button_layout.addWidget(self._quick_add_btn)
        
        self._duplicate_btn = QPushButton("复制事件")
        self._duplicate_btn.clicked.connect(self._duplicate_event)
        self._duplicate_btn.setEnabled(False)
        button_layout.addWidget(self._duplicate_btn)
        
        layout.addLayout(button_layout)
        
        # 连接选择变化事件
        self._events_table.itemSelectionChanged.connect(self._on_event_selection_changed)
        
        tab_widget.addTab(events_widget, "进展事件")
    
    def _create_timeline_tab(self, tab_widget: QTabWidget):
        """创建时间线视图标签页"""
        timeline_widget = QWidget()
        layout = QVBoxLayout(timeline_widget)
        
        # 时间线控制
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("排序方式:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["时间顺序", "重要性", "事件类型", "章节顺序"])
        self._sort_combo.currentTextChanged.connect(self._update_timeline)
        control_layout.addWidget(self._sort_combo)
        
        control_layout.addStretch()
        
        self._show_completed_check = QCheckBox("显示已完成事件")
        self._show_completed_check.setChecked(True)
        self._show_completed_check.toggled.connect(self._update_timeline)
        control_layout.addWidget(self._show_completed_check)
        
        layout.addLayout(control_layout)
        
        # 时间线视图
        self._timeline_view = QTextEdit()
        self._timeline_view.setReadOnly(True)
        self._timeline_view.setFont(QFont("Consolas", 10))
        layout.addWidget(self._timeline_view)
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        
        self._refresh_timeline_btn = QPushButton("刷新时间线")
        self._refresh_timeline_btn.clicked.connect(self._update_timeline)
        refresh_layout.addWidget(self._refresh_timeline_btn)
        
        layout.addLayout(refresh_layout)
        
        tab_widget.addTab(timeline_widget, "时间线")
    
    def _create_stats_tab(self, tab_widget: QTabWidget):
        """创建统计分析标签页"""
        stats_widget = QWidget()
        layout = QVBoxLayout(stats_widget)
        
        # 基础统计
        basic_stats_group = QGroupBox("基础统计")
        basic_stats_layout = QFormLayout(basic_stats_group)
        
        self._total_events_label = QLabel("0")
        basic_stats_layout.addRow("总事件数:", self._total_events_label)
        
        self._completed_events_label = QLabel("0")
        basic_stats_layout.addRow("已完成事件:", self._completed_events_label)
        
        self._pending_events_label = QLabel("0")
        basic_stats_layout.addRow("待处理事件:", self._pending_events_label)
        
        self._event_types_label = QLabel("无")
        basic_stats_layout.addRow("事件类型:", self._event_types_label)
        
        layout.addWidget(basic_stats_group)
        
        # 详细统计
        detailed_stats_group = QGroupBox("详细分析")
        detailed_stats_layout = QVBoxLayout(detailed_stats_group)
        
        self._stats_view = QTextEdit()
        self._stats_view.setReadOnly(True)
        self._stats_view.setFont(QFont("Consolas", 10))
        detailed_stats_layout.addWidget(self._stats_view)
        
        layout.addWidget(detailed_stats_group)
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        
        self._refresh_stats_btn = QPushButton("刷新统计")
        self._refresh_stats_btn.clicked.connect(self._update_stats)
        refresh_layout.addWidget(self._refresh_stats_btn)
        
        layout.addLayout(refresh_layout)
        
        tab_widget.addTab(stats_widget, "统计分析")
    
    def _load_progression(self):
        """加载当前进展"""
        self._events_table.setRowCount(0)
        
        progression = self._entry.progression or []
        
        for event in progression:
            self._add_event_row(event)
        
        self._update_timeline()
        self._update_stats()
    
    def _add_event_row(self, event: Dict[str, Any]):
        """添加事件行到表格"""
        row = self._events_table.rowCount()
        self._events_table.insertRow(row)
        
        # 章节/场景
        chapter = event.get('chapter', '')
        chapter_item = QTableWidgetItem(chapter)
        self._events_table.setItem(row, 0, chapter_item)
        
        # 事件类型
        event_type = event.get('type', '')
        type_item = QTableWidgetItem(event_type)
        self._events_table.setItem(row, 1, type_item)
        
        # 事件描述
        description = event.get('description', '')
        desc_item = QTableWidgetItem(description)
        self._events_table.setItem(row, 2, desc_item)
        
        # 重要性
        importance = event.get('importance', 1)
        importance_text = "★" * importance
        importance_item = QTableWidgetItem(importance_text)
        importance_item.setData(Qt.ItemDataRole.UserRole, importance)
        self._events_table.setItem(row, 3, importance_item)
        
        # 时间
        timestamp = event.get('timestamp', '')
        time_item = QTableWidgetItem(timestamp)
        self._events_table.setItem(row, 4, time_item)
        
        # 状态
        status = event.get('status', 'pending')
        status_text = "✓ 已完成" if status == 'completed' else "⏳ 待处理"
        status_item = QTableWidgetItem(status_text)
        status_item.setData(Qt.ItemDataRole.UserRole, status)
        self._events_table.setItem(row, 5, status_item)
    
    def _on_event_selection_changed(self):
        """处理事件选择变化"""
        has_selection = bool(self._events_table.selectedItems())
        self._edit_event_btn.setEnabled(has_selection)
        self._remove_event_btn.setEnabled(has_selection)
        self._duplicate_btn.setEnabled(has_selection)
    
    @pyqtSlot()
    def _add_event(self):
        """添加新事件"""
        dialog = ProgressionEventDialog(
            entry_type=self._entry.entry_type,
            parent=self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            event = dialog.get_event()
            self._add_event_row(event)
            self._update_timeline()
            self._update_stats()
    
    @pyqtSlot()
    def _edit_event(self):
        """编辑选中的事件"""
        current_row = self._events_table.currentRow()
        if current_row >= 0:
            # 获取当前事件数据
            event = self._get_event_from_row(current_row)
            
            dialog = ProgressionEventDialog(
                entry_type=self._entry.entry_type,
                event=event,
                parent=self
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_event = dialog.get_event()
                self._update_event_row(current_row, new_event)
                self._update_timeline()
                self._update_stats()
    
    @pyqtSlot()
    def _remove_event(self):
        """删除选中的事件"""
        current_row = self._events_table.currentRow()
        if current_row >= 0:
            desc_item = self._events_table.item(current_row, 2)
            description = desc_item.text()[:50] + "..." if len(desc_item.text()) > 50 else desc_item.text()
            
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除事件 '{description}' 吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._events_table.removeRow(current_row)
                self._update_timeline()
                self._update_stats()
    
    @pyqtSlot()
    def _quick_add_event(self):
        """快速添加事件"""
        # 获取当前条目类型的常见事件
        common_types = self.PROGRESSION_TYPES.get(self._entry.entry_type, [])
        
        if not common_types:
            QMessageBox.information(self, "快速添加", "该条目类型没有预定义的事件类型")
            return
        
        # 选择事件类型
        event_type, ok = QInputDialog.getItem(
            self, "选择事件类型",
            f"为 '{self._entry.title}' 选择事件类型:",
            common_types, 0, False
        )
        
        if ok:
            # 创建基础事件
            event = {
                'chapter': '',
                'type': event_type,
                'description': f"{self._entry.title}的{event_type}事件",
                'importance': 3,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'status': 'pending',
                'notes': ''
            }
            
            self._add_event_row(event)
            self._update_timeline()
            self._update_stats()
    
    @pyqtSlot()
    def _duplicate_event(self):
        """复制事件"""
        current_row = self._events_table.currentRow()
        if current_row >= 0:
            event = self._get_event_from_row(current_row)
            
            # 修改描述以表明这是副本
            event['description'] = f"{event['description']} (副本)"
            event['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            event['status'] = 'pending'
            
            self._add_event_row(event)
            self._update_timeline()
            self._update_stats()
    
    def _get_event_from_row(self, row: int) -> Dict[str, Any]:
        """从表格行获取事件数据"""
        chapter_item = self._events_table.item(row, 0)
        type_item = self._events_table.item(row, 1)
        desc_item = self._events_table.item(row, 2)
        importance_item = self._events_table.item(row, 3)
        time_item = self._events_table.item(row, 4)
        status_item = self._events_table.item(row, 5)
        
        return {
            'chapter': chapter_item.text(),
            'type': type_item.text(),
            'description': desc_item.text(),
            'importance': importance_item.data(Qt.ItemDataRole.UserRole),
            'timestamp': time_item.text(),
            'status': status_item.data(Qt.ItemDataRole.UserRole),
            'notes': ''  # 注释需要从编辑对话框获取
        }
    
    def _update_event_row(self, row: int, event: Dict[str, Any]):
        """更新事件行"""
        self._events_table.item(row, 0).setText(event['chapter'])
        self._events_table.item(row, 1).setText(event['type'])
        self._events_table.item(row, 2).setText(event['description'])
        
        importance_item = self._events_table.item(row, 3)
        importance_item.setText("★" * event['importance'])
        importance_item.setData(Qt.ItemDataRole.UserRole, event['importance'])
        
        self._events_table.item(row, 4).setText(event['timestamp'])
        
        status_item = self._events_table.item(row, 5)
        status_text = "✓ 已完成" if event['status'] == 'completed' else "⏳ 待处理"
        status_item.setText(status_text)
        status_item.setData(Qt.ItemDataRole.UserRole, event['status'])
    
    def _update_timeline(self):
        """更新时间线视图"""
        events = self._get_current_events()
        
        # 过滤事件
        if not self._show_completed_check.isChecked():
            events = [event for event in events if event['status'] != 'completed']
        
        # 排序事件
        sort_type = self._sort_combo.currentText()
        if sort_type == "时间顺序":
            events.sort(key=lambda x: x['timestamp'])
        elif sort_type == "重要性":
            events.sort(key=lambda x: x['importance'], reverse=True)
        elif sort_type == "事件类型":
            events.sort(key=lambda x: x['type'])
        elif sort_type == "章节顺序":
            events.sort(key=lambda x: x['chapter'])
        
        # 生成时间线文本
        timeline_text = self._generate_timeline_text(events)
        self._timeline_view.setPlainText(timeline_text)
    
    def _generate_timeline_text(self, events: List[Dict[str, Any]]) -> str:
        """生成时间线视图文本"""
        if not events:
            return f"{self._entry.title} 目前没有记录任何进展事件。"
        
        lines = [f"📈 {self._entry.title} 的进展时间线", ""]
        
        for i, event in enumerate(events, 1):
            status_icon = "✓" if event['status'] == 'completed' else "⏳"
            importance = "★" * event['importance']
            
            lines.append(f"{i:2d}. {status_icon} {event['type']}")
            lines.append(f"     📍 {event['chapter'] or '未指定章节'}")
            lines.append(f"     📝 {event['description']}")
            lines.append(f"     ⭐ {importance} | 🕒 {event['timestamp']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _update_stats(self):
        """更新统计信息"""
        events = self._get_current_events()
        
        # 基础统计
        total = len(events)
        completed = len([e for e in events if e['status'] == 'completed'])
        pending = total - completed
        
        self._total_events_label.setText(str(total))
        self._completed_events_label.setText(str(completed))
        self._pending_events_label.setText(str(pending))
        
        if events:
            types = list(set([event['type'] for event in events]))
            self._event_types_label.setText(", ".join(types[:3]) + ("..." if len(types) > 3 else ""))
        else:
            self._event_types_label.setText("无")
        
        # 详细统计
        stats_text = self._generate_stats_text(events)
        self._stats_view.setPlainText(stats_text)
    
    def _generate_stats_text(self, events: List[Dict[str, Any]]) -> str:
        """生成统计分析文本"""
        if not events:
            return f"{self._entry.title} 目前没有进展事件可供分析。"
        
        lines = [f"📊 {self._entry.title} 进展统计分析", ""]
        
        # 事件类型统计
        type_counts = {}
        for event in events:
            event_type = event['type']
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        
        lines.append("📋 事件类型分布:")
        for event_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(events) * 100
            lines.append(f"   {event_type}: {count} 次 ({percentage:.1f}%)")
        lines.append("")
        
        # 重要性分析
        importance_counts = {}
        for event in events:
            importance = event['importance']
            importance_counts[importance] = importance_counts.get(importance, 0) + 1
        
        lines.append("⭐ 重要性分布:")
        for importance in sorted(importance_counts.keys(), reverse=True):
            count = importance_counts[importance]
            stars = "★" * importance
            lines.append(f"   {stars} ({importance}星): {count} 个事件")
        lines.append("")
        
        # 完成度分析
        total = len(events)
        completed = len([e for e in events if e['status'] == 'completed'])
        completion_rate = completed / total * 100 if total > 0 else 0
        
        lines.append("✅ 完成度分析:")
        lines.append(f"   总事件数: {total}")
        lines.append(f"   已完成: {completed}")
        lines.append(f"   待处理: {total - completed}")
        lines.append(f"   完成率: {completion_rate:.1f}%")
        
        return "\n".join(lines)
    
    def _get_current_events(self) -> List[Dict[str, Any]]:
        """获取当前事件列表"""
        events = []
        
        for row in range(self._events_table.rowCount()):
            event = self._get_event_from_row(row)
            events.append(event)
        
        return events
    
    @pyqtSlot()
    def _save_progression(self):
        """保存进展"""
        try:
            progression = self._get_current_events()
            
            # 更新条目
            if self._codex_manager.update_entry(self._entry_id, progression=progression):
                self.progressionUpdated.emit(self._entry_id)
                self.accept()
                logger.info(f"进展已保存: {len(progression)} 个事件")
            else:
                QMessageBox.critical(self, "保存失败", "无法保存进展，请重试")
                
        except Exception as e:
            logger.error(f"保存进展时出错: {e}")
            QMessageBox.critical(self, "保存错误", f"保存进展时发生错误: {str(e)}")


class ProgressionEventDialog(QDialog):
    """进展事件编辑对话框"""
    
    def __init__(self, entry_type: CodexEntryType, event: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._entry_type = entry_type
        self._event = event or {}
        
        self._init_ui()
        
        if event:
            self._load_event_data()
    
    def _init_ui(self):
        """初始化UI"""
        title = "编辑事件" if self._event else "添加事件"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # 表单
        form_layout = QFormLayout()
        
        # 章节/场景
        self._chapter_edit = QLineEdit()
        self._chapter_edit.setPlaceholderText("如：第一章、序章、第1节等")
        form_layout.addRow("章节/场景:", self._chapter_edit)
        
        # 事件类型
        self._type_combo = QComboBox()
        self._type_combo.setEditable(True)
        
        # 根据条目类型填充事件类型
        common_types = ProgressionManagementDialog.PROGRESSION_TYPES.get(self._entry_type, [])
        for event_type in common_types:
            self._type_combo.addItem(event_type)
        
        form_layout.addRow("事件类型:", self._type_combo)
        
        # 事件描述
        self._description_edit = QTextEdit()
        self._description_edit.setMaximumHeight(100)
        self._description_edit.setPlaceholderText("详细描述这个事件...")
        form_layout.addRow("事件描述:", self._description_edit)
        
        # 重要性
        self._importance_spin = QSpinBox()
        self._importance_spin.setRange(1, 5)
        self._importance_spin.setValue(3)
        self._importance_spin.setToolTip("1=次要事件, 3=一般事件, 5=关键事件")
        form_layout.addRow("重要性 (1-5星):", self._importance_spin)
        
        # 时间
        self._timestamp_edit = QDateTimeEdit()
        self._timestamp_edit.setDateTime(QDateTime.currentDateTime())
        self._timestamp_edit.setDisplayFormat("yyyy-MM-dd hh:mm")
        form_layout.addRow("时间:", self._timestamp_edit)
        
        # 状态
        self._status_combo = QComboBox()
        self._status_combo.addItems(["待处理", "已完成"])
        form_layout.addRow("状态:", self._status_combo)
        
        # 备注
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(80)
        self._notes_edit.setPlaceholderText("可选的备注或详细说明...")
        form_layout.addRow("备注:", self._notes_edit)
        
        layout.addLayout(form_layout)
        
        # 对话框按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_event_data(self):
        """加载事件数据"""
        self._chapter_edit.setText(self._event.get('chapter', ''))
        self._type_combo.setCurrentText(self._event.get('type', ''))
        self._description_edit.setPlainText(self._event.get('description', ''))
        self._importance_spin.setValue(self._event.get('importance', 3))
        
        # 设置时间
        timestamp_str = self._event.get('timestamp', '')
        if timestamp_str:
            try:
                dt = QDateTime.fromString(timestamp_str, "yyyy-MM-dd hh:mm")
                if dt.isValid():
                    self._timestamp_edit.setDateTime(dt)
            except:
                pass
        
        # 设置状态
        status = self._event.get('status', 'pending')
        self._status_combo.setCurrentText("已完成" if status == 'completed' else "待处理")
        
        self._notes_edit.setPlainText(self._event.get('notes', ''))
    
    def _validate_and_accept(self):
        """验证并接受"""
        if not self._type_combo.currentText().strip():
            QMessageBox.warning(self, "验证失败", "请输入事件类型")
            return
        
        if not self._description_edit.toPlainText().strip():
            QMessageBox.warning(self, "验证失败", "请输入事件描述")
            return
        
        self.accept()
    
    def get_event(self) -> Dict[str, Any]:
        """获取事件数据"""
        status = 'completed' if self._status_combo.currentText() == '已完成' else 'pending'
        
        return {
            'chapter': self._chapter_edit.text().strip(),
            'type': self._type_combo.currentText().strip(),
            'description': self._description_edit.toPlainText().strip(),
            'importance': self._importance_spin.value(),
            'timestamp': self._timestamp_edit.dateTime().toString("yyyy-MM-dd hh:mm"),
            'status': status,
            'notes': self._notes_edit.toPlainText().strip()
        }