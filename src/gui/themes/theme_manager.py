"""
主题管理器
实现浅色/深色主题切换和统一的样式系统
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPalette, QColor

logger = logging.getLogger(__name__)


class ThemeType(Enum):
    """主题类型枚举"""
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"


class ThemeManager(QObject):
    """主题管理器"""
    
    # 信号定义
    themeChanged = pyqtSignal(str)  # 主题变更信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._current_theme = ThemeType.LIGHT
        self._themes = {}
        
        self._init_themes()
        
        logger.info("Theme manager initialized")
    
    def _init_themes(self):
        """初始化主题"""
        # 浅色主题
        self._themes[ThemeType.LIGHT] = {
            "name": "浅色主题",
            "colors": {
                # 主色调
                "primary": "#0969da",
                "primary_light": "#54aeff", 
                "primary_dark": "#0550ae",
                
                # 中性色
                "white": "#ffffff",
                "gray_50": "#f8f9fa",
                "gray_100": "#f1f3f4",
                "gray_200": "#e1e4e8",
                "gray_300": "#d0d7de",
                "gray_500": "#656d76",
                "gray_700": "#424a53",
                "gray_900": "#1c2128",
                
                # 语义色
                "success": "#1a7f37",
                "warning": "#d1242f",
                "error": "#cf222e",
                "info": "#0969da",
                
                # AI功能色
                "ai_primary": "#7c3aed",
                "ai_secondary": "#a855f7",
                "ai_background": "rgba(124, 58, 237, 0.1)",
                "ai_border": "rgba(124, 58, 237, 0.2)",
                
                # 背景色
                "bg_primary": "#ffffff",
                "bg_secondary": "#f8f9fa",
                "bg_tertiary": "#f1f3f4",
                
                # 文本色
                "text_primary": "#1c2128",
                "text_secondary": "#656d76",
                "text_tertiary": "#8b949e",
                
                # 边框色
                "border_primary": "#e1e4e8",
                "border_secondary": "#d0d7de",
            },
            "stylesheet": self._get_light_stylesheet()
        }
        
        # 深色主题
        self._themes[ThemeType.DARK] = {
            "name": "深色主题",
            "colors": {
                # 主色调
                "primary": "#58a6ff",
                "primary_light": "#79c0ff",
                "primary_dark": "#388bfd",
                
                # 背景色
                "bg_primary": "#0d1117",
                "bg_secondary": "#161b22",
                "bg_tertiary": "#21262d",
                
                # 文本色
                "text_primary": "#f0f6fc",
                "text_secondary": "#8b949e",
                "text_tertiary": "#6e7681",
                
                # 边框色
                "border_primary": "#30363d",
                "border_secondary": "#21262d",
                
                # 语义色
                "success": "#3fb950",
                "warning": "#d29922",
                "error": "#f85149",
                "info": "#58a6ff",
                
                # AI功能色
                "ai_primary": "#a855f7",
                "ai_secondary": "#c084fc",
                "ai_background": "rgba(168, 85, 247, 0.1)",
                "ai_border": "rgba(168, 85, 247, 0.2)",
            },
            "stylesheet": self._get_dark_stylesheet()
        }
        
        # 高对比度主题
        self._themes[ThemeType.HIGH_CONTRAST] = {
            "name": "高对比度主题",
            "colors": {
                # 高对比度配色
                "bg_primary": "#000000",
                "bg_secondary": "#1a1a1a",
                "text_primary": "#ffffff",
                "text_secondary": "#cccccc",
                "border_primary": "#ffffff",
                "primary": "#00ff00",
                "success": "#00ff00",
                "warning": "#ffff00",
                "error": "#ff0000",
            },
            "stylesheet": self._get_high_contrast_stylesheet()
        }
    
    def _get_light_stylesheet(self) -> str:
        """获取浅色主题样式表"""
        return """
        /* 主窗口 */
        QMainWindow {
            background-color: #ffffff;
            color: #1c2128;
        }
        
        /* 菜单栏 */
        QMenuBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e1e4e8;
            color: #1c2128;
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        
        QMenuBar::item:selected {
            background-color: #e1e4e8;
        }
        
        QMenu {
            background-color: #ffffff;
            border: 1px solid #e1e4e8;
            color: #1c2128;
        }
        
        QMenu::item {
            padding: 6px 20px;
        }
        
        QMenu::item:selected {
            background-color: #f1f3f4;
        }
        
        /* 工具栏 */
        QToolBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e1e4e8;
            spacing: 2px;
        }
        
        QToolButton {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 4px;
            margin: 1px;
        }
        
        QToolButton:hover {
            background-color: #f1f3f4;
            border-color: #d0d7de;
        }
        
        QToolButton:pressed {
            background-color: #e1e4e8;
        }
        
        /* 按钮 */
        QPushButton {
            background-color: #f8f9fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 6px 12px;
            color: #1c2128;
        }
        
        QPushButton:hover {
            background-color: #f1f3f4;
            border-color: #d0d7de;
        }
        
        QPushButton:pressed {
            background-color: #e1e4e8;
        }
        
        /* 文本编辑器 */
        QPlainTextEdit, QTextEdit {
            background-color: #ffffff;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            color: #1c2128;
            selection-background-color: #0969da;
            selection-color: #ffffff;
        }
        
        QPlainTextEdit:focus, QTextEdit:focus {
            border-color: #0969da;
        }
        
        /* 列表组件 */
        QListWidget, QTreeWidget {
            background-color: #ffffff;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            color: #1c2128;
            alternate-background-color: #f8f9fa;
        }
        
        QListWidget::item, QTreeWidget::item {
            padding: 4px;
            border-bottom: 1px solid #f1f3f4;
        }
        
        QListWidget::item:selected, QTreeWidget::item:selected {
            background-color: #0969da;
            color: #ffffff;
        }
        
        QListWidget::item:hover, QTreeWidget::item:hover {
            background-color: #f1f3f4;
        }
        
        /* 标签页 */
        QTabWidget::pane {
            border: 1px solid #e1e4e8;
            background-color: #ffffff;
        }
        
        QTabBar::tab {
            background-color: #f8f9fa;
            border: 1px solid #e1e4e8;
            border-bottom: none;
            padding: 6px 12px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom: 2px solid #0969da;
        }
        
        QTabBar::tab:hover {
            background-color: #f1f3f4;
        }
        
        /* 分割器 */
        QSplitter::handle {
            background-color: #e1e4e8;
        }
        
        QSplitter::handle:horizontal {
            width: 2px;
        }
        
        QSplitter::handle:vertical {
            height: 2px;
        }
        
        /* 滚动条 */
        QScrollBar:vertical {
            background-color: #f8f9fa;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #d0d7de;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #656d76;
        }
        
        QScrollBar:horizontal {
            background-color: #f8f9fa;
            height: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #d0d7de;
            border-radius: 6px;
            min-width: 20px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #656d76;
        }

        /* 状态栏 */
        QStatusBar {
            background-color: #f8f9fa;
            border-top: 1px solid #e1e4e8;
            color: #656d76;
        }

        QStatusBar::item {
            border: none;
        }
        """
    
    def _get_dark_stylesheet(self) -> str:
        """获取深色主题样式表（优化版 - 更和谐的配色）"""
        return """
        /* 主窗口 */
        QMainWindow {
            background-color: #1a1a1a;
            color: #e8e8e8;
        }
        
        /* 菜单栏 - 增加呼吸感和轻微阴影 */
        QMenuBar {
            background-color: #252525;
            border-bottom: 1px solid #383838;
            color: #e8e8e8;
            padding: 4px 8px;
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 10px 16px;
            border-radius: 4px;
            margin: 0 2px;
        }
        
        QMenuBar::item:selected {
            background: qlineargradient(y1: 0, y2: 1, stop: 0 #9d65f7, stop: 1 #8b5cf6);
            color: #ffffff;
        }
        
        QMenu {
            background-color: #252525;
            border: 1px solid #383838;
            border-radius: 6px;
            color: #e8e8e8;
        }
        
        QMenu::item {
            padding: 6px 20px;
            border-radius: 4px;
        }
        
        QMenu::item:selected {
            background-color: #8b5cf6;
            color: #ffffff;
        }
        
        /* 工具栏 - 增加呼吸感 */
        QToolBar {
            background-color: #252525;
            border-bottom: 1px solid #383838;
            spacing: 4px;
            padding: 8px 12px;
        }
        
        QToolButton {
            border: 1px solid transparent;
            border-radius: 6px;
            background-color: transparent;
            color: #e8e8e8;
            font-size: 11px;
            font-weight: 500;
            padding: 6px 10px;
            min-width: 60px;
        }
        
        QToolButton:hover {
            background-color: #2f2f2f;
            border-color: #454545;
            color: #ffffff;
        }
        
        QToolButton:pressed {
            background-color: #252525;
            border-color: #383838;
            color: #ffffff;
        }
        
        QToolButton:checked {
            background: qlineargradient(y1: 0, y2: 1, stop: 0 #9d65f7, stop: 1 #8b5cf6);
            border-color: #8b5cf6;
            color: #ffffff;
        }
        
        QToolButton:checked:hover {
            background: qlineargradient(y1: 0, y2: 1, stop: 0 #8b5cf6, stop: 1 #7c3aed);
            border-color: #7c3aed;
        }
        
        /* 按钮 - 添加动画效果 */
        QPushButton {
            background-color: #2a2a2a;
            border: 1px solid #404040;
            border-radius: 6px;
            padding: 8px 14px;
            color: #e8e8e8;
        }
        
        QPushButton:hover {
            background-color: #353535;
            border-color: #505050;
        }
        
        QPushButton:pressed {
            background-color: #222222;
        }
        
        /* 文本编辑器 - 主内容区域层次感 */
        QPlainTextEdit, QTextEdit {
            background-color: #1f1f1f;
            border: 1px solid #383838;
            border-radius: 6px;
            color: #e8e8e8;
            selection-background-color: #8b5cf6;
            selection-color: #ffffff;
        }
        
        QPlainTextEdit:focus, QTextEdit:focus {
            border-color: #8b5cf6;
            background-color: #222222;
        }
        
        /* 列表组件 - 侧边面板层次感 */
        QListWidget, QTreeWidget {
            background-color: #181818;
            border: 1px solid #383838;
            border-radius: 6px;
            color: #e8e8e8;
            alternate-background-color: #1f1f1f;
        }
        
        QListWidget::item, QTreeWidget::item {
            padding: 8px 12px;
            border: none;
            margin: 1px 0;
        }
        
        QListWidget::item:selected, QTreeWidget::item:selected {
            background-color: #8b5cf6;
            color: #ffffff;
        }
        
        QListWidget::item:hover, QTreeWidget::item:hover {
            background-color: #2a2a2a;
        }
        
        /* 标签页 */
        QTabWidget::pane {
            border: 1px solid #383838;
            border-radius: 6px;
            background-color: #1f1f1f;
        }
        
        QTabBar::tab {
            background-color: #2a2a2a;
            border: 1px solid #383838;
            border-bottom: none;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            color: #b8b8b8;
        }
        
        QTabBar::tab:selected {
            background-color: #1f1f1f;
            color: #e8e8e8;
        }
        
        QTabBar::tab:hover {
            background-color: #353535;
        }
        
        /* 分割器 - 更柔和的设计 */
        QSplitter::handle {
            background-color: #2f2f2f;
            border: none;
        }
        
        QSplitter::handle:horizontal {
            width: 1px;
            background: qlineargradient(y1: 0, y2: 1, stop: 0 transparent, stop: 0.1 #2f2f2f, stop: 0.9 #2f2f2f, stop: 1 transparent);
        }
        
        QSplitter::handle:vertical {
            height: 1px;
            background: qlineargradient(x1: 0, x2: 1, stop: 0 transparent, stop: 0.1 #2f2f2f, stop: 0.9 #2f2f2f, stop: 1 transparent);
        }
        
        QSplitter::handle:hover {
            background-color: #4a4a4a;
        }
        
        QSplitter::handle:horizontal:hover {
            background: qlineargradient(y1: 0, y2: 1, stop: 0 transparent, stop: 0.1 #4a4a4a, stop: 0.9 #4a4a4a, stop: 1 transparent);
        }
        
        QSplitter::handle:vertical:hover {
            background: qlineargradient(x1: 0, x2: 1, stop: 0 transparent, stop: 0.1 #4a4a4a, stop: 0.9 #4a4a4a, stop: 1 transparent);
        }
        
        /* 滚动条 - 现代化设计 */
        QScrollBar:vertical {
            background-color: transparent;
            width: 8px;
            border-radius: 4px;
            margin: 2px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #404040;
            border-radius: 4px;
            min-height: 30px;
            margin: 0;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #505050;
        }
        
        QScrollBar::handle:vertical:pressed {
            background-color: #8b5cf6;
        }
        
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
            background: none;
        }
        
        QScrollBar:horizontal {
            background-color: transparent;
            height: 8px;
            border-radius: 4px;
            margin: 2px;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #404040;
            border-radius: 4px;
            min-width: 30px;
            margin: 0;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #505050;
        }
        
        QScrollBar::handle:horizontal:pressed {
            background-color: #8b5cf6;
        }
        
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0px;
            background: none;
        }

        /* 状态栏 - 增加呼吸感和更好的信息显示 */
        QStatusBar {
            background-color: #252525;
            border-top: 1px solid #383838;
            color: #b8b8b8;
            padding: 6px 12px;
            min-height: 20px;
        }

        QStatusBar::item {
            border: none;
            padding: 0 8px;
        }
        
        QStatusBar QLabel {
            color: #b8b8b8;
            font-size: 12px;
            padding: 2px 4px;
        }
        
        QStatusBar::separator {
            background-color: #383838;
            width: 1px;
            margin: 4px 0;
        }
        """
    
    def _get_high_contrast_stylesheet(self) -> str:
        """获取高对比度主题样式表"""
        return """
        /* 高对比度主题 */
        * {
            background-color: #000000;
            color: #ffffff;
            border: 2px solid #ffffff;
        }
        
        QMainWindow {
            background-color: #000000;
            color: #ffffff;
        }
        
        QPushButton {
            background-color: #000000;
            color: #ffffff;
            border: 2px solid #ffffff;
            padding: 8px 16px;
        }
        
        QPushButton:hover {
            background-color: #ffffff;
            color: #000000;
        }
        
        QPlainTextEdit, QTextEdit {
            background-color: #000000;
            color: #ffffff;
            border: 2px solid #ffffff;
            selection-background-color: #ffffff;
            selection-color: #000000;
        }
        """
    
    def get_current_theme(self) -> ThemeType:
        """获取当前主题"""
        return self._current_theme
    
    def get_theme_colors(self, theme_type: Optional[ThemeType] = None) -> Dict[str, str]:
        """获取主题颜色"""
        theme_type = theme_type or self._current_theme
        return self._themes[theme_type]["colors"]
    
    def set_theme(self, theme_type: ThemeType):
        """设置主题"""
        if theme_type not in self._themes:
            logger.warning(f"Unknown theme type: {theme_type}")
            return
        
        self._current_theme = theme_type
        theme_data = self._themes[theme_type]
        
        # 应用样式表
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme_data["stylesheet"])
        
        # 发出主题变更信号
        self.themeChanged.emit(theme_type.value)
        
        logger.info(f"Theme changed to: {theme_data['name']}")
    
    def toggle_theme(self):
        """切换主题（浅色/深色）"""
        if self._current_theme == ThemeType.LIGHT:
            self.set_theme(ThemeType.DARK)
        else:
            self.set_theme(ThemeType.LIGHT)
    
    def get_available_themes(self) -> Dict[ThemeType, str]:
        """获取可用主题列表"""
        return {theme_type: data["name"] for theme_type, data in self._themes.items()}
    
    def apply_theme_to_widget(self, widget, theme_type: Optional[ThemeType] = None):
        """为特定组件应用主题"""
        theme_type = theme_type or self._current_theme
        theme_data = self._themes[theme_type]
        
        # 应用样式表到特定组件
        widget.setStyleSheet(theme_data["stylesheet"])
