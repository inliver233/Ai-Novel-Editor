"""
导出管理器
负责将项目导出为各种格式（文本、Word、PDF、HTML等）
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .import_export.project.docx import export_project_to_docx
from .import_export.project.html import export_project_to_html
from .import_export.project.markdown import export_project_to_markdown
from .import_export.project.pdf import export_project_to_pdf
from .import_export.project.text import export_project_to_text
from .import_export.project.traversal import collect_novel_documents

if TYPE_CHECKING:
    from core.project import ProjectDocument, ProjectManager

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """导出格式枚举"""
    TEXT = "text"
    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
    EPUB = "epub"


@dataclass
class ExportOptions:
    """导出选项"""
    format: ExportFormat
    output_path: Path
    include_metadata: bool = True
    include_comments: bool = False
    preserve_formatting: bool = True
    chapter_break: str = "\n\n---\n\n"  # 章节分隔符
    encoding: str = "utf-8"
    title: Optional[str] = None
    author: Optional[str] = None


class ExportManager(QObject):
    """导出管理器"""
    
    # 信号
    exportStarted = pyqtSignal(str)  # 导出开始
    exportProgress = pyqtSignal(int, int)  # 当前进度, 总数
    exportCompleted = pyqtSignal(str)  # 导出完成
    exportError = pyqtSignal(str)  # 导出错误
    
    def __init__(self, project_manager: 'ProjectManager'):
        super().__init__()
        self._project_manager = project_manager
        
    def export_project(self, options: ExportOptions) -> bool:
        """导出项目"""
        try:
            self.exportStarted.emit(f"开始导出为 {options.format.value} 格式...")
            
            # 获取当前项目
            project = self._project_manager.get_current_project()
            if not project:
                self.exportError.emit("没有打开的项目")
                return False
            
            # 根据格式选择导出方法
            if options.format == ExportFormat.TEXT:
                return self._export_to_text(project, options)
            elif options.format == ExportFormat.MARKDOWN:
                return self._export_to_markdown(project, options)
            elif options.format == ExportFormat.DOCX:
                return self._export_to_docx(project, options)
            elif options.format == ExportFormat.PDF:
                return self._export_to_pdf(project, options)
            elif options.format == ExportFormat.HTML:
                return self._export_to_html(project, options)
            else:
                self.exportError.emit(f"不支持的导出格式: {options.format.value}")
                return False
                
        except Exception as e:
            logger.error(f"导出失败: {e}")
            self.exportError.emit(str(e))
            return False
    
    def _collect_documents(self, project: Any) -> List['ProjectDocument']:
        """收集要导出的文档（按顺序）"""
        return collect_novel_documents(project)
    
    def _export_to_text(self, project: Any, options: ExportOptions) -> bool:
        """导出为纯文本"""
        try:
            export_project_to_text(
                project,
                options.output_path,
                include_metadata=options.include_metadata,
                chapter_break=options.chapter_break,
                encoding=options.encoding,
                title=options.title,
                author=options.author,
                progress_cb=lambda current, total: self.exportProgress.emit(current, total),
            )

            self.exportCompleted.emit(str(options.output_path))
            return True
            
        except Exception as e:
            logger.error(f"导出文本失败: {e}")
            self.exportError.emit(f"导出文本失败: {e}")
            return False
    
    def _export_to_markdown(self, project: Any, options: ExportOptions) -> bool:
        """导出为Markdown格式"""
        try:
            export_project_to_markdown(
                project,
                options.output_path,
                include_metadata=options.include_metadata,
                encoding=options.encoding,
                title=options.title,
                author=options.author,
                progress_cb=lambda current, total: self.exportProgress.emit(current, total),
            )

            self.exportCompleted.emit(str(options.output_path))
            return True
            
        except Exception as e:
            logger.error(f"导出Markdown失败: {e}")
            self.exportError.emit(f"导出Markdown失败: {e}")
            return False
    
    def _export_to_docx(self, project: Any, options: ExportOptions) -> bool:
        """导出为Word文档"""
        try:
            export_project_to_docx(
                project,
                options.output_path,
                include_metadata=options.include_metadata,
                title=options.title,
                author=options.author,
                progress_cb=lambda current, total: self.exportProgress.emit(current, total),
            )

            self.exportCompleted.emit(str(options.output_path))
            return True
            
        except Exception as e:
            logger.error(f"导出Word文档失败: {e}")
            self.exportError.emit(f"导出Word文档失败: {e}")
            return False
    
    def _export_to_pdf(self, project: Any, options: ExportOptions) -> bool:
        """导出为PDF（通过HTML转换）"""
        try:
            export_project_to_pdf(
                project,
                options.output_path,
                include_metadata=options.include_metadata,
                encoding=options.encoding,
                title=options.title,
                author=options.author,
                progress_cb=lambda current, total: self.exportProgress.emit(current, total),
            )

            self.exportCompleted.emit(str(options.output_path))
            return True
        except Exception as e:
            logger.error(f"导出PDF失败: {e}")
            self.exportError.emit(f"导出PDF失败: {e}")
            return False
    
    def _export_to_html(self, project: Any, options: ExportOptions) -> bool:
        """导出为HTML"""
        try:
            export_project_to_html(
                project,
                options.output_path,
                include_metadata=options.include_metadata,
                encoding=options.encoding,
                title=options.title,
                author=options.author,
                progress_cb=lambda current, total: self.exportProgress.emit(current, total),
            )

            self.exportCompleted.emit(str(options.output_path))
            return True
            
        except Exception as e:
            logger.error(f"导出HTML失败: {e}")
            self.exportError.emit(f"导出HTML失败: {e}")
            return False
