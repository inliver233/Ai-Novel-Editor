"""
项目管理核心模块
基于novelWriter的项目管理设计，实现Act-Chapter-Scene层次结构
重构后使用SQLite进行原子数据持久化。
"""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field, fields
from enum import Enum

from .database_manager import DatabaseManager
from .concepts import ConceptManager, Concept, ConceptType
from .config import Config
from .shared import Shared

logger = logging.getLogger(__name__)


class ProjectError(Exception):
    """项目相关异常基类"""
    pass

class ProjectLockError(ProjectError):
    """项目锁定异常"""
    pass

class ProjectCorruptedError(ProjectError):
    """项目损坏异常"""
    pass

class ProjectVersionError(ProjectError):
    """项目版本不兼容异常"""
    pass

class DocumentType(Enum):
    """文档类型枚举"""
    ROOT = "root"
    ACT = "act"
    CHAPTER = "chapter"
    SCENE = "scene"
    CHARACTER = "character"
    LOCATION = "location"
    ITEM = "item"
    CONCEPT = "concept"
    PLOT = "plot"
    NOTE = "note"


class DocumentStatus(Enum):
    """文档状态枚举"""
    NEW = "new"
    DRAFT = "draft"
    FIRST_DRAFT = "first_draft"
    SECOND_DRAFT = "second_draft"
    FINAL_DRAFT = "final_draft"
    FINISHED = "finished"


@dataclass
class ProjectDocument:
    """项目文档数据模型"""
    id: str
    parent_id: Optional[str]
    name: str
    doc_type: DocumentType
    status: DocumentStatus
    order: int
    content: str = ""
    word_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.content:
            self.word_count = len(self.content.split())

    def to_dict(self) -> Dict[str, Any]:
        """将文档对象转换为可序列化的字典"""
        data = asdict(self)
        data['doc_type'] = self.doc_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data

@dataclass
class ProjectData:
    """项目数据模型"""
    id: str
    name: str
    description: str
    author: str
    language: str
    project_path: str
    version: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    settings: Dict[str, Any] = field(default_factory=dict)
    documents: Dict[str, ProjectDocument] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将项目元数据转换为可序列化的字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'language': self.language,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'settings': self.settings,
            'version': self.version
        }


class ProjectManager:
    """项目管理器 - 使用SQLite进行持久化"""

    def __init__(self, config: 'Config', shared: 'Shared', concept_manager: 'ConceptManager'):
        self._config = config
        self._shared = shared
        self._concept_manager = concept_manager
        self._current_project: Optional[ProjectData] = None
        self._project_path: Optional[Path] = None
        self._db_manager: Optional[DatabaseManager] = None
        self._project_version = "2.0" # 升级版本号以反映新的存储结构
        logger.info("Project manager initialized with dependencies")
    
    def get_current_project(self) -> Optional[ProjectData]:
        return self._current_project
    
    def has_project(self) -> bool:
        """检查是否有打开的项目"""
        return self._current_project is not None
    
    def create_project(self, name: str, path: str, author: str = "",
                          description: str = "", language: str = "zh_CN") -> bool:
        """创建新项目"""
        project_path = Path(path)
        if project_path.exists() and any(project_path.iterdir()):
            logger.error(f"Directory not empty: {project_path}")
            return False

        try:
            project_path.mkdir(parents=True, exist_ok=True)
            self._project_path = project_path
            self._db_manager = DatabaseManager(str(project_path))

            project_data = ProjectData(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                author=author,
                language=language,
                project_path=str(project_path),
                settings=self._get_default_settings(),
                version=self._project_version
            )
            self._current_project = project_data
            self._create_default_documents()

            # 清空并创建默认概念
            self._concept_manager.reload_concepts() # 清空
            self._create_default_concepts()

            if self.save_project():
                self._shared.current_project_path = str(project_path)
                _add_to_recent_projects(str(project_path), self._config)
                
                # 触发项目变化信号（用于RAG服务初始化）
                self._shared.projectChanged.emit(str(project_path))
                
                # 延迟触发自动索引（异步）
                self._trigger_auto_indexing_async()
                
                logger.info(f"New project created: {name} at {path}")
                return True
        except Exception as e:
            logger.error(f"Failed to create project: {e}", exc_info=True)
            if project_path.exists():
                import shutil
                shutil.rmtree(project_path, ignore_errors=True)
        return False

    def open_project(self, path: str) -> bool:
        """打开项目"""
        project_path = Path(path)
        db_file = project_path / "project.db"
        if not db_file.exists():
            logger.error(f"Project database not found: {db_file}")
            return False

        try:
            self.close_project() # 关闭当前项目
            self._project_path = project_path
            self._db_manager = DatabaseManager(str(project_path))
            
            data = self._db_manager.load_project_data()
            if not data or 'metadata' not in data:
                raise ProjectCorruptedError("Project data is empty or metadata is missing.")

            self._current_project = self._dict_to_project(data['metadata'], data.get('documents', []))
            
            self._concept_manager.reload_concepts(data.get('concepts', []))

            self._shared.current_project_path = str(project_path)
            _add_to_recent_projects(str(project_path), self._config)
            
            # 触发项目变化信号（用于RAG服务初始化）
            self._shared.projectChanged.emit(str(project_path))
            
            # 延迟触发自动索引（异步）
            self._trigger_auto_indexing_async()
            
            logger.info(f"Project opened: {self._current_project.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to open project at {path}: {e}", exc_info=True)
            self.close_project()
            return False
    
    def save_project(self) -> bool:
        """保存当前项目到数据库"""
        if not self._current_project or not self._db_manager:
            logger.error("No project or database manager to save")
            return False

        try:
            self._current_project.updated_at = datetime.now()
            
            project_metadata = self._current_project.to_dict()
            documents_data = [doc.to_dict() for doc in self._current_project.documents.values()]
            
            concepts_data = self._concept_manager.get_all_concepts_as_dicts()

            full_data = {
                'metadata': project_metadata,
                'documents': documents_data,
                'concepts': concepts_data
            }
            
            self._db_manager.save_project_data(full_data)
            logger.info(f"Project saved: {self._current_project.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project: {e}", exc_info=True)
            raise # Re-raise the exception to signal failure

    def close_project(self) -> bool:
        """关闭当前项目"""
        if not self._current_project:
            return True
        
        try:
            self.save_project()
        except Exception as e:
            logger.error(f"Error during project save on close: {e}", exc_info=True)
        finally:
            if self._db_manager:
                self._db_manager.close()
            self._current_project = None
            self._project_path = None
            self._db_manager = None
            self._shared.current_project_path = None
            self._concept_manager.reload_concepts() # Clear concepts from memory
            logger.info("Project closed.")
        return True
    
    def add_document(self, name: str, doc_type: DocumentType, parent_id: Optional[str] = None, save: bool = True) -> Optional[ProjectDocument]:
        """添加文档"""
        if not self._current_project: return None
        
        order = len([d for d in self._current_project.documents.values() if d.parent_id == parent_id])
        doc_id = str(uuid.uuid4())
        
        document = ProjectDocument(
            id=doc_id, parent_id=parent_id, name=name,
            doc_type=doc_type, status=DocumentStatus.NEW, order=order
        )
        
        # 先在内存中添加
        self._current_project.documents[doc_id] = document
        logger.info(f"Document '{name}' ({doc_type.value}) added to memory.")

        if save:
            try:
                self.save_project()
            except Exception as e:
                # 如果保存失败，从内存中移除刚刚添加的文档以回滚状态
                logger.error(f"Save failed after adding document. Rolling back memory state for doc id {doc_id}.")
                if doc_id in self._current_project.documents:
                    del self._current_project.documents[doc_id]
                raise e # 重新抛出异常，让调用者知道失败了

        return document

    def remove_document(self, doc_id: str, save: bool = True) -> bool:
        """移除文档及其所有子文档"""
        if not self._current_project or doc_id not in self._current_project.documents:
            return False
        
        docs_to_remove = {doc_id}
        children_queue = [doc_id]
        while children_queue:
            parent = children_queue.pop(0)
            children = [d.id for d in self._current_project.documents.values() if d.parent_id == parent]
            docs_to_remove.update(children)
            children_queue.extend(children)
            
        for id_to_remove in docs_to_remove:
            if id_to_remove in self._current_project.documents:
                del self._current_project.documents[id_to_remove]
        
        logger.info(f"Removed document {doc_id} and its children.")
        
        # 删除RAG索引（如果启用）
        try:
            # 通过共享对象获取AI管理器
            if hasattr(self._shared, 'ai_manager') and self._shared.ai_manager:
                ai_manager = self._shared.ai_manager
                if hasattr(ai_manager, 'delete_document_index'):
                    for id_to_remove in docs_to_remove:
                        ai_manager.delete_document_index(id_to_remove)
                        logger.info(f"Deleted RAG index for document: {id_to_remove}")
        except Exception as e:
            logger.error(f"Failed to delete RAG index: {e}")
            # 不影响文档删除操作，只记录错误
        
        if save:
            self.save_project()
        return True

    def update_document(self, doc_id: str, save: bool = True, **kwargs) -> Optional[ProjectDocument]:
        """更新文档属性"""
        if not self._current_project or doc_id not in self._current_project.documents:
            return None
        
        doc = self._current_project.documents[doc_id]
        has_changed = False
        original_data = doc.to_dict()

        for key, value in kwargs.items():
            if hasattr(doc, key):
                # 特殊处理枚举类型
                if key == 'doc_type' and isinstance(value, str): value = DocumentType(value)
                if key == 'status' and isinstance(value, str): value = DocumentStatus(value)
                
                if getattr(doc, key) != value:
                    setattr(doc, key, value)
                    has_changed = True

        if has_changed:
            doc.updated_at = datetime.now()
            if 'content' in kwargs:
                doc.word_count = len(doc.content.split()) if doc.content else 0
            if save:
                try:
                    self.save_project()
                    # 发出文档保存信号以触发自动索引
                    if 'content' in kwargs and self._shared:
                        self._shared.documentSaved.emit(doc_id, doc.content)
                        logger.debug(f"文档保存信号已发出: {doc_id}")
                except Exception as e:
                    logger.error(f"Save failed after updating document. Rolling back memory state for doc id {doc_id}.")
                    # 恢复原始数据
                    for key, value in original_data.items():
                        if key in kwargs: # 只恢复被尝试修改的字段
                             setattr(doc, key, value)
                    raise e
            logger.info(f"Document updated: {doc.name}")
        return doc

    def get_document(self, doc_id: str) -> Optional[ProjectDocument]:
        if self._current_project:
            return self._current_project.documents.get(doc_id)
        return None

    def get_all_documents(self) -> Dict[str, Dict[str, str]]:
        """获取所有文档的信息"""
        if not self._current_project:
            return {}
        
        all_docs = {}
        for doc_id, doc in self._current_project.documents.items():
            all_docs[doc_id] = {
                'title': doc.name,
                'type': doc.doc_type.value,
                'status': doc.status.value
            }
        return all_docs

    def get_document_content(self, doc_id: str) -> str:
        """获取文档内容"""
        if not self._current_project:
            return ""
        
        doc = self._current_project.documents.get(doc_id)
        if doc:
            return doc.content
        return ""

    def get_children(self, parent_id: Optional[str] = None) -> List[ProjectDocument]:
        if not self._current_project: return []
        children = [d for d in self._current_project.documents.values() if d.parent_id == parent_id]
        return sorted(children, key=lambda x: x.order)

    def get_document_tree(self) -> List[Dict[str, Any]]:
        """获取文档树结构，用于UI显示"""
        if not self._current_project:
            return []
        
        def build_tree(parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
            children = self.get_children(parent_id)
            tree = []
            for doc in children:
                node = {
                    'document': doc,
                    'children': build_tree(doc.id)
                }
                tree.append(node)
            return tree
        
        return build_tree()
    
    def move_document(self, doc_id: str, direction: int) -> bool:
        """移动文档顺序
        Args:
            doc_id: 文档ID
            direction: 移动方向 (-1上移, 1下移)
        Returns:
            bool: 移动是否成功
        """
        try:
            if not self._current_project:
                return False
            
            doc = self.get_document(doc_id)
            if not doc:
                logger.error(f"找不到文档: {doc_id}")
                return False
            
            # 获取同级文档
            siblings = self.get_children(doc.parent_id)
            if len(siblings) <= 1:
                logger.info("只有一个同级文档，无法移动")
                return False
            
            # 找到当前文档在同级中的位置
            current_index = -1
            for i, sibling in enumerate(siblings):
                if sibling.id == doc_id:
                    current_index = i
                    break
            
            if current_index == -1:
                logger.error(f"在同级文档中找不到文档: {doc_id}")
                return False
            
            # 计算新位置
            new_index = current_index + direction
            if new_index < 0 or new_index >= len(siblings):
                logger.info("已经到达边界，无法继续移动")
                return False
            
            # 交换order值
            target_sibling = siblings[new_index]
            
            # 临时保存order值
            old_doc_order = doc.order
            old_target_order = target_sibling.order
            
            # 更新order值
            self.update_document(doc.id, order=old_target_order, save=False)
            self.update_document(target_sibling.id, order=old_doc_order, save=False)
            
            # 保存项目
            self.save_project()
            
            logger.info(f"成功移动文档: {doc.name} (方向: {direction})")
            return True
            
        except Exception as e:
            logger.error(f"移动文档时发生错误: {e}")
            return False

    def _dict_to_project(self, metadata: Dict[str, Any], documents_data: List[Dict[str, Any]]) -> ProjectData:
        """从字典重建ProjectData对象，增强了健壮性"""
        
        project_version = metadata.get('version', '1.0')
        if project_version < self._project_version:
            logger.warning(f"Opening project with old version {project_version}. Current version is {self._project_version}.")

        def safe_iso_to_datetime(iso_string: Optional[str]) -> datetime:
            if isinstance(iso_string, str):
                try:
                    return datetime.fromisoformat(iso_string)
                except (ValueError, TypeError):
                    pass
            return datetime.now()

        metadata['created_at'] = safe_iso_to_datetime(metadata.get('created_at'))
        metadata['updated_at'] = safe_iso_to_datetime(metadata.get('updated_at'))

        documents = {}
        doc_expected_keys = {f.name for f in fields(ProjectDocument)}
        for doc_dict in documents_data:
            try:
                doc_dict['created_at'] = safe_iso_to_datetime(doc_dict.get('created_at'))
                doc_dict['updated_at'] = safe_iso_to_datetime(doc_dict.get('updated_at'))
                doc_dict['doc_type'] = DocumentType(doc_dict['doc_type'])
                doc_dict['status'] = DocumentStatus(doc_dict['status'])
                
                filtered_doc_dict = {k: v for k, v in doc_dict.items() if k in doc_expected_keys}
                
                doc = ProjectDocument(**filtered_doc_dict)
                documents[doc.id] = doc
            except (ValueError, TypeError) as e:
                logger.error(f"Skipping corrupted document {doc_dict.get('id')}: {e}", exc_info=True)
                continue
            
        project_data = ProjectData(
            id=metadata['id'],
            name=metadata['name'],
            description=metadata.get('description', ''),
            author=metadata.get('author', ''),
            language=metadata.get('language', 'zh_CN'),
            project_path=str(self._project_path),
            version=project_version,
            created_at=metadata['created_at'],
            updated_at=metadata['updated_at'],
            settings=metadata.get('settings', {}),
            documents=documents
        )
        return project_data

    def _get_default_settings(self) -> Dict[str, Any]:
        return {
            "auto_save": True, "auto_save_interval": 300,
            "backup_enabled": True, "backup_count": 5
        }

    def _create_default_documents(self):
        """创建默认文档结构"""
        if not self._current_project: return

        novel_root = self.add_document("小说", DocumentType.ROOT, None, save=False)
        self.add_document("角色", DocumentType.ROOT, None, save=False)
        self.add_document("世界观", DocumentType.ROOT, None, save=False)

        if novel_root:
            act1 = self.add_document("第一幕", DocumentType.ACT, novel_root.id, save=False)
            if act1:
                chapter1 = self.add_document("第一章", DocumentType.CHAPTER, act1.id, save=False)
                if chapter1:
                    self.add_document("开场", DocumentType.SCENE, chapter1.id, save=False)

    def _create_default_concepts(self):
        """创建默认概念"""
        self._concept_manager.create_concept("李明", ConceptType.CHARACTER, description="男主角")
        self._concept_manager.create_concept("王小雨", ConceptType.CHARACTER, description="女主角")
        self._concept_manager.create_concept("咖啡厅", ConceptType.LOCATION, description="他们相遇的地方")

    def _trigger_auto_indexing_async(self):
        """智能自动索引（只索引需要索引的文档）"""
        logger.info("开始智能自动索引检查...")
        
        # 启动后台线程进行智能索引
        from PyQt6.QtCore import QThread
        
        class SmartIndexWorker(QThread):
            def __init__(self, project_manager):
                super().__init__()
                self.project_manager = project_manager
                
            def run(self):
                try:
                    # 延迟3秒，让界面完全加载
                    import time
                    time.sleep(3)
                    
                    logger.info("[AUTO_INDEX] 开始智能索引检查...")
                    
                    # 通过shared获取AI管理器
                    if hasattr(self.project_manager._shared, 'ai_manager') and self.project_manager._shared.ai_manager:
                        ai_manager = self.project_manager._shared.ai_manager
                        
                        # 检查RAG服务是否可用
                        if not hasattr(ai_manager, 'rag_service') or not ai_manager.rag_service:
                            logger.info("[AUTO_INDEX] RAG服务不可用，跳过自动索引")
                            return
                            
                        # 获取所有需要索引的文档
                        unindexed_docs = []
                        all_docs = self.project_manager.get_all_documents()
                        
                        logger.info(f"[AUTO_INDEX] 检查 {len(all_docs)} 个文档的索引状态...")
                        
                        for doc_id, doc_info in all_docs.items():
                            # 跳过空文档
                            content = self.project_manager.get_document_content(doc_id)
                            if not content or len(content.strip()) < 50:
                                logger.debug(f"[AUTO_INDEX] 跳过空文档: {doc_info.get('title', doc_id)}")
                                continue
                                
                            # 检查是否已索引
                            if ai_manager.rag_service._vector_store:
                                is_indexed = ai_manager.rag_service._vector_store.document_exists(doc_id)
                                if not is_indexed:
                                    unindexed_docs.append((doc_id, content, doc_info.get('title', doc_id)))
                                    logger.info(f"[AUTO_INDEX] 发现未索引文档: {doc_info.get('title', doc_id)}")
                                else:
                                    logger.debug(f"[AUTO_INDEX] 文档已索引: {doc_info.get('title', doc_id)}")
                        
                        if unindexed_docs:
                            logger.info(f"[AUTO_INDEX] 开始自动索引 {len(unindexed_docs)} 个文档...")
                            
                            for i, (doc_id, content, title) in enumerate(unindexed_docs):
                                logger.info(f"[AUTO_INDEX] 正在索引 ({i+1}/{len(unindexed_docs)}): {title}")
                                
                                try:
                                    # 使用优化的同步索引方法
                                    if hasattr(ai_manager, 'index_document_sync'):
                                        success = ai_manager.index_document_sync(doc_id, content)
                                        if success:
                                            logger.info(f"[AUTO_INDEX] 索引成功: {title}")
                                        else:
                                            logger.warning(f"[AUTO_INDEX] 索引失败: {title}")
                                    else:
                                        logger.warning(f"[AUTO_INDEX] index_document_sync方法不可用")
                                        break
                                        
                                except Exception as e:
                                    logger.error(f"[AUTO_INDEX] 索引文档异常 {title}: {e}")
                                    continue
                            
                            logger.info(f"[AUTO_INDEX] 自动索引完成")
                        else:
                            logger.info("[AUTO_INDEX] 所有文档均已索引，无需重新索引")
                    else:
                        logger.info("[AUTO_INDEX] AI管理器不可用，跳过自动索引")
                        
                except Exception as e:
                    logger.error(f"[AUTO_INDEX] 自动索引过程异常: {e}")
                    import traceback
                    logger.error(f"[AUTO_INDEX] 异常详情: {traceback.format_exc()}")
        
        # 启动智能索引工作线程
        self._smart_index_worker = SmartIndexWorker(self)
        self._smart_index_worker.start()
        logger.info("智能自动索引线程已启动")


def _add_to_recent_projects(project_path: str, config: 'Config'):
    """添加到最近项目列表"""
    try:
        recent_projects = config.get('app', 'recent_projects', [])
        if not isinstance(recent_projects, list): recent_projects = []
        if project_path in recent_projects: recent_projects.remove(project_path)
        recent_projects.insert(0, project_path)
        config.set('app', 'recent_projects', recent_projects[:10])
        config.save()
    except Exception as e:
        logger.error(f"Failed to add to recent projects: {e}")


