"""
概念检测器
基于PlotBunni的概念检测算法，自动检测文档中的概念引用
"""

import re
import logging
from typing import List, Set, Dict, Any, Optional
from dataclasses import dataclass
from core.concepts import Concept, ConceptType


logger = logging.getLogger(__name__)


@dataclass
class ConceptMatch:
    """概念匹配结果"""
    concept: Concept
    matched_text: str
    start_position: int
    end_position: int
    confidence: float = 1.0


class ConceptDetector:
    """概念检测器 - 基于PlotBunni的智能概念检测算法"""
    
    def __init__(self):
        self.concepts_db: List[Concept] = []
        self.concept_cache: Dict[str, List[ConceptMatch]] = {}
        
        # 检测配置
        self.min_word_length = 2
        self.max_cache_size = 1000
        
        logger.info("Concept detector initialized")
    
    def load_concepts(self, concepts: List[Concept]):
        """加载概念数据库"""
        self.concepts_db = concepts
        self.concept_cache.clear()  # 清空缓存
        
        logger.info(f"Loaded {len(concepts)} concepts into detector")
    
    def detect_concepts_in_text(self, text: str) -> List[Concept]:
        """在文本中检测概念 (PlotBunni的核心算法)"""
        if not text or not self.concepts_db:
            return []

        # 检查缓存
        text_hash = str(hash(text))
        if text_hash in self.concept_cache:
            matches = self.concept_cache[text_hash]
            return [match.concept for match in matches]

        detected_matches = []

        for concept in self.concepts_db:
            if self._is_concept_in_text(concept, text):
                match = ConceptMatch(
                    concept=concept,
                    matched_text="",  # 简化版本不记录具体匹配文本
                    start_position=0,
                    end_position=0
                )
                detected_matches.append(match)

        # 按优先级排序 (PlotBunni的排序逻辑)
        detected_matches.sort(key=lambda m: self._get_concept_priority(m.concept))

        # 缓存结果
        if len(self.concept_cache) < self.max_cache_size:
            self.concept_cache[text_hash] = detected_matches

        return [match.concept for match in detected_matches]

    def find_matching_concepts(self, partial_name: str) -> List[Concept]:
        """查找部分匹配的概念 - 用于自动补全"""
        if not partial_name or len(partial_name) < self.min_word_length:
            return []

        matching_concepts = []
        partial_lower = partial_name.lower()

        for concept in self.concepts_db:
            # 检查主名称
            if concept.name.lower().startswith(partial_lower):
                matching_concepts.append((concept, 1))  # 主名称匹配，优先级最高
            elif partial_lower in concept.name.lower():
                matching_concepts.append((concept, 2))  # 包含匹配，优先级中等
            else:
                # 检查别名
                for alias in getattr(concept, 'aliases', []):
                    if alias.lower().startswith(partial_lower):
                        matching_concepts.append((concept, 3))  # 别名匹配，优先级较低
                        break
                    elif partial_lower in alias.lower():
                        matching_concepts.append((concept, 4))  # 别名包含匹配，优先级最低
                        break

        # 按匹配优先级和概念优先级排序
        matching_concepts.sort(key=lambda x: (x[1], self._get_concept_priority(x[0])))

        # 返回概念列表，限制数量
        return [concept for concept, _ in matching_concepts[:10]]
    
    def _is_concept_in_text(self, concept: Concept, text: str) -> bool:
        """检查概念是否在文本中 (PlotBunni的匹配算法)"""
        # 构建搜索词列表
        search_terms = []
        
        # 添加主要名称
        if concept.name and concept.name.strip():
            search_terms.append(concept.name.strip())
        
        # 添加别名 (PlotBunni支持多别名)
        if hasattr(concept, 'aliases') and concept.aliases:
            for alias in concept.aliases:
                if alias and alias.strip():
                    search_terms.append(alias.strip())
        
        # 对每个搜索词进行正则匹配
        for term in search_terms:
            if len(term) >= self.min_word_length and self._match_term_in_text(term, text):
                return True
        
        return False
    
    def _match_term_in_text(self, term: str, text: str) -> bool:
        """在文本中匹配词汇 (PlotBunni的正则匹配逻辑)"""
        # 转义特殊字符 (PlotBunni的转义处理)
        escaped_term = re.escape(term)
        
        # 使用词边界匹配 (PlotBunni的精确匹配)
        pattern = rf'\b{escaped_term}\b'
        
        # 不区分大小写匹配
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def _get_concept_priority(self, concept: Concept) -> float:
        """获取概念优先级 (PlotBunni的优先级逻辑)"""
        if hasattr(concept, 'priority') and isinstance(concept.priority, (int, float)):
            return concept.priority
        
        # 根据概念类型设置默认优先级
        type_priorities = {
            ConceptType.CHARACTER: 1.0,
            ConceptType.LOCATION: 2.0,
            ConceptType.PLOT: 3.0,
            ConceptType.ITEM: 4.0,
            ConceptType.CONCEPT: 5.0
        }
        
        return type_priorities.get(concept.concept_type, float('inf'))
    
    def find_matching_concepts(self, partial_name: str) -> List[Concept]:
        """查找匹配的概念 (用于自动补全)"""
        if not partial_name or len(partial_name) < self.min_word_length:
            return []
        
        matching_concepts = []
        partial_lower = partial_name.lower()
        
        for concept in self.concepts_db:
            # 检查名称匹配
            if concept.name and concept.name.lower().startswith(partial_lower):
                matching_concepts.append(concept)
                continue
            
            # 检查别名匹配
            if hasattr(concept, 'aliases') and concept.aliases:
                for alias in concept.aliases:
                    if alias and alias.lower().startswith(partial_lower):
                        matching_concepts.append(concept)
                        break
        
        # 按优先级排序
        matching_concepts.sort(key=lambda c: self._get_concept_priority(c))
        return matching_concepts[:10]  # 限制返回数量
    
    def detect_detailed_matches(self, text: str) -> List[ConceptMatch]:
        """检测详细的概念匹配信息"""
        if not text or not self.concepts_db:
            return []
        
        detailed_matches = []
        
        for concept in self.concepts_db:
            matches = self._find_concept_matches(concept, text)
            detailed_matches.extend(matches)
        
        # 按位置排序
        detailed_matches.sort(key=lambda m: m.start_position)
        
        return detailed_matches
    
    def _find_concept_matches(self, concept: Concept, text: str) -> List[ConceptMatch]:
        """查找概念的所有匹配位置"""
        matches = []
        
        # 构建搜索词列表
        search_terms = [concept.name]
        if hasattr(concept, 'aliases') and concept.aliases:
            search_terms.extend(concept.aliases)
        
        for term in search_terms:
            if not term or len(term) < self.min_word_length:
                continue
            
            # 转义特殊字符
            escaped_term = re.escape(term)
            pattern = rf'\b{escaped_term}\b'
            
            # 查找所有匹配
            for match in re.finditer(pattern, text, re.IGNORECASE):
                concept_match = ConceptMatch(
                    concept=concept,
                    matched_text=match.group(),
                    start_position=match.start(),
                    end_position=match.end(),
                    confidence=self._calculate_match_confidence(concept, term, text)
                )
                matches.append(concept_match)
        
        return matches
    
    def _calculate_match_confidence(self, concept: Concept, matched_term: str, text: str) -> float:
        """计算匹配置信度"""
        confidence = 1.0
        
        # 完整名称匹配的置信度更高
        if matched_term.lower() == concept.name.lower():
            confidence = 1.0
        elif hasattr(concept, 'aliases') and matched_term.lower() in [a.lower() for a in concept.aliases]:
            confidence = 0.8
        else:
            confidence = 0.6
        
        # 根据上下文调整置信度
        # 这里可以添加更复杂的上下文分析逻辑
        
        return confidence
    
    def get_concept_statistics(self, text: str) -> Dict[str, Any]:
        """获取概念统计信息"""
        matches = self.detect_detailed_matches(text)
        
        stats = {
            'total_matches': len(matches),
            'unique_concepts': len(set(m.concept.id for m in matches)),
            'concept_types': {},
            'most_frequent': [],
            'coverage_ratio': 0.0
        }
        
        # 按类型统计
        for match in matches:
            concept_type = match.concept.concept_type.value
            stats['concept_types'][concept_type] = stats['concept_types'].get(concept_type, 0) + 1
        
        # 计算最频繁的概念
        concept_counts = {}
        for match in matches:
            concept_id = match.concept.id
            concept_counts[concept_id] = concept_counts.get(concept_id, 0) + 1
        
        sorted_concepts = sorted(concept_counts.items(), key=lambda x: x[1], reverse=True)
        stats['most_frequent'] = sorted_concepts[:5]
        
        # 计算覆盖率
        if text:
            matched_chars = sum(m.end_position - m.start_position for m in matches)
            stats['coverage_ratio'] = matched_chars / len(text)
        
        return stats
    
    def clear_cache(self):
        """清空缓存"""
        self.concept_cache.clear()
        logger.debug("Concept detection cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            'cache_size': len(self.concept_cache),
            'max_cache_size': self.max_cache_size,
            'concepts_loaded': len(self.concepts_db)
        }

    def add_concept(self, concept: Concept):
        """添加概念到检测器"""
        if concept not in self.concepts_db:
            self.concepts_db.append(concept)
            self.concept_cache.clear()  # 清空缓存
            logger.debug(f"Added concept: {concept.name}")

    def remove_concept(self, concept_id: str):
        """从检测器中移除概念"""
        self.concepts_db = [c for c in self.concepts_db if c.id != concept_id]
        self.concept_cache.clear()  # 清空缓存
        logger.debug(f"Removed concept: {concept_id}")

    def get_concepts_by_type(self, concept_type) -> List[Concept]:
        """按类型获取概念"""
        return [c for c in self.concepts_db if c.concept_type == concept_type]

    def detect_concepts(self, text: str) -> List[Dict[str, Any]]:
        """检测概念并返回字典格式（兼容接口）"""
        concepts = self.detect_concepts_in_text(text)
        return [self._concept_to_dict(c) for c in concepts]

    def _concept_to_dict(self, concept: Concept) -> Dict[str, Any]:
        """将概念转换为字典格式"""
        return {
            'id': concept.id,
            'name': concept.name,
            'type': concept.concept_type.value,
            'description': getattr(concept, 'description', ''),
            'aliases': getattr(concept, 'aliases', [])
        }

    @property
    def _concepts(self) -> Dict[str, Concept]:
        """兼容属性：返回概念字典"""
        return {c.id: c for c in self.concepts_db}
