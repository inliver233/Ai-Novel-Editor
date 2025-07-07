"""
概念管理核心模块
基于PlotBunni的概念系统设计，实现智能概念检测和管理
"""

import json
import logging
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict, fields, field
from enum import Enum

from .config import Config
from .shared import Shared


logger = logging.getLogger(__name__)


class ConceptType(Enum):
    """概念类型枚举"""
    CHARACTER = "character"
    LOCATION = "location"
    PLOT = "plot"
    SETTING = "setting"
    ITEM = "item"
    EVENT = "event"


@dataclass
class Concept:
    """概念基础数据模型"""
    id: str
    name: str
    aliases: List[str]
    description: str
    concept_type: ConceptType
    tags: List[str]
    priority: int
    auto_detect: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """将概念对象转换为可序列化的字典"""
        data = asdict(self)
        data['concept_type'] = self.concept_type.value
        data['created_at'] = self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        data['updated_at'] = self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at
        return data

@dataclass
class CharacterConcept(Concept):
    """角色概念扩展模型"""
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    personality_traits: List[str] = field(default_factory=list)
    relationships: List[Dict[str, str]] = field(default_factory=list)
    appearance: Optional[str] = None
    backstory: Optional[str] = None

@dataclass
class LocationConcept(Concept):
    """地点概念扩展模型"""
    location_type: str = "general"
    parent_location: Optional[str] = None
    atmosphere: Optional[str] = None
    significance: Optional[str] = None
    physical_description: Optional[str] = None

@dataclass
class PlotConcept(Concept):
    """情节概念扩展模型"""
    plot_type: str = "main"
    status: str = "planned"
    related_characters: List[str] = field(default_factory=list)
    related_locations: List[str] = field(default_factory=list)
    conflict_type: Optional[str] = None
    resolution: Optional[str] = None

CONCEPT_TYPE_MAP = {
    ConceptType.CHARACTER: CharacterConcept,
    ConceptType.LOCATION: LocationConcept,
    ConceptType.PLOT: PlotConcept,
}

class ConceptDetector:
    """概念检测器"""
    
    def __init__(self):
        self._concepts: Dict[str, Concept] = {}
        self._detection_cache: Dict[str, Set[str]] = {}
        self._regex_cache: Dict[str, re.Pattern] = {}
        
    def add_concept(self, concept: Concept):
        self._concepts[concept.id] = concept
        self._clear_cache()
    
    def remove_concept(self, concept_id: str):
        if concept_id in self._concepts:
            del self._concepts[concept_id]
            self._clear_cache()

    def get_all_concepts(self) -> List[Concept]:
        return list(self._concepts.values())

    def clear_all_concepts(self):
        self._concepts.clear()
        self._clear_cache()
        logger.info("All concepts cleared from memory.")
    
    def detect_concepts(self, text: str) -> List[Dict[str, Any]]:
        if not text.strip(): return []
        text_hash = str(hash(text))
        if text_hash in self._detection_cache:
            concept_ids = self._detection_cache[text_hash]
            return [self._concepts[cid].to_dict() for cid in concept_ids if cid in self._concepts]
        
        detected = set()
        for concept in self._concepts.values():
            if not concept.auto_detect: continue
            if self._match_concept_name(text, concept.name):
                detected.add(concept.id)
                continue
            for alias in concept.aliases:
                if self._match_concept_name(text, alias):
                    detected.add(concept.id)
                    break
        
        self._detection_cache[text_hash] = detected
        result_concepts = sorted([self._concepts[cid] for cid in detected], key=lambda x: x.priority, reverse=True)
        return [c.to_dict() for c in result_concepts]
    
    def _match_concept_name(self, text: str, name: str) -> bool:
        if not name.strip(): return False
        if name not in self._regex_cache:
            self._regex_cache[name] = re.compile(rf'\b{re.escape(name)}\b', re.IGNORECASE)
        return bool(self._regex_cache[name].search(text))
    
    def _clear_cache(self):
        self._detection_cache.clear()
        self._regex_cache.clear()
    
    def get_concepts_by_type(self, concept_type: ConceptType) -> List[Concept]:
        return [c for c in self._concepts.values() if c.concept_type == concept_type]
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        return self._concepts.get(concept_id)

class ConceptManager:
    """概念管理器 - 仅负责内存操作"""
    
    def __init__(self, config: Config, shared: Shared):
        self._config = config
        self._shared = shared
        self._detector = ConceptDetector()
        logger.info("Concept manager initialized (In-Memory)")

    def reload_concepts(self, concepts_data: List[Dict[str, Any]] = None):
        self._detector.clear_all_concepts()
        if concepts_data:
            self.load_concepts_from_list(concepts_data)
        logger.info(f"Concepts reloaded. Loaded {len(concepts_data) if concepts_data else 0} concepts.")

    @property
    def detector(self) -> ConceptDetector:
        return self._detector
    
    def create_concept(self, name: str, concept_type: ConceptType, **kwargs) -> Concept:
        concept_id = str(uuid.uuid4())
        now = datetime.now()
        
        base_args = {
            'id': concept_id, 'name': name, 'concept_type': concept_type,
            'created_at': now, 'updated_at': now
        }
        
        # 为可选字段提供默认值
        defaults = {
            'aliases': [], 'description': "", 'tags': [], 
            'priority': 5, 'auto_detect': True, 'metadata': {}
        }
        for key, value in defaults.items():
            base_args[key] = kwargs.pop(key, value)

        concept_class = CONCEPT_TYPE_MAP.get(concept_type, Concept)
        valid_fields = {f.name for f in fields(concept_class)}
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        final_args = {**base_args, **filtered_kwargs}
        concept = concept_class(**final_args)
        
        self._detector.add_concept(concept)
        logger.info(f"Concept created in memory: {name} ({concept_type.value})")
        return concept.id
    
    def update_concept(self, concept_id: str, **kwargs) -> bool:
        concept = self._detector.get_concept(concept_id)
        if not concept: return False
        
        for key, value in kwargs.items():
            if hasattr(concept, key):
                if key == 'concept_type' and isinstance(value, str):
                    value = ConceptType(value)
                setattr(concept, key, value)
        
        concept.updated_at = datetime.now()
        logger.info(f"Concept updated in memory: {concept.name}")
        return True
    
    def delete_concept(self, concept_id: str) -> bool:
        concept = self._detector.get_concept(concept_id)
        if not concept: return False
        self._detector.remove_concept(concept_id)
        logger.info(f"Concept deleted from memory: {concept.name}")
        return True

    def get_concepts_by_type(self, concept_type: ConceptType) -> List[Concept]:
        return self._detector.get_concepts_by_type(concept_type)

    def get_all_concepts_as_dicts(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._detector.get_all_concepts()]

    def load_concepts_from_list(self, concepts_data: List[Dict[str, Any]]):
        for data in concepts_data:
            concept = self._dict_to_concept(data)
            if concept:
                self._detector.add_concept(concept)
    
    def _dict_to_concept(self, data: Dict[str, Any]) -> Optional[Concept]:
        try:
            concept_data = data.copy()
            concept_type_str = concept_data.get('concept_type')
            if not concept_type_str: return None
            
            concept_type = ConceptType(concept_type_str)
            concept_data['concept_type'] = concept_type # <--- 关键修复

            for key in ['created_at', 'updated_at']:
                if isinstance(concept_data.get(key), str):
                    concept_data[key] = datetime.fromisoformat(concept_data[key])
                else:
                    concept_data[key] = datetime.now()

            concept_class = CONCEPT_TYPE_MAP.get(concept_type, Concept)
            valid_fields = {f.name for f in fields(concept_class)}
            filtered_data = {k: v for k, v in concept_data.items() if k in valid_fields}
            
            return concept_class(**filtered_data)
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Failed to convert dict to concept: {data.get('name')}, Error: {e}", exc_info=True)
            return None

