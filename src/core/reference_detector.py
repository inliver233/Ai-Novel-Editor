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
        self.confidence_threshold = 0.75  # 置信度阈值（平衡准确率和召回率）
        
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
        
        # 2. 暂时禁用模糊匹配，专注于修复精确匹配
        # fuzzy_matches = self._detect_fuzzy_matches(text, exact_matches)
        # references.extend(fuzzy_matches)
        
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
        """查找特定词汇在文本中的匹配 - 改进的中文词边界检测版本"""
        if len(search_term) < self.min_word_length:
            return []
        
        references = []
        escaped_term = re.escape(search_term)
        
        try:
            # 先进行简单匹配找到所有可能的位置
            for match in re.finditer(escaped_term, text, re.IGNORECASE):
                start_pos = match.start()
                end_pos = match.end()
                matched_text = match.group()
                
                # 进行词边界验证和上下文检查
                if self._is_valid_match(text, search_term, start_pos, end_pos, entry):
                    confidence = self._calculate_confidence(text, search_term, start_pos, end_pos, entry)
                    
                    if confidence >= self.confidence_threshold:
                        reference = DetectedReference(
                            entry_id=entry.id,
                            entry_title=entry.title,
                            entry_type=entry.entry_type,
                            matched_text=matched_text,
                            start_position=start_pos,
                            end_position=end_pos,
                            confidence=confidence
                        )
                        references.append(reference)
                        
        except re.error as e:
            logger.warning(f"Regex error for term '{search_term}': {e}")
        
        return references

    def _is_valid_match(self, text: str, search_term: str, start_pos: int, end_pos: int, entry: CodexEntry) -> bool:
        """
        验证匹配是否为有效的词边界匹配
        
        Args:
            text: 原文本
            search_term: 搜索词
            start_pos: 匹配开始位置
            end_pos: 匹配结束位置
            entry: Codex条目
            
        Returns:
            bool: 是否为有效匹配
        """
        # 获取匹配词的前后字符
        char_before = text[start_pos - 1] if start_pos > 0 else ""
        char_after = text[end_pos] if end_pos < len(text) else ""
        
        # 中文词边界检测规则
        if self._is_chinese_char(search_term[0]):
            # 对于中文词汇的边界检测
            return self._is_chinese_word_boundary(char_before, char_after, search_term, text, start_pos, end_pos)
        else:
            # 对于英文词汇的边界检测
            return self._is_english_word_boundary(char_before, char_after)

    def _is_chinese_word_boundary(self, char_before: str, char_after: str, search_term: str, 
                                text: str, start_pos: int, end_pos: int) -> bool:
        """检测中文词边界"""
        
        # 规则1: 如果前后都是中文字符，需要进行更细致的检查
        if self._is_chinese_char(char_before) and self._is_chinese_char(char_after):
            # 检查是否为否定语境（如"不是张三"、"没有张三"）
            if self._is_negative_context(text, start_pos, search_term):
                return False
                
            # 检查是否为组合词的一部分（如"张三丰"中的"张三"）
            if self._is_part_of_compound_word(text, start_pos, end_pos, search_term):
                return False
        
        # 规则2: 前后有标点符号或空白符，通常是好的边界
        if (not char_before or self._is_delimiter(char_before)) and \
           (not char_after or self._is_delimiter(char_after)):
            return True
            
        # 规则3: 前面是数字、英文，后面是中文或标点，可能是有效匹配
        if (not self._is_chinese_char(char_before)) and \
           (not char_after or not self._is_chinese_char(char_after) or self._is_delimiter(char_after)):
            return True
            
        # 规则4: 对于2字中文名，如果前后都是中文，需要更严格的检查
        if len(search_term) == 2 and self._is_chinese_char(char_before) and self._is_chinese_char(char_after):
            return False
            
        # 默认情况下，如果没有明显的边界问题，认为是有效的
        return True

    def _is_english_word_boundary(self, char_before: str, char_after: str) -> bool:
        """检测英文词边界"""
        # 英文词边界：前后不能是字母或数字
        if char_before and char_before.isalnum():
            return False
        if char_after and char_after.isalnum():
            return False
        return True

    def _is_negative_context(self, text: str, start_pos: int, search_term: str) -> bool:
        """检测否定语境"""
        # 检查前面是否有否定词
        context_before = text[max(0, start_pos - 15):start_pos]
        context_after = text[start_pos + len(search_term):min(len(text), start_pos + len(search_term) + 10)]
        
        negative_patterns = ['不是', '没有', '不叫', '非', '并非', '绝非', '不认识', '不知道', '不在']
        
        # 检查前面的否定词
        for pattern in negative_patterns:
            if pattern in context_before:
                return True
                
        # 检查特殊的否定句式，如"但没有张三"
        full_context = context_before + search_term + context_after
        if '但没有' + search_term in full_context or '但不是' + search_term in full_context:
            return True
            
        return False

    def _is_part_of_compound_word(self, text: str, start_pos: int, end_pos: int, search_term: str) -> bool:
        """检测是否为组合词的一部分"""
        # 检查是否为三字人名的一部分
        if len(search_term) == 2:  # 对于2字名字，如"张三"
            # 检查是否为"张三丰"、"张三疯"等3字名的一部分
            if end_pos < len(text) and self._is_chinese_char(text[end_pos]):
                next_char = text[end_pos]
                # 只对明确的三字名后缀才判断为组合词
                if self._is_common_three_char_name_suffix(next_char):
                    return True
                    
        # 检查是否为地名组合词的一部分，如"天山雪莲"中的"天山"
        if end_pos < len(text):
            next_char = text[end_pos]
            # 如果后面紧跟着中文字符，检查是否为明确的组合词
            if self._is_chinese_char(next_char):
                # 只对明确的组合词后缀才判断
                common_compound_suffixes = ['雪', '派', '门', '宗', '教', '帮', '会', '堂', '阁', '楼', '院', '宫', '莲', '花', '草', '树']
                if next_char in common_compound_suffixes:
                    return True
                    
                # 检查是否为明确的三字或四字组合词
                if end_pos + 1 < len(text) and self._is_chinese_char(text[end_pos + 1]):
                    # 获取后续2个字符
                    next_two_chars = text[end_pos:end_pos + 2]
                    # 如果形成了明显的组合词，如"雪莲"、"大侠"等
                    known_compound_endings = ['雪莲', '大侠', '公子', '先生', '夫人', '大人', '将军', '长老']
                    if next_two_chars in known_compound_endings:
                        return True
                    
        return False

    def _is_common_three_char_name_suffix(self, char: str) -> bool:
        """检测是否为常见的三字名后缀"""
        common_suffixes = ['丰', '疯', '君', '公', '生', '老', '师', '哥', '姐', '妹', '弟']
        return char in common_suffixes

    def _is_chinese_char(self, char: str) -> bool:
        """判断是否为中文字符"""
        if not char:
            return False
        return '\u4e00' <= char <= '\u9fff'

    def _is_delimiter(self, char: str) -> bool:
        """判断是否为分隔符"""
        delimiters = '，。！？；：、""''（）【】《》〈〉「」『』 \t\n\r.!?;:,-()[]<>{}"\'`~'
        return char in delimiters

    def _calculate_confidence(self, text: str, search_term: str, start_pos: int, end_pos: int, entry: CodexEntry) -> float:
        """
        计算匹配的置信度
        
        Args:
            text: 原文本
            search_term: 搜索词
            start_pos: 匹配开始位置 
            end_pos: 匹配结束位置
            entry: Codex条目
            
        Returns:
            float: 置信度 (0.0-1.0)
        """
        confidence = 1.0
        
        # 获取前后字符
        char_before = text[start_pos - 1] if start_pos > 0 else ""
        char_after = text[end_pos] if end_pos < len(text) else ""
        
        # 基于边界质量调整置信度
        if self._is_delimiter(char_before) or not char_before:
            confidence += 0.1
        if self._is_delimiter(char_after) or not char_after:
            confidence += 0.1
            
        # 如果是精确的标题匹配，提高置信度
        if search_term == entry.title:
            confidence += 0.2
            
        # 基于词长调整置信度（更长的词通常更准确）
        if len(search_term) >= 3:
            confidence += 0.1
        elif len(search_term) == 2:
            confidence -= 0.1
            
        # 如果周围有否定语境，大幅降低置信度
        if self._is_negative_context(text, start_pos, search_term):
            confidence -= 0.5
            
        # 如果可能是组合词的一部分，降低置信度
        if self._is_part_of_compound_word(text, start_pos, end_pos, search_term):
            confidence -= 0.4
            
        return max(0.0, min(1.0, confidence))

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
                    confidence = self._calculate_fuzzy_confidence(matched_text, entry_type, base_confidence)
                    
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

    def _calculate_fuzzy_confidence(self, text: str, entry_type: CodexEntryType, base_confidence: float) -> float:
        """计算模糊匹配的置信度"""
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