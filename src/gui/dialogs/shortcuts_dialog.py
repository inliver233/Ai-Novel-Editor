"""
快捷键帮助对话框
显示应用程序的所有快捷键和操作说明
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QTabWidget, QWidget, QHeaderView, QLineEdit, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class ShortcutsDialog(QDialog):
    """快捷键帮助对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._init_ui()
        self._populate_shortcuts()
        
        # 设置对话框属性
        self.setModal(True)
        self.setWindowTitle("快捷键")
        self.resize(600, 500)
        
        logger.debug("Shortcuts dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索:")
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入快捷键或功能名称...")
        self._search_edit.textChanged.connect(self._filter_shortcuts)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self._search_edit)
        layout.addLayout(search_layout)
        
        # 标签页
        self._tabs = QTabWidget()
        
        # 文件操作标签页
        file_tab = self._create_shortcuts_tab("文件操作")
        self._tabs.addTab(file_tab, "文件")
        
        # 编辑操作标签页
        edit_tab = self._create_shortcuts_tab("编辑操作")
        self._tabs.addTab(edit_tab, "编辑")
        
        # 视图操作标签页
        view_tab = self._create_shortcuts_tab("视图操作")
        self._tabs.addTab(view_tab, "视图")
        
        # AI功能标签页
        ai_tab = self._create_shortcuts_tab("AI功能")
        self._tabs.addTab(ai_tab, "AI")
        
        # 导航操作标签页
        nav_tab = self._create_shortcuts_tab("导航操作")
        self._tabs.addTab(nav_tab, "导航")
        
        layout.addWidget(self._tabs)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_shortcuts_tab(self, category: str) -> QWidget:
        """创建快捷键标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 创建表格
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["功能", "快捷键"])
        
        # 设置表格属性
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # 设置列宽
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        # 保存表格引用
        setattr(widget, 'table', table)
        setattr(widget, 'category', category)
        
        layout.addWidget(table)
        
        return widget
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        layout.addStretch()
        
        # 打印按钮
        print_btn = QPushButton("打印")
        print_btn.clicked.connect(self._print_shortcuts)
        layout.addWidget(print_btn)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        layout.addWidget(close_btn)
        
        return layout
    
    def _populate_shortcuts(self):
        """填充快捷键数据"""
        shortcuts_data = {
            "文件操作": [
                ("新建项目", "Ctrl+Shift+N"),
                ("打开项目", "Ctrl+O"),
                ("新建文档", "Ctrl+N"),
                ("保存文档", "Ctrl+S"),
                ("另存为", "Ctrl+Shift+S"),
                ("关闭文档", "Ctrl+W"),
                ("退出程序", "Ctrl+Q"),
            ],
            "编辑操作": [
                ("撤销", "Ctrl+Z"),
                ("重做", "Ctrl+Y"),
                ("剪切", "Ctrl+X"),
                ("复制", "Ctrl+C"),
                ("粘贴", "Ctrl+V"),
                ("全选", "Ctrl+A"),
                ("查找", "Ctrl+F"),
                ("替换", "Ctrl+H"),
                ("查找下一个", "F3"),
                ("查找上一个", "Shift+F3"),
                ("智能补全", "Tab"),
                ("AI智能补全", "Ctrl+Space"),
                ("转到行", "Ctrl+G"),
                ("删除行", "Ctrl+Shift+K"),
                ("复制行", "Ctrl+Shift+D"),
                ("上移行", "Alt+Up"),
                ("下移行", "Alt+Down"),
            ],
            "视图操作": [
                ("全屏模式", "F11"),
                ("显示/隐藏项目面板", "Ctrl+1"),
                ("显示/隐藏概念面板", "Ctrl+2"),
                ("放大字体", "Ctrl+="),
                ("缩小字体", "Ctrl+-"),
                ("重置字体大小", "Ctrl+0"),
                ("切换主题", "Ctrl+T"),
                ("显示/隐藏状态栏", "Ctrl+/"),
            ],
            "AI功能": [
                ("AI智能补全", "Ctrl+Space"),
                ("AI续写", "Ctrl+Shift+Space"),
                ("AI润色", "Ctrl+Shift+R"),
                ("概念检测", "Ctrl+Shift+D"),
                ("AI配置", "Ctrl+Shift+A"),
                ("显示AI建议", "Ctrl+Shift+I"),
            ],
            "导航操作": [
                ("转到文件", "Ctrl+P"),
                ("转到符号", "Ctrl+Shift+O"),
                ("转到定义", "F12"),
                ("返回", "Alt+Left"),
                ("前进", "Alt+Right"),
                ("书签切换", "Ctrl+F2"),
                ("下一个书签", "F2"),
                ("上一个书签", "Shift+F2"),
                ("转到匹配的括号", "Ctrl+]"),
            ]
        }
        
        # 填充各个标签页的数据
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            category = getattr(widget, 'category', '')
            table = getattr(widget, 'table', None)
            
            if table and category in shortcuts_data:
                shortcuts = shortcuts_data[category]
                table.setRowCount(len(shortcuts))
                
                for row, (function, shortcut) in enumerate(shortcuts):
                    # 功能名称
                    function_item = QTableWidgetItem(function)
                    function_item.setFont(QFont("", 10))
                    table.setItem(row, 0, function_item)
                    
                    # 快捷键
                    shortcut_item = QTableWidgetItem(shortcut)
                    shortcut_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                    shortcut_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, 1, shortcut_item)
    
    def _filter_shortcuts(self, text: str):
        """过滤快捷键"""
        search_text = text.lower()
        
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            table = getattr(widget, 'table', None)
            
            if table:
                for row in range(table.rowCount()):
                    function_item = table.item(row, 0)
                    shortcut_item = table.item(row, 1)
                    
                    if function_item and shortcut_item:
                        function_text = function_item.text().lower()
                        shortcut_text = shortcut_item.text().lower()
                        
                        # 检查是否匹配
                        visible = (search_text in function_text or 
                                 search_text in shortcut_text or 
                                 not search_text)
                        
                        table.setRowHidden(row, not visible)
    
    def _print_shortcuts(self):
        """打印快捷键"""
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QPainter, QTextDocument
        
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            # 生成HTML内容
            html_content = self._generate_html_content()
            
            # 创建文档并打印
            document = QTextDocument()
            document.setHtml(html_content)
            document.print(printer)
    
    def _generate_html_content(self) -> str:
        """生成HTML内容"""
        html = """
        <html>
        <head>
            <title>快捷键参考</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; text-align: center; }
                h2 { color: #666; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
                table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f5f5f5; font-weight: bold; }
                .shortcut { font-family: Consolas, monospace; font-weight: bold; text-align: center; }
            </style>
        </head>
        <body>
            <h1>AI Novel Editor 快捷键参考</h1>
        """
        
        # 添加各个分类的快捷键
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            category = getattr(widget, 'category', '')
            table = getattr(widget, 'table', None)
            tab_text = self._tabs.tabText(i)
            
            if table and category:
                html += f"<h2>{tab_text}</h2>"
                html += "<table>"
                html += "<tr><th>功能</th><th>快捷键</th></tr>"
                
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        function_item = table.item(row, 0)
                        shortcut_item = table.item(row, 1)
                        
                        if function_item and shortcut_item:
                            function = function_item.text()
                            shortcut = shortcut_item.text()
                            html += f"<tr><td>{function}</td><td class='shortcut'>{shortcut}</td></tr>"
                
                html += "</table>"
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def add_custom_shortcut(self, category: str, function: str, shortcut: str):
        """添加自定义快捷键"""
        # 找到对应的标签页
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            widget_category = getattr(widget, 'category', '')
            
            if widget_category == category:
                table = getattr(widget, 'table', None)
                if table:
                    # 添加新行
                    row = table.rowCount()
                    table.setRowCount(row + 1)
                    
                    # 添加数据
                    function_item = QTableWidgetItem(function)
                    function_item.setFont(QFont("", 10))
                    table.setItem(row, 0, function_item)
                    
                    shortcut_item = QTableWidgetItem(shortcut)
                    shortcut_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                    shortcut_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, 1, shortcut_item)
                    
                    break
