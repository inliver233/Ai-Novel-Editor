"""
简化版查找替换对话框
确保基本功能正常工作
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QCheckBox, QTabWidget, QWidget, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression
from PyQt6.QtGui import QTextCursor, QTextDocument

logger = logging.getLogger(__name__)


class SimpleFindDialog(QDialog):
    """简化版查找替换对话框"""
    
    def __init__(self, parent=None, text_editor=None):
        super().__init__(parent)
        
        self._text_editor = text_editor
        
        self._init_ui()
        self._setup_connections()
        
        # 设置对话框属性
        self.setModal(False)
        self.setWindowTitle("查找和替换")
        self.resize(400, 250)
        
        logger.debug("Simple find dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标签页
        self._tabs = QTabWidget()
        
        # 查找标签页
        find_tab = self._create_find_tab()
        self._tabs.addTab(find_tab, "查找")
        
        # 替换标签页
        replace_tab = self._create_replace_tab()
        self._tabs.addTab(replace_tab, "替换")
        
        layout.addWidget(self._tabs)
        
        # 选项区域
        options_group = self._create_options_group()
        layout.addWidget(options_group)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_find_tab(self) -> QWidget:
        """创建查找标签页"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 查找输入框
        self._find_edit = QLineEdit()
        self._find_edit.setPlaceholderText("输入要查找的文本...")
        layout.addRow("查找:", self._find_edit)
        
        return widget
    
    def _create_replace_tab(self) -> QWidget:
        """创建替换标签页"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 查找输入框
        self._replace_find_edit = QLineEdit()
        self._replace_find_edit.setPlaceholderText("输入要查找的文本...")
        layout.addRow("查找:", self._replace_find_edit)
        
        # 替换输入框
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("输入替换文本...")
        layout.addRow("替换为:", self._replace_edit)
        
        return widget
    
    def _create_options_group(self) -> QGroupBox:
        """创建选项组"""
        group = QGroupBox("选项")
        layout = QVBoxLayout(group)
        
        # 基本选项
        self._case_sensitive_check = QCheckBox("区分大小写")
        layout.addWidget(self._case_sensitive_check)
        
        self._whole_word_check = QCheckBox("全字匹配")
        layout.addWidget(self._whole_word_check)
        
        self._regex_check = QCheckBox("正则表达式")
        layout.addWidget(self._regex_check)
        
        return group
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        
        # 查找按钮
        self._find_next_btn = QPushButton("查找下一个")
        self._find_next_btn.clicked.connect(self._find_next)
        layout.addWidget(self._find_next_btn)
        
        self._find_prev_btn = QPushButton("查找上一个")
        self._find_prev_btn.clicked.connect(self._find_previous)
        layout.addWidget(self._find_prev_btn)
        
        # 替换按钮
        self._replace_btn = QPushButton("替换")
        self._replace_btn.clicked.connect(self._replace_current)
        layout.addWidget(self._replace_btn)
        
        self._replace_all_btn = QPushButton("全部替换")
        self._replace_all_btn.clicked.connect(self._replace_all)
        layout.addWidget(self._replace_all_btn)
        
        layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return layout
    
    def _setup_connections(self):
        """设置信号连接"""
        # 输入框回车键
        self._find_edit.returnPressed.connect(self._find_next)
        self._replace_find_edit.returnPressed.connect(self._find_next)
        self._replace_edit.returnPressed.connect(self._replace_current)
        
        # 标签页切换
        self._tabs.currentChanged.connect(self._on_tab_changed)
        
        # 初始化按钮状态
        self._on_tab_changed(0)
    
    def _on_tab_changed(self, index: int):
        """标签页切换处理"""
        print(f"📋 标签页切换到: {index}")  # 调试输出
        
        if index == 0:  # 查找标签页
            self._replace_btn.setEnabled(False)
            self._replace_all_btn.setEnabled(False)
        else:  # 替换标签页
            self._replace_btn.setEnabled(True)
            self._replace_all_btn.setEnabled(True)
    
    def _get_search_text(self) -> str:
        """获取搜索文本"""
        if self._tabs.currentIndex() == 0:
            return self._find_edit.text()
        else:
            return self._replace_find_edit.text()
    
    def _get_search_options(self) -> dict:
        """获取搜索选项"""
        return {
            "case_sensitive": self._case_sensitive_check.isChecked(),
            "whole_word": self._whole_word_check.isChecked(),
            "regex": self._regex_check.isChecked(),
        }
    
    def _find_next(self):
        """查找下一个"""
        search_text = self._get_search_text()
        print(f"🔍 查找下一个: '{search_text}'")  # 调试输出
        
        if not search_text:
            print("❌ 搜索文本为空")
            return
        
        if not self._text_editor:
            print("❌ 文本编辑器为空")
            return
        
        options = self._get_search_options()
        print(f"🔧 搜索选项: {options}")
        
        self._perform_search(search_text, options, True)
    
    def _find_previous(self):
        """查找上一个"""
        search_text = self._get_search_text()
        print(f"🔍 查找上一个: '{search_text}'")
        
        if not search_text:
            print("❌ 搜索文本为空")
            return
        
        if not self._text_editor:
            print("❌ 文本编辑器为空")
            return
        
        options = self._get_search_options()
        self._perform_search(search_text, options, False)
    
    def _replace_current(self):
        """替换当前"""
        search_text = self._replace_find_edit.text()
        replace_text = self._replace_edit.text()
        
        print(f"🔄 替换: '{search_text}' -> '{replace_text}'")
        
        if not search_text:
            print("❌ 搜索文本为空")
            return
        
        if not self._text_editor:
            print("❌ 文本编辑器为空")
            return
        
        # 简单替换：如果有选中文本且匹配，则替换
        cursor = self._text_editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            if selected_text == search_text:
                cursor.insertText(replace_text)
                print("✅ 替换成功")
                return
        
        # 否则先查找
        self._find_next()
    
    def _replace_all(self):
        """全部替换"""
        search_text = self._replace_find_edit.text()
        replace_text = self._replace_edit.text()
        
        print(f"🔄 全部替换: '{search_text}' -> '{replace_text}'")
        
        if not search_text:
            print("❌ 搜索文本为空")
            return
        
        if not self._text_editor:
            print("❌ 文本编辑器为空")
            return
        
        # 简单的全部替换
        content = self._text_editor.toPlainText()
        new_content = content.replace(search_text, replace_text)
        count = content.count(search_text)
        
        if count > 0:
            self._text_editor.setPlainText(new_content)
            print(f"✅ 替换了 {count} 处")
            self._show_message(f"已替换 {count} 处")
        else:
            print("❌ 未找到匹配项")
            self._show_message("未找到匹配项")
    
    def _perform_search(self, search_text: str, options: dict, forward: bool = True):
        """执行搜索"""
        print(f"🔍 执行搜索: '{search_text}', 向前: {forward}")

        # 获取文档内容进行调试
        document_content = self._text_editor.toPlainText()
        print(f"📄 文档内容长度: {len(document_content)}")
        print(f"📄 文档内容预览: {repr(document_content[:100])}")

        # 获取当前光标位置
        cursor = self._text_editor.textCursor()
        original_position = cursor.position()
        print(f"📍 当前光标位置: {original_position}")
        print(f"📍 文档总字符数: {self._text_editor.document().characterCount()}")

        # 如果有选中文本且正在向前搜索，从选中文本的末尾开始搜索
        if forward and cursor.hasSelection():
            cursor.setPosition(cursor.selectionEnd())
            print(f"📍 调整搜索起始位置到选中文本末尾: {cursor.position()}")

        # 构建搜索标志
        flags = QTextDocument.FindFlag(0)

        if options.get("case_sensitive", False):
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        if options.get("whole_word", False):
            flags |= QTextDocument.FindFlag.FindWholeWords

        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward

        # 执行搜索
        if options.get("regex", False):
            # 正则表达式搜索
            regex = QRegularExpression(search_text)
            if not options.get("case_sensitive", False):
                regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
            found_cursor = self._text_editor.document().find(regex, cursor, flags)
        else:
            # 普通文本搜索
            found_cursor = self._text_editor.document().find(search_text, cursor, flags)

        print(f"🔍 第一次搜索结果: {not found_cursor.isNull()}")

        if not found_cursor.isNull():
            print(f"📍 找到匹配项位置: {found_cursor.selectionStart()}-{found_cursor.selectionEnd()}")
            self._text_editor.setTextCursor(found_cursor)
            self._text_editor.ensureCursorVisible()
            print("✅ 找到匹配项")
        else:
            # 尝试循环搜索
            print("🔄 尝试循环搜索...")
            if self._try_wrap_around_search(search_text, options, forward, original_position):
                print("✅ 循环搜索找到匹配项")
            else:
                print("❌ 未找到匹配项")
                self._show_message("未找到匹配项")

    def _try_wrap_around_search(self, search_text: str, options: dict, forward: bool, original_position: int) -> bool:
        """尝试循环搜索"""
        # 构建搜索标志
        flags = QTextDocument.FindFlag(0)

        if options.get("case_sensitive", False):
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        if options.get("whole_word", False):
            flags |= QTextDocument.FindFlag.FindWholeWords

        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward

        # 创建新的光标，从文档开始或结束位置搜索
        cursor = QTextCursor(self._text_editor.document())
        if forward:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.End)

        # 执行搜索
        if options.get("regex", False):
            regex = QRegularExpression(search_text)
            if not options.get("case_sensitive", False):
                regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
            found_cursor = self._text_editor.document().find(regex, cursor, flags)
        else:
            found_cursor = self._text_editor.document().find(search_text, cursor, flags)

        if not found_cursor.isNull():
            # 检查是否回到了原始位置（避免无限循环）
            found_start = found_cursor.selectionStart()
            if found_start != original_position:
                print(f"🔄 循环搜索成功，匹配位置: {found_cursor.selectionStart()}-{found_cursor.selectionEnd()}")
                self._text_editor.setTextCursor(found_cursor)
                self._text_editor.ensureCursorVisible()
                return True
            else:
                print(f"🔄 循环搜索回到原始位置，停止搜索")

        return False
    
    def _show_message(self, message: str):
        """显示消息"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "查找替换", message)
    
    def set_search_text(self, text: str):
        """设置搜索文本"""
        self._find_edit.setText(text)
        self._replace_find_edit.setText(text)
    
    def show_and_focus(self):
        """显示并聚焦"""
        self.show()
        self.raise_()
        self.activateWindow()
        
        if self._tabs.currentIndex() == 0:
            self._find_edit.setFocus()
            self._find_edit.selectAll()
        else:
            self._replace_find_edit.setFocus()
            self._replace_find_edit.selectAll()
