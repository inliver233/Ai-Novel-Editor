"""
改进的上下文提取器
专门处理AI补全触发位置的上下文分析和关键词提取
解决RAG检索上下文不准确的问题
"""

import re
import time
import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ContextType(Enum):
    """上下文类型"""
    NARRATIVE = "narrative"      # 叙述性上下文
    DIALOGUE = "dialogue"        # 对话上下文
    DESCRIPTION = "description"  # 描述性上下文
    ACTION = "action"           # 动作上下文


@dataclass
class ContextSegment:
    """上下文片段"""
    text: str
    start_position: int
    end_position: int
    context_type: ContextType
    importance_score: float
    keywords: List[str]


@dataclass
class ExtractedContext:
    """提取的上下文信息"""
    trigger_position: int
    before_context: str
    after_context: str
    segments: List[ContextSegment]
    primary_keywords: List[str]
    secondary_keywords: List[str]
    context_summary: str
    relevance_score: float


class ImprovedContextExtractor:
    """改进的上下文提取器"""
    
    def __init__(self):
        # 上下文窗口配置
        self.primary_window_size = 300    # 主要上下文窗口（触发位置前）
        self.secondary_window_size = 100  # 次要上下文窗口（触发位置后）
        self.max_keywords = 15           # 最大关键词数量
        
        # 中文停用词
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '那', '里', '就是', '还是', '为了', '又', '如果', '已经', '因为',
            '只是', '当然', '比如', '或者', '虽然', '但是', '然后', '所以', '而且', '不过',
            '什么', '怎么', '为什么', '哪里', '时候', '现在', '这样', '那样', '这里', '那里'
        }
        
        # 重要词汇模式
        self.important_patterns = [
            r'[\u4e00-\u9fff]{2,4}(?:说|道|想|看|听|走|来|去)',  # 动作词
            r'[\u4e00-\u9fff]{2,4}(?:城|镇|村|国|省|市|山|河|湖)',  # 地点词
            r'[\u4e00-\u9fff]{2,4}(?:剑|刀|枪|书|珠|石|丹|药)',  # 物品词
            r'[\u4e00-\u9fff]{2,4}(?:门|派|宗|教|帮|会)',  # 组织词
        ]
        
        # 对话标识符
        self.dialogue_markers = ['"', '"', '"', '「', '」', '『', '』', '：', ':']
        
        logger.info("ImprovedContextExtractor initialized")
    
    def extract_context_for_completion(self, text: str, cursor_position: int) -> ExtractedContext:
        """
        为AI补全提取优化的上下文信息
        
        Args:
            text: 完整文本
            cursor_position: 光标位置（触发补全的位置）
            
        Returns:
            ExtractedContext: 提取的上下文信息
        """
        if not text or cursor_position < 0:
            return self._create_empty_context(cursor_position)
        
        # 调整光标位置，确保不超出文本范围
        cursor_position = min(cursor_position, len(text))
        
        # 1. 确定上下文边界
        before_start, before_end = self._calculate_before_context_bounds(text, cursor_position)
        after_start, after_end = self._calculate_after_context_bounds(text, cursor_position)
        
        # 2. 提取上下文文本
        before_context = text[before_start:before_end]
        after_context = text[after_start:after_end]
        
        # 3. 分析上下文结构
        segments = self._analyze_context_structure(
            before_context, after_context, before_start, cursor_position
        )
        
        # 4. 提取关键词
        primary_keywords = self._extract_primary_keywords(before_context)
        secondary_keywords = self._extract_secondary_keywords(after_context)
        
        # 5. 生成上下文摘要
        context_summary = self._generate_context_summary(segments, primary_keywords)
        
        # 6. 计算相关性分数
        relevance_score = self._calculate_relevance_score(segments, primary_keywords)
        
        return ExtractedContext(
            trigger_position=cursor_position,
            before_context=before_context,
            after_context=after_context,
            segments=segments,
            primary_keywords=primary_keywords,
            secondary_keywords=secondary_keywords,
            context_summary=context_summary,
            relevance_score=relevance_score
        )
    
    def _calculate_before_context_bounds(self, text: str, cursor_position: int) -> Tuple[int, int]:
        """计算触发位置之前的上下文边界"""
        # 基础窗口
        start_pos = max(0, cursor_position - self.primary_window_size)
        
        # 修复：对于较短的文本，直接使用完整上下文，避免过度截断
        if cursor_position <= self.primary_window_size:
            best_boundary = 0  # 直接使用文本开头
        else:
            # 只有在文本很长时才考虑句子边界调整
            before_text = text[start_pos:cursor_position]
            
            # 寻找最近的句子边界
            sentence_boundaries = ['.', '。', '!', '！', '?', '？', '\n\n']
            best_boundary = start_pos
            
            # 提高最小字符要求，确保不会过度截断重要内容
            min_chars = max(100, cursor_position // 3)  # 更保守的最小字符数
            
            for i, char in enumerate(reversed(before_text)):
                if char in sentence_boundaries:
                    # 找到句子边界，但要确保不会截取太少内容
                    boundary_pos = cursor_position - i
                    if cursor_position - boundary_pos >= min_chars:
                        best_boundary = boundary_pos + 1
                        break
        
        
        return best_boundary, cursor_position
    
    def _calculate_after_context_bounds(self, text: str, cursor_position: int) -> Tuple[int, int]:
        """计算触发位置之后的上下文边界"""
        # 基础窗口
        end_pos = min(len(text), cursor_position + self.secondary_window_size)
        
        # 尝试在句子边界处截断
        after_text = text[cursor_position:end_pos]
        
        sentence_boundaries = ['.', '。', '!', '！', '?', '？', '\n\n']
        best_boundary = end_pos
        
        for i, char in enumerate(after_text):
            if char in sentence_boundaries:
                # 找到句子边界
                boundary_pos = cursor_position + i + 1
                if boundary_pos - cursor_position >= 20:  # 至少保留20个字符
                    best_boundary = boundary_pos
                    break
        
        return cursor_position, best_boundary
    
    def _analyze_context_structure(self, before_context: str, after_context: str, 
                                 before_start: int, cursor_position: int) -> List[ContextSegment]:
        """分析上下文结构，识别不同类型的文本段落"""
        segments = []
        
        # 分析前置上下文
        before_segments = self._segment_text(before_context, before_start, ContextType.NARRATIVE)
        segments.extend(before_segments)
        
        # 分析后置上下文（权重较低）
        after_segments = self._segment_text(after_context, cursor_position, ContextType.NARRATIVE)
        for segment in after_segments:
            segment.importance_score *= 0.3  # 降低后置上下文的重要性
        segments.extend(after_segments)
        
        return segments
    
    def _segment_text(self, text: str, start_offset: int, default_type: ContextType) -> List[ContextSegment]:
        """将文本分割成有意义的段落"""
        if not text.strip():
            return []
        
        segments = []
        
        # 简单的段落分割（基于换行和标点）
        paragraphs = re.split(r'\n\s*\n|\。\s*|\！\s*|\？\s*', text)
        current_pos = 0
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                current_pos += len(paragraph)
                continue
            
            # 确定段落类型
            context_type = self._determine_context_type(paragraph)
            
            # 计算重要性分数
            importance_score = self._calculate_segment_importance(paragraph, context_type)
            
            # 提取段落关键词
            keywords = self._extract_segment_keywords(paragraph)
            
            segment = ContextSegment(
                text=paragraph.strip(),
                start_position=start_offset + current_pos,
                end_position=start_offset + current_pos + len(paragraph),
                context_type=context_type,
                importance_score=importance_score,
                keywords=keywords
            )
            
            segments.append(segment)
            current_pos += len(paragraph)
        
        return segments
    
    def _determine_context_type(self, text: str) -> ContextType:
        """确定文本段落的类型"""
        # 检查是否包含对话标识符
        dialogue_count = sum(1 for marker in self.dialogue_markers if marker in text)
        if dialogue_count >= 2:
            return ContextType.DIALOGUE
        
        # 检查是否包含大量动作词
        action_words = ['走', '跑', '跳', '飞', '打', '击', '攻', '防', '躲', '闪']
        action_count = sum(1 for word in action_words if word in text)
        if action_count >= 2:
            return ContextType.ACTION
        
        # 检查是否包含大量描述性词汇
        description_words = ['美丽', '壮观', '巨大', '微小', '明亮', '黑暗', '温暖', '寒冷']
        description_count = sum(1 for word in description_words if word in text)
        if description_count >= 2:
            return ContextType.DESCRIPTION
        
        return ContextType.NARRATIVE
    
    def _calculate_segment_importance(self, text: str, context_type: ContextType) -> float:
        """计算文本段落的重要性分数"""
        base_score = 0.5
        
        # 根据类型调整基础分数
        type_weights = {
            ContextType.DIALOGUE: 0.8,
            ContextType.ACTION: 0.9,
            ContextType.DESCRIPTION: 0.6,
            ContextType.NARRATIVE: 0.7
        }
        base_score = type_weights.get(context_type, 0.5)
        
        # 根据长度调整
        length_factor = min(1.0, len(text) / 100)  # 100字符为满分
        
        # 根据关键词密度调整
        keyword_count = 0
        for pattern in self.important_patterns:
            keyword_count += len(re.findall(pattern, text))
        
        keyword_factor = min(1.0, keyword_count / 5)  # 5个关键词为满分
        
        final_score = base_score * (0.4 + 0.3 * length_factor + 0.3 * keyword_factor)
        return min(1.0, final_score)
    
    def _extract_primary_keywords(self, text: str) -> List[str]:
        """提取主要关键词（来自触发位置之前的上下文）"""
        if not text or len(text.strip()) < 2:
            logger.warning(f"[KEYWORD_EXTRACT] 输入文本为空或过短: '{text}'")
            return []
        
        logger.debug(f"[KEYWORD_EXTRACT] 开始提取关键词，输入长度: {len(text)}")
        start_time = time.time()
        keywords = []
        jieba_available = False
        
        try:
            # 尝试使用jieba进行分词
            import jieba
            import jieba.posseg as pseg
            jieba_available = True
            # 分词并提取名词、动词、形容词等更多词性
            words = pseg.cut(text)
            
            for word, flag in words:
                # 长度检查
                if len(word) < 2:
                    continue
                
                # 停用词检查
                if word in self.stop_words:
                    continue
                
                # 词性检查 - 修复：恢复完整的词性列表，适合文学文本
                allowed_pos = ['n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'vd', 'a', 'ad', 'an', 'i', 'j', 'l', 't', 'x', 'eng', 'f', 'b', 'c', 'd', 'e', 'g', 'h', 'k', 'm', 'o', 'p', 'q', 'r', 's', 'u', 'w', 'y', 'z']
                if flag not in allowed_pos:
                    continue
                
                # 无意义词检查
                if self._is_meaningless_word(word):
                    continue
                
                keywords.append(word)
                
                # 为重要词性（人名、地名、专有名词）增加权重，添加两次
                if flag in ['nr', 'ns', 'nt', 'nz']:
                    keywords.append(word)
        
        except ImportError:
            # 使用简单的正则表达式提取
            keywords = self._simple_keyword_extraction(text)
        
        # 使用重要模式提取特殊关键词
        pattern_keywords = []
        for pattern in self.important_patterns:
            matches = re.findall(pattern, text)
            pattern_keywords.extend(matches)
        
        # 重要模式匹配的关键词添加两次，增加权重
        keywords.extend(pattern_keywords)
        keywords.extend(pattern_keywords)  # 再添加一次增加权重
        
        # 去重并按重要性排序，优化停用词过滤条件
        unique_keywords = []
        seen = set()
        
        # 优先保留重要模式匹配的关键词
        for keyword in keywords:
            if keyword in seen:
                continue
            
            if len(keyword) < 2:
                continue
            
            if keyword in self.stop_words:
                continue
            
            if self._is_meaningless_word(keyword):
                continue
            
            seen.add(keyword)
            unique_keywords.append(keyword)
        
        # 增强宽松提取机制 - 如果关键词太少，使用多重降级策略
        if len(unique_keywords) < 2:  # 进一步降低阈值到2
            logger.warning(f"[KEYWORD_EXTRACT] 关键词数量不足({len(unique_keywords)})，启用降级策略")
            # 策略1: 直接提取中文词汇，大幅放宽条件
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
            for word in chinese_words:
                if word not in seen and len(word) >= 2 and not self._is_meaningless_word(word):
                    seen.add(word)
                    unique_keywords.append(word)
                    if len(unique_keywords) >= 10:  # 增加限制数量
                        break
            
            # 策略2: 如果仍然不足，提取单字符组合
            if len(unique_keywords) < 1:
                logger.warning(f"[KEYWORD_EXTRACT] 启用最后降级策略：单字符组合")
                chars = re.findall(r'[\u4e00-\u9fff]', text)
                for i in range(len(chars)-1):
                    word = chars[i] + chars[i+1]
                    if word not in seen and not self._is_meaningless_word(word):
                        seen.add(word)
                        unique_keywords.append(word)
                        if len(unique_keywords) >= 8:
                            break
        
        # 记录性能和结果
        elapsed = time.time() - start_time
        logger.debug(f"[KEYWORD_EXTRACT] 输入长度={len(text)}, jieba={jieba_available}, 结果数量={len(unique_keywords)}, 耗时={elapsed:.3f}s")
        
        # 如果关键词仍然为空，记录详细信息
        if not unique_keywords:
            logger.error(f"[KEYWORD_EXTRACT] 关键词提取失败！")
            logger.error(f"[KEYWORD_EXTRACT] 输入文本: '{text[:200]}...'")
            logger.error(f"[KEYWORD_EXTRACT] 文本长度: {len(text)}")
            logger.error(f"[KEYWORD_EXTRACT] jieba可用: {jieba_available}")
            chinese_pattern = r'[\u4e00-\u9fff]'
            logger.error(f"[KEYWORD_EXTRACT] 中文字符数: {len(re.findall(chinese_pattern, text))}")
            logger.error(f"[KEYWORD_EXTRACT] 停用词数量: {len(self.stop_words)}")
        else:
            logger.info(f"[KEYWORD_EXTRACT] 成功提取关键词: {unique_keywords}")
        
        # 限制数量
        return unique_keywords[:self.max_keywords]
    
    def _extract_secondary_keywords(self, text: str) -> List[str]:
        """提取次要关键词（来自触发位置之后的上下文）"""
        if not text:
            return []
        
        # 次要关键词的提取更加保守
        keywords = []
        
        try:
            import jieba.posseg as pseg
            words = pseg.cut(text)
            for word, flag in words:
                if (len(word) >= 2 and 
                    word not in self.stop_words and
                    flag in ['n', 'nr', 'ns', 'nt', 'nz']):  # 只提取名词
                    keywords.append(word)
        
        except ImportError:
            keywords = self._simple_keyword_extraction(text)
        
        # 去重并限制数量
        unique_keywords = list(dict.fromkeys(keywords))
        return unique_keywords[:5]  # 次要关键词数量更少
    
    def _extract_segment_keywords(self, text: str) -> List[str]:
        """提取文本段落的关键词"""
        keywords = []
        
        # 提取2-4个中文字符的词汇
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        
        for word in chinese_words:
            if word not in self.stop_words and len(word) >= 2:
                keywords.append(word)
        
        # 去重并限制数量
        return list(dict.fromkeys(keywords))[:8]
    
    def _simple_keyword_extraction(self, text: str) -> List[str]:
        """简单的关键词提取（不依赖jieba）"""
        keywords = []
        
        # 提取中文词汇，使用更保守的方法
        # 先按标点符号分割，然后提取较短的词汇
        sentences = re.split(r'[，。！？；：、\s]+', text)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            # 提取2-4个字符的中文词汇（避免过长的词组）
            words = re.findall(r'[\u4e00-\u9fff]{2,4}', sentence)
            
            for word in words:
                # 严格过滤停用词
                if (word not in self.stop_words and 
                    len(word) >= 2 and 
                    not any(stop_word in word for stop_word in self.stop_words)):
                    keywords.append(word)
        
        # 去重
        unique_keywords = list(dict.fromkeys(keywords))
        
        return unique_keywords
    
    def _is_meaningless_word(self, word: str) -> bool:
        """判断是否为无意义词汇"""
        # 检查是否为纯数字或纯标点符号（不包括中文字符）
        if re.match(r'^[\d\s\u0000-\u007F\u2000-\u206F\u3000-\u303F\uFF00-\uFFEF]+$', word):
            return True
        
        # 检查是否为重复字符
        if len(set(word)) == 1:
            return True
        
        # 检查是否为常见的无意义词
        meaningless_words = {'这样', '那样', '这么', '那么', '如此', '怎样', '什么', '哪里', '为什么', '怎么'}
        if word in meaningless_words:
            return True
        
        return False
    
    def _generate_context_summary(self, segments: List[ContextSegment], 
                                keywords: List[str]) -> str:
        """生成上下文摘要"""
        if not segments:
            return ""
        
        # 选择最重要的段落
        important_segments = sorted(segments, key=lambda x: x.importance_score, reverse=True)[:3]
        
        # 构建摘要
        summary_parts = []
        
        # 添加主要关键词
        if keywords:
            summary_parts.append(f"关键词: {', '.join(keywords[:5])}")
        
        # 添加重要段落的简要描述
        for segment in important_segments:
            if len(segment.text) > 50:
                summary_parts.append(segment.text[:50] + "...")
            else:
                summary_parts.append(segment.text)
        
        return " | ".join(summary_parts)
    
    def _calculate_relevance_score(self, segments: List[ContextSegment], 
                                 keywords: List[str]) -> float:
        """计算上下文的相关性分数"""
        if not segments:
            return 0.0
        
        # 基于段落重要性计算
        avg_importance = sum(seg.importance_score for seg in segments) / len(segments)
        
        # 基于关键词数量计算
        keyword_score = min(1.0, len(keywords) / 10)
        
        # 综合计算
        relevance_score = 0.6 * avg_importance + 0.4 * keyword_score
        
        return min(1.0, relevance_score)
    
    def _create_empty_context(self, cursor_position: int) -> ExtractedContext:
        """创建空的上下文对象"""
        return ExtractedContext(
            trigger_position=cursor_position,
            before_context="",
            after_context="",
            segments=[],
            primary_keywords=[],
            secondary_keywords=[],
            context_summary="",
            relevance_score=0.0
        )
    
    def get_rag_query_context(self, extracted_context: ExtractedContext) -> Dict[str, any]:
        """
        为RAG检索生成优化的查询上下文
        
        Args:
            extracted_context: 提取的上下文信息
            
        Returns:
            Dict: RAG查询上下文
        """
        # 构建查询字符串，重点关注主要关键词
        query_parts = []
        
        # 添加主要关键词（权重最高）
        if extracted_context.primary_keywords:
            query_parts.extend(extracted_context.primary_keywords[:8])
        
        # 添加次要关键词（权重较低）
        if extracted_context.secondary_keywords:
            query_parts.extend(extracted_context.secondary_keywords[:3])
        
        # 构建查询字符串
        query_text = " ".join(query_parts)
        
        return {
            'query': query_text,
            'context_summary': extracted_context.context_summary,
            'relevance_score': extracted_context.relevance_score,
            'primary_keywords': extracted_context.primary_keywords,
            'secondary_keywords': extracted_context.secondary_keywords,
            'context_length': len(extracted_context.before_context),
            'segment_count': len(extracted_context.segments)
        }