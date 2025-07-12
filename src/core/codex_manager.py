"""
Codex知识库管理系统
基于NovelCrafter的Codex设计，管理小说世界观的角色、地点、物品等元素
"""

import re
import uuid
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    HAS_QT = True
except ImportError:
    # 提供Qt的替代实现
    class QObject:
        def __init__(self):
            pass
    
    class pyqtSignal:
        def __init__(self, *args):
            pass
        def emit(self, *args):
            pass
        def connect(self, *args):
            pass
    HAS_QT = False

from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class CodexEntryType(Enum):
    """Codex条目类型枚举"""
    CHARACTER = "CHARACTER"     # 角色
    LOCATION = "LOCATION"       # 地点
    OBJECT = "OBJECT"          # 物品
    LORE = "LORE"              # 传说/背景设定
    SUBPLOT = "SUBPLOT"        # 子情节
    OTHER = "OTHER"            # 其他


@dataclass
class CodexEntry:
    """Codex条目数据类"""
    id: str
    title: str
    entry_type: CodexEntryType
    description: str = ""
    is_global: bool = False              # 是否为全局条目（自动包含在AI上下文中）
    track_references: bool = True        # 是否追踪引用
    aliases: List[str] = None           # 别名列表
    relationships: List[Dict[str, str]] = None  # 关系网络
    progression: List[Dict[str, Any]] = None    # 进展追踪
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.relationships is None:
            self.relationships = []
        if self.progression is None:
            self.progression = []
        if self.metadata is None:
            self.metadata = {}
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


@dataclass 
class CodexReference:
    """Codex引用数据类"""
    id: int
    codex_id: str
    document_id: str
    reference_text: str
    position_start: int
    position_end: int
    context_before: str = ""
    context_after: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_seen_at: str = ""
    deleted_at: str = ""
    access_count: int = 0
    modification_count: int = 0
    last_accessed_at: str = ""
    confidence_score: float = 1.0
    status: str = "active"
    validation_status: str = "pending"
    chapter_id: str = ""
    scene_order: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
        if not self.last_seen_at:
            self.last_seen_at = datetime.now().isoformat()


@dataclass
class ValidationResult:
    """数据验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class CodexManager(QObject):
    """Codex知识库管理器"""
    
    # 信号定义
    entryAdded = pyqtSignal(str)        # 条目添加信号
    entryUpdated = pyqtSignal(str)      # 条目更新信号
    entryDeleted = pyqtSignal(str)      # 条目删除信号
    referencesUpdated = pyqtSignal(str, int)  # 引用更新信号 (document_id, count)
    
    def __init__(self, database_manager: DatabaseManager):
        super().__init__()
        self.db_manager = database_manager
        self._entries: Dict[str, CodexEntry] = {}
        self._references: List[CodexReference] = []
        self._title_to_id: Dict[str, str] = {}  # 标题到ID的映射
        self._alias_to_id: Dict[str, str] = {}  # 别名到ID的映射
        
        # 引用检测的正则模式缓存
        self._reference_patterns: Dict[str, re.Pattern] = {}
        self._pattern_cache_version = 0
        
        self._load_data()
        logger.info("CodexManager initialized")

    def _validate_entry_data(self, title: str, entry_type: CodexEntryType, 
                           description: str = "", aliases: List[str] = None,
                           exclude_id: Optional[str] = None) -> ValidationResult:
        """
        验证条目数据
        
        Args:
            title: 条目标题
            entry_type: 条目类型
            description: 条目描述
            aliases: 别名列表
            exclude_id: 排除的条目ID（用于更新时排除自身）
            
        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []
        
        # 验证标题
        title = title.strip() if title else ""
        if not title:
            errors.append("标题不能为空")
        elif len(title) > 100:
            errors.append("标题长度不能超过100个字符")
        elif len(title) < 2:
            warnings.append("标题太短，建议至少2个字符")
        
        # 检查标题唯一性
        if title:
            existing_id = self._title_to_id.get(title.lower())
            if existing_id and existing_id != exclude_id:
                errors.append(f"标题 '{title}' 已存在，请使用不同的标题")
        
        # 验证条目类型
        if not isinstance(entry_type, CodexEntryType):
            errors.append("无效的条目类型")
        
        # 验证描述
        if description and len(description) > 5000:
            errors.append("描述长度不能超过5000个字符")
        
        # 验证别名
        if aliases:
            aliases = [alias.strip() for alias in aliases if alias.strip()]
            
            # 检查别名长度
            for alias in aliases:
                if len(alias) > 50:
                    errors.append(f"别名 '{alias}' 长度不能超过50个字符")
            
            # 检查别名唯一性
            for alias in aliases:
                alias_lower = alias.lower()
                
                # 检查别名是否与标题重复
                if alias_lower == title.lower():
                    errors.append(f"别名 '{alias}' 不能与标题相同")
                    continue
                
                # 检查别名是否与其他条目标题重复
                existing_title_id = self._title_to_id.get(alias_lower)
                if existing_title_id and existing_title_id != exclude_id:
                    existing_entry = self._entries.get(existing_title_id)
                    if existing_entry:
                        errors.append(f"别名 '{alias}' 与现有条目 '{existing_entry.title}' 的标题重复")
                
                # 检查别名是否与其他别名重复
                existing_alias_id = self._alias_to_id.get(alias_lower)
                if existing_alias_id and existing_alias_id != exclude_id:
                    existing_entry = self._entries.get(existing_alias_id)
                    if existing_entry:
                        errors.append(f"别名 '{alias}' 已被条目 '{existing_entry.title}' 使用")
            
            # 检查重复的别名
            seen_aliases = set()
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in seen_aliases:
                    errors.append(f"别名 '{alias}' 重复")
                else:
                    seen_aliases.add(alias_lower)
            
            # 别名数量检查
            if len(aliases) > 20:
                warnings.append("别名数量较多（超过20个），可能影响性能")
        
        # 业务逻辑验证
        if title:
            # 检查敏感词或保留词
            reserved_words = ["系统", "管理员", "默认", "未知", "空", "测试"]
            if title.lower() in [word.lower() for word in reserved_words]:
                warnings.append(f"标题 '{title}' 可能是保留词，建议使用其他名称")
            
            # 检查特殊字符
            import re
            if re.search(r'[<>:"/\\|?*\x00-\x1f]', title):
                errors.append("标题包含不允许的特殊字符")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_relationship_data(self, relationships: List[Dict[str, Any]]) -> ValidationResult:
        """验证关系数据"""
        errors = []
        warnings = []
        
        if not relationships:
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        for i, relationship in enumerate(relationships):
            prefix = f"关系{i+1}: "
            
            # 验证必需字段
            if 'target_id' not in relationship:
                errors.append(f"{prefix}缺少目标条目ID")
                continue
            
            if 'type' not in relationship:
                errors.append(f"{prefix}缺少关系类型")
                continue
            
            # 验证目标条目存在性
            target_id = relationship['target_id']
            if target_id not in self._entries:
                errors.append(f"{prefix}目标条目不存在")
            
            # 验证关系类型
            rel_type = relationship['type']
            if not rel_type or not rel_type.strip():
                errors.append(f"{prefix}关系类型不能为空")
            elif len(rel_type) > 50:
                errors.append(f"{prefix}关系类型长度不能超过50个字符")
            
            # 验证关系强度
            strength = relationship.get('strength', 1)
            if not isinstance(strength, int) or strength < 1 or strength > 5:
                errors.append(f"{prefix}关系强度必须是1-5之间的整数")
            
            # 验证备注长度
            notes = relationship.get('notes', '')
            if notes and len(notes) > 500:
                errors.append(f"{prefix}备注长度不能超过500个字符")
        
        # 检查重复关系
        seen_relations = set()
        for relationship in relationships:
            key = (relationship.get('target_id'), relationship.get('type'))
            if key in seen_relations:
                warnings.append(f"存在重复的关系: {relationship.get('type')}")
            else:
                seen_relations.add(key)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_progression_data(self, progression: List[Dict[str, Any]]) -> ValidationResult:
        """验证进展数据"""
        errors = []
        warnings = []
        
        if not progression:
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        for i, event in enumerate(progression):
            prefix = f"事件{i+1}: "
            
            # 验证必需字段
            if 'type' not in event or not event['type'].strip():
                errors.append(f"{prefix}缺少事件类型")
            
            if 'description' not in event or not event['description'].strip():
                errors.append(f"{prefix}缺少事件描述")
            
            # 验证字段长度
            if event.get('type') and len(event['type']) > 100:
                errors.append(f"{prefix}事件类型长度不能超过100个字符")
            
            if event.get('description') and len(event['description']) > 1000:
                errors.append(f"{prefix}事件描述长度不能超过1000个字符")
            
            if event.get('chapter') and len(event['chapter']) > 100:
                errors.append(f"{prefix}章节信息长度不能超过100个字符")
            
            # 验证重要性
            importance = event.get('importance', 1)
            if not isinstance(importance, int) or importance < 1 or importance > 5:
                errors.append(f"{prefix}重要性必须是1-5之间的整数")
            
            # 验证状态
            status = event.get('status', 'pending')
            if status not in ['pending', 'completed']:
                errors.append(f"{prefix}状态必须是'pending'或'completed'")
            
            # 验证时间格式
            timestamp = event.get('timestamp')
            if timestamp:
                try:
                    datetime.fromisoformat(timestamp.replace('T', ' ').replace('Z', ''))
                except ValueError:
                    warnings.append(f"{prefix}时间格式可能不正确")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _load_data(self):
        """从数据库加载Codex数据"""
        try:
            codex_data = self.db_manager.load_codex_data()
            
            # 加载条目
            for entry_data in codex_data.get('entries', []):
                entry_data['entry_type'] = CodexEntryType(entry_data['entry_type'])
                entry = CodexEntry(**entry_data)
                self._entries[entry.id] = entry
                
                # 更新映射
                self._title_to_id[entry.title.lower()] = entry.id
                for alias in entry.aliases:
                    if alias.strip():
                        self._alias_to_id[alias.lower().strip()] = entry.id
            
            # 加载引用
            for ref_data in codex_data.get('references', []):
                reference = CodexReference(**ref_data)
                self._references.append(reference)
            
            # 重建引用模式缓存
            self._rebuild_reference_patterns()
            
            logger.info(f"Loaded {len(self._entries)} codex entries and {len(self._references)} references")
            
        except Exception as e:
            logger.error(f"Error loading codex data: {e}")

    def _save_data(self):
        """
        批量保存Codex数据到数据库（仅用于初始化和完整重建）
        建议使用增量更新方法以获得更好的性能
        """
        try:
            entries_data = []
            for entry in self._entries.values():
                entry_dict = asdict(entry)
                entry_dict['entry_type'] = entry.entry_type.value
                entry_dict['updated_at'] = datetime.now().isoformat()
                entries_data.append(entry_dict)
            
            references_data = [asdict(ref) for ref in self._references]
            
            self.db_manager.save_codex_data(entries_data, references_data)
            logger.info("Codex data saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving codex data: {e}")

    def _save_entry_incremental(self, entry: CodexEntry) -> bool:
        """
        增量保存单个条目到数据库
        
        Args:
            entry: 要保存的条目
            
        Returns:
            bool: 保存是否成功
        """
        try:
            entry_dict = asdict(entry)
            entry_dict['entry_type'] = entry.entry_type.value
            entry_dict['updated_at'] = datetime.now().isoformat()
            
            return self.db_manager.insert_codex_entry(entry_dict)
        except Exception as e:
            logger.error(f"Error saving entry incrementally: {e}")
            return False

    def _update_entry_incremental(self, entry: CodexEntry) -> bool:
        """
        增量更新单个条目到数据库
        
        Args:
            entry: 要更新的条目
            
        Returns:
            bool: 更新是否成功
        """
        try:
            entry_dict = asdict(entry)
            entry_dict['entry_type'] = entry.entry_type.value
            entry_dict['updated_at'] = datetime.now().isoformat()
            
            return self.db_manager.update_codex_entry(entry.id, entry_dict)
        except Exception as e:
            logger.error(f"Error updating entry incrementally: {e}")
            return False

    def _delete_entry_incremental(self, entry_id: str) -> bool:
        """
        增量删除单个条目从数据库
        
        Args:
            entry_id: 要删除的条目ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            return self.db_manager.delete_codex_entry(entry_id)
        except Exception as e:
            logger.error(f"Error deleting entry incrementally: {e}")
            return False

    def add_entry(self, title: str, entry_type: CodexEntryType, 
                  description: str = "", is_global: bool = False,
                  aliases: List[str] = None) -> Optional[str]:
        """
        添加新的Codex条目
        
        Args:
            title: 条目标题
            entry_type: 条目类型
            description: 条目描述
            is_global: 是否为全局条目
            aliases: 别名列表
            
        Returns:
            str: 成功时返回条目ID，失败时返回None
            
        Raises:
            ValueError: 当数据验证失败时
        """
        # 数据验证
        validation_result = self._validate_entry_data(
            title=title,
            entry_type=entry_type,
            description=description,
            aliases=aliases or [],
            exclude_id=None  # 新建条目时不排除任何ID
        )
        
        if not validation_result.is_valid:
            logger.error(f"添加条目失败，验证错误: {validation_result.errors}")
            raise ValueError(f"数据验证失败: {'; '.join(validation_result.errors)}")
        
        entry_id = str(uuid.uuid4())
        
        entry = CodexEntry(
            id=entry_id,
            title=title.strip(),
            entry_type=entry_type,
            description=description.strip(),
            is_global=is_global,
            aliases=[alias.strip() for alias in (aliases or []) if alias.strip()]
        )
        
        self._entries[entry_id] = entry
        
        # 更新映射
        self._title_to_id[title.lower()] = entry_id
        for alias in entry.aliases:
            if alias.strip():
                self._alias_to_id[alias.lower().strip()] = entry_id
        
        # 重建引用模式
        self._rebuild_reference_patterns()
        
        # 增量保存数据
        if not self._save_entry_incremental(entry):
            logger.error(f"Failed to save entry {title} to database")
            # 如果保存失败，需要回滚内存状态
            del self._entries[entry_id]
            if title.lower() in self._title_to_id:
                del self._title_to_id[title.lower()]
            for alias in entry.aliases:
                if alias.lower().strip() in self._alias_to_id:
                    del self._alias_to_id[alias.lower().strip()]
            self._rebuild_reference_patterns()
            return None
        
        # 发送信号
        if HAS_QT:
            self.entryAdded.emit(entry_id)
        
        logger.info(f"Added codex entry: {title} ({entry_type.value})")
        return entry_id

    def update_entry(self, entry_id: str, **kwargs) -> bool:
        """
        更新Codex条目
        
        Args:
            entry_id: 条目ID
            **kwargs: 要更新的字段
            
        Returns:
            bool: 更新是否成功
            
        Raises:
            ValueError: 当数据验证失败时
        """
        if entry_id not in self._entries:
            logger.warning(f"Codex entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        # 准备验证数据
        title = kwargs.get('title', entry.title)
        entry_type = kwargs.get('entry_type', entry.entry_type)
        description = kwargs.get('description', entry.description)
        aliases = kwargs.get('aliases', entry.aliases)
        relationships = kwargs.get('relationships', entry.relationships)
        progression = kwargs.get('progression', entry.progression)
        
        # 验证基本数据
        validation_result = self._validate_entry_data(
            title=title,
            entry_type=entry_type,
            description=description,
            aliases=aliases,
            exclude_id=entry_id  # 更新时排除自身
        )
        
        if not validation_result.is_valid:
            logger.error(f"更新条目失败，验证错误: {validation_result.errors}")
            raise ValueError(f"数据验证失败: {'; '.join(validation_result.errors)}")
        
        # 验证关系数据
        if relationships is not None:
            relationship_validation = self._validate_relationship_data(relationships)
            if not relationship_validation.is_valid:
                logger.error(f"更新条目失败，关系验证错误: {relationship_validation.errors}")
                raise ValueError(f"关系数据验证失败: {'; '.join(relationship_validation.errors)}")
        
        # 验证进展数据
        if progression is not None:
            progression_validation = self._validate_progression_data(progression)
            if not progression_validation.is_valid:
                logger.error(f"更新条目失败，进展验证错误: {progression_validation.errors}")
                raise ValueError(f"进展数据验证失败: {'; '.join(progression_validation.errors)}")
        
        # 记录原始状态以便回滚
        old_title = entry.title
        old_aliases = entry.aliases[:]
        old_updated_at = entry.updated_at
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(entry, key):
                if key == 'title' and value:
                    setattr(entry, key, value.strip())
                elif key == 'description' and value:
                    setattr(entry, key, value.strip())
                elif key == 'aliases' and value:
                    setattr(entry, key, [alias.strip() for alias in value if alias.strip()])
                else:
                    setattr(entry, key, value)
        
        entry.updated_at = datetime.now().isoformat()
        
        # 更新映射
        if entry.title != old_title:
            if old_title.lower() in self._title_to_id:
                del self._title_to_id[old_title.lower()]
            self._title_to_id[entry.title.lower()] = entry_id
        
        # 更新别名映射
        for old_alias in old_aliases:
            if old_alias.lower().strip() in self._alias_to_id:
                del self._alias_to_id[old_alias.lower().strip()]
        
        for new_alias in entry.aliases:
            if new_alias.strip():
                self._alias_to_id[new_alias.lower().strip()] = entry_id
        
        # 重建引用模式
        self._rebuild_reference_patterns()
        
        # 增量更新数据
        if not self._update_entry_incremental(entry):
            logger.error(f"Failed to update entry {entry.title} in database")
            # 如果更新失败，需要回滚内存状态
            entry.title = old_title
            entry.aliases = old_aliases
            entry.updated_at = old_updated_at
            
            # 恢复映射
            if old_title.lower() != entry.title.lower():
                if entry.title.lower() in self._title_to_id:
                    del self._title_to_id[entry.title.lower()]
                self._title_to_id[old_title.lower()] = entry_id
            
            # 恢复别名映射
            for new_alias in entry.aliases:
                if new_alias.lower().strip() in self._alias_to_id:
                    del self._alias_to_id[new_alias.lower().strip()]
            for old_alias in old_aliases:
                if old_alias.strip():
                    self._alias_to_id[old_alias.lower().strip()] = entry_id
            
            self._rebuild_reference_patterns()
            return False
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        logger.info(f"Updated codex entry: {entry.title}")
        return True

    def delete_entry(self, entry_id: str) -> bool:
        """删除Codex条目"""
        if entry_id not in self._entries:
            logger.warning(f"Codex entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        # 从映射中移除
        if entry.title.lower() in self._title_to_id:
            del self._title_to_id[entry.title.lower()]
        
        for alias in entry.aliases:
            if alias.lower().strip() in self._alias_to_id:
                del self._alias_to_id[alias.lower().strip()]
        
        # 保存待删除的引用以便回滚
        old_references = [ref for ref in self._references if ref.codex_id == entry_id]
        
        # 删除相关引用
        self._references = [ref for ref in self._references if ref.codex_id != entry_id]
        
        # 删除条目
        del self._entries[entry_id]
        
        # 重建引用模式
        self._rebuild_reference_patterns()
        
        # 增量删除数据
        if not self._delete_entry_incremental(entry_id):
            logger.error(f"Failed to delete entry {entry.title} from database")
            # 如果删除失败，需要回滚内存状态
            self._entries[entry_id] = entry
            self._title_to_id[entry.title.lower()] = entry_id
            for alias in entry.aliases:
                if alias.strip():
                    self._alias_to_id[alias.lower().strip()] = entry_id
            
            # 恢复引用
            for ref in old_references:
                self._references.append(ref)
            
            self._rebuild_reference_patterns()
            return False
        
        # 发送信号
        if HAS_QT:
            self.entryDeleted.emit(entry_id)
        
        logger.info(f"Deleted codex entry: {entry.title}")
        return True

    def get_entry(self, entry_id: str) -> Optional[CodexEntry]:
        """获取Codex条目"""
        return self._entries.get(entry_id)

    def get_entry_by_title(self, title: str) -> Optional[CodexEntry]:
        """根据标题获取Codex条目"""
        entry_id = self._title_to_id.get(title.lower())
        return self._entries.get(entry_id) if entry_id else None

    def get_entries_by_type(self, entry_type: CodexEntryType) -> List[CodexEntry]:
        """根据类型获取Codex条目列表"""
        return [entry for entry in self._entries.values() 
                if entry.entry_type == entry_type]

    def get_global_entries(self) -> List[CodexEntry]:
        """获取全局Codex条目"""
        return [entry for entry in self._entries.values() if entry.is_global]

    def get_all_entries(self) -> List[CodexEntry]:
        """获取所有Codex条目"""
        return list(self._entries.values())

    def search_entries(self, query: str) -> List[CodexEntry]:
        """搜索Codex条目"""
        query_lower = query.lower()
        results = []
        
        for entry in self._entries.values():
            # 搜索标题
            if query_lower in entry.title.lower():
                results.append(entry)
                continue
            
            # 搜索别名
            if any(query_lower in alias.lower() for alias in entry.aliases):
                results.append(entry)
                continue
            
            # 搜索描述
            if query_lower in entry.description.lower():
                results.append(entry)
                continue
        
        return results

    def _rebuild_reference_patterns(self):
        """重建引用检测的正则模式缓存"""
        self._reference_patterns.clear()
        
        for entry in self._entries.values():
            if entry.track_references:
                patterns = []
                
                # 添加标题模式
                title_pattern = re.escape(entry.title)
                patterns.append(title_pattern)
                
                # 添加别名模式
                for alias in entry.aliases:
                    if alias.strip():
                        alias_pattern = re.escape(alias.strip())
                        patterns.append(alias_pattern)
                
                if patterns:
                    # 创建组合模式，使用词边界确保完整匹配
                    combined_pattern = r'\b(?:' + '|'.join(patterns) + r')\b'
                    try:
                        self._reference_patterns[entry.id] = re.compile(
                            combined_pattern, re.IGNORECASE
                        )
                    except re.error as e:
                        logger.warning(f"Failed to compile pattern for {entry.title}: {e}")
        
        self._pattern_cache_version += 1
        logger.debug(f"Rebuilt {len(self._reference_patterns)} reference patterns")

    def detect_references_in_text(self, text: str, document_id: str) -> List[Tuple[str, str, int, int]]:
        """
        在文本中检测Codex引用
        
        Returns:
            List[Tuple[str, str, int, int]]: (entry_id, matched_text, start_pos, end_pos)
        """
        if not text or not self._reference_patterns:
            return []
        
        references = []
        
        for entry_id, pattern in self._reference_patterns.items():
            for match in pattern.finditer(text):
                references.append((
                    entry_id,
                    match.group(),
                    match.start(),
                    match.end()
                ))
        
        return references

    def update_references_for_document(self, document_id: str, text: str):
        """更新文档的引用记录"""
        # 删除该文档的旧引用
        self._references = [ref for ref in self._references 
                           if ref.document_id != document_id]
        
        # 检测新引用
        detected_refs = self.detect_references_in_text(text, document_id)
        
        # 添加新引用记录
        for entry_id, matched_text, start_pos, end_pos in detected_refs:
            # 提取上下文
            context_start = max(0, start_pos - 50)
            context_end = min(len(text), end_pos + 50)
            context_before = text[context_start:start_pos]
            context_after = text[end_pos:context_end]
            
            reference = CodexReference(
                id=0,  # 数据库会自动分配
                codex_id=entry_id,
                document_id=document_id,
                reference_text=matched_text,
                position_start=start_pos,
                position_end=end_pos,
                context_before=context_before,
                context_after=context_after
            )
            
            self._references.append(reference)
        
        # 保存到数据库
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.referencesUpdated.emit(document_id, len(detected_refs))
        
        logger.debug(f"Updated references for document {document_id}: {len(detected_refs)} found")

    def get_references_for_entry(self, entry_id: str) -> List[CodexReference]:
        """获取特定条目的所有引用"""
        return [ref for ref in self._references if ref.codex_id == entry_id]

    def get_references_for_document(self, document_id: str) -> List[CodexReference]:
        """获取特定文档的所有引用"""
        return [ref for ref in self._references if ref.document_id == document_id]

    def get_detected_entries_for_document(self, document_id: str) -> List[CodexEntry]:
        """获取在指定文档中被检测到的Codex条目"""
        document_refs = self.get_references_for_document(document_id)
        entry_ids = set(ref.codex_id for ref in document_refs)
        return [self._entries[entry_id] for entry_id in entry_ids 
                if entry_id in self._entries]

    def get_statistics(self) -> Dict[str, Any]:
        """获取Codex统计信息"""
        type_counts = {}
        for entry_type in CodexEntryType:
            type_counts[entry_type.value] = len(self.get_entries_by_type(entry_type))
        
        return {
            'total_entries': len(self._entries),
            'total_references': len(self._references),
            'global_entries': len(self.get_global_entries()),
            'type_counts': type_counts,
            'entries_with_aliases': len([e for e in self._entries.values() if e.aliases]),
            'tracked_entries': len([e for e in self._entries.values() if e.track_references])
        }

    # ========== NovelCrafter风格的高级功能API ==========
    
    def add_alias(self, entry_id: str, alias: str) -> bool:
        """
        为Codex条目添加别名 - NovelCrafter核心功能
        
        别名系统允许一个角色/地点有多个称呼（真名、昵称、外号等），
        这是NovelCrafter的关键创新功能。
        
        Args:
            entry_id: 条目ID
            alias: 新别名
            
        Returns:
            bool: 是否成功添加
            
        Raises:
            ValueError: 当别名已被其他条目使用时
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        # 清理别名
        alias = alias.strip()
        if not alias:
            logger.warning("Empty alias not allowed")
            return False
        
        alias_lower = alias.lower()
        
        # 检查别名是否已被使用
        if alias_lower in self._alias_to_id:
            existing_entry_id = self._alias_to_id[alias_lower]
            if existing_entry_id != entry_id:
                existing_entry = self._entries.get(existing_entry_id)
                existing_title = existing_entry.title if existing_entry else "未知条目"
                raise ValueError(f"别名 '{alias}' 已被条目 '{existing_title}' 使用")
            else:
                logger.info(f"Alias '{alias}' already exists for this entry")
                return True
        
        # 检查是否与其他条目标题冲突
        if alias_lower in self._title_to_id:
            existing_entry_id = self._title_to_id[alias_lower]
            if existing_entry_id != entry_id:
                existing_entry = self._entries.get(existing_entry_id)
                existing_title = existing_entry.title if existing_entry else "未知条目"
                raise ValueError(f"别名 '{alias}' 与条目标题 '{existing_title}' 冲突")
        
        # 添加别名
        entry = self._entries[entry_id]
        if alias not in entry.aliases:
            entry.aliases.append(alias)
            self._alias_to_id[alias_lower] = entry_id
            
            # 重建引用模式（关键：别名变化影响引用检测）
            self._rebuild_reference_patterns()
            
            # 保存数据
            self._save_data()
            
            # 发送信号
            if HAS_QT:
                self.entryUpdated.emit(entry_id)
            
            logger.info(f"Added alias '{alias}' to entry '{entry.title}'")
            return True
        
        return True
    
    def remove_alias(self, entry_id: str, alias: str) -> bool:
        """
        从Codex条目中移除别名
        
        Args:
            entry_id: 条目ID
            alias: 要移除的别名
            
        Returns:
            bool: 是否成功移除
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        alias = alias.strip()
        alias_lower = alias.lower()
        
        entry = self._entries[entry_id]
        
        # 从条目的别名列表中移除
        original_count = len(entry.aliases)
        entry.aliases = [a for a in entry.aliases if a.lower() != alias_lower]
        
        if len(entry.aliases) == original_count:
            logger.info(f"Alias '{alias}' not found in entry '{entry.title}'")
            return False
        
        # 从映射中移除
        if alias_lower in self._alias_to_id:
            del self._alias_to_id[alias_lower]
        
        # 重建引用模式
        self._rebuild_reference_patterns()
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        logger.info(f"Removed alias '{alias}' from entry '{entry.title}'")
        return True
    
    def get_entry_by_alias(self, alias: str) -> Optional[CodexEntry]:
        """
        通过别名查找Codex条目 - 支持智能搜索
        
        Args:
            alias: 别名或标题
            
        Returns:
            Optional[CodexEntry]: 找到的条目，如果没找到返回None
        """
        alias_lower = alias.strip().lower()
        
        # 先在别名映射中查找
        if alias_lower in self._alias_to_id:
            entry_id = self._alias_to_id[alias_lower]
            return self._entries.get(entry_id)
        
        # 再在标题映射中查找
        if alias_lower in self._title_to_id:
            entry_id = self._title_to_id[alias_lower]
            return self._entries.get(entry_id)
        
        return None
    
    def list_aliases(self, entry_id: str) -> List[str]:
        """
        获取条目的所有别名
        
        Args:
            entry_id: 条目ID
            
        Returns:
            List[str]: 别名列表
        """
        if entry_id not in self._entries:
            return []
        
        return self._entries[entry_id].aliases.copy()
    
    def update_aliases(self, entry_id: str, aliases: List[str]) -> bool:
        """
        批量更新条目的别名 - 原子操作
        
        Args:
            entry_id: 条目ID
            aliases: 新的别名列表
            
        Returns:
            bool: 是否成功更新
            
        Raises:
            ValueError: 当某个别名已被其他条目使用时
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        # 清理和验证新别名
        new_aliases = []
        for alias in aliases:
            alias = alias.strip()
            if alias:
                alias_lower = alias.lower()
                
                # 检查别名冲突
                if alias_lower in self._alias_to_id:
                    existing_entry_id = self._alias_to_id[alias_lower]
                    if existing_entry_id != entry_id:
                        existing_entry = self._entries.get(existing_entry_id)
                        existing_title = existing_entry.title if existing_entry else "未知条目"
                        raise ValueError(f"别名 '{alias}' 已被条目 '{existing_title}' 使用")
                
                # 检查标题冲突
                if alias_lower in self._title_to_id:
                    existing_entry_id = self._title_to_id[alias_lower]
                    if existing_entry_id != entry_id:
                        existing_entry = self._entries.get(existing_entry_id)
                        existing_title = existing_entry.title if existing_entry else "未知条目"
                        raise ValueError(f"别名 '{alias}' 与条目标题 '{existing_title}' 冲突")
                
                new_aliases.append(alias)
        
        # 移除旧的别名映射
        for old_alias in entry.aliases:
            old_alias_lower = old_alias.lower()
            if old_alias_lower in self._alias_to_id:
                del self._alias_to_id[old_alias_lower]
        
        # 设置新别名
        entry.aliases = new_aliases
        
        # 添加新的别名映射
        for alias in new_aliases:
            self._alias_to_id[alias.lower()] = entry_id
        
        # 重建引用模式
        self._rebuild_reference_patterns()
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        logger.info(f"Updated aliases for entry '{entry.title}': {len(new_aliases)} aliases")
        return True
    
    # ========== 关系管理API - NovelCrafter风格的关系网络功能 ==========
    
    def add_relationship(self, entry_id: str, target_id: str, relationship_type: str, 
                        description: str = "", strength: str = "medium") -> bool:
        """
        为Codex条目添加关系 - NovelCrafter关系网络核心功能
        
        关系系统允许定义角色、地点、物品之间的复杂关系网络，
        这是NovelCrafter的关键创新功能，支持智能上下文生成。
        
        Args:
            entry_id: 源条目ID
            target_id: 目标条目ID
            relationship_type: 关系类型（如：朋友、敌人、父子、师生、位于、拥有等）
            description: 关系描述（可选）
            strength: 关系强度（strong, medium, weak）
            
        Returns:
            bool: 是否成功添加
            
        Raises:
            ValueError: 当目标条目不存在或关系已存在时
        """
        if entry_id not in self._entries:
            logger.warning(f"Source entry not found: {entry_id}")
            return False
        
        if target_id not in self._entries:
            logger.warning(f"Target entry not found: {target_id}")
            raise ValueError(f"目标条目不存在: {target_id}")
        
        if entry_id == target_id:
            logger.warning("Cannot add relationship to self")
            raise ValueError("不能添加自身关系")
        
        entry = self._entries[entry_id]
        
        # 检查关系是否已存在
        for existing_rel in entry.relationships:
            if (existing_rel.get('target_id') == target_id and 
                existing_rel.get('relationship_type') == relationship_type):
                logger.info(f"Relationship already exists: {entry_id} -> {target_id} ({relationship_type})")
                return True
        
        # 创建新关系
        relationship = {
            'target_id': target_id,
            'relationship_type': relationship_type,
            'description': description,
            'strength': strength,
            'created_at': datetime.now().isoformat()
        }
        
        entry.relationships.append(relationship)
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        target_entry = self._entries[target_id]
        logger.info(f"Added relationship: '{entry.title}' -{relationship_type}-> '{target_entry.title}'")
        return True
    
    def remove_relationship(self, entry_id: str, target_id: str, relationship_type: str = None) -> bool:
        """
        移除Codex条目的关系
        
        Args:
            entry_id: 源条目ID
            target_id: 目标条目ID
            relationship_type: 关系类型（如果为None则移除所有到目标的关系）
            
        Returns:
            bool: 是否成功移除
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        original_count = len(entry.relationships)
        
        # 过滤掉要移除的关系
        if relationship_type is None:
            # 移除所有到目标条目的关系
            entry.relationships = [rel for rel in entry.relationships 
                                 if rel.get('target_id') != target_id]
        else:
            # 移除特定类型的关系
            entry.relationships = [rel for rel in entry.relationships 
                                 if not (rel.get('target_id') == target_id and 
                                        rel.get('relationship_type') == relationship_type)]
        
        removed_count = original_count - len(entry.relationships)
        
        if removed_count == 0:
            logger.info(f"No matching relationships found to remove")
            return False
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        logger.info(f"Removed {removed_count} relationship(s) from entry '{entry.title}'")
        return True
    
    def get_relationships(self, entry_id: str) -> List[Dict[str, str]]:
        """
        获取条目的所有关系
        
        Args:
            entry_id: 条目ID
            
        Returns:
            List[Dict[str, str]]: 关系列表，包含详细信息
        """
        if entry_id not in self._entries:
            return []
        
        entry = self._entries[entry_id]
        relationships = []
        
        for rel in entry.relationships:
            target_id = rel.get('target_id')
            if target_id in self._entries:
                target_entry = self._entries[target_id]
                relationship_info = {
                    'target_id': target_id,
                    'target_title': target_entry.title,
                    'target_type': target_entry.entry_type.value,
                    'relationship_type': rel.get('relationship_type', ''),
                    'description': rel.get('description', ''),
                    'strength': rel.get('strength', 'medium'),
                    'created_at': rel.get('created_at', '')
                }
                relationships.append(relationship_info)
            else:
                logger.warning(f"Target entry not found: {target_id}")
        
        return relationships
    
    def find_related_entries(self, entry_id: str, relationship_type: str = None, 
                           target_type: CodexEntryType = None) -> List[CodexEntry]:
        """
        查找与指定条目相关的所有条目
        
        Args:
            entry_id: 源条目ID
            relationship_type: 关系类型过滤（可选）
            target_type: 目标条目类型过滤（可选）
            
        Returns:
            List[CodexEntry]: 相关条目列表
        """
        if entry_id not in self._entries:
            return []
        
        entry = self._entries[entry_id]
        related_entries = []
        
        for rel in entry.relationships:
            target_id = rel.get('target_id')
            if target_id in self._entries:
                target_entry = self._entries[target_id]
                
                # 应用过滤条件
                if relationship_type and rel.get('relationship_type') != relationship_type:
                    continue
                
                if target_type and target_entry.entry_type != target_type:
                    continue
                
                related_entries.append(target_entry)
        
        return related_entries
    
    def update_relationships(self, entry_id: str, relationships: List[Dict[str, str]]) -> bool:
        """
        批量更新条目的关系 - 原子操作
        
        Args:
            entry_id: 条目ID
            relationships: 新的关系列表
            
        Returns:
            bool: 是否成功更新
            
        Raises:
            ValueError: 当某个目标条目不存在时
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        # 验证所有关系的目标条目存在
        for rel in relationships:
            target_id = rel.get('target_id')
            if not target_id:
                raise ValueError("关系必须包含 target_id")
            
            if target_id not in self._entries:
                target_entry = self._entries.get(target_id)
                target_title = target_entry.title if target_entry else "未知条目"
                raise ValueError(f"目标条目不存在: {target_title} ({target_id})")
            
            if target_id == entry_id:
                raise ValueError("不能添加自身关系")
        
        # 规范化关系数据
        normalized_relationships = []
        for rel in relationships:
            normalized_rel = {
                'target_id': rel.get('target_id'),
                'relationship_type': rel.get('relationship_type', ''),
                'description': rel.get('description', ''),
                'strength': rel.get('strength', 'medium'),
                'created_at': rel.get('created_at', datetime.now().isoformat())
            }
            normalized_relationships.append(normalized_rel)
        
        # 更新关系
        entry.relationships = normalized_relationships
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        logger.info(f"Updated relationships for entry '{entry.title}': {len(normalized_relationships)} relationships")
        return True
    
    def get_relationship_network(self, entry_id: str, depth: int = 1) -> Dict[str, Any]:
        """
        获取以指定条目为中心的关系网络视图 - 支持关系可视化
        
        Args:
            entry_id: 中心条目ID
            depth: 关系深度（1=直接关系，2=二度关系，等等）
            
        Returns:
            Dict[str, Any]: 关系网络数据，包含节点和边信息
        """
        if entry_id not in self._entries:
            return {"nodes": [], "edges": []}
        
        visited = set()
        nodes = []
        edges = []
        
        def explore_node(current_id: str, current_depth: int):
            if current_id in visited or current_depth > depth:
                return
            
            visited.add(current_id)
            current_entry = self._entries.get(current_id)
            
            if not current_entry:
                return
            
            # 添加节点
            node = {
                'id': current_id,
                'title': current_entry.title,
                'type': current_entry.entry_type.value,
                'is_global': current_entry.is_global,
                'depth': current_depth
            }
            nodes.append(node)
            
            # 添加关系边
            for rel in current_entry.relationships:
                target_id = rel.get('target_id')
                if target_id in self._entries:
                    edge = {
                        'source': current_id,
                        'target': target_id,
                        'relationship_type': rel.get('relationship_type', ''),
                        'description': rel.get('description', ''),
                        'strength': rel.get('strength', 'medium')
                    }
                    edges.append(edge)
                    
                    # 递归探索（如果深度允许）
                    if current_depth < depth:
                        explore_node(target_id, current_depth + 1)
        
        # 开始探索
        explore_node(entry_id, 0)
        
        # 也要查找指向中心节点的关系
        for other_entry in self._entries.values():
            if other_entry.id != entry_id:
                for rel in other_entry.relationships:
                    if rel.get('target_id') == entry_id:
                        # 添加反向关系边
                        edge = {
                            'source': other_entry.id,
                            'target': entry_id,
                            'relationship_type': rel.get('relationship_type', ''),
                            'description': rel.get('description', ''),
                            'strength': rel.get('strength', 'medium')
                        }
                        if edge not in edges:  # 避免重复
                            edges.append(edge)
                        
                        # 如果这个节点还没被访问过，添加它
                        if other_entry.id not in visited:
                            node = {
                                'id': other_entry.id,
                                'title': other_entry.title,
                                'type': other_entry.entry_type.value,
                                'is_global': other_entry.is_global,
                                'depth': 1  # 反向关系深度为1
                            }
                            nodes.append(node)
        
        network_data = {
            'center_id': entry_id,
            'depth': depth,
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'relationship_types': list(set(edge['relationship_type'] for edge in edges if edge['relationship_type']))
            }
        }
        
        logger.debug(f"Generated relationship network for '{self._entries[entry_id].title}': {len(nodes)} nodes, {len(edges)} edges")
        return network_data
    
    def get_relationship_statistics(self) -> Dict[str, Any]:
        """
        获取整个知识库的关系统计信息
        
        Returns:
            Dict[str, Any]: 关系统计数据
        """
        total_relationships = 0
        relationship_types = {}
        strength_distribution = {'strong': 0, 'medium': 0, 'weak': 0}
        entries_with_relationships = 0
        
        for entry in self._entries.values():
            if entry.relationships:
                entries_with_relationships += 1
                total_relationships += len(entry.relationships)
                
                for rel in entry.relationships:
                    rel_type = rel.get('relationship_type', '未分类')
                    relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1
                    
                    strength = rel.get('strength', 'medium')
                    if strength in strength_distribution:
                        strength_distribution[strength] += 1
        
        # 计算平均关系数
        avg_relationships = total_relationships / max(len(self._entries), 1)
        
        # 找出最连接的条目
        most_connected = None
        max_connections = 0
        
        for entry in self._entries.values():
            connection_count = len(entry.relationships)
            # 同时计算指向这个条目的关系
            incoming_count = sum(1 for other_entry in self._entries.values() 
                               if other_entry.id != entry.id 
                               for rel in other_entry.relationships 
                               if rel.get('target_id') == entry.id)
            
            total_connections = connection_count + incoming_count
            
            if total_connections > max_connections:
                max_connections = total_connections
                most_connected = {
                    'id': entry.id,
                    'title': entry.title,
                    'outgoing': connection_count,
                    'incoming': incoming_count,
                    'total': total_connections
                }
        
        return {
            'total_relationships': total_relationships,
            'entries_with_relationships': entries_with_relationships,
            'relationship_coverage': entries_with_relationships / max(len(self._entries), 1) * 100,
            'average_relationships_per_entry': avg_relationships,
            'relationship_types': relationship_types,
            'strength_distribution': strength_distribution,
            'most_connected_entry': most_connected
        }
    
    # ========== 进展追踪API - NovelCrafter风格的动态发展追踪功能 ==========
    
    def add_progression_event(self, entry_id: str, event_type: str, description: str,
                            chapter_id: str = None, position: int = None, 
                            metadata: Dict[str, Any] = None) -> bool:
        """
        为Codex条目添加进展事件 - NovelCrafter动态追踪核心功能
        
        进展追踪系统允许记录角色、地点、物品在故事中的发展变化，
        这是NovelCrafter的关键创新功能，支持智能故事分析和一致性检查。
        
        Args:
            entry_id: 条目ID
            event_type: 事件类型（如：出现、对话、状态变化、发展、转折等）
            description: 事件描述
            chapter_id: 所在章节ID（可选）
            position: 在文档中的位置（可选）
            metadata: 额外元数据（如情绪状态、关系变化等）
            
        Returns:
            bool: 是否成功添加
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        # 创建进展事件
        event = {
            'event_type': event_type,
            'description': description,
            'chapter_id': chapter_id,
            'position': position,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        entry.progression.append(event)
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        logger.info(f"Added progression event to '{entry.title}': {event_type} - {description}")
        return True
    
    def remove_progression_event(self, entry_id: str, event_index: int) -> bool:
        """
        移除指定索引的进展事件
        
        Args:
            entry_id: 条目ID
            event_index: 事件索引（从0开始）
            
        Returns:
            bool: 是否成功移除
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        if 0 <= event_index < len(entry.progression):
            removed_event = entry.progression.pop(event_index)
            
            # 保存数据
            self._save_data()
            
            # 发送信号
            if HAS_QT:
                self.entryUpdated.emit(entry_id)
            
            logger.info(f"Removed progression event from '{entry.title}': {removed_event.get('event_type', '')} - {removed_event.get('description', '')}")
            return True
        else:
            logger.warning(f"Invalid event index {event_index} for entry {entry_id}")
            return False
    
    def get_progression_history(self, entry_id: str, event_type: str = None, 
                              limit: int = None) -> List[Dict[str, Any]]:
        """
        获取条目的进展历史
        
        Args:
            entry_id: 条目ID
            event_type: 事件类型过滤（可选）
            limit: 返回数量限制（可选，按时间倒序）
            
        Returns:
            List[Dict[str, Any]]: 进展事件列表
        """
        if entry_id not in self._entries:
            return []
        
        entry = self._entries[entry_id]
        events = entry.progression.copy()
        
        # 按时间排序（最新的在前）
        events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # 应用过滤
        if event_type:
            events = [event for event in events if event.get('event_type') == event_type]
        
        # 应用数量限制
        if limit and limit > 0:
            events = events[:limit]
        
        # 添加索引信息
        for i, event in enumerate(events):
            event['index'] = len(entry.progression) - 1 - i  # 原始索引
        
        return events
    
    def get_progression_timeline(self, entry_ids: List[str] = None, 
                               start_time: str = None, end_time: str = None) -> List[Dict[str, Any]]:
        """
        获取进展时间线视图 - 跨条目的时间线分析
        
        Args:
            entry_ids: 条目ID列表（如果为None则包含所有条目）
            start_time: 开始时间（ISO格式，可选）
            end_time: 结束时间（ISO格式，可选）
            
        Returns:
            List[Dict[str, Any]]: 时间线事件列表，按时间排序
        """
        timeline_events = []
        
        # 确定要包含的条目
        target_entries = entry_ids if entry_ids else list(self._entries.keys())
        
        for entry_id in target_entries:
            if entry_id not in self._entries:
                continue
            
            entry = self._entries[entry_id]
            
            for event in entry.progression:
                timestamp = event.get('timestamp', '')
                
                # 应用时间过滤
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                
                timeline_event = {
                    'entry_id': entry_id,
                    'entry_title': entry.title,
                    'entry_type': entry.entry_type.value,
                    'event_type': event.get('event_type', ''),
                    'description': event.get('description', ''),
                    'chapter_id': event.get('chapter_id'),
                    'position': event.get('position'),
                    'timestamp': timestamp,
                    'metadata': event.get('metadata', {})
                }
                timeline_events.append(timeline_event)
        
        # 按时间排序
        timeline_events.sort(key=lambda x: x['timestamp'])
        
        return timeline_events
    
    def update_progression_events(self, entry_id: str, events: List[Dict[str, Any]]) -> bool:
        """
        批量更新条目的进展事件 - 原子操作
        
        Args:
            entry_id: 条目ID
            events: 新的事件列表
            
        Returns:
            bool: 是否成功更新
        """
        if entry_id not in self._entries:
            logger.warning(f"Entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        # 规范化事件数据
        normalized_events = []
        for event in events:
            normalized_event = {
                'event_type': event.get('event_type', ''),
                'description': event.get('description', ''),
                'chapter_id': event.get('chapter_id'),
                'position': event.get('position'),
                'timestamp': event.get('timestamp', datetime.now().isoformat()),
                'metadata': event.get('metadata', {})
            }
            normalized_events.append(normalized_event)
        
        # 更新事件列表
        entry.progression = normalized_events
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        if HAS_QT:
            self.entryUpdated.emit(entry_id)
        
        logger.info(f"Updated progression events for entry '{entry.title}': {len(normalized_events)} events")
        return True
    
    def get_progression_statistics(self) -> Dict[str, Any]:
        """
        获取整个知识库的进展统计信息
        
        Returns:
            Dict[str, Any]: 进展统计数据
        """
        total_events = 0
        event_types = {}
        entries_with_progression = 0
        chapter_distribution = {}
        
        # 按类型统计事件
        type_progression = {
            'CHARACTER': 0,
            'LOCATION': 0,
            'OBJECT': 0,
            'LORE': 0,
            'SUBPLOT': 0,
            'OTHER': 0
        }
        
        for entry in self._entries.values():
            if entry.progression:
                entries_with_progression += 1
                total_events += len(entry.progression)
                type_progression[entry.entry_type.value] += len(entry.progression)
                
                for event in entry.progression:
                    event_type = event.get('event_type', '未分类')
                    event_types[event_type] = event_types.get(event_type, 0) + 1
                    
                    chapter_id = event.get('chapter_id')
                    if chapter_id:
                        chapter_distribution[chapter_id] = chapter_distribution.get(chapter_id, 0) + 1
        
        # 计算平均事件数
        avg_events = total_events / max(len(self._entries), 1)
        
        # 找出最活跃的条目（事件最多）
        most_active = None
        max_events = 0
        
        for entry in self._entries.values():
            event_count = len(entry.progression)
            if event_count > max_events:
                max_events = event_count
                most_active = {
                    'id': entry.id,
                    'title': entry.title,
                    'type': entry.entry_type.value,
                    'event_count': event_count
                }
        
        # 获取最近的事件
        recent_events = []
        for entry in self._entries.values():
            for event in entry.progression:
                recent_events.append({
                    'entry_title': entry.title,
                    'event_type': event.get('event_type', ''),
                    'description': event.get('description', ''),
                    'timestamp': event.get('timestamp', '')
                })
        
        # 按时间排序，取最近的5个
        recent_events.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_events = recent_events[:5]
        
        return {
            'total_events': total_events,
            'entries_with_progression': entries_with_progression,
            'progression_coverage': entries_with_progression / max(len(self._entries), 1) * 100,
            'average_events_per_entry': avg_events,
            'event_types': event_types,
            'type_progression': type_progression,
            'chapter_distribution': chapter_distribution,
            'most_active_entry': most_active,
            'recent_events': recent_events
        }
    
    def find_entries_by_progression(self, event_type: str = None, chapter_id: str = None, 
                                  has_metadata_key: str = None) -> List[CodexEntry]:
        """
        根据进展事件查找条目
        
        Args:
            event_type: 事件类型过滤（可选）
            chapter_id: 章节ID过滤（可选）
            has_metadata_key: 包含特定元数据键的事件（可选）
            
        Returns:
            List[CodexEntry]: 匹配的条目列表
        """
        matching_entries = []
        
        for entry in self._entries.values():
            for event in entry.progression:
                # 检查事件类型
                if event_type and event.get('event_type') != event_type:
                    continue
                
                # 检查章节ID
                if chapter_id and event.get('chapter_id') != chapter_id:
                    continue
                
                # 检查元数据键
                if has_metadata_key and has_metadata_key not in event.get('metadata', {}):
                    continue
                
                # 如果通过所有过滤条件，添加条目（避免重复）
                if entry not in matching_entries:
                    matching_entries.append(entry)
                    break  # 找到一个匹配事件就够了
        
        return matching_entries
    
    # ========== 增强的引用统计功能 ==========
    
    def get_enhanced_reference_statistics(self) -> Dict[str, Any]:
        """
        获取增强的引用统计信息，包含时间维度和使用情况
        
        Returns:
            Dict[str, Any]: 增强的统计数据
        """
        from datetime import datetime, timedelta
        import statistics
        
        # 基础统计
        total_refs = len(self._references)
        active_refs = len([r for r in self._references if getattr(r, 'status', 'active') == 'active'])
        deleted_refs = len([r for r in self._references if getattr(r, 'deleted_at', None)])
        
        # 按条目统计引用
        entry_ref_counts = {}
        for ref in self._references:
            if ref.codex_id not in entry_ref_counts:
                entry_ref_counts[ref.codex_id] = 0
            entry_ref_counts[ref.codex_id] += 1
        
        # 计算引用分布统计
        ref_counts = list(entry_ref_counts.values())
        ref_distribution = {
            'mean': statistics.mean(ref_counts) if ref_counts else 0,
            'median': statistics.median(ref_counts) if ref_counts else 0,
            'std_dev': statistics.stdev(ref_counts) if len(ref_counts) > 1 else 0,
            'max': max(ref_counts) if ref_counts else 0,
            'min': min(ref_counts) if ref_counts else 0
        }
        
        # 时间维度统计
        now = datetime.now()
        recent_refs = []
        hourly_distribution = {}
        daily_distribution = {}
        
        for ref in self._references:
            try:
                created_time = datetime.fromisoformat(ref.created_at) if hasattr(ref, 'created_at') and ref.created_at else None
                if created_time:
                    # 最近7天的引用
                    if (now - created_time).days <= 7:
                        recent_refs.append(ref)
                    
                    # 按小时统计
                    hour = created_time.hour
                    hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
                    
                    # 按天统计（最近30天）
                    if (now - created_time).days <= 30:
                        day_key = created_time.strftime('%Y-%m-%d')
                        daily_distribution[day_key] = daily_distribution.get(day_key, 0) + 1
            except:
                pass
        
        # 使用频率统计
        access_counts = [getattr(r, 'access_count', 0) for r in self._references]
        access_stats = {
            'total_accesses': sum(access_counts),
            'avg_accesses': statistics.mean(access_counts) if access_counts else 0,
            'most_accessed': max(access_counts) if access_counts else 0
        }
        
        # 置信度统计
        confidence_scores = [getattr(r, 'confidence_score', 1.0) for r in self._references]
        confidence_stats = {
            'avg_confidence': statistics.mean(confidence_scores) if confidence_scores else 0,
            'low_confidence_count': len([s for s in confidence_scores if s < 0.5]),
            'high_confidence_count': len([s for s in confidence_scores if s >= 0.8])
        }
        
        # 查找最活跃的条目
        most_referenced_entries = sorted(
            [(entry_id, count) for entry_id, count in entry_ref_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # 查找未使用的条目
        unused_entries = []
        for entry_id, entry in self._entries.items():
            if entry_id not in entry_ref_counts and entry.track_references:
                unused_entries.append({
                    'id': entry_id,
                    'title': entry.title,
                    'type': entry.entry_type.value
                })
        
        return {
            'total_references': total_refs,
            'active_references': active_refs,
            'deleted_references': deleted_refs,
            'reference_distribution': ref_distribution,
            'recent_references_7d': len(recent_refs),
            'hourly_distribution': hourly_distribution,
            'daily_distribution': daily_distribution,
            'access_statistics': access_stats,
            'confidence_statistics': confidence_stats,
            'most_referenced_entries': [
                {
                    'entry_id': eid,
                    'title': self._entries[eid].title if eid in self._entries else 'Unknown',
                    'count': count
                }
                for eid, count in most_referenced_entries
            ],
            'unused_entries': unused_entries[:10]  # 限制返回数量
        }
    
    def get_reference_timeline(self, entry_id: str = None, days: int = 30) -> Dict[str, Any]:
        """
        获取引用时间线数据，用于图表展示
        
        Args:
            entry_id: 特定条目ID（可选，不指定则返回所有条目）
            days: 统计天数（默认30天）
            
        Returns:
            Dict[str, Any]: 时间线数据
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        start_date = now - timedelta(days=days)
        
        # 初始化日期字典
        timeline = {}
        current_date = start_date
        while current_date <= now:
            date_key = current_date.strftime('%Y-%m-%d')
            timeline[date_key] = {'count': 0, 'entries': set()}
            current_date += timedelta(days=1)
        
        # 统计引用
        for ref in self._references:
            # 过滤特定条目
            if entry_id and ref.codex_id != entry_id:
                continue
            
            try:
                created_time = datetime.fromisoformat(ref.created_at) if hasattr(ref, 'created_at') and ref.created_at else None
                if created_time and created_time >= start_date:
                    date_key = created_time.strftime('%Y-%m-%d')
                    if date_key in timeline:
                        timeline[date_key]['count'] += 1
                        timeline[date_key]['entries'].add(ref.codex_id)
            except:
                pass
        
        # 转换为列表格式，方便图表使用
        timeline_list = []
        for date, data in sorted(timeline.items()):
            timeline_list.append({
                'date': date,
                'count': data['count'],
                'unique_entries': len(data['entries'])
            })
        
        return {
            'timeline': timeline_list,
            'total_references': sum(item['count'] for item in timeline_list),
            'days_with_references': len([item for item in timeline_list if item['count'] > 0]),
            'peak_day': max(timeline_list, key=lambda x: x['count']) if timeline_list else None
        }
    
    def update_reference_access(self, ref_id: int, increment_access: bool = True):
        """
        更新引用访问统计
        
        Args:
            ref_id: 引用ID
            increment_access: 是否增加访问计数
        """
        try:
            # 更新数据库中的访问统计
            with self.db_manager._get_connection() as conn:
                if increment_access:
                    conn.execute("""
                        UPDATE codex_references 
                        SET access_count = access_count + 1,
                            last_accessed_at = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), ref_id))
                else:
                    conn.execute("""
                        UPDATE codex_references 
                        SET last_accessed_at = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), ref_id))
                
                conn.commit()
                
            # 更新内存中的引用对象
            for ref in self._references:
                if hasattr(ref, 'id') and ref.id == ref_id:
                    if hasattr(ref, 'access_count'):
                        ref.access_count = getattr(ref, 'access_count', 0) + 1
                    if hasattr(ref, 'last_accessed_at'):
                        ref.last_accessed_at = datetime.now().isoformat()
                    break
                    
        except Exception as e:
            logger.error(f"Error updating reference access: {e}")
    
    def mark_reference_as_deleted(self, ref_id: int):
        """
        软删除引用（标记为已删除）
        
        Args:
            ref_id: 引用ID
        """
        try:
            with self.db_manager._get_connection() as conn:
                conn.execute("""
                    UPDATE codex_references 
                    SET deleted_at = ?,
                        status = 'deleted'
                    WHERE id = ?
                """, (datetime.now().isoformat(), ref_id))
                conn.commit()
                
            # 更新内存中的引用
            for ref in self._references:
                if hasattr(ref, 'id') and ref.id == ref_id:
                    if hasattr(ref, 'deleted_at'):
                        ref.deleted_at = datetime.now().isoformat()
                    if hasattr(ref, 'status'):
                        ref.status = 'deleted'
                    break
                    
        except Exception as e:
            logger.error(f"Error marking reference as deleted: {e}")
    
    def get_reference_co_occurrences(self, entry_id: str, threshold: int = 2) -> List[Dict[str, Any]]:
        """
        获取与指定条目共同出现的其他条目
        
        Args:
            entry_id: 条目ID
            threshold: 最小共现次数阈值
            
        Returns:
            List[Dict[str, Any]]: 共现条目列表
        """
        # 找出包含指定条目的文档
        target_docs = set()
        for ref in self._references:
            if ref.codex_id == entry_id and getattr(ref, 'status', 'active') == 'active':
                target_docs.add(ref.document_id)
        
        if not target_docs:
            return []
        
        # 统计在这些文档中出现的其他条目
        co_occurrences = {}
        for ref in self._references:
            if (ref.document_id in target_docs and 
                ref.codex_id != entry_id and 
                getattr(ref, 'status', 'active') == 'active'):
                
                if ref.codex_id not in co_occurrences:
                    co_occurrences[ref.codex_id] = {
                        'count': 0,
                        'documents': set()
                    }
                
                co_occurrences[ref.codex_id]['count'] += 1
                co_occurrences[ref.codex_id]['documents'].add(ref.document_id)
        
        # 过滤并排序结果
        results = []
        for codex_id, data in co_occurrences.items():
            if data['count'] >= threshold:
                entry = self._entries.get(codex_id)
                if entry:
                    results.append({
                        'entry_id': codex_id,
                        'title': entry.title,
                        'type': entry.entry_type.value,
                        'co_occurrence_count': data['count'],
                        'shared_documents': len(data['documents'])
                    })
        
        results.sort(key=lambda x: x['co_occurrence_count'], reverse=True)
        return results
    
    def get_progression_summary(self, entry_id: str) -> Dict[str, Any]:
        """
        获取条目的进展摘要 - 用于AI上下文生成
        
        Args:
            entry_id: 条目ID
            
        Returns:
            Dict[str, Any]: 进展摘要数据
        """
        if entry_id not in self._entries:
            return {}
        
        entry = self._entries[entry_id]
        
        if not entry.progression:
            return {
                'entry_title': entry.title,
                'total_events': 0,
                'summary': '暂无发展记录'
            }
        
        # 统计事件类型
        event_type_counts = {}
        for event in entry.progression:
            event_type = event.get('event_type', '未分类')
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # 获取最新事件
        latest_events = sorted(entry.progression, 
                             key=lambda x: x.get('timestamp', ''), 
                             reverse=True)[:3]
        
        # 获取关键章节
        chapters = set()
        for event in entry.progression:
            chapter_id = event.get('chapter_id')
            if chapter_id:
                chapters.add(chapter_id)
        
        # 生成文本摘要
        summary_parts = []
        summary_parts.append(f"在故事中共有{len(entry.progression)}个重要发展事件")
        
        if event_type_counts:
            type_summary = "，".join([f"{count}次{event_type}" 
                                   for event_type, count in event_type_counts.items()])
            summary_parts.append(f"包括{type_summary}")
        
        if chapters:
            summary_parts.append(f"涉及{len(chapters)}个章节")
        
        if latest_events:
            latest_desc = latest_events[0].get('description', '')
            if latest_desc:
                summary_parts.append(f"最近的发展：{latest_desc}")
        
        summary = "，".join(summary_parts) + "。"
        
        return {
            'entry_title': entry.title,
            'total_events': len(entry.progression),
            'event_type_counts': event_type_counts,
            'chapters_involved': list(chapters),
            'latest_events': latest_events,
            'summary': summary
        }