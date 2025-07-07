from __future__ import annotations

"""
novelWriter风格的语法高亮器
基于设计文档实现@标记系统的语法高亮

配色方案（柔和版本）：
- 基于流行的Dracula和One Dark主题，降低饱和度和亮度
- @标记：柔和粉色 (#E8A2C7) - 温和的粉色，护眼易识别
- @标记值：柔和绿色 (#98D982) - 温和的绿色，清晰舒适
- 标题：渐变色彩层次 (柔和紫色 -> 柔和青色 -> 柔和蓝色 -> 柔和橙色)
- 注释：柔和灰色 (#9CA3AF) - 温和的注释色
- 格式化文本：柔和的色彩表达，降低对比度
"""

import re
import logging
from typing import Dict, List, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QSyntaxHighlighter, QTextDocument, QTextCharFormat,
    QColor, QFont, QTextCursor
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Config


logger = logging.getLogger(__name__)


class NovelWriterHighlighter(QSyntaxHighlighter):
    """novelWriter风格的语法高亮器"""
    
    def __init__(self, config: Config, document: QTextDocument):
        super().__init__(document)
        
        self._config = config
        self._highlighting_rules = []
        
        # 初始化高亮规则
        self._init_highlighting_rules()
        
        logger.info("NovelWriter syntax highlighter initialized")
    
    def _init_highlighting_rules(self):
        """初始化高亮规则"""
        self._highlighting_rules = []
        
        # @标记高亮规则
        self._init_tag_rules()
        
        # 标题高亮规则
        self._init_title_rules()
        
        # 注释高亮规则
        self._init_comment_rules()
        
        # 格式化文本规则
        self._init_format_rules()
        
        logger.debug(f"Initialized {len(self._highlighting_rules)} highlighting rules")
    
    def _init_tag_rules(self):
        """初始化@标记高亮规则"""
        # @标记格式 - 使用柔和的粉色，降低饱和度
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#E8A2C7"))  # 柔和的粉色 - 降低饱和度的粉色
        tag_format.setFontWeight(QFont.Weight.Bold)

        # @标记值格式 - 使用柔和的绿色，更护眼
        tag_value_format = QTextCharFormat()
        tag_value_format.setForeground(QColor("#98D982"))  # 柔和的绿色 - 降低亮度的绿色
        
        # 支持的@标记类型 - 分别定义键和值的模式
        tag_key_patterns = [
            r'@(?:char|character):',
            r'@(?:location|place):',
            r'@(?:time|when):',
            r'@(?:plot|storyline):',
            r'@(?:mood|atmosphere):',
            r'@(?:pov|viewpoint):',
            r'@(?:focus|emphasis):',
        ]

        tag_value_patterns = [
            r'@(?:char|character):\s*([^\n]+)',
            r'@(?:location|place):\s*([^\n]+)',
            r'@(?:time|when):\s*([^\n]+)',
            r'@(?:plot|storyline):\s*([^\n]+)',
            r'@(?:mood|atmosphere):\s*([^\n]+)',
            r'@(?:pov|viewpoint):\s*([^\n]+)',
            r'@(?:focus|emphasis):\s*([^\n]+)',
        ]

        # 添加@标记键的高亮规则
        for pattern in tag_key_patterns:
            self._highlighting_rules.append((
                re.compile(pattern, re.IGNORECASE),
                tag_format
            ))

        # 添加@标记值的高亮规则
        for pattern in tag_value_patterns:
            self._highlighting_rules.append((
                re.compile(pattern, re.IGNORECASE),
                tag_value_format
            ))
    
    def _init_title_rules(self):
        """初始化标题高亮规则"""
        # H1标题 (# 标题) - 使用柔和的紫色，最重要的标题
        h1_format = QTextCharFormat()
        h1_format.setForeground(QColor("#A78BFA"))  # 柔和的紫色 - 降低饱和度
        h1_format.setFontWeight(QFont.Weight.Bold)
        h1_format.setFontPointSize(18)

        # H2标题 (## 标题) - 使用柔和的青色，次重要标题
        h2_format = QTextCharFormat()
        h2_format.setForeground(QColor("#7DD3FC"))  # 柔和的青色 - 降低亮度
        h2_format.setFontWeight(QFont.Weight.Bold)
        h2_format.setFontPointSize(16)

        # H3标题 (### 标题) - 使用柔和的蓝色，清晰易读
        h3_format = QTextCharFormat()
        h3_format.setForeground(QColor("#93C5FD"))  # 柔和的蓝色 - 更温和的蓝色
        h3_format.setFontWeight(QFont.Weight.Bold)
        h3_format.setFontPointSize(14)

        # H4标题 (#### 标题) - 使用柔和的橙色，温和的强调
        h4_format = QTextCharFormat()
        h4_format.setForeground(QColor("#FCD34D"))  # 柔和的橙色 - 降低饱和度的橙色
        h4_format.setFontWeight(QFont.Weight.Bold)
        
        # 标题规则
        title_rules = [
            (r'^#{1}\s+(.+)$', h1_format),
            (r'^#{2}\s+(.+)$', h2_format),
            (r'^#{3}\s+(.+)$', h3_format),
            (r'^#{4}\s+(.+)$', h4_format),
        ]
        
        for pattern, format_obj in title_rules:
            self._highlighting_rules.append((
                re.compile(pattern, re.MULTILINE),
                format_obj
            ))
    
    def _init_comment_rules(self):
        """初始化注释高亮规则"""
        # 作者注释 (% 注释) - 使用更柔和的注释颜色
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#9CA3AF"))  # 柔和的灰色 - 更温和的注释色
        comment_format.setFontItalic(True)
        
        # 注释规则
        self._highlighting_rules.append((
            re.compile(r'^%.*$', re.MULTILINE),
            comment_format
        ))
    
    def _init_format_rules(self):
        """初始化格式化文本规则"""
        # 粗体文本 (**文本**) - 使用柔和的红色，温和的强调
        bold_format = QTextCharFormat()
        bold_format.setFontWeight(QFont.Weight.Bold)
        bold_format.setForeground(QColor("#F87171"))  # 柔和的红色 - 降低饱和度的红色

        # 斜体文本 (*文本*) - 使用柔和的黄色，温和的强调
        italic_format = QTextCharFormat()
        italic_format.setFontItalic(True)
        italic_format.setForeground(QColor("#FDE047"))  # 柔和的黄色 - 降低亮度的黄色

        # 删除线文本 (~~文本~~) - 使用柔和的注释色，表示已删除
        strikethrough_format = QTextCharFormat()
        strikethrough_format.setFontStrikeOut(True)
        strikethrough_format.setForeground(QColor("#9CA3AF"))  # 柔和的灰色 - 与注释色一致

        # 高亮文本 (==文本==) - 使用温和的背景色
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#374151"))  # 柔和的深灰背景 - 更温和的背景色
        highlight_format.setForeground(QColor("#FDE047"))  # 柔和的黄色文字
        
        # 格式化规则
        format_rules = [
            (r'\*\*([^*]+)\*\*', bold_format),      # 粗体
            (r'\*([^*]+)\*', italic_format),        # 斜体
            (r'~~([^~]+)~~', strikethrough_format), # 删除线
            (r'==([^=]+)==', highlight_format),     # 高亮
        ]
        
        for pattern, format_obj in format_rules:
            self._highlighting_rules.append((
                re.compile(pattern),
                format_obj
            ))
    
    def highlightBlock(self, text: str):
        """高亮文本块"""
        # 应用所有高亮规则
        for pattern, format_obj in self._highlighting_rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format_obj)
        
        # 特殊处理：@标记的键值分离高亮
        self._highlight_tag_key_value(text)
    
    def _highlight_tag_key_value(self, text: str):
        """分别高亮@标记的键和值"""
        # @标记键格式 - 使用柔和的粉色，与初始化保持一致
        tag_key_format = QTextCharFormat()
        tag_key_format.setForeground(QColor("#E8A2C7"))  # 柔和的粉色 - 与初始化一致
        tag_key_format.setFontWeight(QFont.Weight.Bold)

        # @标记值格式 - 使用柔和的绿色，与初始化保持一致
        tag_value_format = QTextCharFormat()
        tag_value_format.setForeground(QColor("#98D982"))  # 柔和的绿色 - 与初始化一致
        
        # 匹配@标记模式
        tag_pattern = re.compile(r'(@\w+):\s*([^\n]+)')
        
        for match in tag_pattern.finditer(text):
            # 高亮@标记键
            key_start = match.start(1)
            key_length = match.end(1) - key_start + 1  # 包含冒号
            self.setFormat(key_start, key_length, tag_key_format)
            
            # 高亮@标记值
            value_start = match.start(2)
            value_length = match.end(2) - value_start
            if value_length > 0:  # 只有当值不为空时才高亮
                self.setFormat(value_start, value_length, tag_value_format)
    
    def rehighlight_document(self):
        """重新高亮整个文档"""
        self.rehighlight()
        logger.debug("Document rehighlighted")
    
    def update_theme(self, theme: str):
        """更新主题颜色"""
        # 根据主题更新颜色
        if theme == "dark":
            self._update_dark_theme_colors()
        else:
            self._update_light_theme_colors()
        
        # 重新初始化规则
        self._init_highlighting_rules()
        
        # 重新高亮
        self.rehighlight()
        
        logger.info(f"Syntax highlighter theme updated to: {theme}")
    
    def _update_dark_theme_colors(self):
        """更新深色主题颜色 - 使用Dracula配色方案"""
        # 深色主题已经是默认配置，使用Dracula主题色彩
        # 这些颜色在深色背景下有最佳的对比度和可读性
        pass

    def _update_light_theme_colors(self):
        """更新浅色主题颜色 - 调整为适合浅色背景的配色"""
        # 浅色主题需要调整颜色以适应白色背景
        # 可以使用更深的颜色版本以保持良好的对比度
        # 例如：将Dracula的明亮色彩调暗一些
        pass
