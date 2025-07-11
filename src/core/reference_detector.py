"""
引用检测器
基于NovelCrafter的引用检测机制，智能识别文本中的Codex条目引用
"""

import re
import logging
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass

from .codex_manager import CodexManager, CodexEntry, CodexEntryType

logger = logging.getLogger(__name__)


@dataclass
class DetectedReference:
    """检测到的引用"""
    entry_id: str
    entry_title: str
    entry_type: CodexEntryType
    matched_text: str
    start_position: int
    end_position: int
    confidence: float  # 匹配置信度 0.0-1.0
    context_before: str = ""
    context_after: str = ""


class ReferenceDetector:
    """智能引用检测器"""
    
    def __init__(self, codex_manager: CodexManager):
        self.codex_manager = codex_manager
        
        # 检测配置
        self.min_word_length = 2  # 最小词长
        self.context_window = 50  # 上下文窗口大小
        self.confidence_threshold = 0.7  # 置信度阈值
        
        # 中文名字检测模式
        self.chinese_name_patterns = [
            r'[\u4e00-\u9fff]{2,4}',  # 2-4个中文字符
            r'[\u4e00-\u9fff][\u4e00-\u9fff\u0030-\u0039A-Za-z]+',  # 中文开头的混合名称
        ]
        
        # 地点名称检测模式
        self.location_patterns = [
            r'[\u4e00-\u9fff]{2,6}(?:城|镇|村|国|省|市|区|县|山|河|湖|海|岛|宫|院|寺|观|楼|塔|桥)',
            r'(?:东|西|南|北|中)[\u4e00-\u9fff]{1,4}',
            r'[\u4e00-\u9fff]{2,4}(?:大陆|王国|帝国|公国|共和国)',
        ]
        
        # 物品名称检测模式  
        self.object_patterns = [
            r'[\u4e00-\u9fff]{2,6}(?:剑|刀|枪|矛|斧|锤|弓|盾|甲|袍|冠|戒|珠|石|书|卷|符|丹|药)',
            r'(?:神|魔|仙|圣|邪|天|地|玄|黄)[\u4e00-\u9fff]{1,4}',
        ]
        
        logger.info("ReferenceDetector initialized")

    def detect_references(self, text: str, document_id: str = None) -> List[DetectedReference]:
        """
        检测文本中的所有Codex引用
        
        Args:
            text: 待检测的文本
            document_id: 文档ID（可选）
            
        Returns:
            检测到的引用列表
        """
        if not text.strip():
            return []
        
        references = []
        
        # 1. 精确匹配已知的Codex条目
        exact_matches = self._detect_exact_matches(text)
        references.extend(exact_matches)
        
        # 2. 模糊匹配潜在的引用
        fuzzy_matches = self._detect_fuzzy_matches(text, exact_matches)
        references.extend(fuzzy_matches)
        
        # 3. 去重和排序
        references = self._deduplicate_references(references)
        references.sort(key=lambda x: x.start_position)
        
        # 4. 添加上下文信息
        for ref in references:
            ref.context_before, ref.context_after = self._extract_context(
                text, ref.start_position, ref.end_position
            )
        
        logger.debug(f"Detected {len(references)} references in text")
        return references

    def _detect_exact_matches(self, text: str) -> List[DetectedReference]:
        """检测与已知Codex条目的精确匹配"""
        references = []
        
        for entry in self.codex_manager.get_all_entries():
            if not entry.track_references:
                continue
            
            # 检测标题匹配
            title_matches = self._find_text_matches(text, entry.title, entry)
            references.extend(title_matches)
            
            # 检测别名匹配
            for alias in entry.aliases:
                if alias.strip():
                    alias_matches = self._find_text_matches(text, alias.strip(), entry)
                    references.extend(alias_matches)
        
        return references

    def _find_text_matches(self, text: str, search_term: str, entry: CodexEntry) -> List[DetectedReference]:
        """查找特定词汇在文本中的匹配"""
        if len(search_term) < self.min_word_length:
            return []
        
        references = []
        
        # 创建词边界正则模式
        pattern = r'\b' + re.escape(search_term) + r'\b'
        
        try:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                reference = DetectedReference(
                    entry_id=entry.id,
                    entry_title=entry.title,
                    entry_type=entry.entry_type,
                    matched_text=match.group(),
                    start_position=match.start(),
                    end_position=match.end(),
                    confidence=1.0  # 精确匹配的置信度为100%
                )
                references.append(reference)
        except re.error as e:
            logger.warning(f"Regex error for term '{search_term}': {e}")
        
        return references

    def _detect_fuzzy_matches(self, text: str, exact_matches: List[DetectedReference]) -> List[DetectedReference]:
        """检测模糊匹配的潜在引用"""
        references = []
        
        # 获取已经精确匹配的位置，避免重复检测
        matched_positions = set()
        for ref in exact_matches:
            matched_positions.update(range(ref.start_position, ref.end_position))
        
        # 使用不同的模式检测不同类型的引用
        pattern_configs = [
            (self.chinese_name_patterns, CodexEntryType.CHARACTER, 0.8),
            (self.location_patterns, CodexEntryType.LOCATION, 0.7),
            (self.object_patterns, CodexEntryType.OBJECT, 0.6),
        ]
        
        for patterns, entry_type, base_confidence in pattern_configs:
            type_matches = self._detect_by_patterns(
                text, patterns, entry_type, base_confidence, matched_positions
            )
            references.extend(type_matches)
        
        return references

    def _detect_by_patterns(self, text: str, patterns: List[str], entry_type: CodexEntryType, 
                           base_confidence: float, exclude_positions: Set[int]) -> List[DetectedReference]:
        """使用特定模式检测引用"""
        references = []
        
        for pattern_str in patterns:
            try:
                pattern = re.compile(pattern_str)
                for match in pattern.finditer(text):
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # 检查是否与已匹配的位置重叠
                    if any(pos in exclude_positions for pos in range(start_pos, end_pos)):
                        continue
                    
                    matched_text = match.group()
                    
                    # 计算置信度
                    confidence = self._calculate_confidence(matched_text, entry_type, base_confidence)
                    
                    if confidence >= self.confidence_threshold:
                        reference = DetectedReference(
                            entry_id="",  # 模糊匹配没有确定的entry_id
                            entry_title=matched_text,
                            entry_type=entry_type,
                            matched_text=matched_text,
                            start_position=start_pos,
                            end_position=end_pos,
                            confidence=confidence
                        )
                        references.append(reference)
                        
                        # 标记这些位置已被匹配
                        exclude_positions.update(range(start_pos, end_pos))
                        
            except re.error as e:
                logger.warning(f"Pattern compilation error: {e}")
        
        return references

    def _calculate_confidence(self, text: str, entry_type: CodexEntryType, base_confidence: float) -> float:
        """计算匹配置信度"""
        confidence = base_confidence
        
        # 根据长度调整置信度
        if len(text) >= 4:
            confidence += 0.1
        elif len(text) <= 2:
            confidence -= 0.2
        
        # 根据字符类型调整
        if entry_type == CodexEntryType.CHARACTER:
            # 角色名通常是纯中文或中英混合
            if re.match(r'^[\u4e00-\u9fff]+$', text):
                confidence += 0.1
            elif re.match(r'^[\u4e00-\u9fff][A-Za-z]+$', text):
                confidence += 0.05
        
        elif entry_type == CodexEntryType.LOCATION:
            # 地点名带有特定后缀的置信度更高
            location_suffixes = ['城', '镇', '村', '国', '省', '市', '山', '河', '湖']
            if any(text.endswith(suffix) for suffix in location_suffixes):
                confidence += 0.15
        
        elif entry_type == CodexEntryType.OBJECT:
            # 物品名带有特定后缀的置信度更高
            object_suffixes = ['剑', '刀', '枪', '书', '珠', '石', '丹', '药']
            if any(text.endswith(suffix) for suffix in object_suffixes):
                confidence += 0.1
        
        return max(0.0, min(1.0, confidence))

    def _deduplicate_references(self, references: List[DetectedReference]) -> List[DetectedReference]:
        """去除重复的引用"""
        if not references:
            return []
        
        # 按位置排序
        references.sort(key=lambda x: (x.start_position, x.end_position))
        
        deduplicated = []
        for ref in references:
            # 检查是否与已有引用重叠
            is_duplicate = False
            for existing_ref in deduplicated:
                if self._references_overlap(ref, existing_ref):
                    # 如果重叠，保留置信度更高的
                    if ref.confidence > existing_ref.confidence:
                        deduplicated.remove(existing_ref)
                        deduplicated.append(ref)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(ref)
        
        return deduplicated

    def _references_overlap(self, ref1: DetectedReference, ref2: DetectedReference) -> bool:
        """检查两个引用是否重叠"""
        return not (ref1.end_position <= ref2.start_position or 
                   ref2.end_position <= ref1.start_position)

    def _extract_context(self, text: str, start_pos: int, end_pos: int) -> Tuple[str, str]:
        """提取引用的上下文"""
        context_start = max(0, start_pos - self.context_window)
        context_end = min(len(text), end_pos + self.context_window)
        
        context_before = text[context_start:start_pos]
        context_after = text[end_pos:context_end]
        
        return context_before, context_after

    def update_detection_config(self, **kwargs):
        """更新检测配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Updated detection config: {key} = {value}")

    def get_detection_statistics(self) -> Dict[str, any]:
        """获取检测统计信息"""
        all_entries = self.codex_manager.get_all_entries()
        
        stats = {
            'total_trackable_entries': len([e for e in all_entries if e.track_references]),
            'total_aliases': sum(len(e.aliases) for e in all_entries),
            'entry_types': {},
            'pattern_configs': {
                'min_word_length': self.min_word_length,
                'confidence_threshold': self.confidence_threshold,
                'context_window': self.context_window
            }
        }
        
        # 统计各类型条目数量
        for entry_type in CodexEntryType:
            count = len([e for e in all_entries if e.entry_type == entry_type and e.track_references])
            stats['entry_types'][entry_type.value] = count
        
        return stats