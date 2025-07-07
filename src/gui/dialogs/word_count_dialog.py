"""
字数统计对话框
显示详细的文本统计信息，包括字数、字符数、段落数等
"""

import logging
import re
from typing import Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class WordCountDialog(QDialog):
    """字数统计对话框"""
    
    def __init__(self, parent=None, text_editor=None):
        super().__init__(parent)
        
        self._text_editor = text_editor
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_statistics)
        self._update_timer.setSingleShot(True)
        
        self._init_ui()
        self._setup_connections()
        
        # 设置对话框属性
        self.setModal(False)
        self.setWindowTitle("字数统计")
        self.resize(400, 500)
        
        # 初始更新
        self._update_statistics()
        
        logger.debug("Word count dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标签页
        self._tabs = QTabWidget()
        
        # 基本统计标签页
        basic_tab = self._create_basic_tab()
        self._tabs.addTab(basic_tab, "基本统计")
        
        # 详细统计标签页
        detailed_tab = self._create_detailed_tab()
        self._tabs.addTab(detailed_tab, "详细统计")
        
        # 阅读时间标签页
        reading_tab = self._create_reading_tab()
        self._tabs.addTab(reading_tab, "阅读时间")
        
        layout.addWidget(self._tabs)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_basic_tab(self) -> QWidget:
        """创建基本统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 基本统计组
        basic_group = QGroupBox("基本统计")
        basic_layout = QFormLayout(basic_group)
        
        # 创建标签
        self._word_count_label = QLabel("0")
        self._word_count_label.setFont(QFont("", 14, QFont.Weight.Bold))
        basic_layout.addRow("字数:", self._word_count_label)
        
        self._char_count_label = QLabel("0")
        self._char_count_label.setFont(QFont("", 12))
        basic_layout.addRow("字符数:", self._char_count_label)
        
        self._char_no_space_label = QLabel("0")
        self._char_no_space_label.setFont(QFont("", 12))
        basic_layout.addRow("字符数(不含空格):", self._char_no_space_label)
        
        self._paragraph_count_label = QLabel("0")
        self._paragraph_count_label.setFont(QFont("", 12))
        basic_layout.addRow("段落数:", self._paragraph_count_label)
        
        self._line_count_label = QLabel("0")
        self._line_count_label.setFont(QFont("", 12))
        basic_layout.addRow("行数:", self._line_count_label)
        
        layout.addWidget(basic_group)
        
        # 选中文本统计组
        selection_group = QGroupBox("选中文本统计")
        selection_layout = QFormLayout(selection_group)
        
        self._sel_word_count_label = QLabel("0")
        selection_layout.addRow("选中字数:", self._sel_word_count_label)
        
        self._sel_char_count_label = QLabel("0")
        selection_layout.addRow("选中字符数:", self._sel_char_count_label)
        
        layout.addWidget(selection_group)
        layout.addStretch()
        
        return widget
    
    def _create_detailed_tab(self) -> QWidget:
        """创建详细统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 语言统计组
        lang_group = QGroupBox("语言统计")
        lang_layout = QFormLayout(lang_group)
        
        self._chinese_char_label = QLabel("0")
        lang_layout.addRow("中文字符:", self._chinese_char_label)
        
        self._english_word_label = QLabel("0")
        lang_layout.addRow("英文单词:", self._english_word_label)
        
        self._number_count_label = QLabel("0")
        lang_layout.addRow("数字:", self._number_count_label)
        
        self._punctuation_label = QLabel("0")
        lang_layout.addRow("标点符号:", self._punctuation_label)
        
        layout.addWidget(lang_group)
        
        # 结构统计组
        structure_group = QGroupBox("结构统计")
        structure_layout = QFormLayout(structure_group)
        
        self._sentence_count_label = QLabel("0")
        structure_layout.addRow("句子数:", self._sentence_count_label)
        
        self._avg_words_per_sentence_label = QLabel("0")
        structure_layout.addRow("平均每句字数:", self._avg_words_per_sentence_label)
        
        self._avg_chars_per_paragraph_label = QLabel("0")
        structure_layout.addRow("平均每段字符数:", self._avg_chars_per_paragraph_label)
        
        layout.addWidget(structure_group)
        layout.addStretch()
        
        return widget
    
    def _create_reading_tab(self) -> QWidget:
        """创建阅读时间标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 阅读时间组
        reading_group = QGroupBox("预估阅读时间")
        reading_layout = QFormLayout(reading_group)
        
        self._reading_time_slow_label = QLabel("0分钟")
        reading_layout.addRow("慢速阅读(150字/分):", self._reading_time_slow_label)
        
        self._reading_time_normal_label = QLabel("0分钟")
        reading_layout.addRow("正常阅读(250字/分):", self._reading_time_normal_label)
        
        self._reading_time_fast_label = QLabel("0分钟")
        reading_layout.addRow("快速阅读(400字/分):", self._reading_time_fast_label)
        
        layout.addWidget(reading_group)
        
        # 写作进度组
        progress_group = QGroupBox("写作进度")
        progress_layout = QFormLayout(progress_group)
        
        self._target_words_label = QLabel("未设置")
        progress_layout.addRow("目标字数:", self._target_words_label)
        
        self._progress_percentage_label = QLabel("0%")
        progress_layout.addRow("完成进度:", self._progress_percentage_label)
        
        self._remaining_words_label = QLabel("0")
        progress_layout.addRow("剩余字数:", self._remaining_words_label)
        
        layout.addWidget(progress_group)
        layout.addStretch()
        
        return widget
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._update_statistics)
        layout.addWidget(refresh_btn)
        
        # 导出按钮
        export_btn = QPushButton("导出统计")
        export_btn.clicked.connect(self._export_statistics)
        layout.addWidget(export_btn)
        
        layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return layout
    
    def _setup_connections(self):
        """设置信号连接"""
        if self._text_editor:
            # 连接文本变化信号
            self._text_editor.textChanged.connect(self._on_text_changed)
            self._text_editor.selectionChanged.connect(self._update_selection_stats)
    
    def _on_text_changed(self):
        """文本变化处理"""
        # 延迟更新，避免频繁计算
        self._update_timer.start(500)
    
    def _update_statistics(self):
        """更新统计信息"""
        if not self._text_editor:
            return
        
        text = self._text_editor.toPlainText()
        stats = self._calculate_statistics(text)
        
        # 更新基本统计
        self._word_count_label.setText(f"{stats['word_count']:,}")
        self._char_count_label.setText(f"{stats['char_count']:,}")
        self._char_no_space_label.setText(f"{stats['char_no_space']:,}")
        self._paragraph_count_label.setText(f"{stats['paragraph_count']:,}")
        self._line_count_label.setText(f"{stats['line_count']:,}")
        
        # 更新详细统计
        self._chinese_char_label.setText(f"{stats['chinese_chars']:,}")
        self._english_word_label.setText(f"{stats['english_words']:,}")
        self._number_count_label.setText(f"{stats['numbers']:,}")
        self._punctuation_label.setText(f"{stats['punctuation']:,}")
        self._sentence_count_label.setText(f"{stats['sentences']:,}")
        
        # 计算平均值
        avg_words_per_sentence = stats['word_count'] / max(stats['sentences'], 1)
        self._avg_words_per_sentence_label.setText(f"{avg_words_per_sentence:.1f}")
        
        avg_chars_per_paragraph = stats['char_count'] / max(stats['paragraph_count'], 1)
        self._avg_chars_per_paragraph_label.setText(f"{avg_chars_per_paragraph:.1f}")
        
        # 更新阅读时间
        self._update_reading_time(stats['word_count'])
        
        # 更新选中文本统计
        self._update_selection_stats()
    
    def _update_selection_stats(self):
        """更新选中文本统计"""
        if not self._text_editor:
            return
        
        cursor = self._text_editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            stats = self._calculate_statistics(selected_text)
            
            self._sel_word_count_label.setText(f"{stats['word_count']:,}")
            self._sel_char_count_label.setText(f"{stats['char_count']:,}")
        else:
            self._sel_word_count_label.setText("0")
            self._sel_char_count_label.setText("0")
    
    def _update_reading_time(self, word_count: int):
        """更新阅读时间"""
        # 慢速阅读 150字/分钟
        slow_minutes = word_count / 150
        self._reading_time_slow_label.setText(f"{slow_minutes:.1f}分钟")
        
        # 正常阅读 250字/分钟
        normal_minutes = word_count / 250
        self._reading_time_normal_label.setText(f"{normal_minutes:.1f}分钟")
        
        # 快速阅读 400字/分钟
        fast_minutes = word_count / 400
        self._reading_time_fast_label.setText(f"{fast_minutes:.1f}分钟")
    
    def _calculate_statistics(self, text: str) -> Dict[str, int]:
        """计算文本统计信息"""
        if not text:
            return {
                'word_count': 0, 'char_count': 0, 'char_no_space': 0,
                'paragraph_count': 0, 'line_count': 0, 'chinese_chars': 0,
                'english_words': 0, 'numbers': 0, 'punctuation': 0, 'sentences': 0
            }
        
        # 基本统计
        word_count = len(text.split())
        char_count = len(text)
        char_no_space = len(text.replace(' ', '').replace('\t', '').replace('\n', ''))
        
        # 段落和行数
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        paragraph_count = len(paragraphs)
        line_count = len(text.split('\n'))
        
        # 中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        
        # 英文单词
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        
        # 数字
        numbers = len(re.findall(r'\d+', text))
        
        # 标点符号
        punctuation = len(re.findall(r'[^\w\s]', text))
        
        # 句子数（简单估算）
        sentences = len(re.findall(r'[.!?。！？]+', text))
        
        return {
            'word_count': word_count,
            'char_count': char_count,
            'char_no_space': char_no_space,
            'paragraph_count': paragraph_count,
            'line_count': line_count,
            'chinese_chars': chinese_chars,
            'english_words': english_words,
            'numbers': numbers,
            'punctuation': punctuation,
            'sentences': max(sentences, 1)  # 至少1句
        }
    
    def _export_statistics(self):
        """导出统计信息"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出统计信息", "word_statistics.txt", "文本文件 (*.txt)"
        )
        
        if filename:
            try:
                text = self._text_editor.toPlainText() if self._text_editor else ""
                stats = self._calculate_statistics(text)
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("文本统计报告\n")
                    f.write("=" * 30 + "\n\n")
                    f.write(f"字数: {stats['word_count']:,}\n")
                    f.write(f"字符数: {stats['char_count']:,}\n")
                    f.write(f"字符数(不含空格): {stats['char_no_space']:,}\n")
                    f.write(f"段落数: {stats['paragraph_count']:,}\n")
                    f.write(f"行数: {stats['line_count']:,}\n")
                    f.write(f"中文字符: {stats['chinese_chars']:,}\n")
                    f.write(f"英文单词: {stats['english_words']:,}\n")
                    f.write(f"数字: {stats['numbers']:,}\n")
                    f.write(f"标点符号: {stats['punctuation']:,}\n")
                    f.write(f"句子数: {stats['sentences']:,}\n")
                
                QMessageBox.information(self, "导出成功", f"统计信息已导出到: {filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出统计信息时发生错误: {str(e)}")
    
    def set_target_words(self, target: int):
        """设置目标字数"""
        self._target_words_label.setText(f"{target:,}")
        
        if self._text_editor:
            current_words = len(self._text_editor.toPlainText().split())
            progress = (current_words / target * 100) if target > 0 else 0
            remaining = max(0, target - current_words)
            
            self._progress_percentage_label.setText(f"{progress:.1f}%")
            self._remaining_words_label.setText(f"{remaining:,}")
    
    def show_and_focus(self):
        """显示并聚焦"""
        self.show()
        self.raise_()
        self.activateWindow()
        self._update_statistics()
