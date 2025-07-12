"""
增强引用检测器
结合中文分词技术，提供更智能的引用检测
"""

import logging
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

from .reference_detector import ReferenceDetector, DetectedReference
from .codex_manager import CodexManager, CodexEntry
from .chinese_segmentation import get_segmenter, SegmentedWord, WordType

logger = logging.getLogger(__name__)


@dataclass
class EnhancedDetectedReference(DetectedReference):
    """增强的检测引用，包含分词信息"""
    segment_info: Optional[SegmentedWord] = None
    confidence_factors: Dict[str, float] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.confidence_factors is None:
            self.confidence_factors = {}


class EnhancedReferenceDetector(ReferenceDetector):
    """增强引用检测器，结合分词技术"""
    
    def __init__(self, codex_manager: CodexManager):
        super().__init__(codex_manager)
        self.segmenter = get_segmenter()
        
        # 更新分词器的自定义词典
        self._update_segmenter_dictionary()
        
        # 检测配置优化
        self.confidence_threshold = 0.6  # 降低阈值，使用更智能的置信度计算
        self.enable_segmentation = True   # 启用分词增强
        self.enable_context_analysis = True  # 启用上下文分析
        
        logger.info("Enhanced reference detector initialized with segmentation support")
    
    def _update_segmenter_dictionary(self):
        """更新分词器词典"""
        try:
            all_entries = self.codex_manager.get_all_entries()
            self.segmenter.update_custom_dictionary(all_entries)
        except Exception as e:
            logger.warning(f"Failed to update segmenter dictionary: {e}")
    
    def detect_references(self, text: str, document_id: str = None) -> List[DetectedReference]:
        """
        增强的引用检测
        
        Args:
            text: 待检测的文本
            document_id: 文档ID（可选）
            
        Returns:
            检测到的引用列表
        """
        if not text.strip():
            return []
        
        references = []
        
        if self.enable_segmentation:
            # 使用分词增强的检测
            references = self._detect_with_segmentation(text)
        else:
            # 降级到基础检测
            references = super().detect_references(text, document_id)
        
        # 去重和排序
        references = self._deduplicate_enhanced_references(references)
        references.sort(key=lambda x: x.start_position)
        
        # 添加上下文信息
        for ref in references:
            ref.context_before, ref.context_after = self._extract_context(
                text, ref.start_position, ref.end_position
            )
        
        logger.debug(f"Enhanced detection found {len(references)} references")
        return references
    
    def _detect_with_segmentation(self, text: str) -> List[DetectedReference]:
        """使用分词进行增强检测"""
        references = []
        
        # 1. 基础精确匹配（保持原有功能）
        exact_matches = self._detect_exact_matches_enhanced(text)
        references.extend(exact_matches)
        
        # 2. 分词辅助的智能检测
        if self.enable_segmentation:
            segmented_matches = self._detect_with_word_segmentation(text, exact_matches)
            references.extend(segmented_matches)
        
        return references
    
    def _detect_exact_matches_enhanced(self, text: str) -> List[DetectedReference]:
        """增强的精确匹配"""
        references = []
        
        for entry in self.codex_manager.get_all_entries():
            if not entry.track_references:
                continue
            
            # 检查标题
            title_matches = self._find_text_matches_enhanced(text, entry.title, entry)
            references.extend(title_matches)
            
            # 检查别名
            if entry.aliases:
                for alias in entry.aliases:
                    alias_matches = self._find_text_matches_enhanced(text, alias, entry)
                    references.extend(alias_matches)
        
        return references
    
    def _find_text_matches_enhanced(self, text: str, search_term: str, entry: CodexEntry) -> List[DetectedReference]:
        """增强的文本匹配"""
        if len(search_term) < self.min_word_length:
            return []
        
        references = []
        
        # 使用基础的直接匹配（已经修复了中文支持）
        import re
        escaped_term = re.escape(search_term)
        pattern = escaped_term
        
        try:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # 计算增强的置信度
                confidence = self._calculate_enhanced_confidence(
                    text, match, search_term, entry
                )
                
                if confidence >= self.confidence_threshold:
                    reference = EnhancedDetectedReference(
                        entry_id=entry.id,
                        entry_title=entry.title,
                        entry_type=entry.entry_type,
                        matched_text=match.group(),
                        start_position=match.start(),
                        end_position=match.end(),
                        confidence=confidence,
                        confidence_factors={}
                    )
                    references.append(reference)
                    
        except re.error as e:
            logger.warning(f"Regex error for term '{search_term}': {e}")
        
        return references
    
    def _detect_with_word_segmentation(self, text: str, existing_matches: List[DetectedReference]) -> List[DetectedReference]:
        """基于分词的智能检测"""
        references = []
        
        # 获取已匹配的位置
        matched_positions = set()
        for ref in existing_matches:
            matched_positions.update(range(ref.start_position, ref.end_position))
        
        try:
            # 对文本进行分词
            segments = self.segmenter.segment_text(text, with_pos=True)
            
            # 分析每个分词
            for segment in segments:
                # 跳过已匹配的位置
                if any(pos in matched_positions for pos in range(segment.start, segment.end)):
                    continue
                
                # 检查是否为有意义的词汇
                if self._is_meaningful_segment(segment):
                    # 尝试匹配Codex条目
                    matched_entry = self._find_entry_by_segment(segment)
                    if matched_entry:
                        confidence = self._calculate_segment_confidence(segment, matched_entry)
                        
                        if confidence >= self.confidence_threshold:
                            reference = EnhancedDetectedReference(
                                entry_id=matched_entry.id,
                                entry_title=matched_entry.title,
                                entry_type=matched_entry.entry_type,
                                matched_text=segment.word,
                                start_position=segment.start,
                                end_position=segment.end,
                                confidence=confidence,
                                segment_info=segment
                            )
                            references.append(reference)
                            
                            # 标记位置已匹配
                            matched_positions.update(range(segment.start, segment.end))
        
        except Exception as e:
            logger.warning(f"Segmentation-based detection failed: {e}")
        
        return references
    
    def _is_meaningful_segment(self, segment: SegmentedWord) -> bool:
        """判断分词是否有意义"""
        # 过滤掉标点符号、连词等
        if segment.word_type in [WordType.PUNCTUATION, WordType.CONJUNCTION, WordType.PARTICLE]:
            return False
        
        # 过滤掉单字（除非是重要的单字）
        if len(segment.word) < 2:
            return False
        
        # 过滤掉纯数字
        if segment.word.isdigit():
            return False
        
        return True
    
    def _find_entry_by_segment(self, segment: SegmentedWord) -> Optional[CodexEntry]:
        """根据分词查找对应的Codex条目"""
        word = segment.word
        
        # 精确匹配标题
        entry = self.codex_manager.get_entry_by_title(word)
        if entry:
            return entry
        
        # 匹配别名
        entry = self.codex_manager.get_entry_by_alias(word)
        if entry:
            return entry
        
        # 模糊匹配（如果词是某个条目的子串）
        all_entries = self.codex_manager.get_all_entries()
        for entry in all_entries:
            # 检查是否为条目标题的一部分
            if word in entry.title or entry.title in word:
                # 确保不是意外的包含关系
                if abs(len(word) - len(entry.title)) <= 2:
                    return entry
            
            # 检查别名
            if entry.aliases:
                for alias in entry.aliases:
                    if word in alias or alias in word:
                        if abs(len(word) - len(alias)) <= 2:
                            return entry
        
        return None
    
    def _calculate_enhanced_confidence(self, text: str, match, search_term: str, entry: CodexEntry) -> float:
        """计算增强的置信度"""
        base_confidence = 1.0  # 精确匹配的基础置信度
        factors = {}
        
        # 因子1: 匹配类型
        if match.group() == entry.title:
            factors['exact_title_match'] = 0.2
        elif entry.aliases and match.group() in entry.aliases:
            factors['alias_match'] = 0.1
        
        # 因子2: 词长度
        word_length = len(search_term)
        if word_length >= 3:
            factors['word_length'] = 0.1
        elif word_length == 2:
            factors['word_length'] = 0.0
        else:
            factors['word_length'] = -0.2
        
        # 因子3: 上下文分析
        context_score = self._analyze_context_match(text, match, entry)
        factors['context_match'] = context_score * 0.15
        
        # 因子4: 全局条目加权
        if entry.is_global:
            factors['global_entry'] = 0.1
        
        # 计算最终置信度
        final_confidence = base_confidence + sum(factors.values())
        return max(0.0, min(1.0, final_confidence))  # 限制在0-1范围内
    
    def _calculate_segment_confidence(self, segment: SegmentedWord, entry: CodexEntry) -> float:
        """计算分词的置信度"""
        base_confidence = 0.7  # 分词匹配的基础置信度
        factors = {}
        
        # 因子1: 词性匹配
        if entry.entry_type.name == 'CHARACTER' and segment.word_type == WordType.NOUN:
            factors['pos_match'] = 0.2
        elif entry.entry_type.name == 'LOCATION' and segment.word_type == WordType.NOUN:
            factors['pos_match'] = 0.2
        
        # 因子2: 精确匹配
        if segment.word == entry.title:
            factors['exact_match'] = 0.2
        elif entry.aliases and segment.word in entry.aliases:
            factors['alias_match'] = 0.15
        
        # 因子3: 词长度
        if len(segment.word) >= 3:
            factors['word_length'] = 0.1
        
        # 计算最终置信度
        final_confidence = base_confidence + sum(factors.values())
        return max(0.0, min(1.0, final_confidence))
    
    def _analyze_context_match(self, text: str, match, entry: CodexEntry) -> float:
        """分析上下文匹配度"""
        try:
            # 获取匹配词周围的上下文
            start_pos = max(0, match.start() - 20)
            end_pos = min(len(text), match.end() + 20)
            context = text[start_pos:end_pos]
            
            # 简单的上下文分析
            score = 0.0
            
            # 检查上下文中是否有相关的条目类型关键词
            if entry.entry_type.name == 'CHARACTER':
                character_keywords = ['说', '道', '想', '看', '听', '走', '来', '去', '的']
                for keyword in character_keywords:
                    if keyword in context:
                        score += 0.1
                        break
            
            elif entry.entry_type.name == 'LOCATION':
                location_keywords = ['在', '到', '去', '来', '的', '中', '里', '内', '外']
                for keyword in location_keywords:
                    if keyword in context:
                        score += 0.1
                        break
            
            return min(score, 1.0)
        
        except Exception:
            return 0.0
    
    def _deduplicate_enhanced_references(self, references: List[DetectedReference]) -> List[DetectedReference]:
        """去重增强引用"""
        if not references:
            return []
        
        # 按位置和内容去重
        seen = set()
        unique_refs = []
        
        for ref in references:
            key = (ref.start_position, ref.end_position, ref.entry_id)
            if key not in seen:
                seen.add(key)
                unique_refs.append(ref)
        
        return unique_refs
    
    def get_text_analysis(self, text: str) -> Dict:
        """获取文本的完整分析"""
        analysis = self.segmenter.analyze_text_structure(text)
        
        # 添加引用检测结果
        references = self.detect_references(text)
        analysis['detected_references'] = len(references)
        analysis['reference_details'] = [
            {
                'text': ref.matched_text,
                'type': ref.entry_type.value,
                'confidence': ref.confidence,
                'position': f"{ref.start_position}-{ref.end_position}"
            }
            for ref in references
        ]
        
        return analysis
    
    def refresh_custom_dictionary(self):
        """刷新自定义词典"""
        self._update_segmenter_dictionary()
        logger.info("Custom dictionary refreshed")