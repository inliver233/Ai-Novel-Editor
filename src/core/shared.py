"""
共享数据管理系统
基于novelWriter的SHARED设计，管理全局共享状态和数据
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from .config import Config


logger = logging.getLogger(__name__)


class Shared(QObject):
    """全局共享数据管理器"""
    
    # 信号定义
    projectChanged = pyqtSignal(str)  # 项目变化信号
    documentChanged = pyqtSignal(str)  # 文档变化信号
    documentSaved = pyqtSignal(str, str)  # 文档保存信号 (document_id, content)
    themeChanged = pyqtSignal(str)  # 主题变化信号
    configChanged = pyqtSignal(str, str)  # 配置变化信号
    
    def __init__(self, config: Config):
        super().__init__()
        self._config = config
        
        # 当前状态
        self._current_project_path: Optional[Path] = None
        self._current_document_id: Optional[str] = None
        self._current_theme: str = self._config.get("ui", "theme", "dark")
        
        # 项目相关数据
        self._project_data: Dict[str, Any] = {}
        self._document_cache: Dict[str, str] = {}
        
        # 应用状态
        self._is_modified: bool = False
        self._auto_save_enabled: bool = True
        
        # AI管理器引用（延迟设置）
        self._ai_manager = None
        
        logger.info("Shared data manager initialized")
    
    @property
    def current_project_path(self) -> Optional[Path]:
        """当前项目路径"""
        return self._current_project_path
    
    @current_project_path.setter
    def current_project_path(self, path: Optional[Path]):
        """设置当前项目路径"""
        if self._current_project_path != path:
            self._current_project_path = path
            if path:
                self.projectChanged.emit(str(path))
                logger.info(f"Current project changed to: {path}")
    
    @property
    def current_document_id(self) -> Optional[str]:
        """当前文档ID"""
        return self._current_document_id
    
    @current_document_id.setter
    def current_document_id(self, doc_id: Optional[str]):
        """设置当前文档ID"""
        if self._current_document_id != doc_id:
            self._current_document_id = doc_id
            if doc_id:
                self.documentChanged.emit(doc_id)
                logger.info(f"Current document changed to: {doc_id}")
    
    @property
    def current_theme(self) -> str:
        """当前主题"""
        return self._current_theme
    
    @current_theme.setter
    def current_theme(self, theme: str):
        """设置当前主题"""
        if self._current_theme != theme:
            self._current_theme = theme
            self._config.set("ui", "theme", theme)
            self.themeChanged.emit(theme)
            logger.info(f"Theme changed to: {theme}")
    
    @property
    def is_modified(self) -> bool:
        """是否有未保存的修改"""
        return self._is_modified
    
    @is_modified.setter
    def is_modified(self, modified: bool):
        """设置修改状态"""
        self._is_modified = modified
    
    @property
    def auto_save_enabled(self) -> bool:
        """自动保存是否启用"""
        return self._auto_save_enabled
    
    @auto_save_enabled.setter
    def auto_save_enabled(self, enabled: bool):
        """设置自动保存状态"""
        self._auto_save_enabled = enabled
    
    @property
    def ai_manager(self):
        """获取AI管理器引用"""
        return self._ai_manager
    
    @ai_manager.setter
    def ai_manager(self, manager):
        """设置AI管理器引用"""
        self._ai_manager = manager
    
    def get_project_data(self, key: str, default: Any = None) -> Any:
        """获取项目数据"""
        return self._project_data.get(key, default)
    
    def set_project_data(self, key: str, value: Any):
        """设置项目数据"""
        self._project_data[key] = value
    
    def clear_project_data(self):
        """清空项目数据"""
        self._project_data.clear()
        self._document_cache.clear()
        self._current_document_id = None
        self._is_modified = False
    
    def cache_document(self, doc_id: str, content: str):
        """缓存文档内容"""
        self._document_cache[doc_id] = content
    
    def get_cached_document(self, doc_id: str) -> Optional[str]:
        """获取缓存的文档内容"""
        return self._document_cache.get(doc_id)
    
    def remove_cached_document(self, doc_id: str):
        """移除缓存的文档"""
        if doc_id in self._document_cache:
            del self._document_cache[doc_id]
    
    def get_app_data_dir(self) -> Path:
        """获取应用数据目录"""
        return self._config.config_dir
    
    def get_temp_dir(self) -> Path:
        """获取临时目录"""
        temp_dir = self.get_app_data_dir() / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    def get_backup_dir(self) -> Path:
        """获取备份目录"""
        backup_dir = self.get_app_data_dir() / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir


# 全局共享实例
_shared_instance = None


