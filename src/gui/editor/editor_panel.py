"""
编辑器面板
包装智能文本编辑器，提供完整的编辑环境
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, 
    QPushButton, QToolButton, QSplitter, QTabWidget,
    QProgressBar, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon

from .text_editor import IntelligentTextEditor
from core.config import Config
from core.shared import Shared


logger = logging.getLogger(__name__)


class EditorPanel(QWidget):
    """编辑器面板"""
    
    # 信号定义
    documentModified = pyqtSignal(str, bool)  # 文档修改信号 (文档ID, 是否修改)
    documentSaved = pyqtSignal(str)  # 文档保存信号
    completionRequested = pyqtSignal(str, int, str)  # 补全请求信号 (文本, 位置, 文档ID)
    conceptsDetected = pyqtSignal(str, list)  # 概念检测信号 (文档ID, 概念列表)
    textStatisticsChanged = pyqtSignal(str)  # 文本统计变化信号 (文本内容)
    cursorPositionChanged = pyqtSignal(int, int)  # 光标位置变化信号 (行, 列)
    
    def __init__(self, config: Config, shared: Shared, parent=None):
        super().__init__(parent)
        
        self._config = config
        self._shared = shared
        
        # 当前文档状态
        self._current_document_id: Optional[str] = None
        self._document_tabs: Dict[str, IntelligentTextEditor] = {}
        
        # 初始化UI
        self._init_ui()
        self._init_signals()

        logger.info("Editor panel initialized")

        # 连接默认编辑器的信号（在UI初始化完成后）
        if "default_doc" in self._document_tabs:
            self._connect_editor_signals(self._document_tabs["default_doc"])

        # 触发初始统计更新（在UI初始化完成后）
        self._trigger_initial_update()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题栏
        title_frame = self._create_title_frame()
        layout.addWidget(title_frame)
        
        # 编辑器标签页
        self._editor_tabs = self._create_editor_tabs()
        layout.addWidget(self._editor_tabs)
        
        # 状态栏
        status_frame = self._create_status_frame()
        layout.addWidget(status_frame)
        
        # 设置样式
        # Style is now managed globally by the theme QSS files.
        self.setStyleSheet("""
            EditorPanel {
                border-radius: 6px;
            }
        """)
    
    def _create_title_frame(self) -> QFrame:
        """创建标题栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # 标题
        title_label = QLabel("文档编辑器")
        # Style is now managed globally by the theme QSS files.
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 4px;
            }
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 工具按钮
        self._create_tool_buttons(layout)
        
        return frame
    
    def _create_tool_buttons(self, layout: QHBoxLayout):
        """创建工具按钮"""
        # AI助手按钮
        ai_btn = QToolButton()
        ai_btn.setText("AI")
        ai_btn.setToolTip("AI助手")
        ai_btn.setFixedSize(32, 24)
        ai_btn.clicked.connect(self._on_ai_assistant)
        layout.addWidget(ai_btn)

        # 保存按钮
        save_btn = QToolButton()
        save_btn.setText("保存")
        save_btn.setToolTip("保存文档 (Ctrl+S)")
        save_btn.setFixedSize(40, 24)
        save_btn.clicked.connect(self._on_save_document)
        layout.addWidget(save_btn)
        
        # 设置按钮样式
        # Style is now managed globally by the theme QSS files.
        pass
    
    def _create_editor_tabs(self) -> QTabWidget:
        """创建编辑器标签页"""
        tabs = QTabWidget()
        tabs.setTabsClosable(True)
        tabs.setMovable(True)
        tabs.setDocumentMode(True)
        
        # 创建默认编辑器
        self._create_default_editor(tabs)

        # 连接标签页信号 (在创建默认编辑器后连接，避免初始化时触发信号)
        tabs.tabCloseRequested.connect(self._close_document_tab)
        tabs.currentChanged.connect(self._on_tab_changed)
        
        # 设置标签页样式
        # Style is now managed globally by the theme QSS files.
        tabs.setStyleSheet("""
            QTabBar::tab {
                font-size: 13px;
                min-width: 100px;
            }
        """)
        
        return tabs
    
    def _create_default_editor(self, tabs: QTabWidget):
        """创建默认编辑器"""
        editor = IntelligentTextEditor(self._config, self._shared)
        
        # 如果已有Codex组件，立即设置
        if hasattr(self, '_codex_manager') and hasattr(self, '_reference_detector'):
            editor.set_codex_components(self._codex_manager, self._reference_detector)

        # 暂不连接编辑器信号，等UI初始化完成后再连接
        
        # 添加到标签页
        tab_index = tabs.addTab(editor, "新建文档")
        tabs.setCurrentIndex(tab_index)
        
        # 设置示例内容
        sample_content = """# 我的小说

## 第一章：开端

@char: 李明
@location: 咖啡厅
@time: 2024年春天

李明坐在咖啡厅的角落里，手中握着一杯热腾腾的拿铁。窗外的阳光透过百叶窗洒在桌面上，形成斑驳的光影。

他正在等待一个重要的人...

% 这里是作者注释：需要描述女主角的出场
% TODO: 添加更多环境描写

"""
        editor.set_document_content(sample_content, "default_doc")
        
        # 记录文档
        self._document_tabs["default_doc"] = editor
        self._current_document_id = "default_doc"
    
    def _connect_editor_signals(self, editor: IntelligentTextEditor):
        """连接编辑器信号"""
        editor.textModified.connect(self._on_text_modified)
        editor.cursorPositionChanged.connect(self._on_cursor_position_changed)
        editor.completionRequested.connect(self._on_completion_requested)
        editor.conceptDetected.connect(self._on_concepts_detected)
        editor.autoSaveTriggered.connect(self._on_auto_save)
    
    def _create_status_frame(self) -> QFrame:
        """创建状态栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        frame.setMaximumHeight(30)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # 光标位置
        self._cursor_label = QLabel("行: 1, 列: 1")
        layout.addWidget(self._cursor_label)
        
        layout.addStretch()
        
        # 字数统计
        self._word_count_label = QLabel("字数: 0")
        layout.addWidget(self._word_count_label)
        
        # 修改状态
        self._modified_label = QLabel("")
        layout.addWidget(self._modified_label)

        # 补全状态指示器
        current_editor = self.get_current_editor()
        if current_editor and hasattr(current_editor, '_status_indicator'):
            layout.addWidget(current_editor._status_indicator)
        
        # 设置样式
        # Style is now managed globally by the theme QSS files.
        frame.setStyleSheet("""
            QFrame {
                border-top: 1px solid #555555;
                border-radius: 0px;
            }
            QLabel {
                font-size: 12px;
                padding: 2px 8px;
            }
        """)
        
        return frame
    
    def _init_signals(self):
        """初始化信号连接"""
        # 连接共享数据信号
        self._shared.documentChanged.connect(self._on_shared_document_changed)

    def _trigger_initial_update(self):
        """触发初始统计更新"""
        if (self._current_document_id and
            self._current_document_id in self._document_tabs and
            hasattr(self, '_cursor_label') and
            hasattr(self, '_word_count_label')):

            editor = self._document_tabs[self._current_document_id]
            text = editor.toPlainText()

            # 直接更新UI组件，不发出信号避免递归
            word_count = self._calculate_word_count(text)
            self._word_count_label.setText(f"字数: {word_count}")

            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            column = cursor.columnNumber()  # 修复列数多1的问题
            self._cursor_label.setText(f"行: {line}, 列: {column}")

            # 发出信号给主窗口
            self.textStatisticsChanged.emit(text)
            self.cursorPositionChanged.emit(line, column)

    def _calculate_word_count(self, text: str) -> int:
        """计算字数（中文友好）"""
        if not text:
            return 0

        import re

        # 计算中文字符数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))

        # 计算英文单词数
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))

        # 计算数字
        numbers = len(re.findall(r'\b\d+\b', text))

        # 总字数 = 中文字符数 + 英文单词数 + 数字个数
        return chinese_chars + english_words + numbers

    @pyqtSlot(str)
    def _on_text_modified(self, text: str):
        """文本修改处理"""
        if self._current_document_id:
            # 更新字数统计（使用中文友好算法）
            word_count = self._calculate_word_count(text)
            self._word_count_label.setText(f"字数: {word_count}")

            # 更新修改状态
            self._modified_label.setText("● 已修改")
            # Color should be handled by a more robust state/theme system
            # For now, we use a slightly less alarming color that might fit a dark theme better
            self._modified_label.setStyleSheet("QLabel { color: #f08080; }")

            # 发出文本统计变化信号
            self.textStatisticsChanged.emit(text)

            # 发出文档修改信号
            self.documentModified.emit(self._current_document_id, True)
    
    @pyqtSlot(int, int)
    def _on_cursor_position_changed(self, line: int, column: int):
        """光标位置变化处理"""
        logger.debug(f"Editor panel cursor position changed: line={line}, column={column}")
        self._cursor_label.setText(f"行: {line}, 列: {column}")

        # 发出光标位置变化信号
        self.cursorPositionChanged.emit(line, column)
    
    @pyqtSlot(str, int)
    def _on_completion_requested(self, text: str, position: int):
        """补全请求处理"""
        if self._current_document_id:
            self.completionRequested.emit(text, position, self._current_document_id)
    
    @pyqtSlot(list)
    def _on_concepts_detected(self, concepts: list):
        """概念检测处理"""
        if self._current_document_id:
            self.conceptsDetected.emit(self._current_document_id, concepts)
    
    @pyqtSlot(str)
    def _on_auto_save(self, content: str):
        """自动保存处理"""
        if self._current_document_id:
            # 更新修改状态
            self._modified_label.setText("✓ 已保存")
            # Color should be handled by a more robust state/theme system
            # For now, we use a color that fits a dark theme better
            self._modified_label.setStyleSheet("QLabel { color: #98fb98; }")
            
            # 发出保存信号
            self.documentSaved.emit(self._current_document_id)
            self.documentModified.emit(self._current_document_id, False)
    
    @pyqtSlot(int)
    def _close_document_tab(self, index: int):
        """关闭文档标签页"""
        if self._editor_tabs.count() <= 1:
            return  # 至少保留一个标签页
        
        widget = self._editor_tabs.widget(index)
        if widget and isinstance(widget, IntelligentTextEditor):
            # 检查是否有未保存的修改
            if widget.is_modified():
                from PyQt6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, "确认关闭",
                    "文档有未保存的修改，确定要关闭吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # 移除标签页
            self._editor_tabs.removeTab(index)
            
            # 从文档字典中移除
            for doc_id, editor in list(self._document_tabs.items()):
                if editor == widget:
                    del self._document_tabs[doc_id]
                    break
    
    @pyqtSlot(int)
    def _on_tab_changed(self, index: int):
        """标签页切换处理"""
        widget = self._editor_tabs.widget(index)
        if widget and isinstance(widget, IntelligentTextEditor):
            # 查找对应的文档ID
            for doc_id, editor in self._document_tabs.items():
                if editor == widget:
                    self._current_document_id = doc_id
                    self._shared.current_document_id = doc_id

                    # 触发初始统计更新
                    text = editor.toPlainText()
                    self._on_text_modified(text)

                    # 触发光标位置更新
                    cursor = editor.textCursor()
                    line = cursor.blockNumber() + 1
                    column = cursor.columnNumber()  # 修复列数多1的问题
                    self._on_cursor_position_changed(line, column)
                    
                    # 更新状态栏的状态指示器
                    self._update_status_indicator(editor)
                    break
    
    def _update_status_indicator(self, editor: IntelligentTextEditor):
        """更新状态栏的状态指示器"""
        # 在状态栏中查找并更新状态指示器
        status_frame = None
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if widget and hasattr(widget, '_status_indicator'):
                status_frame = widget
                break
        
        if status_frame and hasattr(editor, '_status_indicator') and editor._status_indicator:
            # 移除旧的状态指示器
            status_layout = status_frame.layout()
            for i in range(status_layout.count()):
                item = status_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    # 检查是否是状态指示器组件
                    if hasattr(widget, 'get_current_mode'):
                        status_layout.removeWidget(widget)
                        break
            
            # 添加新的状态指示器
            status_layout.addWidget(editor._status_indicator)
            logger.debug(f"状态指示器已更新为编辑器: {editor}")
    
    @pyqtSlot()
    def _on_ai_assistant(self):
        """AI助手按钮处理"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "AI助手", "AI助手功能待实现")
    
    @pyqtSlot()
    def _on_save_document(self):
        """保存文档按钮处理"""
        current_editor = self.get_current_editor()
        if current_editor:
            current_editor.save_document()
    
    @pyqtSlot(str)
    def _on_shared_document_changed(self, document_id: str):
        """共享文档变化处理"""
        # 切换到指定文档
        self.switch_to_document(document_id)
    
    def get_current_editor(self) -> Optional[IntelligentTextEditor]:
        """获取当前编辑器"""
        current_widget = self._editor_tabs.currentWidget()
        if isinstance(current_widget, IntelligentTextEditor):
            return current_widget
        return None
    
    def set_codex_components(self, codex_manager, reference_detector):
        """设置Codex组件到所有编辑器"""
        self._codex_manager = codex_manager
        self._reference_detector = reference_detector
        
        # 设置到所有现有编辑器
        for editor in self._document_tabs.values():
            if hasattr(editor, 'set_codex_components'):
                editor.set_codex_components(codex_manager, reference_detector)
        
        logger.info(f"Codex components set to {len(self._document_tabs)} editors")
    
    def create_new_document(self, document_id: str, title: str = "新建文档", content: str = "") -> bool:
        """创建新文档"""
        if document_id in self._document_tabs:
            return False  # 文档已存在
        
        # 创建新编辑器
        editor = IntelligentTextEditor(self._config, self._shared)
        self._connect_editor_signals(editor)
        
        # 如果已有Codex组件，立即设置
        if hasattr(self, '_codex_manager') and hasattr(self, '_reference_detector'):
            editor.set_codex_components(self._codex_manager, self._reference_detector)
        
        # 设置内容
        editor.set_document_content(content, document_id)
        
        # 添加到标签页
        tab_index = self._editor_tabs.addTab(editor, title)
        self._editor_tabs.setCurrentIndex(tab_index)
        
        # 记录文档
        self._document_tabs[document_id] = editor
        self._current_document_id = document_id

        # 触发初始统计更新
        text = editor.toPlainText()
        self._on_text_modified(text)

        # 触发光标位置更新
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber()  # 修复列数多1的问题
        self._on_cursor_position_changed(line, column)

        logger.info(f"New document created: {document_id}")
        return True
    
    def switch_to_document(self, document_id: str) -> bool:
        """切换到指定文档"""
        if document_id not in self._document_tabs:
            return False

        editor = self._document_tabs[document_id]

        # 查找标签页索引
        for i in range(self._editor_tabs.count()):
            if self._editor_tabs.widget(i) == editor:
                self._editor_tabs.setCurrentIndex(i)
                self._current_document_id = document_id

                # 触发初始统计更新
                text = editor.toPlainText()
                self._on_text_modified(text)

                # 触发光标位置更新
                cursor = editor.textCursor()
                line = cursor.blockNumber() + 1
                column = cursor.columnNumber()  # 修复列数多1的问题
                self._on_cursor_position_changed(line, column)

                return True
        
        return False
    
    def get_document_content(self, document_id: str = None) -> str:
        """获取文档内容"""
        if document_id is None:
            document_id = self._current_document_id
        
        if document_id and document_id in self._document_tabs:
            return self._document_tabs[document_id].get_document_content()
        
        return ""
    
    def set_document_content(self, document_id: str, content: str):
        """设置文档内容"""
        if document_id in self._document_tabs:
            self._document_tabs[document_id].set_document_content(content, document_id)
