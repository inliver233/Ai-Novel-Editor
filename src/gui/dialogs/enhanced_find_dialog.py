"""
增强版查找替换对话框
支持当前文档搜索和全局项目搜索
"""

import logging
from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QCheckBox, QTabWidget, QWidget, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, QLabel,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QTextCursor, QTextDocument, QFont

logger = logging.getLogger(__name__)


class GlobalSearchWorker(QThread):
    """全局搜索工作线程"""
    
    searchResult = pyqtSignal(str, str, int, str)  # 文档ID, 文档标题, 行号, 匹配行内容
    searchFinished = pyqtSignal()
    
    def __init__(self, project_manager, search_text: str, options: dict):
        super().__init__()
        self.project_manager = project_manager
        self.search_text = search_text
        self.options = options
    
    def run(self):
        """执行全局搜索"""
        print(f"🔍 全局搜索线程开始运行")

        if not self.project_manager:
            print("❌ 项目管理器为空，搜索结束")
            self.searchFinished.emit()
            return

        try:
            # 获取所有文档
            print("📚 获取所有文档...")

            # 检查项目管理器是否有当前项目
            if not hasattr(self.project_manager, '_current_project') or not self.project_manager._current_project:
                print("❌ 没有当前项目")
                return

            documents = self.project_manager._current_project.documents
            print(f"📚 找到 {len(documents)} 个文档")

            for doc_id, document in documents.items():
                print(f"🔍 搜索文档: {doc_id} - {document.name}")
                content = document.content
                if content:
                    print(f"📄 文档内容长度: {len(content)}")
                    self._search_in_content(doc_id, document.name, content)
                else:
                    print(f"❌ 文档内容为空: {doc_id}")

        except Exception as e:
            print(f"❌ 全局搜索异常: {e}")
            logger.error(f"Global search error: {e}")
        finally:
            print("🏁 全局搜索完成")
            self.searchFinished.emit()
    
    def _search_in_content(self, doc_id: str, doc_title: str, content: str):
        """在内容中搜索"""
        lines = content.split('\n')
        print(f"🔍 在文档 {doc_title} 中搜索，共 {len(lines)} 行")

        for line_num, line in enumerate(lines, 1):
            if self._line_matches(line):
                print(f"✅ 找到匹配项: {doc_title} 第{line_num}行 - {line.strip()}")
                self.searchResult.emit(doc_id, doc_title, line_num, line.strip())
            else:
                print(f"❌ 第{line_num}行不匹配: {repr(line[:50])}")
    
    def _line_matches(self, line: str) -> bool:
        """检查行是否匹配搜索条件"""
        search_text = self.search_text
        
        if not self.options.get("case_sensitive", False):
            line = line.lower()
            search_text = search_text.lower()
        
        if self.options.get("regex", False):
            try:
                regex = QRegularExpression(self.search_text)
                if not self.options.get("case_sensitive", False):
                    regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
                return regex.match(line).hasMatch()
            except:
                return False
        elif self.options.get("whole_word", False):
            import re
            pattern = r'\b' + re.escape(search_text) + r'\b'
            flags = 0 if self.options.get("case_sensitive", False) else re.IGNORECASE
            return bool(re.search(pattern, line, flags))
        else:
            return search_text in line


class EnhancedFindDialog(QDialog):
    """增强版查找替换对话框"""
    
    documentRequested = pyqtSignal(str)  # 请求打开文档
    
    def __init__(self, parent=None, text_editor=None, project_manager=None):
        super().__init__(parent)
        
        self._text_editor = text_editor
        self._project_manager = project_manager
        self._search_worker = None
        
        self._init_ui()
        self._setup_connections()
        
        # 设置对话框属性
        self.setModal(False)
        self.setWindowTitle("查找和替换")
        self.resize(800, 600)
        
        logger.debug("Enhanced find dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 主分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：搜索控制面板
        left_panel = self._create_search_panel()
        main_splitter.addWidget(left_panel)
        
        # 右侧：搜索结果面板
        right_panel = self._create_results_panel()
        main_splitter.addWidget(right_panel)
        
        # 设置分割比例
        main_splitter.setSizes([400, 400])
        
        layout.addWidget(main_splitter)
        
        # 底部按钮
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_search_panel(self) -> QWidget:
        """创建搜索控制面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 搜索输入
        search_group = QGroupBox("搜索")
        search_layout = QFormLayout(search_group)
        
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入要查找的文本...")
        search_layout.addRow("查找:", self._search_edit)
        
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("输入替换文本...")
        search_layout.addRow("替换为:", self._replace_edit)
        
        layout.addWidget(search_group)
        
        # 搜索选项
        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout(options_group)
        
        self._case_sensitive_check = QCheckBox("区分大小写")
        options_layout.addWidget(self._case_sensitive_check)
        
        self._whole_word_check = QCheckBox("全字匹配")
        options_layout.addWidget(self._whole_word_check)
        
        self._regex_check = QCheckBox("正则表达式")
        options_layout.addWidget(self._regex_check)
        
        layout.addWidget(options_group)
        
        # 搜索范围 - 使用单选按钮组
        scope_group = QGroupBox("搜索范围")
        scope_layout = QVBoxLayout(scope_group)

        from PyQt6.QtWidgets import QRadioButton, QButtonGroup

        # 创建按钮组确保互斥
        self._scope_button_group = QButtonGroup()

        self._current_doc_radio = QRadioButton("当前文档")
        self._current_doc_radio.setChecked(True)
        self._scope_button_group.addButton(self._current_doc_radio, 0)
        scope_layout.addWidget(self._current_doc_radio)

        self._global_search_radio = QRadioButton("整个项目")
        self._scope_button_group.addButton(self._global_search_radio, 1)
        scope_layout.addWidget(self._global_search_radio)
        
        layout.addWidget(scope_group)
        
        # 操作按钮
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout(action_group)
        
        self._find_next_btn = QPushButton("查找下一个")
        action_layout.addWidget(self._find_next_btn)
        
        self._find_prev_btn = QPushButton("查找上一个")
        action_layout.addWidget(self._find_prev_btn)
        
        self._replace_btn = QPushButton("替换")
        action_layout.addWidget(self._replace_btn)
        
        self._replace_all_btn = QPushButton("全部替换")
        action_layout.addWidget(self._replace_all_btn)
        
        self._global_search_btn = QPushButton("全局搜索")
        action_layout.addWidget(self._global_search_btn)
        
        layout.addWidget(action_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_results_panel(self) -> QWidget:
        """创建搜索结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 结果标题
        self._results_label = QLabel("搜索结果")
        layout.addWidget(self._results_label)
        
        # 结果树
        self._results_tree = QTreeWidget()
        self._results_tree.setHeaderLabels(["文档", "行号", "内容"])
        self._results_tree.setColumnWidth(0, 150)
        self._results_tree.setColumnWidth(1, 50)
        layout.addWidget(self._results_tree)
        
        return widget
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        
        layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return layout
    
    def _setup_connections(self):
        """设置信号连接"""
        # 搜索按钮
        self._find_next_btn.clicked.connect(self._find_next)
        self._find_prev_btn.clicked.connect(self._find_previous)
        self._replace_btn.clicked.connect(self._replace_current)
        self._replace_all_btn.clicked.connect(self._replace_all)
        self._global_search_btn.clicked.connect(self._start_global_search)
        
        # 输入框回车键
        self._search_edit.returnPressed.connect(self._find_next)
        self._replace_edit.returnPressed.connect(self._replace_current)
        
        # 结果树双击
        self._results_tree.itemDoubleClicked.connect(self._on_result_double_clicked)
        
        # 搜索范围变化
        self._current_doc_radio.toggled.connect(self._on_scope_changed)
        self._global_search_radio.toggled.connect(self._on_scope_changed)
    
    def _on_scope_changed(self):
        """搜索范围变化处理"""
        is_global = self._global_search_radio.isChecked()
        
        # 更新按钮状态
        self._find_next_btn.setEnabled(not is_global or self._text_editor is not None)
        self._find_prev_btn.setEnabled(not is_global or self._text_editor is not None)
        self._replace_btn.setEnabled(not is_global or self._text_editor is not None)
        self._replace_all_btn.setEnabled(not is_global or self._text_editor is not None)
    
    def _get_search_options(self) -> dict:
        """获取搜索选项"""
        return {
            "case_sensitive": self._case_sensitive_check.isChecked(),
            "whole_word": self._whole_word_check.isChecked(),
            "regex": self._regex_check.isChecked(),
        }
    
    def _find_next(self):
        """查找下一个"""
        search_text = self._search_edit.text()
        if not search_text:
            print("❌ 搜索文本为空")
            return

        if self._global_search_radio.isChecked():
            print("🌍 执行全局搜索")
            self._start_global_search()
        else:
            print("📄 执行当前文档搜索")
            self._find_in_current_document(True)
    
    def _find_previous(self):
        """查找上一个"""
        if not self._global_search_radio.isChecked():
            self._find_in_current_document(False)
    
    def _find_in_current_document(self, forward: bool):
        """在当前文档中查找"""
        search_text = self._search_edit.text()
        print(f"🔍 在当前文档中查找: '{search_text}', 向前: {forward}")

        if not search_text:
            print("❌ 搜索文本为空")
            return

        if not self._text_editor:
            print("❌ 文本编辑器为空")
            return

        options = self._get_search_options()
        print(f"🔧 搜索选项: {options}")

        # 直接实现搜索逻辑，不依赖简化版对话框
        self._perform_current_document_search(search_text, options, forward)

    def _perform_current_document_search(self, search_text: str, options: dict, forward: bool):
        """在当前文档中执行搜索"""
        print(f"🔍 执行当前文档搜索: '{search_text}', 向前: {forward}")

        # 获取文档内容进行调试
        document_content = self._text_editor.toPlainText()
        print(f"📄 文档内容长度: {len(document_content)}")
        print(f"📄 文档内容预览: {repr(document_content[:100])}")

        # 获取当前光标位置
        cursor = self._text_editor.textCursor()
        original_position = cursor.position()
        print(f"📍 当前光标位置: {original_position}")

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
            if self._try_wrap_around_search_current(search_text, options, forward, original_position):
                print("✅ 循环搜索找到匹配项")
            else:
                print("❌ 未找到匹配项")
                self._show_message("未找到匹配项")

    def _try_wrap_around_search_current(self, search_text: str, options: dict, forward: bool, original_position: int) -> bool:
        """尝试循环搜索当前文档"""
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
            print(f"🔄 循环搜索找到匹配项，位置: {found_start}, 原始位置: {original_position}")
            if found_start != original_position:
                print(f"🔄 循环搜索成功，匹配位置: {found_cursor.selectionStart()}-{found_cursor.selectionEnd()}")
                self._text_editor.setTextCursor(found_cursor)
                self._text_editor.ensureCursorVisible()
                return True
            else:
                print(f"🔄 循环搜索回到原始位置，停止搜索")
        else:
            print(f"🔄 循环搜索未找到匹配项")

        return False

    def _show_message(self, message: str):
        """显示消息"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "查找替换", message)
    
    def _replace_current(self):
        """替换当前"""
        # 实现替换逻辑
        pass
    
    def _replace_all(self):
        """全部替换"""
        # 实现全部替换逻辑
        pass
    
    def _start_global_search(self):
        """开始全局搜索"""
        search_text = self._search_edit.text()
        print(f"🌍 开始全局搜索: '{search_text}'")

        if not search_text:
            print("❌ 搜索文本为空")
            return

        if not self._project_manager:
            print("❌ 项目管理器为空")
            return

        # 清空结果
        self._results_tree.clear()
        self._results_label.setText("搜索中...")
        print("🔄 清空搜索结果，开始搜索...")

        # 启动搜索线程
        options = self._get_search_options()
        print(f"🔧 全局搜索选项: {options}")

        self._search_worker = GlobalSearchWorker(self._project_manager, search_text, options)
        self._search_worker.searchResult.connect(self._add_search_result)
        self._search_worker.searchFinished.connect(self._on_search_finished)
        self._search_worker.start()
        print("🚀 全局搜索线程已启动")
    
    @pyqtSlot(str, str, int, str)
    def _add_search_result(self, doc_id: str, doc_title: str, line_num: int, line_content: str):
        """添加搜索结果"""
        item = QTreeWidgetItem([doc_title, str(line_num), line_content])
        item.setData(0, Qt.ItemDataRole.UserRole, doc_id)
        item.setData(1, Qt.ItemDataRole.UserRole, line_num)  # 存储行号
        self._results_tree.addTopLevelItem(item)
        print(f"➕ 添加搜索结果: {doc_title} 第{line_num}行")
    
    @pyqtSlot()
    def _on_search_finished(self):
        """搜索完成"""
        count = self._results_tree.topLevelItemCount()
        self._results_label.setText(f"搜索结果 ({count} 项)")
    
    def _on_result_double_clicked(self, item: QTreeWidgetItem, column: int):
        """结果项双击处理"""
        doc_id = item.data(0, Qt.ItemDataRole.UserRole)
        line_num = item.data(1, Qt.ItemDataRole.UserRole)
        print(f"🖱️ 双击搜索结果: 文档ID={doc_id}, 行号={line_num}")

        if doc_id:
            # 先发出文档请求信号
            self.documentRequested.emit(doc_id)
            print(f"📄 请求打开文档: {doc_id}")
            
            # 延迟一下，等文档加载完成后再跳转到指定行
            if line_num:
                QTimer.singleShot(100, lambda: self._jump_to_line(line_num))
    
    def _jump_to_line(self, line_num: int):
        """跳转到指定行"""
        if self._text_editor:
            # 获取文本编辑器的文档
            document = self._text_editor.document()
            
            # 获取指定行的文本块
            block = document.findBlockByLineNumber(line_num - 1)  # 行号从0开始
            
            if block.isValid():
                # 创建一个光标并定位到该行
                cursor = QTextCursor(block)
                self._text_editor.setTextCursor(cursor)
                self._text_editor.ensureCursorVisible()
                
                # 高亮该行（可选）
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                self._text_editor.setTextCursor(cursor)
                
                print(f"✅ 跳转到第 {line_num} 行")
            else:
                print(f"❌ 无法跳转到第 {line_num} 行")
    
    def set_search_text(self, text: str):
        """设置搜索文本"""
        self._search_edit.setText(text)
    
    def show_and_focus(self):
        """显示并聚焦"""
        self.show()
        self.raise_()
        self.activateWindow()
        self._search_edit.setFocus()
        self._search_edit.selectAll()
    
    def update_text_editor(self, text_editor):
        """更新文本编辑器引用"""
        self._text_editor = text_editor
        self._on_scope_changed()  # 更新按钮状态
