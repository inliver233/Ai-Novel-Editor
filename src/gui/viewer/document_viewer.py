from __future__ import annotations

"""
文档预览器
基于novelWriter的GuiDocViewer设计，实现实时文档预览功能
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QFrame,
    QToolButton, QScrollArea, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, pyqtSlot, QUrl, QThread, QObject
)
from PyQt6.QtGui import (
    QFont, QTextDocument, QTextCursor, QTextCharFormat,
    QColor, QPalette, QDesktopServices, QPixmap
)

from typing import TYPE_CHECKING
from core.metadata_extractor import MetadataExtractor
from gui.themes import ThemeManager, ThemeType

if TYPE_CHECKING:
    from core.config import Config
    from core.shared import Shared
    from core.project import ProjectManager


logger = logging.getLogger(__name__)


class DocumentRenderer(QObject):
    """文档渲染器 - 负责将Markdown和@标记转换为HTML"""
    
    # 渲染完成信号
    renderCompleted = pyqtSignal(str)  # HTML内容
    renderFailed = pyqtSignal(str)     # 错误信息
    
    def __init__(self, theme_manager: ThemeManager = None):
        super().__init__()
        self._metadata_extractor = MetadataExtractor()
        self._theme_manager = theme_manager
    
    def render_document(self, content: str, document_id: str = None) -> str:
        """渲染文档内容为HTML"""
        try:
            # 预处理内容
            processed_content = self._preprocess_content(content)
            
            # 转换为HTML
            html_content = self._convert_to_html(processed_content, document_id)
            
            # 应用样式
            styled_html = self._apply_styles(html_content)
            
            self.renderCompleted.emit(styled_html)
            return styled_html
            
        except Exception as e:
            error_msg = f"文档渲染失败: {str(e)}"
            logger.error(error_msg)
            self.renderFailed.emit(error_msg)
            return self._create_error_html(error_msg)
    
    def _preprocess_content(self, content: str) -> str:
        """预处理文档内容"""
        # 处理@标记
        lines = content.split('\n')
        processed_lines = []
        
        for line in lines:
            # 处理@标记
            if line.strip().startswith('@'):
                processed_lines.append(self._process_metadata_line(line))
            else:
                processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def _process_metadata_line(self, line: str) -> str:
        """处理@标记行"""
        # 使用正则表达式直接解析@标记
        import re

        # 匹配@标记模式
        pattern = r'@(\w+):\s*(.+)'
        match = re.match(pattern, line.strip())

        if match:
            tag_type = match.group(1)
            tag_value = match.group(2).strip()

            if tag_type and tag_value:
                return f'<div class="metadata-tag" data-type="{tag_type}">' \
                       f'<span class="tag-type">@{tag_type}:</span> ' \
                       f'<span class="tag-value">{tag_value}</span></div>'

        return line

    def _get_theme_colors(self) -> dict:
        """获取当前主题的颜色配置"""
        if self._theme_manager:
            return self._theme_manager.get_theme_colors()
        else:
            # 默认深色主题颜色
            return {
                'bg_primary': '#0d1117',
                'bg_secondary': '#161b22',
                'text_primary': '#f0f6fc',
                'text_secondary': '#8b949e',
                'text_tertiary': '#6e7681',
                'border_primary': '#30363d',
                'primary': '#58a6ff',
                'success': '#3fb950',
                'warning': '#d29922',
                'ai_primary': '#a855f7'
            }
    
    def _convert_to_html(self, content: str, document_id: str = None) -> str:
        """转换Markdown内容为HTML"""
        lines = content.split('\n')
        html_lines = []
        in_paragraph = False
        in_code_block = False
        code_block_lines = []
        code_language = ""

        for line in lines:
            stripped = line.strip()

            # 处理代码块
            if stripped.startswith('```'):
                if not in_code_block:
                    # 开始代码块
                    if in_paragraph:
                        html_lines.append('</p>')
                        in_paragraph = False

                    in_code_block = True
                    code_language = stripped[3:].strip()
                    code_block_lines = []
                else:
                    # 结束代码块
                    in_code_block = False
                    code_content = '\n'.join(code_block_lines)
                    # 转义HTML字符
                    code_content = code_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    if code_language:
                        html_lines.append(f'<pre><code class="language-{code_language}">{code_content}</code></pre>')
                    else:
                        html_lines.append(f'<pre><code>{code_content}</code></pre>')
                    code_language = ""
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # 处理标题
            if stripped.startswith('#'):
                if in_paragraph:
                    html_lines.append('</p>')
                    in_paragraph = False

                level = len(stripped) - len(stripped.lstrip('#'))
                title_text = stripped[level:].strip()
                html_lines.append(f'<h{level} class="heading-{level}">{title_text}</h{level}>')

            # 处理元数据标记（已经在预处理中转换）
            elif stripped.startswith('<div class="metadata-tag"'):
                if in_paragraph:
                    html_lines.append('</p>')
                    in_paragraph = False
                html_lines.append(line)

            # 处理空行
            elif not stripped:
                if in_paragraph:
                    html_lines.append('</p>')
                    in_paragraph = False
                html_lines.append('<br>')

            # 处理普通段落
            else:
                if not in_paragraph:
                    html_lines.append('<p>')
                    in_paragraph = True

                # 处理内联格式
                formatted_line = self._format_inline_text(line)
                html_lines.append(formatted_line)

        # 关闭未关闭的段落
        if in_paragraph:
            html_lines.append('</p>')

        # 如果文件结束时还在代码块中，关闭它
        if in_code_block:
            code_content = '\n'.join(code_block_lines)
            code_content = code_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if code_language:
                html_lines.append(f'<pre><code class="language-{code_language}">{code_content}</code></pre>')
            else:
                html_lines.append(f'<pre><code>{code_content}</code></pre>')

        return '\n'.join(html_lines)
    
    def _format_inline_text(self, text: str) -> str:
        """格式化内联文本"""
        # 处理粗体 **text**
        import re
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        
        # 处理斜体 *text*
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        
        # 处理删除线 ~~text~~
        text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
        
        # 处理高亮 ==text==
        text = re.sub(r'==(.*?)==', r'<mark>\1</mark>', text)
        
        return text
    
    def _apply_styles(self, html_content: str) -> str:
        """应用CSS样式"""
        # 获取当前主题颜色
        colors = self._get_theme_colors()

        css_styles = f"""
        <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: {colors['text_primary']};
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: {colors['bg_primary']};
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: {colors['text_primary']};
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}

        h1 {{ font-size: 2.2em; border-bottom: 3px solid {colors['primary']}; padding-bottom: 10px; }}
        h2 {{ font-size: 1.8em; border-bottom: 2px solid {colors['border_primary']}; padding-bottom: 8px; }}
        h3 {{ font-size: 1.5em; color: {colors['text_secondary']}; }}
        h4 {{ font-size: 1.3em; color: {colors['text_tertiary']}; }}

        p {{
            margin-bottom: 1em;
            text-align: justify;
        }}

        .metadata-tag {{
            background-color: {colors['bg_secondary']};
            border-left: 4px solid {colors['primary']};
            padding: 8px 12px;
            margin: 10px 0;
            border-radius: 4px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
        }}

        .tag-type {{
            color: {colors['ai_primary']};
            font-weight: bold;
        }}

        .tag-value {{
            color: {colors['success']};
        }}

        code {{
            background-color: {colors['bg_secondary']};
            color: {colors['text_primary']};
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
        }}

        pre {{
            background-color: {colors['bg_secondary']};
            color: {colors['text_primary']};
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid {colors['primary']};
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            line-height: 1.4;
        }}

        pre code {{
            background-color: transparent;
            padding: 0;
        }}

        strong {{ color: {colors['text_primary']}; }}
        em {{ color: {colors['ai_primary']}; }}
        del {{ color: {colors['text_tertiary']}; }}
        mark {{ background-color: {colors['warning']}; color: {colors['bg_primary']}; }}

        br {{ margin: 0.5em 0; }}
        </style>
        """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>文档预览</title>
            {css_styles}
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
    
    def _create_error_html(self, error_msg: str) -> str:
        """创建错误显示HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>渲染错误</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .error {{ color: #d32f2f; background-color: #ffebee; 
                         padding: 15px; border-radius: 4px; border-left: 4px solid #d32f2f; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h3>文档渲染错误</h3>
                <p>{error_msg}</p>
            </div>
        </body>
        </html>
        """


class DocumentOutline(QWidget):
    """文档大纲组件"""
    
    # 大纲项点击信号
    outlineItemClicked = pyqtSignal(str, int)  # 标题文本, 行号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._headings = []
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title_label = QLabel("文档大纲")
        title_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(title_label)
        
        # 大纲树
        self._outline_tree = QTreeWidget()
        self._outline_tree.setHeaderHidden(True)
        self._outline_tree.setRootIsDecorated(True)
        self._outline_tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._outline_tree)
    
    def update_outline(self, content: str):
        """更新文档大纲"""
        self._outline_tree.clear()
        self._headings = []
        
        lines = content.split('\n')
        current_items = [None] * 6  # 支持H1-H6
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                level = len(stripped) - len(stripped.lstrip('#'))
                if level <= 6:
                    title_text = stripped[level:].strip()
                    
                    # 创建树项
                    item = QTreeWidgetItem([title_text])
                    item.setData(0, Qt.ItemDataRole.UserRole, line_num)
                    
                    # 确定父项
                    parent_item = None
                    for i in range(level - 1, 0, -1):
                        if current_items[i - 1]:
                            parent_item = current_items[i - 1]
                            break
                    
                    if parent_item:
                        parent_item.addChild(item)
                    else:
                        self._outline_tree.addTopLevelItem(item)
                    
                    # 更新当前项
                    current_items[level - 1] = item
                    # 清除更深层级的项
                    for i in range(level, 6):
                        current_items[i] = None
                    
                    # 记录标题信息
                    self._headings.append({
                        'level': level,
                        'text': title_text,
                        'line': line_num
                    })
        
        # 展开所有项
        self._outline_tree.expandAll()
    
    @pyqtSlot(QTreeWidgetItem, int)
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """处理大纲项点击"""
        line_num = item.data(0, Qt.ItemDataRole.UserRole)
        title_text = item.text(0)
        self.outlineItemClicked.emit(title_text, line_num)


class DocumentViewer(QWidget):
    """文档预览器主组件"""
    
    # 信号定义
    documentChanged = pyqtSignal(str)  # 文档ID
    linkClicked = pyqtSignal(str)      # 链接URL
    
    def __init__(self, config: Config, shared: Shared, project_manager: ProjectManager, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._shared = shared
        self._project_manager = project_manager
        self._theme_manager = theme_manager
        self._current_document_id = None
        self._navigation_history = []
        self._history_index = -1

        self._init_ui()
        self._init_renderer()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧：文档大纲
        self._outline = DocumentOutline()
        self._outline.setMaximumWidth(250)
        self._outline.setMinimumWidth(150)
        splitter.addWidget(self._outline)
        
        # 右侧：文档预览
        preview_widget = self._create_preview_widget()
        splitter.addWidget(preview_widget)
        
        # 设置分割器比例
        splitter.setSizes([200, 600])
    
    def _create_preview_widget(self) -> QWidget:
        """创建预览组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 预览区域
        self._preview_browser = QTextBrowser()
        self._preview_browser.setOpenExternalLinks(False)
        self._preview_browser.anchorClicked.connect(self._on_link_clicked)
        layout.addWidget(self._preview_browser)
        
        return widget
    
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel)
        toolbar.setMaximumHeight(40)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 导航按钮
        self._back_button = QPushButton("← 后退")
        self._back_button.setEnabled(False)
        self._back_button.clicked.connect(self._go_back)
        layout.addWidget(self._back_button)
        
        self._forward_button = QPushButton("前进 →")
        self._forward_button.setEnabled(False)
        self._forward_button.clicked.connect(self._go_forward)
        layout.addWidget(self._forward_button)
        
        layout.addStretch()
        
        # 刷新按钮
        refresh_button = QPushButton("🔄 刷新")
        refresh_button.clicked.connect(self._refresh_preview)
        layout.addWidget(refresh_button)
        
        return toolbar
    
    def _init_renderer(self):
        """初始化渲染器"""
        self._renderer = DocumentRenderer(self._theme_manager)
        self._renderer.renderCompleted.connect(self._on_render_completed)
        self._renderer.renderFailed.connect(self._on_render_failed)
    
    def _connect_signals(self):
        """连接信号"""
        self._outline.outlineItemClicked.connect(self._on_outline_clicked)
    
    def load_document(self, document_id: str):
        """加载文档"""
        if document_id == self._current_document_id:
            return
        
        if not self._project_manager:
            logger.warning("No project manager available")
            return
        
        document = self._project_manager.get_document(document_id)
        if document is None:
            logger.warning(f"Failed to load document: {document_id}")
            return

        content = document.content
        if content is None:
            logger.warning(f"Document has no content: {document_id}")
            return
        
        # 添加到导航历史
        if self._current_document_id:
            self._add_to_history(self._current_document_id)
        
        self._current_document_id = document_id
        
        # 更新大纲
        self._outline.update_outline(content)
        
        # 渲染文档
        self._renderer.render_document(content, document_id)
        
        # 发出文档变化信号
        self.documentChanged.emit(document_id)
        
        logger.info(f"Document loaded in viewer: {document_id}")
    
    def _add_to_history(self, document_id: str):
        """添加到导航历史"""
        # 移除当前位置之后的历史
        if self._history_index < len(self._navigation_history) - 1:
            self._navigation_history = self._navigation_history[:self._history_index + 1]
        
        # 添加新项
        self._navigation_history.append(document_id)
        self._history_index = len(self._navigation_history) - 1
        
        # 限制历史长度
        if len(self._navigation_history) > 50:
            self._navigation_history.pop(0)
            self._history_index -= 1
        
        self._update_navigation_buttons()
    
    def _update_navigation_buttons(self):
        """更新导航按钮状态"""
        self._back_button.setEnabled(self._history_index > 0)
        self._forward_button.setEnabled(self._history_index < len(self._navigation_history) - 1)
    
    @pyqtSlot()
    def _go_back(self):
        """后退"""
        if self._history_index > 0:
            self._history_index -= 1
            document_id = self._navigation_history[self._history_index]
            self._load_document_without_history(document_id)
            self._update_navigation_buttons()
    
    @pyqtSlot()
    def _go_forward(self):
        """前进"""
        if self._history_index < len(self._navigation_history) - 1:
            self._history_index += 1
            document_id = self._navigation_history[self._history_index]
            self._load_document_without_history(document_id)
            self._update_navigation_buttons()
    
    def _load_document_without_history(self, document_id: str):
        """加载文档但不添加到历史"""
        if not self._project_manager:
            return
        
        content = self._project_manager.get_document_content(document_id)
        if content is None:
            return
        
        self._current_document_id = document_id
        self._outline.update_outline(content)
        self._renderer.render_document(content, document_id)
        self.documentChanged.emit(document_id)
    
    @pyqtSlot()
    def _refresh_preview(self):
        """刷新预览"""
        if self._current_document_id:
            self._load_document_without_history(self._current_document_id)
    
    @pyqtSlot(str)
    def _on_render_completed(self, html_content: str):
        """渲染完成处理"""
        self._preview_browser.setHtml(html_content)
    
    @pyqtSlot(str)
    def _on_render_failed(self, error_msg: str):
        """渲染失败处理"""
        error_html = f"""
        <html><body>
        <h3 style="color: red;">预览失败</h3>
        <p>{error_msg}</p>
        </body></html>
        """
        self._preview_browser.setHtml(error_html)
    
    @pyqtSlot(str, int)
    def _on_outline_clicked(self, title_text: str, line_num: int):
        """处理大纲点击"""
        # 滚动到对应位置（简化实现）
        cursor = self._preview_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        
        # 查找标题文本
        if self._preview_browser.find(title_text):
            self._preview_browser.ensureCursorVisible()
    
    @pyqtSlot(QUrl)
    def _on_link_clicked(self, url: QUrl):
        """处理链接点击"""
        url_string = url.toString()
        
        # 处理内部链接（@标记引用）
        if url_string.startswith('@'):
            # 查找对应的文档或概念
            self.linkClicked.emit(url_string)
        else:
            # 外部链接
            QDesktopServices.openUrl(url)
    
    def get_current_document_id(self) -> Optional[str]:
        """获取当前文档ID"""
        return self._current_document_id
