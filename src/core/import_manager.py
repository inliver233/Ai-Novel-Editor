"""
导入管理器
负责从各种格式导入内容到项目中
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from core.project import DocumentType, ProjectManager

from core.project import DocumentType  # 直接导入用于运行时
from .import_export.project.markdown import import_novel_from_markdown
from .import_export.project.text import import_novel_from_text
from .import_export.project.docx import import_novel_from_docx

logger = logging.getLogger(__name__)


class ImportFormat(Enum):
    """导入格式枚举"""
    TEXT = "text"
    MARKDOWN = "markdown"
    DOCX = "docx"
    PROJECT = "project"  # 导入其他项目


@dataclass
class ImportOptions:
    """导入选项"""
    format: ImportFormat
    input_path: Path
    encoding: str = "utf-8"
    split_chapters: bool = True  # 是否自动分割章节
    chapter_pattern: str = r"^第[一二三四五六七八九十\d]+章"  # 章节识别模式
    create_project: bool = False  # 是否创建新项目
    project_name: Optional[str] = None
    project_path: Optional[Path] = None  # create_project=True 时的新项目目录（可选）


class ImportManager(QObject):
    """导入管理器"""
    
    # 信号
    importStarted = pyqtSignal(str)  # 导入开始
    importProgress = pyqtSignal(int, int)  # 当前进度, 总数
    importCompleted = pyqtSignal(int)  # 导入完成，返回导入的文档数
    importError = pyqtSignal(str)  # 导入错误
    
    def __init__(self, project_manager: 'ProjectManager'):
        super().__init__()
        self._project_manager = project_manager
        
    def import_content(self, options: ImportOptions) -> bool:
        """导入内容"""
        try:
            self.importStarted.emit(f"开始从 {options.format.value} 格式导入...")
            
            # 检查文件是否存在
            if not options.input_path.exists():
                self.importError.emit(f"文件不存在: {options.input_path}")
                return False
            
            # 根据格式选择导入方法
            if options.format == ImportFormat.TEXT:
                return self._import_from_text(options)
            elif options.format == ImportFormat.MARKDOWN:
                return self._import_from_markdown(options)
            elif options.format == ImportFormat.DOCX:
                return self._import_from_docx(options)
            elif options.format == ImportFormat.PROJECT:
                return self._import_project(options)
            else:
                self.importError.emit(f"不支持的导入格式: {options.format.value}")
                return False
                
        except Exception as e:
            logger.error(f"导入失败: {e}")
            self.importError.emit(str(e))
            return False
    
    def _create_project_if_requested(self, options: ImportOptions) -> bool:
        if not options.create_project:
            return True

        project_name = options.project_name or options.input_path.stem
        project_dir = options.project_path
        if project_dir is None:
            project_dir = options.input_path.parent / project_name
            if project_dir.exists() and any(project_dir.iterdir()):
                project_dir = options.input_path.parent / f"{project_name}_imported"

        if project_dir.exists() and any(project_dir.iterdir()):
            self.importError.emit(f"目标目录非空: {project_dir}")
            return False

        if not self._project_manager.create_project(project_name, str(project_dir)):
            self.importError.emit("创建项目失败")
            return False

        return True

    def _import_from_text(self, options: ImportOptions) -> bool:
        """从纯文本导入"""
        try:
            if not self._create_project_if_requested(options):
                return False

            imported_count = import_novel_from_text(
                self._project_manager,
                options.input_path,
                encoding=options.encoding,
                split_chapters=options.split_chapters,
                chapter_pattern=options.chapter_pattern,
                replace_existing=options.create_project,
                progress_cb=lambda current, total: self.importProgress.emit(current, total),
            )

            self.importCompleted.emit(imported_count)
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"导入文本失败: {e}")
            self.importError.emit(f"导入文本失败: {e}")
            return False
    
    def _import_from_markdown(self, options: ImportOptions) -> bool:
        """从Markdown导入"""
        try:
            if not self._create_project_if_requested(options):
                return False

            imported_count = import_novel_from_markdown(
                self._project_manager,
                options.input_path,
                encoding=options.encoding,
                replace_existing=options.create_project,
                progress_cb=lambda current, total: self.importProgress.emit(current, total),
            )

            self.importCompleted.emit(imported_count)
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"导入Markdown失败: {e}")
            self.importError.emit(f"导入Markdown失败: {e}")
            return False
    
    def _import_from_docx(self, options: ImportOptions) -> bool:
        """从Word文档导入"""
        try:
            if not self._create_project_if_requested(options):
                return False

            imported_count = import_novel_from_docx(
                self._project_manager,
                options.input_path,
                replace_existing=options.create_project,
                progress_cb=lambda current, total: self.importProgress.emit(current, total),
            )
            
            self.importCompleted.emit(imported_count)
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"导入Word文档失败: {e}")
            self.importError.emit(f"导入Word文档失败: {e}")
            return False
    
    def _import_project(self, options: ImportOptions) -> bool:
        """导入项目文件"""
        # TODO: 实现项目导入功能
        self.importError.emit("项目导入功能尚未实现")
        return False
