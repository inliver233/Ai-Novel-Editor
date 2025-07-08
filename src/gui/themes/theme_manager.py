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
        
        self._current_theme = ThemeType.DARK
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
            "stylesheet": ""  # 将在预加载中填充
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
            "stylesheet": ""  # 将在预加载中填充
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
            "stylesheet": ""  # 将在预加载中填充
        }
        
        # 预加载所有样式表
        self._preload_stylesheets()
    
    def _preload_stylesheets(self):
        """预加载所有样式表到内存中，确保主题切换瞬间完成"""
        logger.debug("开始预加载主题样式表...")
        
        # 预加载浅色主题
        self._themes[ThemeType.LIGHT]["stylesheet"] = self._load_stylesheet_from_file('light_theme.qss')
        
        # 预加载深色主题  
        self._themes[ThemeType.DARK]["stylesheet"] = self._load_stylesheet_from_file('dark_theme.qss')
        
        # 预加载高对比度主题
        self._themes[ThemeType.HIGH_CONTRAST]["stylesheet"] = self._get_high_contrast_stylesheet()
        
        # 验证样式表是否成功加载
        for theme_type, theme_data in self._themes.items():
            if not theme_data["stylesheet"]:
                logger.warning(f"样式表加载失败: {theme_type.value}")
            else:
                logger.debug(f"样式表预加载成功: {theme_type.value} ({len(theme_data['stylesheet'])} 字符)")
        
        logger.info("所有主题样式表预加载完成")
    
    def _load_stylesheet_from_file(self, filename: str) -> str:
        """从文件加载样式表（带缓存机制）"""
        # 如果已经缓存，直接返回
        if hasattr(self, '_stylesheet_cache') and filename in self._stylesheet_cache:
            return self._stylesheet_cache[filename]
        
        # 初始化缓存
        if not hasattr(self, '_stylesheet_cache'):
            self._stylesheet_cache = {}
        
        try:
            import os
            style_path = os.path.join(os.path.dirname(__file__), '../../resources/styles', filename)
            with open(style_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 缓存样式表内容
                self._stylesheet_cache[filename] = content
                return content
        except FileNotFoundError:
            logger.error(f"样式文件未找到: {filename}")
            self._stylesheet_cache[filename] = ""
            return ""
        except Exception as e:
            logger.error(f"加载样式文件失败: {e}")
            self._stylesheet_cache[filename] = ""
            return ""
    
    def _get_dark_stylesheet(self) -> str:
        """获取深色主题样式表"""
        return self._load_stylesheet_from_file('dark_theme.qss')
    
    def _get_high_contrast_stylesheet(self) -> str:
        """获取高对比度主题样式表"""
        return self._load_stylesheet_from_file('high_contrast_theme.qss')
    
    def get_current_theme(self) -> ThemeType:
        """获取当前主题"""
        return self._current_theme
    
    def get_theme_colors(self, theme_type: Optional[ThemeType] = None) -> Dict[str, str]:
        """获取主题颜色"""
        theme_type = theme_type or self._current_theme
        return self._themes[theme_type]["colors"]
    
    def set_theme(self, theme_type: ThemeType):
        """设置主题（优化版，支持平滑切换）"""
        if theme_type not in self._themes:
            logger.warning(f"Unknown theme type: {theme_type}")
            return
        
        # 如果是同一主题，无需切换
        if theme_type == self._current_theme:
            logger.debug(f"Theme already set to: {theme_type.value}")
            return
        
        self._current_theme = theme_type
        theme_data = self._themes[theme_type]
        
        try:
            # 获取应用实例
            app = QApplication.instance()
            if not app:
                logger.error("QApplication instance not found")
                return
            
            # 预加载样式表（如果还没有缓存）
            stylesheet = theme_data["stylesheet"]
            if not stylesheet:
                logger.error(f"Empty stylesheet for theme: {theme_type.value}")
                return
            
            # 应用样式表 - 一次性应用，避免闪烁
            app.setStyleSheet(stylesheet)
            
            # 强制刷新所有Widget
            for widget in app.allWidgets():
                if widget:
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                    widget.update()
            
            # 发出主题变更信号
            self.themeChanged.emit(theme_type.value)
            
            logger.info(f"Theme successfully changed to: {theme_data['name']}")
            
        except Exception as e:
            logger.error(f"Failed to apply theme {theme_type.value}: {e}")
            # 如果切换失败，尝试回退到之前的主题
            self._current_theme = ThemeType.DARK if theme_type != ThemeType.DARK else ThemeType.LIGHT
    
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
