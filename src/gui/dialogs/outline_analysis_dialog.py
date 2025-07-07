"""
大纲分析结果对话框
显示大纲优化建议、分析结果和改进方案
"""

import logging
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, 
    QPushButton, QTabWidget, QWidget, QScrollArea, QFrame,
    QProgressBar, QGroupBox, QListWidget, QListWidgetItem,
    QSplitter, QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QPalette

logger = logging.getLogger(__name__)


class SuggestionItemWidget(QWidget):
    """建议项目小部件"""
    
    applyRequested = pyqtSignal(object)  # 应用建议信号
    
    def __init__(self, suggestion, parent=None):
        super().__init__(parent)
        self.suggestion = suggestion
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # 建议标题和优先级
        header_layout = QHBoxLayout()
        
        title_label = QLabel(self.suggestion.title)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        # 优先级标签
        priority_label = QLabel(self._get_priority_text())
        priority_label.setStyleSheet(self._get_priority_style())
        priority_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        priority_label.setMinimumWidth(60)
        header_layout.addWidget(priority_label)
        
        layout.addLayout(header_layout)
        
        # 建议描述
        desc_label = QLabel(self.suggestion.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 10pt;")
        layout.addWidget(desc_label)
        
        # 行动项目
        if self.suggestion.action_items:
            action_label = QLabel("建议行动:")
            action_label.setStyleSheet("font-weight: bold; color: #444; margin-top: 4px;")
            layout.addWidget(action_label)
            
            for action in self.suggestion.action_items:
                action_item = QLabel(f"• {action}")
                action_item.setStyleSheet("color: #555; margin-left: 12px;")
                action_item.setWordWrap(True)
                layout.addWidget(action_item)
        
        # 示例
        if self.suggestion.examples:
            example_label = QLabel("参考示例:")
            example_label.setStyleSheet("font-weight: bold; color: #444; margin-top: 4px;")
            layout.addWidget(example_label)
            
            for example in self.suggestion.examples:
                example_item = QLabel(f"• {example}")
                example_item.setStyleSheet("color: #666; margin-left: 12px; font-style: italic;")
                example_item.setWordWrap(True)
                layout.addWidget(example_item)
        
        # 应用按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        apply_btn = QPushButton("应用建议")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        apply_btn.clicked.connect(lambda: self.applyRequested.emit(self.suggestion))
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
        # 整体样式
        self.setStyleSheet("""
            SuggestionItemWidget {
                background-color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 6px;
                margin: 2px;
            }
        """)
    
    def _get_priority_text(self):
        priority_map = {
            'high': '高',
            'medium': '中', 
            'low': '低'
        }
        return priority_map.get(self.suggestion.priority.value, '中')
    
    def _get_priority_style(self):
        styles = {
            'high': """
                background-color: #ff4444;
                color: white;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 9pt;
                font-weight: bold;
            """,
            'medium': """
                background-color: #ffaa00;
                color: white;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 9pt;
                font-weight: bold;
            """,
            'low': """
                background-color: #44aa44;
                color: white;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 9pt;
                font-weight: bold;
            """
        }
        return styles.get(self.suggestion.priority.value, styles['medium'])


class OutlineAnalysisDialog(QDialog):
    """大纲分析结果对话框"""
    
    applyChangesRequested = pyqtSignal(list)  # 应用更改信号
    
    def __init__(self, analysis_result, parent=None):
        super().__init__(parent)
        self.analysis_result = analysis_result
        self.selected_suggestions = []
        
        self.setWindowTitle("智能大纲分析报告")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        self._init_ui()
        self._populate_data()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # 标题
        title_label = QLabel("📊 智能大纲分析报告")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 主要内容区域
        tab_widget = QTabWidget()
        
        # 概览标签页
        overview_tab = self._create_overview_tab()
        tab_widget.addTab(overview_tab, "📈 分析概览")
        
        # 建议标签页
        suggestions_tab = self._create_suggestions_tab()
        tab_widget.addTab(suggestions_tab, "💡 优化建议")
        
        # 详细报告标签页
        details_tab = self._create_details_tab()
        tab_widget.addTab(details_tab, "📋 详细报告")
        
        layout.addWidget(tab_widget)
        
        # 底部按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | 
            QDialogButtonBox.StandardButton.Close
        )
        
        apply_btn = button_box.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.setText("应用选中建议")
        apply_btn.clicked.connect(self._apply_selected_suggestions)
        
        close_btn = button_box.button(QDialogButtonBox.StandardButton.Close)
        close_btn.setText("关闭")
        close_btn.clicked.connect(self.reject)
        
        layout.addWidget(button_box)
    
    def _create_overview_tab(self) -> QWidget:
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        
        # 分析指标卡片
        metrics_frame = QFrame()
        metrics_frame.setFrameStyle(QFrame.Shape.Box)
        metrics_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        metrics_layout = QVBoxLayout(metrics_frame)
        
        # 指标标题
        metrics_title = QLabel("📊 大纲质量指标")
        metrics_title.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 8px;")
        metrics_layout.addWidget(metrics_title)
        
        # 创建指标进度条
        self.metrics_bars = {}
        metrics = [
            ('content_coverage', '内容覆盖率', '%'),
            ('plot_coherence', '情节连贯性', '%'),
            ('character_development', '角色发展度', '%'),
            ('pacing_balance', '节奏平衡度', '%')
        ]
        
        for metric_key, metric_name, unit in metrics:
            metric_layout = QHBoxLayout()
            
            label = QLabel(f"{metric_name}:")
            label.setMinimumWidth(100)
            metric_layout.addWidget(label)
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setStyleSheet(self._get_progress_bar_style())
            metric_layout.addWidget(progress_bar)
            
            value_label = QLabel("0%")
            value_label.setMinimumWidth(40)
            metric_layout.addWidget(value_label)
            
            metrics_layout.addLayout(metric_layout)
            self.metrics_bars[metric_key] = (progress_bar, value_label)
        
        layout.addWidget(metrics_frame)
        
        # 优点和不足
        strengths_weaknesses_layout = QHBoxLayout()
        
        # 优点
        strengths_group = QGroupBox("✅ 优点")
        strengths_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        strengths_layout = QVBoxLayout(strengths_group)
        
        self.strengths_list = QListWidget()
        self.strengths_list.setStyleSheet("""
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)
        strengths_layout.addWidget(self.strengths_list)
        
        strengths_weaknesses_layout.addWidget(strengths_group)
        
        # 不足
        weaknesses_group = QGroupBox("⚠️ 需要改进")
        weaknesses_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        weaknesses_layout = QVBoxLayout(weaknesses_group)
        
        self.weaknesses_list = QListWidget()
        self.weaknesses_list.setStyleSheet("""
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)
        weaknesses_layout.addWidget(self.weaknesses_list)
        
        strengths_weaknesses_layout.addWidget(weaknesses_group)
        
        layout.addLayout(strengths_weaknesses_layout)
        
        return widget
    
    def _create_suggestions_tab(self) -> QWidget:
        """创建建议标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 建议说明
        info_label = QLabel("💡 基于大纲分析，系统为您生成了以下优化建议。您可以选择应用感兴趣的建议。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 11pt; color: #666; margin-bottom: 8px;")
        layout.addWidget(info_label)
        
        # 建议滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarNever)
        
        self.suggestions_widget = QWidget()
        self.suggestions_layout = QVBoxLayout(self.suggestions_widget)
        self.suggestions_layout.setSpacing(8)
        
        scroll_area.setWidget(self.suggestions_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def _create_details_tab(self) -> QWidget:
        """创建详细报告标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 详细报告文本
        self.details_browser = QTextBrowser()
        self.details_browser.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 4px;
                padding: 12px;
                font-family: 'Microsoft YaHei';
                font-size: 10pt;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.details_browser)
        
        return widget
    
    def _populate_data(self):
        """填充数据"""
        if not self.analysis_result:
            return
        
        # 填充指标数据
        metrics_data = {
            'content_coverage': self.analysis_result.content_coverage,
            'plot_coherence': self.analysis_result.plot_coherence,
            'character_development': self.analysis_result.character_development,
            'pacing_balance': self.analysis_result.pacing_balance
        }
        
        for metric_key, value in metrics_data.items():
            if metric_key in self.metrics_bars:
                progress_bar, value_label = self.metrics_bars[metric_key]
                percentage = int(value * 100)
                progress_bar.setValue(percentage)
                value_label.setText(f"{percentage}%")
        
        # 填充优点列表
        for strength in self.analysis_result.strengths:
            item = QListWidgetItem(f"✓ {strength}")
            item.setForeground(Qt.GlobalColor.darkGreen)
            self.strengths_list.addItem(item)
        
        # 填充不足列表
        for weakness in self.analysis_result.weaknesses:
            item = QListWidgetItem(f"• {weakness}")
            item.setForeground(Qt.GlobalColor.darkRed)
            self.weaknesses_list.addItem(item)
        
        # 填充建议
        for suggestion in self.analysis_result.suggestions:
            suggestion_widget = SuggestionItemWidget(suggestion)
            suggestion_widget.applyRequested.connect(self._on_suggestion_apply_requested)
            self.suggestions_layout.addWidget(suggestion_widget)
        
        self.suggestions_layout.addStretch()
        
        # 填充详细报告
        self._generate_detailed_report()
    
    def _generate_detailed_report(self):
        """生成详细报告"""
        report_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Microsoft YaHei'; line-height: 1.6; }}
                h1, h2, h3 {{ color: #333; }}
                .metric {{ margin: 10px 0; padding: 8px; background-color: #f9f9f9; border-radius: 4px; }}
                .high {{ color: #d32f2f; font-weight: bold; }}
                .medium {{ color: #ff9800; font-weight: bold; }}
                .low {{ color: #388e3c; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>📊 大纲分析详细报告</h1>
            
            <h2>基本信息</h2>
            <div class="metric">
                <strong>总节点数:</strong> {self.analysis_result.total_nodes}<br>
                <strong>结构深度:</strong> {self.analysis_result.structure_depth} 层<br>
                <strong>生成时间:</strong> {self._get_current_time()}
            </div>
            
            <h2>质量指标详情</h2>
            <div class="metric">
                <strong>内容覆盖率:</strong> {self.analysis_result.content_coverage:.1%}<br>
                <em>表示有内容描述的节点占总节点的比例</em>
            </div>
            <div class="metric">
                <strong>情节连贯性:</strong> {self.analysis_result.plot_coherence:.1%}<br>
                <em>评估故事情节的逻辑性和连贯性</em>
            </div>
            <div class="metric">
                <strong>角色发展度:</strong> {self.analysis_result.character_development:.1%}<br>
                <em>衡量角色成长弧线的完整性</em>
            </div>
            <div class="metric">
                <strong>节奏平衡度:</strong> {self.analysis_result.pacing_balance:.1%}<br>
                <em>分析章节长度和内容分布的均衡性</em>
            </div>
            
            <h2>优化建议汇总</h2>
        """
        
        # 按优先级分组建议
        high_priority = [s for s in self.analysis_result.suggestions if s.priority.value == 'high']
        medium_priority = [s for s in self.analysis_result.suggestions if s.priority.value == 'medium']
        low_priority = [s for s in self.analysis_result.suggestions if s.priority.value == 'low']
        
        if high_priority:
            report_html += "<h3 class='high'>🔴 高优先级建议</h3><ul>"
            for suggestion in high_priority:
                report_html += f"<li><strong>{suggestion.title}</strong>: {suggestion.description}</li>"
            report_html += "</ul>"
        
        if medium_priority:
            report_html += "<h3 class='medium'>🟡 中优先级建议</h3><ul>"
            for suggestion in medium_priority:
                report_html += f"<li><strong>{suggestion.title}</strong>: {suggestion.description}</li>"
            report_html += "</ul>"
        
        if low_priority:
            report_html += "<h3 class='low'>🟢 低优先级建议</h3><ul>"
            for suggestion in low_priority:
                report_html += f"<li><strong>{suggestion.title}</strong>: {suggestion.description}</li>"
            report_html += "</ul>"
        
        report_html += """
            <h2>分析方法说明</h2>
            <p>本分析基于以下维度对大纲进行评估：</p>
            <ul>
                <li><strong>结构分析:</strong> 检查大纲的层次结构和组织方式</li>
                <li><strong>内容质量:</strong> 评估内容的完整性和详细程度</li>
                <li><strong>情节分析:</strong> 分析故事的逻辑性和发展脉络</li>
                <li><strong>角色发展:</strong> 评估角色弧线的设计和发展</li>
                <li><strong>节奏控制:</strong> 分析叙述节奏和内容分布</li>
            </ul>
            
            <h2>使用建议</h2>
            <p>建议您按照优先级顺序逐步应用这些建议，并在修改后重新进行分析以观察改进效果。</p>
        </body>
        </html>
        """
        
        self.details_browser.setHtml(report_html)
    
    def _on_suggestion_apply_requested(self, suggestion):
        """处理建议应用请求"""
        if suggestion not in self.selected_suggestions:
            self.selected_suggestions.append(suggestion)
            QMessageBox.information(
                self, 
                "建议已选中", 
                f"建议 '{suggestion.title}' 已添加到应用列表。\n\n"
                f"您可以继续选择其他建议，然后点击 '应用选中建议' 按钮。"
            )
    
    def _apply_selected_suggestions(self):
        """应用选中的建议"""
        if not self.selected_suggestions:
            QMessageBox.warning(self, "无选中建议", "请先选择要应用的建议。")
            return
        
        # 确认对话框
        suggestion_titles = [s.title for s in self.selected_suggestions]
        confirmation_text = f"确定要应用以下 {len(suggestion_titles)} 个建议吗？\n\n"
        confirmation_text += "\n".join(f"• {title}" for title in suggestion_titles)
        
        reply = QMessageBox.question(
            self, 
            "确认应用建议", 
            confirmation_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.applyChangesRequested.emit(self.selected_suggestions)
            self.accept()
    
    def _get_progress_bar_style(self):
        """获取进度条样式"""
        return """
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                font-size: 9pt;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #45a049);
                border-radius: 3px;
            }
        """
    
    def _get_current_time(self):
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")