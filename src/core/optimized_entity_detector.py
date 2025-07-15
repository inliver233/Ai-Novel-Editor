"""
优化的实体检测器
修复时间表达式误识别问题，改进中文实体识别准确性
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .reference_detector import ReferenceDetector, DetectedReference
from .codex_manager import CodexManager, CodexEntry, CodexEntryType
from .chinese_segmentation import get_segmenter, SegmentedWord, WordType

logger = logging.getLogger(__name__)


class EntityConfidence(Enum):
    """实体置信度等级"""
    HIGH = "high"      # 高置信度 (0.8-1.0)
    MEDIUM = "medium"  # 中等置信度 (0.6-0.8)
    LOW = "low"        # 低置信度 (0.4-0.6)
    VERY_LOW = "very_low"  # 极低置信度 (0.0-0.4)


@dataclass
class OptimizedDetectedReference(DetectedReference):
    """优化的检测引用，包含置信度等级和过滤原因"""
    confidence_level: EntityConfidence = EntityConfidence.MEDIUM
    filter_reasons: List[str] = None
    context_keywords: List[str] = None
    
    def __post_init__(self):
        if self.filter_reasons is None:
            self.filter_reasons = []
        if self.context_keywords is None:
            self.context_keywords = []


class OptimizedEntityDetector(ReferenceDetector):
    """优化的实体检测器"""
    
    def __init__(self, codex_manager: CodexManager):
        super().__init__(codex_manager)
        
        # 时间表达式过滤模式
        self.time_expression_patterns = [
            r'第[一二三四五六七八九十\d]+次',  # 第X次
            r'[一二三四五六七八九十\d]+次了?',  # X次、X次了
            r'再[一二三四五六七八九十\d]*次',  # 再X次
            r'又[一二三四五六七八九十\d]*次',  # 又X次
            r'[上下]次',  # 上次、下次
            r'这次|那次|每次|有时|偶尔',  # 时间副词
            r'[昨今明]天|[昨今明]日',  # 时间词
            r'[早中晚]上|[上下]午',  # 时段词
            r'刚才|现在|马上|立刻|随即',  # 时间副词
            r'[前后]天|[前后]日',  # 相对时间
            r'这个月',  # 月份表达
            r'这个月.*次',  # "这个月第X次"模式
            r'本月',  # 月份表达
            r'上个?月',  # 上月
            r'下个?月',  # 下月
            r'[一二三四五六七八九十\d]+个?月',  # X月
        ]
        
        # 数量表达式过滤模式
        self.quantity_patterns = [
            r'[一二三四五六七八九十百千万\d]+[个只条件张片块]',  # 数量词
            r'[几多少]个?',  # 疑问数量词
            r'[一二三四五六七八九十\d]+[人名个]',  # 人数表达
        ]
        
        # 否定语境模式
        self.negative_context_patterns = [
            r'不是.{0,5}',  # 不是X
            r'没有.{0,5}',  # 没有X
            r'不叫.{0,5}',  # 不叫X
            r'非.{0,3}',    # 非X
            r'并非.{0,5}',  # 并非X
            r'不认识.{0,5}',  # 不认识X
            r'不知道.{0,5}',  # 不知道X
        ]
        
        # 常见误识别词汇
        self.common_false_positives = {
            '第三次', '第二次', '第一次', '这次', '那次', '上次', '下次',
            '几次', '多次', '有时', '偶尔', '刚才', '现在', '马上',
            '昨天', '今天', '明天', '早上', '中午', '晚上', '下午',
            '一个', '两个', '三个', '几个', '多个', '少个',
            '这个月第三次了', '这个月第二次了', '这个月第一次了',
            '一人', '两人', '三人', '几人', '多人',
        }
        
        # 置信度阈值配置
        self.confidence_thresholds = {
            EntityConfidence.HIGH: 0.8,
            EntityConfidence.MEDIUM: 0.6,
            EntityConfidence.LOW: 0.4,
            EntityConfidence.VERY_LOW: 0.0
        }
        
        # 最低接受置信度
        self.min_confidence_threshold = 0.6
        
        logger.info("OptimizedEntityDetector initialized with enhanced filtering")
    
    def detect_references(self, text: str, document_id: str = None) -> List[DetectedReference]:
        """
        优化的引用检测，包含时间表达式过滤和置信度评估
        
        Args:
            text: 待检测的文本
            document_id: 文档ID（可选）
            
        Returns:
            检测到的引用列表（已过滤低置信度结果）
        """
        if not text.strip():
            return []
        
        # 1. 基础检测
        raw_references = self._detect_raw_references(text)
        
        # 2. 应用过滤器
        filtered_references = []
        for ref in raw_references:
            optimized_ref = self._apply_filters_and_scoring(ref, text)
            if optimized_ref and optimized_ref.confidence >= self.min_confidence_threshold:
                filtered_references.append(optimized_ref)
        
        # 3. 去重和排序
        filtered_references = self._deduplicate_references(filtered_references)
        filtered_references.sort(key=lambda x: x.start_position)
        
        # 4. 添加上下文信息
        for ref in filtered_references:
            ref.context_before, ref.context_after = self._extract_context(
                text, ref.start_position, ref.end_position
            )
            # 提取上下文关键词
            ref.context_keywords = self._extract_context_keywords(
                text, ref.start_position, ref.end_position
            )
        
        logger.debug(f"Optimized detection: {len(raw_references)} raw -> {len(filtered_references)} filtered")
        return filtered_references
    
    def _detect_raw_references(self, text: str) -> List[DetectedReference]:
        """执行基础的引用检测"""
        references = []
        
        # 直接实现简单的文本匹配
        for entry in self.codex_manager.get_all_entries():
            if not entry.track_references:
                continue
            
            # 检测标题匹配
            title_matches = self._simple_text_match(text, entry.title, entry)
            references.extend(title_matches)
            
            # 检测别名匹配
            for alias in entry.aliases:
                if alias.strip():
                    alias_matches = self._simple_text_match(text, alias.strip(), entry)
                    references.extend(alias_matches)
        
        return references
    
    def _simple_text_match(self, text: str, search_term: str, entry: CodexEntry) -> List[DetectedReference]:
        """简单的文本匹配实现"""
        if len(search_term) < 2:
            return []
        
        references = []
        import re
        
        # 使用简单的正则匹配
        pattern = re.escape(search_term)
        
        try:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                reference = DetectedReference(
                    entry_id=entry.id,
                    entry_title=entry.title,
                    entry_type=entry.entry_type,
                    matched_text=match.group(),
                    start_position=match.start(),
                    end_position=match.end(),
                    confidence=1.0  # 基础置信度
                )
                references.append(reference)
        except re.error as e:
            logger.warning(f"Regex error for term '{search_term}': {e}")
        
        return references
    
    def _apply_filters_and_scoring(self, ref: DetectedReference, full_text: str) -> Optional[OptimizedDetectedReference]:
        """
        应用过滤器和置信度评分
        
        Args:
            ref: 原始检测引用
            full_text: 完整文本
            
        Returns:
            优化后的引用或None（如果被过滤）
        """
        matched_text = ref.matched_text
        filter_reasons = []
        
        # 过滤器1: 时间表达式过滤
        if self._is_time_expression(matched_text):
            filter_reasons.append("时间表达式")
            logger.debug(f"Filtered time expression: {matched_text}")
            return None
        
        # 过滤器2: 数量表达式过滤
        if self._is_quantity_expression(matched_text):
            filter_reasons.append("数量表达式")
            logger.debug(f"Filtered quantity expression: {matched_text}")
            return None
        
        # 过滤器3: 常见误识别词汇过滤
        if matched_text in self.common_false_positives:
            filter_reasons.append("常见误识别词汇")
            logger.debug(f"Filtered common false positive: {matched_text}")
            return None
        
        # 过滤器4: 否定语境过滤
        if self._is_in_negative_context(full_text, ref.start_position, matched_text):
            filter_reasons.append("否定语境")
            logger.debug(f"Filtered negative context: {matched_text}")
            return None
        
        # 计算置信度
        confidence = self._calculate_optimized_confidence(ref, full_text)
        confidence_level = self._get_confidence_level(confidence)
        
        # 创建优化的引用对象
        optimized_ref = OptimizedDetectedReference(
            entry_id=ref.entry_id,
            entry_title=ref.entry_title,
            entry_type=ref.entry_type,
            matched_text=ref.matched_text,
            start_position=ref.start_position,
            end_position=ref.end_position,
            confidence=confidence,
            confidence_level=confidence_level,
            filter_reasons=filter_reasons
        )
        
        return optimized_ref
    
    def _is_time_expression(self, text: str) -> bool:
        """检测是否为时间表达式"""
        for pattern in self.time_expression_patterns:
            if re.fullmatch(pattern, text):
                return True
        return False
    
    def _is_quantity_expression(self, text: str) -> bool:
        """检测是否为数量表达式"""
        for pattern in self.quantity_patterns:
            if re.fullmatch(pattern, text):
                return True
        return False
    
    def _is_in_negative_context(self, text: str, start_pos: int, matched_text: str) -> bool:
        """检测是否在否定语境中"""
        # 检查前面20个字符的上下文
        context_start = max(0, start_pos - 20)
        context_before = text[context_start:start_pos]
        
        # 检查后面10个字符的上下文，用于识别转折
        context_end = min(len(text), start_pos + len(matched_text) + 10)
        context_after = text[start_pos + len(matched_text):context_end]
        
        # 检查是否有转折词，如"而是"、"但是"等
        transition_words = ['而是', '但是', '不过', '然而', '可是']
        has_transition_before = any(word in context_before for word in transition_words)
        
        # 如果前面有转折词，说明这是肯定语境
        if has_transition_before:
            return False
        
        # 检查直接的否定模式
        for pattern in self.negative_context_patterns:
            # 构建完整的否定模式
            full_pattern = pattern + re.escape(matched_text)
            if re.search(full_pattern, context_before + matched_text):
                # 进一步检查是否有转折，如"不是张三，而是李四"
                full_context = context_before + matched_text + context_after
                if any(word in full_context for word in transition_words):
                    # 如果转折词在匹配文本之后，说明这个实体是被否定的
                    transition_after_match = any(word in context_after for word in transition_words)
                    if transition_after_match:
                        return True
                    else:
                        return False
                else:
                    return True
        
        return False
    
    def _calculate_optimized_confidence(self, ref: DetectedReference, full_text: str) -> float:
        """
        计算优化的置信度分数
        
        Args:
            ref: 检测到的引用
            full_text: 完整文本
            
        Returns:
            float: 置信度分数 (0.0-1.0)
        """
        base_confidence = 0.7  # 基础置信度
        factors = {}
        
        # 因子1: 匹配长度加权
        text_length = len(ref.matched_text)
        if text_length >= 3:
            factors['length_bonus'] = 0.2
        elif text_length == 2:
            factors['length_bonus'] = 0.0
        else:
            factors['length_penalty'] = -0.3
        
        # 因子2: 边界质量
        char_before = full_text[ref.start_position - 1] if ref.start_position > 0 else ""
        char_after = full_text[ref.end_position] if ref.end_position < len(full_text) else ""
        
        boundary_score = 0.0
        if self._is_delimiter(char_before) or not char_before:
            boundary_score += 0.1
        if self._is_delimiter(char_after) or not char_after:
            boundary_score += 0.1
        
        factors['boundary_quality'] = boundary_score
        
        # 因子3: 上下文相关性
        context_score = self._calculate_context_relevance(ref, full_text)
        factors['context_relevance'] = context_score * 0.15
        
        # 因子4: 实体类型匹配度
        type_score = self._calculate_entity_type_match(ref, full_text)
        factors['entity_type_match'] = type_score * 0.1
        
        # 因子5: 全局条目加权
        entry = self.codex_manager.get_entry(ref.entry_id)
        if entry and entry.is_global:
            factors['global_entry_bonus'] = 0.1
        
        # 计算最终置信度
        final_confidence = base_confidence + sum(factors.values())
        
        # 限制在合理范围内
        return max(0.0, min(1.0, final_confidence))
    
    def _calculate_context_relevance(self, ref: DetectedReference, full_text: str) -> float:
        """计算上下文相关性分数"""
        try:
            # 获取更大的上下文窗口
            context_size = 100
            start_pos = max(0, ref.start_position - context_size)
            end_pos = min(len(full_text), ref.end_position + context_size)
            context = full_text[start_pos:end_pos]
            
            score = 0.0
            
            # 根据实体类型检查相关关键词
            if ref.entry_type == CodexEntryType.CHARACTER:
                character_keywords = ['说', '道', '想', '看', '听', '走', '来', '去', '笑', '哭', '怒', '喜']
                for keyword in character_keywords:
                    if keyword in context:
                        score += 0.1
                        if score >= 1.0:
                            break
            
            elif ref.entry_type == CodexEntryType.LOCATION:
                location_keywords = ['在', '到', '去', '来', '从', '向', '朝', '往', '处', '地方']
                for keyword in location_keywords:
                    if keyword in context:
                        score += 0.1
                        if score >= 1.0:
                            break
            
            elif ref.entry_type == CodexEntryType.OBJECT:
                object_keywords = ['拿', '用', '持', '握', '放', '取', '给', '递', '扔', '丢']
                for keyword in object_keywords:
                    if keyword in context:
                        score += 0.1
                        if score >= 1.0:
                            break
            
            return min(score, 1.0)
        
        except Exception as e:
            logger.warning(f"Error calculating context relevance: {e}")
            return 0.0
    
    def _calculate_entity_type_match(self, ref: DetectedReference, full_text: str) -> float:
        """计算实体类型匹配度"""
        matched_text = ref.matched_text
        
        # 基于文本特征判断实体类型匹配度
        if ref.entry_type == CodexEntryType.CHARACTER:
            # 角色名通常是2-4个中文字符
            if 2 <= len(matched_text) <= 4 and all('\u4e00' <= c <= '\u9fff' for c in matched_text):
                return 1.0
            return 0.5
        
        elif ref.entry_type == CodexEntryType.LOCATION:
            # 地点名可能包含特定后缀
            location_suffixes = ['城', '镇', '村', '国', '省', '市', '区', '县', '山', '河', '湖', '海']
            if any(matched_text.endswith(suffix) for suffix in location_suffixes):
                return 1.0
            return 0.7
        
        elif ref.entry_type == CodexEntryType.OBJECT:
            # 物品名可能包含特定后缀
            object_suffixes = ['剑', '刀', '枪', '书', '珠', '石', '丹', '药', '符', '印']
            if any(matched_text.endswith(suffix) for suffix in object_suffixes):
                return 1.0
            return 0.6
        
        return 0.5
    
    def _get_confidence_level(self, confidence: float) -> EntityConfidence:
        """根据置信度分数获取置信度等级"""
        if confidence >= self.confidence_thresholds[EntityConfidence.HIGH]:
            return EntityConfidence.HIGH
        elif confidence >= self.confidence_thresholds[EntityConfidence.MEDIUM]:
            return EntityConfidence.MEDIUM
        elif confidence >= self.confidence_thresholds[EntityConfidence.LOW]:
            return EntityConfidence.LOW
        else:
            return EntityConfidence.VERY_LOW
    
    def _extract_context_keywords(self, text: str, start_pos: int, end_pos: int) -> List[str]:
        """提取上下文关键词用于RAG检索"""
        # 扩大上下文窗口以获取更多相关信息
        context_size = 200  # 增加上下文窗口大小
        context_start = max(0, start_pos - context_size)
        context_end = min(len(text), end_pos + context_size)
        
        # 获取触发位置之前的内容作为主要上下文
        before_context = text[context_start:start_pos]
        after_context = text[end_pos:context_end]
        
        # 重点关注触发位置之前的内容
        primary_context = before_context
        secondary_context = after_context
        
        keywords = []
        
        try:
            # 使用简单的中文分词提取关键词
            # 提取名词、动词、形容词等
            import jieba
            import jieba.posseg as pseg
            logger.critical("🎯[JIEBA_DEBUG] optimized_entity_detector中jieba导入成功，准备提取上下文关键词")
            
            # 分析主要上下文（触发位置之前）
            primary_words = pseg.cut(primary_context)
            for word, flag in primary_words:
                # 扩展词性标记，包含更多有意义的词汇
                if len(word) >= 2 and flag in ['n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'a', 'ad', 'an', 't', 'i', 'l']:
                    keywords.append(word)
            
            # 分析次要上下文（触发位置之后）
            secondary_words = pseg.cut(secondary_context)
            for word, flag in secondary_words:
                # 扩展词性标记，包含更多有意义的词汇
                if len(word) >= 2 and flag in ['n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'a', 'ad', 'an', 't', 'i', 'l']:
                    keywords.append(word)
            
            # 去重并保持顺序
            seen = set()
            unique_keywords = []
            for keyword in keywords:
                if keyword not in seen:
                    seen.add(keyword)
                    unique_keywords.append(keyword)
            
            # 限制关键词数量，优先保留前面的（更接近触发位置）
            return unique_keywords[:10]
        
        except ImportError as e:
            logger.critical("❌[JIEBA_DEBUG] optimized_entity_detector中jieba导入失败: %s", e)
            logger.warning("jieba not available, using simple keyword extraction")
            # 简单的关键词提取作为后备方案
            return self._simple_keyword_extraction(primary_context + secondary_context)
        except Exception as e:
            logger.warning(f"Error extracting context keywords: {e}")
            return []
    
    def _simple_keyword_extraction(self, context: str) -> List[str]:
        """简单的关键词提取（不依赖jieba）"""
        # 使用正则表达式提取可能的关键词
        keywords = []
        
        # 提取2-4个中文字符的词汇
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', context)
        
        # 过滤掉常见的停用词
        stop_words = {'这个', '那个', '一个', '什么', '怎么', '为什么', '因为', '所以', '但是', '然后', '现在', '时候'}
        
        for word in chinese_words:
            if word not in stop_words and len(word) >= 2:
                keywords.append(word)
        
        # 去重并限制数量
        return list(dict.fromkeys(keywords))[:8]
    
    def get_detection_statistics(self) -> Dict[str, any]:
        """获取优化检测器的统计信息"""
        base_stats = super().get_detection_statistics()
        
        # 添加优化相关的统计
        base_stats.update({
            'optimization_config': {
                'min_confidence_threshold': self.min_confidence_threshold,
                'time_expression_patterns': len(self.time_expression_patterns),
                'quantity_patterns': len(self.quantity_patterns),
                'negative_context_patterns': len(self.negative_context_patterns),
                'common_false_positives': len(self.common_false_positives)
            },
            'confidence_thresholds': {
                level.value: threshold 
                for level, threshold in self.confidence_thresholds.items()
            }
        })
        
        return base_stats
    
    def update_confidence_threshold(self, new_threshold: float):
        """更新最低置信度阈值"""
        if 0.0 <= new_threshold <= 1.0:
            self.min_confidence_threshold = new_threshold
            logger.info(f"Updated minimum confidence threshold to {new_threshold}")
        else:
            logger.warning(f"Invalid confidence threshold: {new_threshold}")
    
    def add_false_positive_filter(self, word: str):
        """添加误识别词汇到过滤列表"""
        if word and word not in self.common_false_positives:
            self.common_false_positives.add(word)
            logger.info(f"Added false positive filter: {word}")
    
    def remove_false_positive_filter(self, word: str):
        """从过滤列表中移除词汇"""
        if word in self.common_false_positives:
            self.common_false_positives.remove(word)
            logger.info(f"Removed false positive filter: {word}")