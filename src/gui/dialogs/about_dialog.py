"""
关于对话框
显示应用程序信息、版本、开发者信息等
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QTabWidget, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap

logger = logging.getLogger(__name__)


class AboutDialog(QDialog):
    """关于对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._init_ui()
        
        # 设置对话框属性
        self.setModal(True)
        self.setFixedSize(500, 400)
        self.setWindowTitle("关于 AI Novel Editor")
        
        logger.debug("About dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 应用图标和标题
        header_layout = self._create_header()
        layout.addLayout(header_layout)
        
        # 标签页
        tabs = self._create_tabs()
        layout.addWidget(tabs)
        
        # 按钮
        button_layout = self._create_buttons()
        layout.addLayout(button_layout)
    
    def _create_header(self) -> QHBoxLayout:
        """创建头部"""
        layout = QHBoxLayout()
        
        # 应用图标
        icon_label = QLabel()
        icon_label.setText("🤖")  # 临时使用emoji，实际应该使用应用图标
        icon_label.setFont(QFont("", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(80, 80)
        layout.addWidget(icon_label)
        
        # 应用信息
        info_layout = QVBoxLayout()
        
        # 应用名称
        app_name = QLabel("AI Novel Editor")
        app_name.setFont(QFont("", 18, QFont.Weight.Bold))
        info_layout.addWidget(app_name)
        
        # 版本信息
        version_label = QLabel("版本 1.0.0")
        version_label.setFont(QFont("", 12))
        version_label.setStyleSheet("color: #656d76;")
        info_layout.addWidget(version_label)
        
        # 描述
        description = QLabel("智能AI小说编辑器")
        description.setFont(QFont("", 10))
        description.setStyleSheet("color: #656d76;")
        info_layout.addWidget(description)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        return layout
    
    def _create_tabs(self) -> QTabWidget:
        """创建标签页"""
        tabs = QTabWidget()
        
        # 关于标签页
        about_tab = self._create_about_tab()
        tabs.addTab(about_tab, "关于")
        
        # 开发者标签页
        developers_tab = self._create_developers_tab()
        tabs.addTab(developers_tab, "开发者")
        
        # 许可证标签页
        license_tab = self._create_license_tab()
        tabs.addTab(license_tab, "许可证")
        
        # 致谢标签页
        credits_tab = self._create_credits_tab()
        tabs.addTab(credits_tab, "致谢")
        
        return tabs
    
    def _create_about_tab(self) -> QWidget:
        """创建关于标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setHtml("""
        <h3>AI Novel Editor</h3>
        <p>一款专为小说创作者设计的智能编辑器，集成了先进的AI技术，
        帮助作者提高创作效率和质量。</p>
        
        <h4>主要特性：</h4>
        <ul>
            <li>🤖 AI智能补全和续写</li>
            <li>📝 专业的文本编辑器</li>
            <li>🗂️ 项目管理和文档组织</li>
            <li>👥 角色和概念管理</li>
            <li>🎨 多主题界面</li>
            <li>📊 写作统计和分析</li>
        </ul>
        
        <h4>技术栈：</h4>
        <ul>
            <li>Python 3.11+</li>
            <li>PyQt6</li>
            <li>AI模型集成</li>
        </ul>
        """)
        layout.addWidget(about_text)
        
        return widget
    
    def _create_developers_tab(self) -> QWidget:
        """创建开发者标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        developers_text = QTextEdit()
        developers_text.setReadOnly(True)
        developers_text.setHtml("""
        <h3>开发团队</h3>
        
        <h4>作者：</h4>
        <ul>
            <li><b>inliver</b></li>
        </ul>
        
        <h4>联系方式：</h4>
        <ul>
            <li>📧 邮箱: inliverapi@outlook.com</li>
            <li>📱 GitHub: https://github.com/inliver233</li>
        </ul>
        """)
        layout.addWidget(developers_text)
        
        return widget
    
    def _create_license_tab(self) -> QWidget:
        """创建许可证标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        license_text = QTextEdit()
        license_text.setReadOnly(True)
        license_text.setPlainText("""
MIT License

Copyright (c) 2024 AI Novel Editor Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
        """)
        layout.addWidget(license_text)
        
        return widget
    
    def _create_credits_tab(self) -> QWidget:
        """创建致谢标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        credits_text = QTextEdit()
        credits_text.setReadOnly(True)
        credits_text.setHtml("""
        <h3>致谢</h3>
        
        <h4>开源项目：</h4>
        <ul>
            <li><b>PyQt6</b> - 跨平台GUI框架</li>
            <li><b>Python</b> - 编程语言</li>
            <li><b>OpenAI</b> - AI模型支持</li>
            <li><b>Anthropic Claude</b> - AI助手技术</li>
        </ul>
        
        <h4>图标和资源：</h4>
        <ul>
            <li><b>Feather Icons</b> - 界面图标</li>
            <li><b>Google Fonts</b> - 字体资源</li>
        </ul>
        
        <h4>特别感谢：</h4>
        <ul>
            <li>所有测试用户的反馈和建议</li>
            <li>开源社区的支持和贡献</li>
            <li>小说创作者们的需求和灵感</li>
        </ul>
        
        <p><i>感谢每一位为这个项目做出贡献的人！</i></p>
        """)
        layout.addWidget(credits_text)
        
        return widget
    
    def _create_buttons(self) -> QHBoxLayout:
        """创建按钮"""
        layout = QHBoxLayout()
        layout.addStretch()
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        layout.addWidget(ok_btn)
        
        return layout
