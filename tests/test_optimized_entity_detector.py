"""
优化实体检测器的单元测试
测试时间表达式过滤、置信度机制等功能
"""

import unittest
from unittest.mock import Mock, MagicMock
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.optimized_entity_detector import (
    OptimizedEntityDetector, 
    OptimizedDetectedReference,
    EntityConfidence
)
from core.codex_manager import CodexManager, CodexEntry, CodexEntryType


class TestOptimizedEntityDetector(unittest.TestCase):
    """优化实体检测器测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建模拟的CodexManager
        self.mock_codex_manager = Mock(spec=CodexManager)
        
        # 创建测试用的Codex条目
        self.test_entries = [
            CodexEntry(
                id="char1",
                title="张三",
                entry_type=CodexEntryType.CHARACTER,
                description="主角",
                track_references=True,
                aliases=["小张", "张公子"]
            ),
            CodexEntry(
                id="loc1", 
                title="天山",
                entry_type=CodexEntryType.LOCATION,
                description="雪山",
                track_references=True,
                aliases=["天山雪峰"]
            ),
            CodexEntry(
                id="obj1",
                title="倚天剑",
                entry_type=CodexEntryType.OBJECT,
                description="神剑",
                track_references=True,
                aliases=["神剑"]
            )
        ]
        
        # 配置mock方法
        self.mock_codex_manager.get_all_entries.return_value = self.test_entries
        self.mock_codex_manager.get_entry.side_effect = lambda entry_id: next(
            (entry for entry in self.test_entries if entry.id == entry_id), None
        )
        
        # 创建检测器实例
        self.detector = OptimizedEntityDetector(self.mock_codex_manager)
    
    def test_time_expression_filtering(self):
        """测试时间表达式过滤功能"""
        # 测试文本包含时间表达式
        test_text = "这个月第三次了，张三又来到天山。"
        
        references = self.detector.detect_references(test_text)
        
        # 验证"第三次"被过滤掉，但"张三"和"天山"被保留
        matched_texts = [ref.matched_text for ref in references]
        
        self.assertNotIn("第三次", matched_texts, "时间表达式应该被过滤")
        self.assertIn("张三", matched_texts, "角色名应该被保留")
        self.assertIn("天山", matched_texts, "地点名应该被保留")
    
    def test_quantity_expression_filtering(self):
        """测试数量表达式过滤功能"""
        test_text = "张三拿了三个苹果，去了天山。"
        
        references = self.detector.detect_references(test_text)
        matched_texts = [ref.matched_text for ref in references]
        
        self.assertNotIn("三个", matched_texts, "数量表达式应该被过滤")
        self.assertIn("张三", matched_texts, "角色名应该被保留")
        self.assertIn("天山", matched_texts, "地点名应该被保留")
    
    def test_negative_context_filtering(self):
        """测试否定语境过滤功能"""
        test_text = "这不是张三，而是李四。天山很美。"
        
        references = self.detector.detect_references(test_text)
        matched_texts = [ref.matched_text for ref in references]
        
        # 在否定语境中的"张三"应该被过滤或置信度降低
        zhang_san_refs = [ref for ref in references if ref.matched_text == "张三"]
        if zhang_san_refs:
            # 如果没有被完全过滤，置信度应该很低
            self.assertLess(zhang_san_refs[0].confidence, 0.6, "否定语境中的实体置信度应该很低")
        
        self.assertIn("天山", matched_texts, "正常语境中的地点名应该被保留")
    
    def test_confidence_calculation(self):
        """测试置信度计算功能"""
        test_text = "张三说道：'我要去天山寻找倚天剑。'"
        
        references = self.detector.detect_references(test_text)
        
        # 验证所有引用都有合理的置信度
        for ref in references:
            self.assertGreaterEqual(ref.confidence, 0.0, "置信度不应该小于0")
            self.assertLessEqual(ref.confidence, 1.0, "置信度不应该大于1")
            
            # 验证置信度等级
            if hasattr(ref, 'confidence_level'):
                self.assertIsInstance(ref.confidence_level, EntityConfidence)
    
    def test_context_relevance_scoring(self):
        """测试上下文相关性评分"""
        # 角色相关的上下文
        character_context = "张三走过来说道：'你好。'"
        char_refs = self.detector.detect_references(character_context)
        
        # 地点相关的上下文
        location_context = "他们来到天山脚下。"
        loc_refs = self.detector.detect_references(location_context)
        
        # 验证在相关上下文中的实体有更高的置信度
        zhang_san_ref = next((ref for ref in char_refs if ref.matched_text == "张三"), None)
        tian_shan_ref = next((ref for ref in loc_refs if ref.matched_text == "天山"), None)
        
        if zhang_san_ref:
            self.assertGreater(zhang_san_ref.confidence, 0.6, "相关上下文中的角色应该有较高置信度")
        
        if tian_shan_ref:
            self.assertGreater(tian_shan_ref.confidence, 0.6, "相关上下文中的地点应该有较高置信度")
    
    def test_alias_detection(self):
        """测试别名检测功能"""
        test_text = "小张和张公子都是好人，他们去了天山雪峰。"
        
        references = self.detector.detect_references(test_text)
        matched_texts = [ref.matched_text for ref in references]
        
        self.assertIn("小张", matched_texts, "别名应该被检测到")
        self.assertIn("张公子", matched_texts, "别名应该被检测到")
        self.assertIn("天山雪峰", matched_texts, "地点别名应该被检测到")
    
    def test_common_false_positives(self):
        """测试常见误识别词汇过滤"""
        test_text = "第一次见面，张三说了几个字。"
        
        references = self.detector.detect_references(test_text)
        matched_texts = [ref.matched_text for ref in references]
        
        self.assertNotIn("第一次", matched_texts, "常见误识别词汇应该被过滤")
        self.assertNotIn("几个", matched_texts, "常见误识别词汇应该被过滤")
        self.assertIn("张三", matched_texts, "真实实体应该被保留")
    
    def test_confidence_threshold_filtering(self):
        """测试置信度阈值过滤"""
        # 设置较高的置信度阈值
        original_threshold = self.detector.min_confidence_threshold
        self.detector.min_confidence_threshold = 0.8
        
        try:
            test_text = "可能是张三吧，不太确定。"
            references = self.detector.detect_references(test_text)
            
            # 在不确定的语境中，低置信度的引用应该被过滤
            for ref in references:
                self.assertGreaterEqual(ref.confidence, 0.8, "低于阈值的引用应该被过滤")
        
        finally:
            # 恢复原始阈值
            self.detector.min_confidence_threshold = original_threshold
    
    def test_entity_type_matching(self):
        """测试实体类型匹配度计算"""
        test_text = "张三拿着倚天剑来到天山城。"
        
        references = self.detector.detect_references(test_text)
        
        # 验证不同类型的实体都被正确识别
        entity_types = {ref.matched_text: ref.entry_type for ref in references}
        
        if "张三" in entity_types:
            self.assertEqual(entity_types["张三"], CodexEntryType.CHARACTER)
        
        if "倚天剑" in entity_types:
            self.assertEqual(entity_types["倚天剑"], CodexEntryType.OBJECT)
        
        if "天山" in entity_types:
            self.assertEqual(entity_types["天山"], CodexEntryType.LOCATION)
    
    def test_context_keywords_extraction(self):
        """测试上下文关键词提取"""
        test_text = "在一个风雪交加的夜晚，张三独自一人来到了天山脚下，寻找传说中的倚天剑。"
        cursor_pos = test_text.find("张三") + 2  # 张三之后的位置
        
        references = self.detector.detect_references(test_text)
        
        # 检查是否有上下文关键词
        for ref in references:
            if hasattr(ref, 'context_keywords') and ref.matched_text == "张三":
                self.assertIsInstance(ref.context_keywords, list)
                # 应该包含一些相关的关键词
                keywords_text = " ".join(ref.context_keywords)
                self.assertTrue(
                    any(keyword in keywords_text for keyword in ["风雪", "夜晚", "独自", "寻找"]),
                    "应该提取到相关的上下文关键词"
                )
    
    def test_update_confidence_threshold(self):
        """测试更新置信度阈值"""
        original_threshold = self.detector.min_confidence_threshold
        
        # 测试有效的阈值更新
        self.detector.update_confidence_threshold(0.7)
        self.assertEqual(self.detector.min_confidence_threshold, 0.7)
        
        # 测试无效的阈值（应该被忽略）
        self.detector.update_confidence_threshold(1.5)
        self.assertEqual(self.detector.min_confidence_threshold, 0.7)  # 应该保持不变
        
        self.detector.update_confidence_threshold(-0.1)
        self.assertEqual(self.detector.min_confidence_threshold, 0.7)  # 应该保持不变
        
        # 恢复原始阈值
        self.detector.min_confidence_threshold = original_threshold
    
    def test_false_positive_filter_management(self):
        """测试误识别过滤器管理"""
        # 添加新的误识别词汇
        self.detector.add_false_positive_filter("测试词")
        self.assertIn("测试词", self.detector.common_false_positives)
        
        # 移除误识别词汇
        self.detector.remove_false_positive_filter("测试词")
        self.assertNotIn("测试词", self.detector.common_false_positives)
    
    def test_detection_statistics(self):
        """测试检测统计信息"""
        stats = self.detector.get_detection_statistics()
        
        # 验证统计信息包含必要的字段
        self.assertIn('optimization_config', stats)
        self.assertIn('confidence_thresholds', stats)
        
        optimization_config = stats['optimization_config']
        self.assertIn('min_confidence_threshold', optimization_config)
        self.assertIn('time_expression_patterns', optimization_config)
        self.assertIn('quantity_patterns', optimization_config)
        
        confidence_thresholds = stats['confidence_thresholds']
        self.assertIn('high', confidence_thresholds)
        self.assertIn('medium', confidence_thresholds)
        self.assertIn('low', confidence_thresholds)


if __name__ == '__main__':
    unittest.main()