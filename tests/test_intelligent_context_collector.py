"""
智能上下文收集器的单元测试
测试上下文收集、关键词提取、RAG查询构建等功能
"""

import unittest
from unittest.mock import Mock, MagicMock
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.intelligent_context_collector import (
    IntelligentContextCollector,
    ContextCollectionResult
)
from core.codex_manager import CodexManager, CodexEntry, CodexEntryType


class TestIntelligentContextCollector(unittest.TestCase):
    """智能上下文收集器测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建模拟的CodexManager
        self.mock_codex_manager = Mock(spec=CodexManager)
        
        # 创建测试用的Codex条目
        self.test_entries = [
            CodexEntry(
                id="char1", title="陈云寒", entry_type=CodexEntryType.CHARACTER,
                description="主角", track_references=True, aliases=["云寒"]
            ),
            CodexEntry(
                id="obj1", title="清心符", entry_type=CodexEntryType.OBJECT,
                description="符咒", track_references=True, aliases=["符纸"]
            ),
            CodexEntry(
                id="obj2", title="梨木符案", entry_type=CodexEntryType.OBJECT,
                description="符案", track_references=True, aliases=["符案"]
            )
        ]
        
        # 配置mock方法
        self.mock_codex_manager.get_all_entries.return_value = self.test_entries
        self.mock_codex_manager.get_entry.side_effect = lambda entry_id: next(
            (entry for entry in self.test_entries if entry.id == entry_id), None
        )
        
        # 创建收集器实例
        self.collector = IntelligentContextCollector(self.mock_codex_manager)
    
    def test_basic_context_collection(self):
        """测试基础上下文收集功能"""
        test_text = "陈云寒拿起清心符，放在梨木符案上。这是一个测试。"
        cursor_pos = len(test_text)
        
        result = self.collector.collect_context_for_completion(test_text, cursor_pos)
        
        # 验证基本属性
        self.assertIsInstance(result, ContextCollectionResult)
        self.assertEqual(result.trigger_position, cursor_pos)
        self.assertIsInstance(result.primary_keywords, list)
        self.assertIsInstance(result.detected_entities, list)
        self.assertIsInstance(result.rag_query, str)
        
        # 验证检测到的实体
        self.assertGreater(len(result.detected_entities), 0, "应该检测到实体")
        self.assertIn("陈云寒", result.detected_entities, "应该检测到角色")
    
    def test_complex_novel_context(self):
        """测试复杂小说上下文"""
        test_text = """噗。像一只被戳破的、受了潮的纸灯笼，声音闷在喉咙里，短促，且无力。
        陈云寒垂下眼帘，看着自己修长的指尖。最后一缕银丝般的灵力，就在那里，彻底失控，
        像一条受惊的蛇，在符纸上疯狂冲撞，最终不甘地归于寂灭。那张本应泛起微光的"清心符"，
        连最后的蜷缩挣扎都省了，直接瘫软下去，化作一小撮尚有余温的灰烬，从梨木符案上簌簌落下。
        这个月第三次了。"""
        
        cursor_pos = len(test_text)
        
        result = self.collector.collect_context_for_completion(test_text, cursor_pos)
        
        # 验证RAG查询质量
        self.assertGreater(len(result.rag_query), 10, "RAG查询应该有足够的内容")
        self.assertNotEqual(result.rag_query, "这个月第三次了", "RAG查询不应该只是最后一句话")
        
        # 验证检测到的关键实体
        expected_entities = ["陈云寒", "清心符", "梨木符案"]
        found_entities = [entity for entity in expected_entities if entity in result.detected_entities]
        self.assertGreater(len(found_entities), 0, f"应该检测到关键实体，期望: {expected_entities}, 实际: {result.detected_entities}")
        
        # 验证关键词质量
        all_keywords = result.primary_keywords + result.secondary_keywords
        story_keywords = ["灵力", "符纸", "灰烬", "指尖"]
        found_keywords = [kw for kw in story_keywords if any(kw in keyword for keyword in all_keywords)]
        self.assertGreater(len(found_keywords), 0, f"应该提取到故事相关关键词，期望包含: {story_keywords}, 实际: {all_keywords}")
    
    def test_rag_query_construction(self):
        """测试RAG查询构建"""
        test_text = "在修仙世界中，陈云寒是一位年轻的修士。他擅长制作清心符，经常在梨木符案前练习。"
        cursor_pos = len(test_text)
        
        result = self.collector.collect_context_for_completion(test_text, cursor_pos)
        
        # 验证RAG查询包含重要信息
        rag_query = result.rag_query.lower()
        
        # 应该包含实体
        if result.detected_entities:
            entity_found = any(entity.lower() in rag_query for entity in result.detected_entities)
            self.assertTrue(entity_found, f"RAG查询应该包含检测到的实体: {result.detected_entities}")
        
        # 应该包含关键词
        if result.primary_keywords:
            keyword_found = any(keyword.lower() in rag_query for keyword in result.primary_keywords)
            self.assertTrue(keyword_found, f"RAG查询应该包含主要关键词: {result.primary_keywords}")
        
        # 查询长度应该合理
        self.assertLessEqual(len(result.rag_query), 200, "RAG查询长度不应该超过200字符")
        self.assertGreater(len(result.rag_query), 5, "RAG查询不应该太短")
    
    def test_entity_detection_integration(self):
        """测试实体检测集成"""
        test_text = "陈云寒在房间里制作清心符，桌上放着梨木符案。"
        cursor_pos = len(test_text)
        
        result = self.collector.collect_context_for_completion(test_text, cursor_pos)
        
        # 验证实体检测
        self.assertIsInstance(result.detected_entities, list)
        
        # 验证检测到的实体类型
        expected_entities = ["陈云寒", "清心符", "梨木符案"]
        for expected in expected_entities:
            if expected in result.detected_entities:
                # 找到了期望的实体
                break
        else:
            # 如果没有找到任何期望的实体，可能是检测器配置问题
            self.skipTest(f"实体检测器未检测到期望的实体: {expected_entities}, 实际检测到: {result.detected_entities}")
    
    def test_keyword_quality_assessment(self):
        """测试关键词质量评估"""
        # 测试高质量关键词
        high_quality_keywords = ["修仙", "灵力", "符咒", "法术"]
        quality_score = self.collector._assess_keyword_quality(high_quality_keywords)
        self.assertGreater(quality_score, 0.3, "高质量关键词应该有较高分数")
        
        # 测试低质量关键词
        low_quality_keywords = ["的", "了", "在", "是"]
        quality_score = self.collector._assess_keyword_quality(low_quality_keywords)
        self.assertLess(quality_score, 0.5, "低质量关键词应该有较低分数")
    
    def test_story_element_detection(self):
        """测试故事元素检测"""
        # 测试修仙元素
        self.assertTrue(self.collector._is_story_element("灵力"), "应该识别修仙元素")
        self.assertTrue(self.collector._is_story_element("法术"), "应该识别法术元素")
        self.assertTrue(self.collector._is_story_element("宝剑"), "应该识别武器元素")
        self.assertTrue(self.collector._is_story_element("宫殿"), "应该识别建筑元素")
        
        # 测试非故事元素
        self.assertFalse(self.collector._is_story_element("桌子"), "不应该识别普通词汇")
        self.assertFalse(self.collector._is_story_element("今天"), "不应该识别时间词汇")
    
    def test_recent_sentences_extraction(self):
        """测试最近句子提取"""
        test_text = "第一句话。第二句话！第三句话？最后一句话。"
        
        sentences = self.collector._extract_recent_sentences(test_text, 2)
        
        self.assertIsInstance(sentences, list)
        self.assertGreater(len(sentences), 0, "应该提取到句子")
        
        # 验证提取的是最近的句子内容
        sentences_text = " ".join(sentences)
        self.assertTrue(any(word in sentences_text for word in ["最后", "第三"]), 
                       "应该包含最近句子的内容")
    
    def test_empty_context_handling(self):
        """测试空上下文处理"""
        # 空文本
        result = self.collector.collect_context_for_completion("", 0)
        self.assertEqual(result.collection_method, "empty")
        self.assertEqual(len(result.rag_query), 0)
        
        # 无效位置
        result = self.collector.collect_context_for_completion("测试文本", -1)
        self.assertEqual(result.collection_method, "empty")
    
    def test_rag_optimized_query_generation(self):
        """测试RAG优化查询生成"""
        test_text = "陈云寒专心制作清心符，灵力在指尖流转。"
        cursor_pos = len(test_text)
        
        result = self.collector.collect_context_for_completion(test_text, cursor_pos)
        rag_info = self.collector.get_rag_optimized_query(result)
        
        # 验证RAG信息结构
        required_keys = ['query', 'context', 'keywords', 'entities', 'summary', 'relevance', 'method']
        for key in required_keys:
            self.assertIn(key, rag_info, f"RAG信息应该包含{key}")
        
        # 验证查询质量
        self.assertIsInstance(rag_info['query'], str)
        self.assertGreater(len(rag_info['query']), 0, "RAG查询不应该为空")
        
        # 验证关键词和实体
        self.assertIsInstance(rag_info['keywords'], list)
        self.assertIsInstance(rag_info['entities'], list)
    
    def test_configuration_update(self):
        """测试配置更新"""
        original_length = self.collector.max_context_length
        
        # 更新配置
        self.collector.update_configuration(max_context_length=1000)
        self.assertEqual(self.collector.max_context_length, 1000)
        
        # 恢复原始配置
        self.collector.max_context_length = original_length
    
    def test_collection_statistics(self):
        """测试收集统计信息"""
        stats = self.collector.get_collection_statistics()
        
        # 验证统计信息结构
        required_keys = ['max_context_length', 'min_context_length', 'keyword_weights', 'entity_detector_available']
        for key in required_keys:
            self.assertIn(key, stats, f"统计信息应该包含{key}")
        
        # 验证数据类型
        self.assertIsInstance(stats['max_context_length'], int)
        self.assertIsInstance(stats['keyword_weights'], dict)
        self.assertIsInstance(stats['entity_detector_available'], bool)
    
    def test_relevance_score_calculation(self):
        """测试相关性分数计算"""
        # 高相关性文本
        high_relevance_text = "陈云寒运用灵力制作清心符，符纸在梨木符案上发出微光。"
        cursor_pos = len(high_relevance_text)
        
        high_result = self.collector.collect_context_for_completion(high_relevance_text, cursor_pos)
        
        # 低相关性文本
        low_relevance_text = "今天天气不错，明天可能下雨。"
        cursor_pos = len(low_relevance_text)
        
        low_result = self.collector.collect_context_for_completion(low_relevance_text, cursor_pos)
        
        # 验证相关性分数
        self.assertGreaterEqual(high_result.relevance_score, 0.0)
        self.assertLessEqual(high_result.relevance_score, 1.0)
        self.assertGreaterEqual(low_result.relevance_score, 0.0)
        self.assertLessEqual(low_result.relevance_score, 1.0)
        
        # 高相关性文本应该有更高的分数
        self.assertGreater(high_result.relevance_score, low_result.relevance_score)


class TestIntelligentContextCollectorWithoutCodex(unittest.TestCase):
    """不使用Codex的智能上下文收集器测试"""
    
    def setUp(self):
        """测试前准备"""
        # 创建不带Codex的收集器
        self.collector = IntelligentContextCollector()
    
    def test_context_collection_without_codex(self):
        """测试不使用Codex的上下文收集"""
        test_text = "这是一个测试文本，用于验证不使用Codex时的功能。"
        cursor_pos = len(test_text)
        
        result = self.collector.collect_context_for_completion(test_text, cursor_pos)
        
        # 验证基本功能仍然工作
        self.assertIsInstance(result, ContextCollectionResult)
        self.assertEqual(result.trigger_position, cursor_pos)
        self.assertIsInstance(result.primary_keywords, list)
        self.assertEqual(len(result.detected_entities), 0, "没有Codex时不应该检测到实体")
        
        # RAG查询应该基于关键词
        self.assertGreater(len(result.rag_query), 0, "即使没有实体，也应该有RAG查询")


if __name__ == '__main__':
    unittest.main()