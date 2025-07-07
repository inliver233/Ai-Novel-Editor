"""
查找替换对话框
实现文本查找、替换、正则表达式搜索等功能
"""

import logging
import re
from typing import Optional, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QCheckBox, QTextEdit,
    QTabWidget, QWidget, QGroupBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression
from PyQt6.QtGui import QFont, QTextCursor, QTextDocument, QTextCharFormat, QColor

logger = logging.getLogger(__name__)


class FindReplaceDialog(QDialog):
    """查找替换对话框"""
    
    # 信号定义
    findRequested = pyqtSignal(str, dict)  # 查找请求信号
    replaceRequested = pyqtSignal(str, str, dict)  # 替换请求信号
    
    def __init__(self, parent=None, text_editor=None):
        super().__init__(parent)

        self._text_editor = text_editor
        self._last_search_position = 0

        # 搜索高亮
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setBackground(QColor(255, 255, 0, 100))  # 黄色半透明背景
        self._current_highlights = []

        # 搜索历史
        self._search_history = []
        self._max_history = 20

        self._init_ui()
        self._setup_connections()

        # 初始化按钮状态
        self._on_tab_changed(0)  # 默认查找标签页

        # 设置对话框属性
        self.setModal(False)  # 非模态对话框
        self.setWindowTitle("查找和替换")
        self.resize(400, 300)

        logger.debug("Find replace dialog initialized")
    
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
        
        # 查找历史
        self._find_history = []
        
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
        
        # 搜索方向
        direction_layout = QHBoxLayout()
        self._forward_check = QCheckBox("向前搜索")
        self._forward_check.setChecked(True)
        direction_layout.addWidget(self._forward_check)
        
        self._backward_check = QCheckBox("向后搜索")
        direction_layout.addWidget(self._backward_check)
        
        layout.addLayout(direction_layout)
        
        # 搜索范围
        self._selection_only_check = QCheckBox("仅在选中区域")
        layout.addWidget(self._selection_only_check)
        
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
        
        # 选项变化
        self._forward_check.toggled.connect(self._on_direction_changed)
        self._backward_check.toggled.connect(self._on_direction_changed)
    
    def _on_tab_changed(self, index: int):
        """标签页切换处理"""
        if index == 0:  # 查找标签页
            self._replace_btn.setEnabled(False)
            self._replace_all_btn.setEnabled(False)
        else:  # 替换标签页
            self._replace_btn.setEnabled(True)
            self._replace_all_btn.setEnabled(True)
    
    def _on_direction_changed(self, checked: bool):
        """搜索方向变化处理"""
        sender = self.sender()
        if sender == self._forward_check and checked:
            self._backward_check.setChecked(False)
        elif sender == self._backward_check and checked:
            self._forward_check.setChecked(False)
    
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
            "forward": self._forward_check.isChecked(),
            "selection_only": self._selection_only_check.isChecked()
        }
    
    def _find_next(self):
        """查找下一个"""
        search_text = self._get_search_text()
        print(f"🔍 查找下一个: '{search_text}'")  # 调试输出

        if not search_text:
            print("❌ 搜索文本为空")  # 调试输出
            return

        options = self._get_search_options()
        options["forward"] = True
        print(f"🔧 搜索选项: {options}")  # 调试输出

        if self._text_editor:
            print("✅ 文本编辑器存在，执行搜索")  # 调试输出
            self._perform_search(search_text, options)
        else:
            print("❌ 文本编辑器不存在，发送信号")  # 调试输出
            self.findRequested.emit(search_text, options)
    
    def _find_previous(self):
        """查找上一个"""
        search_text = self._get_search_text()
        if not search_text:
            return
        
        options = self._get_search_options()
        options["forward"] = False
        
        if self._text_editor:
            self._perform_search(search_text, options)
        else:
            self.findRequested.emit(search_text, options)
    
    def _replace_current(self):
        """替换当前"""
        search_text = self._replace_find_edit.text()
        replace_text = self._replace_edit.text()
        
        if not search_text:
            return
        
        options = self._get_search_options()
        
        if self._text_editor:
            self._perform_replace(search_text, replace_text, options, False)
        else:
            self.replaceRequested.emit(search_text, replace_text, options)
    
    def _replace_all(self):
        """全部替换"""
        search_text = self._replace_find_edit.text()
        replace_text = self._replace_edit.text()
        
        if not search_text:
            return
        
        options = self._get_search_options()
        options["replace_all"] = True
        
        if self._text_editor:
            self._perform_replace(search_text, replace_text, options, True)
        else:
            self.replaceRequested.emit(search_text, replace_text, options)
    
    def _perform_search(self, search_text: str, options: dict):
        """执行搜索"""
        print(f"🔍 开始执行搜索: '{search_text}'")  # 调试输出

        if not self._text_editor:
            print("❌ 文本编辑器为空")  # 调试输出
            return

        try:
            # 验证正则表达式
            if options.get("regex", False):
                regex = QRegularExpression(search_text)
                if not regex.isValid():
                    print(f"❌ 正则表达式无效: {regex.errorString()}")  # 调试输出
                    self._show_regex_error(regex.errorString())
                    return
        except Exception as e:
            print(f"❌ 正则表达式异常: {e}")  # 调试输出
            self._show_regex_error(str(e))
            return

        # 构建搜索标志
        flags = QTextDocument.FindFlag(0)

        if options.get("case_sensitive", False):
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        if options.get("whole_word", False):
            flags |= QTextDocument.FindFlag.FindWholeWords

        if not options.get("forward", True):
            flags |= QTextDocument.FindFlag.FindBackward

        # 执行搜索
        cursor = self._text_editor.textCursor()
        original_position = cursor.position()

        print(f"🔍 当前光标位置: {cursor.position()}")  # 调试输出

        # 直接使用QTextDocument的find方法
        if options.get("regex", False):
            # 正则表达式搜索
            regex = QRegularExpression(search_text)
            if not options.get("case_sensitive", False):
                regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
            found_cursor = self._text_editor.document().find(regex, cursor, flags)
        else:
            # 普通文本搜索
            found_cursor = self._text_editor.document().find(search_text, cursor, flags)

        print(f"🔍 搜索结果: {not found_cursor.isNull()}")  # 调试输出

        if not found_cursor.isNull():
            self._text_editor.setTextCursor(found_cursor)
            self._text_editor.ensureCursorVisible()
            self._add_to_search_history(search_text)

            # 高亮所有匹配项
            self._highlight_all_matches(search_text, options)
        else:
            # 循环搜索
            if self._try_wrap_around_search(search_text, options, original_position):
                # 高亮所有匹配项
                self._highlight_all_matches(search_text, options)
                return

            # 未找到，显示提示
            self._show_not_found_message()
    
    def _perform_replace(self, search_text: str, replace_text: str, options: dict, replace_all: bool):
        """执行替换"""
        if not self._text_editor:
            return

        try:
            # 验证正则表达式
            if options.get("regex", False):
                regex = QRegularExpression(search_text)
                if not regex.isValid():
                    self._show_regex_error(regex.errorString())
                    return
        except Exception as e:
            self._show_regex_error(str(e))
            return

        cursor = self._text_editor.textCursor()

        if replace_all:
            # 全部替换
            count = self._replace_all_occurrences(search_text, replace_text, options)
            self._show_replace_result(count)
        else:
            # 单个替换
            self._replace_current_selection(search_text, replace_text, options)

    def _replace_all_occurrences(self, search_text: str, replace_text: str, options: dict) -> int:
        """替换所有匹配项"""
        count = 0
        cursor = self._text_editor.textCursor()
        cursor.beginEditBlock()

        try:
            # 移动到文档开始
            cursor.movePosition(QTextCursor.MoveOperation.Start)

            # 构建搜索标志
            flags = QTextDocument.FindFlag(0)
            if options.get("case_sensitive", False):
                flags |= QTextDocument.FindFlag.FindCaseSensitively
            if options.get("whole_word", False):
                flags |= QTextDocument.FindFlag.FindWholeWords

            while True:
                if options.get("regex", False):
                    # 正则表达式替换
                    regex = QRegularExpression(search_text)
                    if not options.get("case_sensitive", False):
                        regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)

                    found_cursor = self._text_editor.document().find(regex, cursor, flags)

                    if found_cursor.isNull():
                        break

                    # 处理正则表达式捕获组
                    match = regex.match(found_cursor.selectedText())
                    if match.hasMatch():
                        actual_replace_text = replace_text
                        # 替换捕获组引用 \1, \2, etc.
                        for i in range(match.lastCapturedIndex() + 1):
                            actual_replace_text = actual_replace_text.replace(f"\\{i}", match.captured(i))
                        found_cursor.insertText(actual_replace_text)
                    else:
                        found_cursor.insertText(replace_text)
                else:
                    # 普通文本替换
                    found_cursor = self._text_editor.document().find(search_text, cursor, flags)

                    if found_cursor.isNull():
                        break

                    found_cursor.insertText(replace_text)

                cursor = found_cursor
                count += 1

                # 防止无限循环
                if count > 10000:
                    from PyQt6.QtWidgets import QMessageBox
                    if QMessageBox.question(self, "替换",
                                          f"已替换 {count} 处，是否继续？") != QMessageBox.StandardButton.Yes:
                        break

        finally:
            cursor.endEditBlock()

        return count

    def _replace_current_selection(self, search_text: str, replace_text: str, options: dict):
        """替换当前选中的文本"""
        cursor = self._text_editor.textCursor()

        if cursor.hasSelection():
            selected_text = cursor.selectedText()

            # 检查选中文本是否匹配搜索条件
            if self._text_matches_search(selected_text, search_text, options):
                if options.get("regex", False):
                    # 正则表达式替换
                    regex = QRegularExpression(search_text)
                    match = regex.match(selected_text)
                    if match.hasMatch():
                        actual_replace_text = replace_text
                        # 替换捕获组引用
                        for i in range(match.lastCapturedIndex() + 1):
                            actual_replace_text = actual_replace_text.replace(f"\\{i}", match.captured(i))
                        cursor.insertText(actual_replace_text)
                    else:
                        cursor.insertText(replace_text)
                else:
                    cursor.insertText(replace_text)

        # 查找下一个
        self._find_next()

    def _text_matches_search(self, text: str, search_text: str, options: dict) -> bool:
        """检查文本是否匹配搜索条件"""
        if options.get("regex", False):
            try:
                regex = QRegularExpression(search_text)
                if not options.get("case_sensitive", False):
                    regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
                return regex.match(text).hasMatch()
            except:
                return False
        else:
            if options.get("case_sensitive", False):
                return text == search_text
            else:
                return text.lower() == search_text.lower()
    
    def _find_in_range(self, search_text: str, cursor: QTextCursor, flags: QTextDocument.FindFlag,
                      options: dict, start_pos: int, end_pos: int) -> QTextCursor:
        """在指定范围内搜索"""
        if options.get("regex", False):
            # 正则表达式搜索
            regex = QRegularExpression(search_text)
            if not options.get("case_sensitive", False):
                regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)

            return self._text_editor.document().find(regex, cursor, flags)
        else:
            # 普通文本搜索
            return self._text_editor.document().find(search_text, cursor, flags)

    def _try_wrap_around_search(self, search_text: str, options: dict, original_position: int) -> bool:
        """尝试循环搜索"""
        cursor = self._text_editor.textCursor()

        # 根据搜索方向决定起始位置
        if options.get("forward", True):
            # 向前搜索：从文档开始
            cursor.movePosition(QTextCursor.MoveOperation.Start)
        else:
            # 向后搜索：从文档末尾
            cursor.movePosition(QTextCursor.MoveOperation.End)

        # 构建搜索标志
        flags = QTextDocument.FindFlag(0)
        if options.get("case_sensitive", False):
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if options.get("whole_word", False):
            flags |= QTextDocument.FindFlag.FindWholeWords
        if not options.get("forward", True):
            flags |= QTextDocument.FindFlag.FindBackward

        # 执行循环搜索
        found_cursor = self._find_in_range(search_text, cursor, flags, options, 0,
                                         self._text_editor.document().characterCount())

        if not found_cursor.isNull():
            # 检查是否回到了原始位置（避免无限循环）
            if found_cursor.position() != original_position:
                self._text_editor.setTextCursor(found_cursor)
                self._text_editor.ensureCursorVisible()
                self._show_wrap_around_message(options.get("forward", True))
                return True

        return False

    def _add_to_search_history(self, search_text: str):
        """添加到搜索历史"""
        if search_text and search_text not in self._find_history:
            self._find_history.insert(0, search_text)
            # 限制历史记录数量
            if len(self._find_history) > 20:
                self._find_history = self._find_history[:20]

    def _show_not_found_message(self):
        """显示未找到消息"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "查找", "未找到指定的文本。")

    def _show_wrap_around_message(self, forward: bool):
        """显示循环搜索消息"""
        from PyQt6.QtWidgets import QMessageBox
        direction = "末尾" if forward else "开头"
        QMessageBox.information(self, "查找", f"已到达文档{direction}，从{'开头' if forward else '末尾'}继续搜索。")

    def _show_regex_error(self, error_message: str):
        """显示正则表达式错误"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "正则表达式错误", f"正则表达式无效：\n{error_message}")

    def _show_replace_result(self, count: int):
        """显示替换结果"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "替换", f"已替换 {count} 处。")

    def _highlight_all_matches(self, search_text: str, options: dict):
        """高亮显示所有匹配项"""
        if not self._text_editor or not search_text:
            return

        # 清除之前的高亮
        self._clear_highlights()

        try:
            # 验证正则表达式
            if options.get("regex", False):
                regex = QRegularExpression(search_text)
                if not regex.isValid():
                    return
        except:
            return

        # 构建搜索标志
        flags = QTextDocument.FindFlag(0)
        if options.get("case_sensitive", False):
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if options.get("whole_word", False):
            flags |= QTextDocument.FindFlag.FindWholeWords

        # 搜索所有匹配项
        cursor = QTextCursor(self._text_editor.document())
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        while True:
            if options.get("regex", False):
                regex = QRegularExpression(search_text)
                if not options.get("case_sensitive", False):
                    regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
                found_cursor = self._text_editor.document().find(regex, cursor, flags)
            else:
                found_cursor = self._text_editor.document().find(search_text, cursor, flags)

            if found_cursor.isNull():
                break

            # 添加高亮
            self._add_highlight(found_cursor)
            cursor = found_cursor

    def _add_highlight(self, cursor: QTextCursor):
        """添加高亮"""
        # 创建额外选择来高亮文本
        extra_selection = QTextEdit.ExtraSelection()
        extra_selection.cursor = cursor
        extra_selection.format = self._highlight_format

        self._current_highlights.append(extra_selection)

        # 应用高亮
        self._apply_highlights()

    def _apply_highlights(self):
        """应用所有高亮"""
        if self._text_editor:
            self._text_editor.setExtraSelections(self._current_highlights)

    def _clear_highlights(self):
        """清除所有高亮"""
        self._current_highlights.clear()
        if self._text_editor:
            self._text_editor.setExtraSelections([])

    def closeEvent(self, event):
        """对话框关闭时清除高亮"""
        self._clear_highlights()
        super().closeEvent(event)

    def hideEvent(self, event):
        """对话框隐藏时清除高亮"""
        self._clear_highlights()
        super().hideEvent(event)
    
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
