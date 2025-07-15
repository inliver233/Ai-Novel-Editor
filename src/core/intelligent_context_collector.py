"""
智能上下文收集器
专门为AI补全收集和处理上下文信息，解决RAG检索上下文不准确的问题
"""

import re
import time
import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

from .improved_context_extractor import ImprovedContextExtractor, ExtractedContext
from .optimized_entity_detector import OptimizedEntityDetector

logger = logging.getLogger(__name__)


@dataclass
class ContextCollectionResult:
    """上下文收集结果"""
    trigger_position: int
    full_context: str
    primary_keywords: List[str]
    secondary_keywords: List[str]
    detected_entities: List[str]
    rag_query: str
    context_summary: str
    relevance_score: float
    collection_method: str


class IntelligentContextCollector:
    """智能上下文收集器"""
    
    def __init__(self, codex_manager=None):
        self.context_extractor = ImprovedContextExtractor()
        self.entity_detector = OptimizedEntityDetector(codex_manager) if codex_manager else None
        
        # 上下文收集配置
        self.max_context_length = 800  # 最大上下文长度
        self.min_context_length = 100  # 最小上下文长度
        self.keyword_weight_primary = 0.7  # 主要关键词权重
        self.keyword_weight_secondary = 0.3  # 次要关键词权重
        
        logger.info("IntelligentContextCollector initialized")
    
    def collect_context_for_completion(self, text: str, cursor_position: int,
                                     document_id: str = None) -> ContextCollectionResult:
        """
        为AI补全收集智能上下文

        Args:
            text: 完整文本
            cursor_position: 光标位置
            document_id: 文档ID

        Returns:
            ContextCollectionResult: 收集的上下文结果
        """
        if not text:
            return self._create_empty_result(cursor_position)
        
        # 修复光标位置：如果是-1或无效值，使用文本末尾
        if cursor_position < 0:
            cursor_position = len(text)
        elif cursor_position > len(text):
            cursor_position = len(text)

        # 1. 使用改进的上下文提取器获取基础上下文
        extracted_context = self.context_extractor.extract_context_for_completion(
            text, cursor_position
        )
        
        # 2. 检测实体（如果有codex_manager）
        detected_entities = []
        if self.entity_detector:
            entity_refs = self.entity_detector.detect_references(extracted_context.before_context)
            detected_entities = [ref.matched_text for ref in entity_refs]
        
        # 3. 构建智能RAG查询
        rag_query = self._build_intelligent_rag_query(
            extracted_context, detected_entities
        )
        
        # 紧急修复：如果智能RAG查询为空，使用降级策略确保返回有效查询
        if not rag_query or len(rag_query.strip()) < 5:
            logger.warning(f"[EMERGENCY_FIX] 智能RAG查询构建失败，启用紧急降级策略")
            
            # 降级策略1: 直接使用before_context的最后部分
            if extracted_context.before_context and len(extracted_context.before_context) > 20:
                # 取最后150个字符作为查询
                fallback_text = extracted_context.before_context[-150:].strip()
                # 使用简单的中文词汇提取
                import re
                chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', fallback_text)
                if chinese_words:
                    rag_query = " ".join(chinese_words[:10])  # 最多取10个词
                    logger.warning(f"[EMERGENCY_FIX] 降级策略1成功，查询长度: {len(rag_query)}")
            
            # 降级策略2: 如果仍然为空，使用整个before_context
            if not rag_query or len(rag_query.strip()) < 5:
                if extracted_context.before_context:
                    # 直接使用前100个字符
                    rag_query = extracted_context.before_context[:100].strip()
                    logger.warning(f"[EMERGENCY_FIX] 降级策略2，直接使用前100字符")
            
            # 降级策略3: 最后的保险措施
            if not rag_query or len(rag_query.strip()) < 5:
                rag_query = "默认查询内容"
                logger.error(f"[EMERGENCY_FIX] 所有策略失败，使用默认查询")
        
        # 4. 生成上下文摘要
        context_summary = self._generate_intelligent_summary(
            extracted_context, detected_entities
        )
        
        # 5. 计算相关性分数
        relevance_score = self._calculate_enhanced_relevance(
            extracted_context, detected_entities
        )
        
        # 最终强制检查：绝对不允许返回空查询
        if not rag_query or len(rag_query.strip()) < 5:
            if extracted_context.before_context:
                # 直接使用部分原文作为查询
                fallback_query = extracted_context.before_context[:50].strip()
                if fallback_query:
                    rag_query = fallback_query
                else:
                    rag_query = "强制默认查询"
            else:
                rag_query = "强制默认查询"
        
        return ContextCollectionResult(
            trigger_position=cursor_position,
            full_context=extracted_context.before_context,
            primary_keywords=extracted_context.primary_keywords,
            secondary_keywords=extracted_context.secondary_keywords,
            detected_entities=detected_entities,
            rag_query=rag_query,
            context_summary=context_summary,
            relevance_score=relevance_score,
            collection_method="intelligent_extraction"
        )
    
    def _build_intelligent_rag_query(self, extracted_context: ExtractedContext, 
                                   detected_entities: List[str]) -> str:
        """构建智能的RAG查询"""
        start_time = time.time()
        query_parts = []
        
        logger.debug(f"[RAG_QUERY_BUILD] 开始构建查询，实体数={len(detected_entities)}, 主关键词数={len(extracted_context.primary_keywords)}, 次关键词数={len(extracted_context.secondary_keywords)}")
        
        # 1. 优先添加检测到的实体（角色、地点、物品等）
        if detected_entities:
            # 去重并限制数量
            unique_entities = list(dict.fromkeys(detected_entities))[:5]
            query_parts.extend(unique_entities)
            logger.debug(f"[RAG_QUERY_BUILD] 添加实体: {unique_entities}")
        
        # 2. 添加主要关键词（权重高）
        if extracted_context.primary_keywords:
            # 过滤掉已经包含的实体
            filtered_primary = [
                kw for kw in extracted_context.primary_keywords 
                if kw not in detected_entities
            ]
            query_parts.extend(filtered_primary[:8])
            logger.debug(f"[RAG_QUERY_BUILD] 添加主要关键词: {filtered_primary[:8]}")
        
        # 3. 添加次要关键词（权重低）
        if extracted_context.secondary_keywords:
            filtered_secondary = [
                kw for kw in extracted_context.secondary_keywords 
                if kw not in detected_entities and kw not in extracted_context.primary_keywords
            ]
            query_parts.extend(filtered_secondary[:3])
            logger.debug(f"[RAG_QUERY_BUILD] 添加次要关键词: {filtered_secondary[:3]}")
        
        logger.debug(f"[RAG_QUERY_BUILD] 第一阶段查询部分: {query_parts}")
        
        # 4. 多重降级策略
        if len(query_parts) < 3:
            # 4.1 首先尝试提取最近的句子
            if extracted_context.before_context:
                sentences = self._extract_recent_sentences(extracted_context.before_context, 3)  # 增加句子数量
                if sentences:
                    query_parts.extend(sentences)
            
            # 4.2 如果仍然不足，尝试直接使用段落
            if len(query_parts) < 2 and extracted_context.segments:
                # 选择最重要的段落提取关键词
                important_segments = sorted(extracted_context.segments, 
                                          key=lambda x: x.importance_score, 
                                          reverse=True)[:2]
                for segment in important_segments:
                    segment_keywords = segment.keywords[:3]  # 每个段落最多3个关键词
                    query_parts.extend([kw for kw in segment_keywords if kw not in query_parts])
        
        # 5. 构建最终查询字符串
        query = " ".join(query_parts)
        
        # 6. 限制查询长度
        if len(query) > 200:
            query = query[:200]
        
        # 7. 确保查询不为空（多重备用策略）
        if not query.strip():
            # 7.1 首先使用原始上下文的最后一部分
            if extracted_context.before_context:
                last_part = extracted_context.before_context[-150:].strip()  # 增加字符数
                if last_part:
                    query = last_part
                    logger.warning(f"查询为空，使用最后150个字符作为备用查询")
            
            # 7.2 如果仍然为空，尝试使用全文的关键字符
            if not query.strip() and len(extracted_context.before_context) > 0:
                # 提取全文中的数字、专有名词等特殊字符
                special_chars = re.findall(r'[\d]+|[\u4e00-\u9fff]{2,3}', extracted_context.before_context)
                if special_chars:
                    query = " ".join(special_chars[:10])
                    logger.warning(f"使用特殊字符作为备用查询: '{query}'")
            
            # 7.3 最后的备用方案
            if not query.strip():
                query = "默认查询"
                logger.warning("无法构建有效查询，使用默认查询")
        
        elapsed = time.time() - start_time
        logger.debug(f"[RAG_QUERY] 构建查询耗时={elapsed:.3f}s, 实体={len(detected_entities)}, 关键词={len(extracted_context.primary_keywords)}, 查询='{query[:50]}...'")
        
        return query.strip()
    
    def _extract_recent_sentences(self, text: str, max_sentences: int = 2) -> List[str]:
        """提取最近的几句话"""
        if not text:
            return []
        
        # 按句号、感叹号、问号分割
        sentences = re.split(r'[。！？]', text)
        
        # 过滤空句子并获取最后几句
        valid_sentences = [s.strip() for s in sentences if s.strip()]
        
        if not valid_sentences:
            return []
        
        # 返回最后几句，但不超过指定数量
        recent_sentences = valid_sentences[-max_sentences:]
        
        # 进一步处理，提取关键词
        processed_sentences = []
        for sentence in recent_sentences:
            # 提取中文词汇
            words = re.findall(r'[\u4e00-\u9fff]{2,4}', sentence)
            if words:
                # 限制每句话的词汇数量
                processed_sentences.extend(words[:5])
        
        # 如果提取的关键词太少，尝试使用更宽松的提取方法
        if len(processed_sentences) < 3:
            # 直接使用最后一句话的片段
            if recent_sentences:
                last_sentence = recent_sentences[-1]
                # 如果句子较长，取最后部分
                if len(last_sentence) > 20:
                    processed_sentences.append(last_sentence[-20:])
                else:
                    processed_sentences.append(last_sentence)
        
        # 记录提取结果
        logger.debug(f"[SENTENCE_EXTRACT] 输入长度={len(text)}, 句子数={len(valid_sentences)}, 提取关键词={len(processed_sentences)}")
        
        return processed_sentences
    
    def _generate_intelligent_summary(self, extracted_context: ExtractedContext, 
                                    detected_entities: List[str]) -> str:
        """生成智能上下文摘要"""
        summary_parts = []
        
        # 1. 添加检测到的实体
        if detected_entities:
            entity_summary = f"实体: {', '.join(detected_entities[:5])}"
            summary_parts.append(entity_summary)
        
        # 2. 添加主要关键词
        if extracted_context.primary_keywords:
            keyword_summary = f"关键词: {', '.join(extracted_context.primary_keywords[:5])}"
            summary_parts.append(keyword_summary)
        
        # 3. 添加上下文类型信息
        if extracted_context.segments:
            context_types = list(set([seg.context_type.value for seg in extracted_context.segments]))
            type_summary = f"类型: {', '.join(context_types)}"
            summary_parts.append(type_summary)
        
        # 4. 添加相关性信息
        relevance_info = f"相关性: {extracted_context.relevance_score:.2f}"
        summary_parts.append(relevance_info)
        
        return " | ".join(summary_parts)
    
    def _calculate_enhanced_relevance(self, extracted_context: ExtractedContext, 
                                    detected_entities: List[str]) -> float:
        """计算增强的相关性分数"""
        base_score = extracted_context.relevance_score
        
        # 实体加权
        entity_bonus = min(0.2, len(detected_entities) * 0.05)
        
        # 关键词质量加权
        keyword_quality = self._assess_keyword_quality(
            extracted_context.primary_keywords + extracted_context.secondary_keywords
        )
        
        # 上下文长度加权
        length_factor = min(1.0, len(extracted_context.before_context) / 300)
        
        # 计算最终分数
        final_score = base_score + entity_bonus + keyword_quality * 0.1 + length_factor * 0.1
        
        return min(1.0, final_score)
    
    def _assess_keyword_quality(self, keywords: List[str]) -> float:
        """评估关键词质量"""
        if not keywords:
            return 0.0
        
        quality_score = 0.0
        
        for keyword in keywords:
            # 长度加权
            if len(keyword) >= 3:
                quality_score += 0.2
            elif len(keyword) == 2:
                quality_score += 0.1
            
            # 特殊词汇加权
            if self._is_story_element(keyword):
                quality_score += 0.3
        
        # 归一化
        return min(1.0, quality_score / len(keywords))
    
    def _is_story_element(self, word: str) -> bool:
        """判断是否为故事元素"""
        story_patterns = [
            r'[\u4e00-\u9fff]*[力气血魂魄]',  # 修仙元素
            r'[\u4e00-\u9fff]*[符咒法术]',    # 法术元素
            r'[\u4e00-\u9fff]*[剑刀枪矛]',    # 武器元素
            r'[\u4e00-\u9fff]*[宫殿楼阁]',    # 建筑元素
        ]
        
        for pattern in story_patterns:
            if re.search(pattern, word):
                return True
        
        return False
    
    def _create_empty_result(self, cursor_position: int) -> ContextCollectionResult:
        """创建空的收集结果"""
        return ContextCollectionResult(
            trigger_position=cursor_position,
            full_context="",
            primary_keywords=[],
            secondary_keywords=[],
            detected_entities=[],
            rag_query="",
            context_summary="",
            relevance_score=0.0,
            collection_method="empty"
        )
    
    def get_rag_optimized_query(self, collection_result: ContextCollectionResult) -> Dict[str, any]:
        """获取RAG优化的查询信息"""
        return {
            'query': collection_result.rag_query,
            'context': collection_result.full_context,
            'keywords': collection_result.primary_keywords + collection_result.secondary_keywords,
            'entities': collection_result.detected_entities,
            'summary': collection_result.context_summary,
            'relevance': collection_result.relevance_score,
            'method': collection_result.collection_method
        }
    
    def update_configuration(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Updated context collector config: {key} = {value}")
    
    def get_collection_statistics(self) -> Dict[str, any]:
        """获取收集统计信息"""
        return {
            'max_context_length': self.max_context_length,
            'min_context_length': self.min_context_length,
            'keyword_weights': {
                'primary': self.keyword_weight_primary,
                'secondary': self.keyword_weight_secondary
            },
            'extractor_config': self.context_extractor.__dict__ if hasattr(self.context_extractor, '__dict__') else {},
            'entity_detector_available': self.entity_detector is not None
        }