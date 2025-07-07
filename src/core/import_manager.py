"""
导入管理器
负责从各种格式导入内容到项目中
"""

import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.project import ProjectManager, DocumentType

from core.project import DocumentType  # 直接导入用于运行时

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
    
    def _import_from_text(self, options: ImportOptions) -> bool:
        """从纯文本导入"""
        try:
            # 读取文件内容
            with open(options.input_path, 'r', encoding=options.encoding) as f:
                content = f.read()
            
            # 如果需要创建新项目
            if options.create_project:
                project_name = options.project_name or options.input_path.stem
                if not self._project_manager.create_project(project_name):
                    self.importError.emit("创建项目失败")
                    return False
            
            # 如果不分割章节，作为单个文档导入
            if not options.split_chapters:
                doc_name = options.input_path.stem
                doc = self._project_manager.add_document(
                    name=doc_name,
                    doc_type=DocumentType.SCENE,
                    parent_id=None
                )
                if doc:
                    # 更新文档内容
                    self._project_manager.update_document(doc.id, content=content)
                    self.importCompleted.emit(1)
                    return True
                else:
                    self.importError.emit("创建文档失败")
                    return False
            
            # 分割章节
            chapters = self._split_chapters(content, options.chapter_pattern)
            total = len(chapters)
            
            # 创建章节文档
            imported_count = 0
            for i, (title, chapter_content) in enumerate(chapters):
                self.importProgress.emit(i + 1, total)
                
                # 创建章节
                doc = self._project_manager.add_document(
                    name=title,
                    doc_type=DocumentType.CHAPTER,
                    parent_id=None
                )
                
                if doc:
                    # 更新文档内容
                    self._project_manager.update_document(doc.id, content=chapter_content)
                    imported_count += 1
                else:
                    logger.warning(f"创建章节失败: {title}")
            
            self.importCompleted.emit(imported_count)
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"导入文本失败: {e}")
            self.importError.emit(f"导入文本失败: {e}")
            return False
    
    def _import_from_markdown(self, options: ImportOptions) -> bool:
        """从Markdown导入"""
        try:
            # 读取文件内容
            with open(options.input_path, 'r', encoding=options.encoding) as f:
                content = f.read()
            
            # 如果需要创建新项目
            if options.create_project:
                project_name = options.project_name or options.input_path.stem
                if not self._project_manager.create_project(project_name):
                    self.importError.emit("创建项目失败")
                    return False
            
            # 解析Markdown结构
            sections = self._parse_markdown_structure(content)
            total = len(sections)
            
            # 创建文档
            imported_count = 0
            parent_map = {}  # 用于跟踪父文档ID
            
            for i, (level, title, section_content) in enumerate(sections):
                self.importProgress.emit(i + 1, total)
                
                # 根据标题级别确定文档类型和父级
                if level == 1:
                    doc_type = DocumentType.ACT
                    parent_id = None
                elif level == 2:
                    doc_type = DocumentType.CHAPTER
                    parent_id = parent_map.get(1)  # 父级是最近的act
                else:
                    doc_type = DocumentType.SCENE
                    parent_id = parent_map.get(2) or parent_map.get(1)  # 父级是最近的chapter或act
                
                # 创建文档
                doc = self._project_manager.add_document(
                    name=title,
                    doc_type=doc_type,
                    parent_id=parent_id
                )
                
                if doc:
                    # 更新文档内容
                    self._project_manager.update_document(doc.id, content=section_content)
                    imported_count += 1
                    parent_map[level] = doc.id
                else:
                    logger.warning(f"创建文档失败: {title}")
            
            self.importCompleted.emit(imported_count)
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"导入Markdown失败: {e}")
            self.importError.emit(f"导入Markdown失败: {e}")
            return False
    
    def _import_from_docx(self, options: ImportOptions) -> bool:
        """从Word文档导入"""
        try:
            from docx import Document
        except ImportError:
            self.importError.emit("需要安装python-docx库: pip install python-docx")
            return False
        
        try:
            # 打开Word文档
            doc = Document(str(options.input_path))
            
            # 如果需要创建新项目
            if options.create_project:
                project_name = options.project_name or options.input_path.stem
                if not self._project_manager.create_project(project_name):
                    self.importError.emit("创建项目失败")
                    return False
            
            # 提取内容和结构
            sections = []
            current_section = None
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                
                # 检查是否是标题
                if para.style.name.startswith('Heading'):
                    # 保存之前的章节
                    if current_section:
                        sections.append(current_section)
                    
                    # 获取标题级别
                    level = int(para.style.name[-1]) if para.style.name[-1].isdigit() else 1
                    current_section = (level, text, [])
                else:
                    # 添加到当前章节内容
                    if current_section:
                        current_section[2].append(text)
                    else:
                        # 如果没有标题，创建默认章节
                        current_section = (1, "导入内容", [text])
            
            # 保存最后一个章节
            if current_section:
                sections.append(current_section)
            
            # 创建文档
            total = len(sections)
            imported_count = 0
            parent_map = {}
            
            for i, (level, title, paragraphs) in enumerate(sections):
                self.importProgress.emit(i + 1, total)
                
                # 合并段落
                content = '\n\n'.join(paragraphs)
                
                # 根据级别确定文档类型
                if level == 1:
                    doc_type = DocumentType.ACT
                    parent_id = None
                elif level == 2:
                    doc_type = DocumentType.CHAPTER
                    parent_id = parent_map.get(1)
                else:
                    doc_type = DocumentType.SCENE
                    parent_id = parent_map.get(2) or parent_map.get(1)
                
                # 创建文档
                doc = self._project_manager.add_document(
                    name=title,
                    doc_type=doc_type,
                    parent_id=parent_id
                )
                
                if doc:
                    # 更新文档内容
                    self._project_manager.update_document(doc.id, content=content)
                    imported_count += 1
                    parent_map[level] = doc.id
            
            self.importCompleted.emit(imported_count)
            return imported_count > 0
            
        except Exception as e:
            logger.error(f"导入Word文档失败: {e}")
            self.importError.emit(f"导入Word文档失败: {e}")
            return False
    
    def _split_chapters(self, content: str, pattern: str) -> List[Tuple[str, str]]:
        """分割章节"""
        chapters = []
        
        # 编译正则表达式
        chapter_regex = re.compile(pattern, re.MULTILINE)
        
        # 查找所有章节标题
        matches = list(chapter_regex.finditer(content))
        
        if not matches:
            # 没有找到章节，作为单个章节返回
            return [("导入内容", content)]
        
        # 提取每个章节
        for i, match in enumerate(matches):
            # 章节标题
            title_start = match.start()
            title_end = content.find('\n', title_start)
            if title_end == -1:
                title_end = len(content)
            title = content[title_start:title_end].strip()
            
            # 章节内容
            content_start = title_end + 1
            if i < len(matches) - 1:
                content_end = matches[i + 1].start()
            else:
                content_end = len(content)
            
            chapter_content = content[content_start:content_end].strip()
            
            if title and chapter_content:
                chapters.append((title, chapter_content))
        
        return chapters
    
    def _parse_markdown_structure(self, content: str) -> List[Tuple[int, str, str]]:
        """解析Markdown结构"""
        sections = []
        lines = content.split('\n')
        
        current_section = None
        current_content = []
        
        for line in lines:
            # 检查是否是标题
            if line.startswith('#'):
                # 保存之前的章节
                if current_section:
                    sections.append((
                        current_section[0],
                        current_section[1],
                        '\n'.join(current_content).strip()
                    ))
                    current_content = []
                
                # 解析标题级别
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                current_section = (level, title)
            else:
                # 添加到内容
                current_content.append(line)
        
        # 保存最后一个章节
        if current_section:
            sections.append((
                current_section[0],
                current_section[1],
                '\n'.join(current_content).strip()
            ))
        
        return sections
    
    def _import_project(self, options: ImportOptions) -> bool:
        """导入项目文件"""
        # TODO: 实现项目导入功能
        self.importError.emit("项目导入功能尚未实现")
        return False