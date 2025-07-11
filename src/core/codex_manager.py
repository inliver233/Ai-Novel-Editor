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
from PyQt6.QtCore import QObject, pyqtSignal

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

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


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
        """保存Codex数据到数据库"""
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

    def add_entry(self, title: str, entry_type: CodexEntryType, 
                  description: str = "", is_global: bool = False,
                  aliases: List[str] = None) -> str:
        """添加新的Codex条目"""
        entry_id = str(uuid.uuid4())
        
        entry = CodexEntry(
            id=entry_id,
            title=title,
            entry_type=entry_type,
            description=description,
            is_global=is_global,
            aliases=aliases or []
        )
        
        self._entries[entry_id] = entry
        
        # 更新映射
        self._title_to_id[title.lower()] = entry_id
        for alias in entry.aliases:
            if alias.strip():
                self._alias_to_id[alias.lower().strip()] = entry_id
        
        # 重建引用模式
        self._rebuild_reference_patterns()
        
        # 保存数据
        self._save_data()
        
        # 发送信号
        self.entryAdded.emit(entry_id)
        
        logger.info(f"Added codex entry: {title} ({entry_type.value})")
        return entry_id

    def update_entry(self, entry_id: str, **kwargs) -> bool:
        """更新Codex条目"""
        if entry_id not in self._entries:
            logger.warning(f"Codex entry not found: {entry_id}")
            return False
        
        entry = self._entries[entry_id]
        
        # 如果标题或别名发生变化，需要更新映射
        old_title = entry.title
        old_aliases = entry.aliases[:]
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(entry, key):
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
        
        # 保存数据
        self._save_data()
        
        # 发送信号
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
        
        # 删除相关引用
        self._references = [ref for ref in self._references if ref.codex_id != entry_id]
        
        # 删除条目
        del self._entries[entry_id]
        
        # 重建引用模式
        self._rebuild_reference_patterns()
        
        # 保存数据
        self._save_data()
        
        # 发送信号
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