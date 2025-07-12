"""
增强的引用统计面板
提供图表化的引用统计展示，包含时间线、分布图、热力图等
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QGroupBox, QGridLayout,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QListWidget, QListWidgetItem,
    QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ChartWidget(QWidget):
    """基础图表绘制组件"""
    
    def __init__(self):
        super().__init__()
        self.data = []
        self.chart_type = "line"
        self.setMinimumHeight(200)
        
    def set_data(self, data: List[Dict[str, Any]], chart_type: str = "line"):
        """设置图表数据"""
        self.data = data
        self.chart_type = chart_type
        self.update()
        
    def paintEvent(self, event):
        """绘制图表"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        
        if not self.data:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无数据")
            return
            
        # 边距
        margin = 40
        chart_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        
        if self.chart_type == "line":
            self._draw_line_chart(painter, chart_rect)
        elif self.chart_type == "bar":
            self._draw_bar_chart(painter, chart_rect)
        elif self.chart_type == "pie":
            self._draw_pie_chart(painter, chart_rect)
            
    def _draw_line_chart(self, painter: QPainter, rect):
        """绘制折线图"""
        if len(self.data) < 2:
            return
            
        # 找出最大值
        max_value = max(item.get('count', 0) for item in self.data)
        if max_value == 0:
            return
            
        # 绘制坐标轴
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        
        # 绘制数据点和连线
        painter.setPen(QPen(QColor(52, 152, 219), 2))
        points = []
        
        for i, item in enumerate(self.data):
            x = rect.left() + (i / (len(self.data) - 1)) * rect.width()
            y = rect.bottom() - (item.get('count', 0) / max_value) * rect.height()
            points.append((int(x), int(y)))
            
        # 绘制线条
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
            
        # 绘制数据点
        painter.setBrush(QBrush(QColor(52, 152, 219)))
        for x, y in points:
            painter.drawEllipse(x - 3, y - 3, 6, 6)
            
    def _draw_bar_chart(self, painter: QPainter, rect):
        """绘制柱状图"""
        if not self.data:
            return
            
        # 找出最大值
        max_value = max(item.get('count', 0) for item in self.data[:10])  # 只显示前10个
        if max_value == 0:
            return
            
        # 绘制坐标轴
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        
        # 绘制柱子
        bar_width = rect.width() / min(len(self.data), 10)
        painter.setBrush(QBrush(QColor(52, 152, 219)))
        
        for i, item in enumerate(self.data[:10]):
            height = (item.get('count', 0) / max_value) * rect.height()
            x = rect.left() + i * bar_width
            y = rect.bottom() - height
            
            painter.fillRect(int(x + bar_width * 0.1), int(y), 
                           int(bar_width * 0.8), int(height), 
                           QColor(52, 152, 219))
                           
    def _draw_pie_chart(self, painter: QPainter, rect):
        """绘制饼图"""
        if not self.data:
            return
            
        # 计算总和
        total = sum(item.get('count', 0) for item in self.data[:5])  # 只显示前5个
        if total == 0:
            return
            
        # 绘制饼图
        start_angle = 0
        colors = [
            QColor(52, 152, 219),   # 蓝色
            QColor(46, 204, 113),   # 绿色
            QColor(231, 76, 60),    # 红色
            QColor(241, 196, 15),   # 黄色
            QColor(155, 89, 182)    # 紫色
        ]
        
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 20
        
        for i, item in enumerate(self.data[:5]):
            value = item.get('count', 0)
            if value == 0:
                continue
                
            angle = int((value / total) * 360 * 16)
            painter.setBrush(QBrush(colors[i % len(colors)]))
            painter.drawPie(center.x() - radius, center.y() - radius,
                          radius * 2, radius * 2, start_angle, angle)
            start_angle += angle


class EnhancedReferenceStatsWidget(QWidget):
    """增强的引用统计面板"""
    
    # 信号
    entry_selected = pyqtSignal(str)  # 选中条目信号
    
    def __init__(self, codex_manager):
        super().__init__()
        self.codex_manager = codex_manager
        self._init_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh_statistics)
        self._refresh_timer.start(30000)  # 30秒自动刷新
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 概览标签页
        overview_tab = self._create_overview_tab()
        self.tab_widget.addTab(overview_tab, "概览")
        
        # 时间线标签页
        timeline_tab = self._create_timeline_tab()
        self.tab_widget.addTab(timeline_tab, "时间线")
        
        # 分布标签页
        distribution_tab = self._create_distribution_tab()
        self.tab_widget.addTab(distribution_tab, "分布")
        
        # 共现分析标签页
        cooccurrence_tab = self._create_cooccurrence_tab()
        self.tab_widget.addTab(cooccurrence_tab, "共现分析")
        
        # 详细数据标签页
        details_tab = self._create_details_tab()
        self.tab_widget.addTab(details_tab, "详细数据")
        
        layout.addWidget(self.tab_widget)
        
        # 初始刷新
        self.refresh_statistics()
        
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_statistics)
        layout.addWidget(self.refresh_btn)
        
        # 时间范围选择
        layout.addWidget(QLabel("时间范围:"))
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["最近7天", "最近30天", "最近90天", "全部"])
        self.time_range_combo.currentIndexChanged.connect(self.refresh_statistics)
        layout.addWidget(self.time_range_combo)
        
        # 导出按钮
        self.export_btn = QPushButton("导出报告")
        self.export_btn.clicked.connect(self._export_report)
        layout.addWidget(self.export_btn)
        
        layout.addStretch()
        
        return toolbar
        
    def _create_overview_tab(self) -> QWidget:
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 统计卡片区域
        cards_layout = QGridLayout()
        
        # 总引用数卡片
        self.total_refs_card = self._create_stat_card("总引用数", "0")
        cards_layout.addWidget(self.total_refs_card, 0, 0)
        
        # 活跃引用卡片
        self.active_refs_card = self._create_stat_card("活跃引用", "0")
        cards_layout.addWidget(self.active_refs_card, 0, 1)
        
        # 未使用条目卡片
        self.unused_entries_card = self._create_stat_card("未使用条目", "0")
        cards_layout.addWidget(self.unused_entries_card, 0, 2)
        
        # 平均引用数卡片
        self.avg_refs_card = self._create_stat_card("平均引用数", "0")
        cards_layout.addWidget(self.avg_refs_card, 1, 0)
        
        # 最近7天引用卡片
        self.recent_refs_card = self._create_stat_card("最近7天", "0")
        cards_layout.addWidget(self.recent_refs_card, 1, 1)
        
        # 低置信度引用卡片
        self.low_confidence_card = self._create_stat_card("低置信度", "0")
        cards_layout.addWidget(self.low_confidence_card, 1, 2)
        
        layout.addLayout(cards_layout)
        
        # 最活跃条目列表
        active_group = QGroupBox("最活跃条目 (Top 10)")
        active_layout = QVBoxLayout(active_group)
        
        self.active_entries_list = QListWidget()
        self.active_entries_list.itemDoubleClicked.connect(self._on_entry_double_clicked)
        active_layout.addWidget(self.active_entries_list)
        
        layout.addWidget(active_group)
        
        return widget
        
    def _create_timeline_tab(self) -> QWidget:
        """创建时间线标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 控制区域
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("显示天数:"))
        self.timeline_days_spin = QSpinBox()
        self.timeline_days_spin.setRange(7, 365)
        self.timeline_days_spin.setValue(30)
        self.timeline_days_spin.setSuffix(" 天")
        self.timeline_days_spin.valueChanged.connect(self._update_timeline)
        control_layout.addWidget(self.timeline_days_spin)
        
        control_layout.addWidget(QLabel("条目:"))
        self.timeline_entry_combo = QComboBox()
        self.timeline_entry_combo.addItem("全部条目", None)
        self.timeline_entry_combo.currentIndexChanged.connect(self._update_timeline)
        control_layout.addWidget(self.timeline_entry_combo)
        
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 图表区域
        self.timeline_chart = ChartWidget()
        layout.addWidget(self.timeline_chart)
        
        # 统计信息
        self.timeline_stats_label = QLabel()
        layout.addWidget(self.timeline_stats_label)
        
        return widget
        
    def _create_distribution_tab(self) -> QWidget:
        """创建分布标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 引用数分布柱状图
        dist_group = QGroupBox("引用数分布")
        dist_layout = QVBoxLayout(dist_group)
        
        self.distribution_chart = ChartWidget()
        dist_layout.addWidget(self.distribution_chart)
        
        layout.addWidget(dist_group)
        
        # 类型分布饼图
        type_group = QGroupBox("类型分布")
        type_layout = QVBoxLayout(type_group)
        
        self.type_chart = ChartWidget()
        type_layout.addWidget(self.type_chart)
        
        layout.addWidget(type_group)
        
        return widget
        
    def _create_cooccurrence_tab(self) -> QWidget:
        """创建共现分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 控制区域
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("选择条目:"))
        self.cooccurrence_entry_combo = QComboBox()
        self.cooccurrence_entry_combo.currentIndexChanged.connect(self._update_cooccurrence)
        control_layout.addWidget(self.cooccurrence_entry_combo)
        
        control_layout.addWidget(QLabel("最小共现次数:"))
        self.cooccurrence_threshold_spin = QSpinBox()
        self.cooccurrence_threshold_spin.setRange(1, 10)
        self.cooccurrence_threshold_spin.setValue(2)
        self.cooccurrence_threshold_spin.valueChanged.connect(self._update_cooccurrence)
        control_layout.addWidget(self.cooccurrence_threshold_spin)
        
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 共现结果表格
        self.cooccurrence_table = QTableWidget()
        self.cooccurrence_table.setColumnCount(4)
        self.cooccurrence_table.setHorizontalHeaderLabels(["条目", "类型", "共现次数", "共享文档数"])
        self.cooccurrence_table.horizontalHeader().setStretchLastSection(True)
        self.cooccurrence_table.itemDoubleClicked.connect(self._on_cooccurrence_item_clicked)
        
        layout.addWidget(self.cooccurrence_table)
        
        return widget
        
    def _create_details_tab(self) -> QWidget:
        """创建详细数据标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        # 详细信息容器
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        self.details_text_label = QLabel()
        self.details_text_label.setWordWrap(True)
        self.details_text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self.details_text_label)
        
        details_layout.addStretch()
        
        scroll.setWidget(details_widget)
        layout.addWidget(scroll)
        
        return widget
        
    def _create_stat_card(self, title: str, value: str) -> QGroupBox:
        """创建统计卡片"""
        card = QGroupBox()
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        value_label.setObjectName(f"{title}_value")  # 用于后续更新
        layout.addWidget(value_label)
        
        return card
        
    def refresh_statistics(self):
        """刷新所有统计数据"""
        try:
            # 获取增强的统计数据
            stats = self.codex_manager.get_enhanced_reference_statistics()
            
            # 更新概览卡片
            self._update_overview_cards(stats)
            
            # 更新最活跃条目列表
            self._update_active_entries_list(stats.get('most_referenced_entries', []))
            
            # 更新条目下拉列表
            self._update_entry_combos()
            
            # 更新时间线
            self._update_timeline()
            
            # 更新分布图表
            self._update_distribution_charts(stats)
            
            # 更新详细信息
            self._update_details(stats)
            
        except Exception as e:
            logger.error(f"Error refreshing statistics: {e}")
            
    def _update_overview_cards(self, stats: Dict[str, Any]):
        """更新概览卡片"""
        # 查找并更新各个值标签
        self.total_refs_card.findChild(QLabel, "总引用数_value").setText(str(stats.get('total_references', 0)))
        self.active_refs_card.findChild(QLabel, "活跃引用_value").setText(str(stats.get('active_references', 0)))
        self.unused_entries_card.findChild(QLabel, "未使用条目_value").setText(str(len(stats.get('unused_entries', []))))
        
        ref_dist = stats.get('reference_distribution', {})
        self.avg_refs_card.findChild(QLabel, "平均引用数_value").setText(f"{ref_dist.get('mean', 0):.1f}")
        
        self.recent_refs_card.findChild(QLabel, "最近7天_value").setText(str(stats.get('recent_references_7d', 0)))
        
        confidence_stats = stats.get('confidence_statistics', {})
        self.low_confidence_card.findChild(QLabel, "低置信度_value").setText(str(confidence_stats.get('low_confidence_count', 0)))
        
    def _update_active_entries_list(self, entries: List[Dict[str, Any]]):
        """更新最活跃条目列表"""
        self.active_entries_list.clear()
        
        for entry in entries:
            title = entry.get('title', 'Unknown')
            count = entry.get('count', 0)
            item = QListWidgetItem(f"{title} ({count} 次引用)")
            item.setData(Qt.ItemDataRole.UserRole, entry.get('entry_id'))
            self.active_entries_list.addItem(item)
            
    def _update_entry_combos(self):
        """更新条目下拉列表"""
        # 保存当前选择
        timeline_current = self.timeline_entry_combo.currentData()
        cooccurrence_current = self.cooccurrence_entry_combo.currentData()
        
        # 清空并重新填充
        self.timeline_entry_combo.clear()
        self.timeline_entry_combo.addItem("全部条目", None)
        
        self.cooccurrence_entry_combo.clear()
        
        # 添加所有条目
        for entry_id, entry in self.codex_manager._entries.items():
            if entry.track_references:
                self.timeline_entry_combo.addItem(entry.title, entry_id)
                self.cooccurrence_entry_combo.addItem(entry.title, entry_id)
                
        # 恢复选择
        if timeline_current:
            index = self.timeline_entry_combo.findData(timeline_current)
            if index >= 0:
                self.timeline_entry_combo.setCurrentIndex(index)
                
        if cooccurrence_current:
            index = self.cooccurrence_entry_combo.findData(cooccurrence_current)
            if index >= 0:
                self.cooccurrence_entry_combo.setCurrentIndex(index)
                
    def _update_timeline(self):
        """更新时间线图表"""
        days = self.timeline_days_spin.value()
        entry_id = self.timeline_entry_combo.currentData()
        
        # 获取时间线数据
        timeline_data = self.codex_manager.get_reference_timeline(entry_id, days)
        
        # 更新图表
        self.timeline_chart.set_data(timeline_data.get('timeline', []), "line")
        
        # 更新统计信息
        total = timeline_data.get('total_references', 0)
        days_with_refs = timeline_data.get('days_with_references', 0)
        peak_day = timeline_data.get('peak_day', {})
        
        stats_text = f"总引用: {total} | 有引用的天数: {days_with_refs}"
        if peak_day:
            stats_text += f" | 峰值: {peak_day.get('date', '')} ({peak_day.get('count', 0)} 次)"
            
        self.timeline_stats_label.setText(stats_text)
        
    def _update_distribution_charts(self, stats: Dict[str, Any]):
        """更新分布图表"""
        # 更新引用数分布
        most_referenced = stats.get('most_referenced_entries', [])
        self.distribution_chart.set_data(most_referenced, "bar")
        
        # 更新类型分布
        type_counts = []
        for entry_type in ['CHARACTER', 'LOCATION', 'OBJECT', 'LORE', 'SUBPLOT', 'OTHER']:
            count = len([e for e in self.codex_manager._entries.values() 
                        if e.entry_type.value == entry_type and e.track_references])
            if count > 0:
                type_counts.append({'title': entry_type, 'count': count})
                
        self.type_chart.set_data(type_counts, "pie")
        
    def _update_cooccurrence(self):
        """更新共现分析"""
        entry_id = self.cooccurrence_entry_combo.currentData()
        if not entry_id:
            self.cooccurrence_table.setRowCount(0)
            return
            
        threshold = self.cooccurrence_threshold_spin.value()
        
        # 获取共现数据
        cooccurrences = self.codex_manager.get_reference_co_occurrences(entry_id, threshold)
        
        # 更新表格
        self.cooccurrence_table.setRowCount(len(cooccurrences))
        
        for i, item in enumerate(cooccurrences):
            self.cooccurrence_table.setItem(i, 0, QTableWidgetItem(item.get('title', '')))
            self.cooccurrence_table.setItem(i, 1, QTableWidgetItem(item.get('type', '')))
            self.cooccurrence_table.setItem(i, 2, QTableWidgetItem(str(item.get('co_occurrence_count', 0))))
            self.cooccurrence_table.setItem(i, 3, QTableWidgetItem(str(item.get('shared_documents', 0))))
            
            # 存储条目ID
            self.cooccurrence_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, item.get('entry_id'))
            
    def _update_details(self, stats: Dict[str, Any]):
        """更新详细信息"""
        details_html = "<h3>详细统计报告</h3>"
        
        # 引用分布
        ref_dist = stats.get('reference_distribution', {})
        details_html += f"""
        <h4>引用分布统计</h4>
        <ul>
            <li>平均值: {ref_dist.get('mean', 0):.2f}</li>
            <li>中位数: {ref_dist.get('median', 0):.2f}</li>
            <li>标准差: {ref_dist.get('std_dev', 0):.2f}</li>
            <li>最大值: {ref_dist.get('max', 0)}</li>
            <li>最小值: {ref_dist.get('min', 0)}</li>
        </ul>
        """
        
        # 访问统计
        access_stats = stats.get('access_statistics', {})
        details_html += f"""
        <h4>访问统计</h4>
        <ul>
            <li>总访问次数: {access_stats.get('total_accesses', 0)}</li>
            <li>平均访问次数: {access_stats.get('avg_accesses', 0):.2f}</li>
            <li>最高访问次数: {access_stats.get('most_accessed', 0)}</li>
        </ul>
        """
        
        # 置信度统计
        confidence_stats = stats.get('confidence_statistics', {})
        details_html += f"""
        <h4>置信度统计</h4>
        <ul>
            <li>平均置信度: {confidence_stats.get('avg_confidence', 0):.2%}</li>
            <li>低置信度引用: {confidence_stats.get('low_confidence_count', 0)}</li>
            <li>高置信度引用: {confidence_stats.get('high_confidence_count', 0)}</li>
        </ul>
        """
        
        # 未使用条目
        unused = stats.get('unused_entries', [])
        if unused:
            details_html += "<h4>未使用条目 (前10个)</h4><ul>"
            for entry in unused[:10]:
                details_html += f"<li>{entry.get('title', '')} ({entry.get('type', '')})</li>"
            details_html += "</ul>"
            
        self.details_text_label.setText(details_html)
        
    def _on_entry_double_clicked(self, item: QListWidgetItem):
        """处理条目双击事件"""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if entry_id:
            self.entry_selected.emit(entry_id)
            
    def _on_cooccurrence_item_clicked(self, item: QTableWidgetItem):
        """处理共现表格项点击"""
        if item.column() == 0:  # 只响应条目名称列
            entry_id = item.data(Qt.ItemDataRole.UserRole)
            if entry_id:
                self.entry_selected.emit(entry_id)
                
    def _export_report(self):
        """导出统计报告"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            import json
            
            # 选择保存位置
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出统计报告", "", "JSON文件 (*.json);;文本文件 (*.txt)"
            )
            
            if not file_path:
                return
                
            # 收集所有统计数据
            stats = self.codex_manager.get_enhanced_reference_statistics()
            
            # 添加时间戳
            stats['export_time'] = datetime.now().isoformat()
            stats['export_type'] = 'enhanced_reference_statistics'
            
            # 保存文件
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)
            else:
                # 文本格式
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("增强引用统计报告\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"导出时间: {stats['export_time']}\n\n")
                    
                    f.write("基础统计:\n")
                    f.write(f"- 总引用数: {stats.get('total_references', 0)}\n")
                    f.write(f"- 活跃引用数: {stats.get('active_references', 0)}\n")
                    f.write(f"- 删除引用数: {stats.get('deleted_references', 0)}\n")
                    f.write(f"- 最近7天引用数: {stats.get('recent_references_7d', 0)}\n\n")
                    
                    f.write("最活跃条目 (Top 10):\n")
                    for entry in stats.get('most_referenced_entries', []):
                        f.write(f"- {entry.get('title', 'Unknown')}: {entry.get('count', 0)} 次\n")
                        
            logger.info(f"Statistics report exported to: {file_path}")
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}")