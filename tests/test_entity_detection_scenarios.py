"""
实体检测场景测试
测试各种复杂文本场景下的实体识别准确性
"""

import unittest
from unittest.mock import Mock
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.optimized_entity_detector import OptimizedEntityDetector, EntityConfidence
from core.codex_manager import CodexManager, CodexEntry, CodexEntryType


class TestEntityDetectionScenarios(unittest.TestCase):
    """实体检测场景测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建模拟的CodexManager
        self.mock_codex_manager = Mock(spec=CodexManager)
        
        # 创建丰富的测试用Codex条目
        self.test_entries = [
            # 角色
            CodexEntry(
                id="char1", title="张三", entry_type=CodexEntryType.CHARACTER,
                description="主角", track_references=True, aliases=["小张", "张公子"]
            ),
            CodexEntry(
                id="char2", title="李四", entry_type=CodexEntryType.CHARACTER,
                description="配角", track_references=True, aliases=["李师傅"]
            ),
            CodexEntry(
                id="char3", title="王五", entry_type=CodexEntryType.CHARACTER,
                description="反派", track_references=True, aliases=["王老五"]
            ),
            # 地点
            CodexEntry(
                id="loc1", title="天山", entry_type=CodexEntryType.LOCATION,
                description="雪山", track_references=True, aliases=["天山雪峰", "雪山"]
            ),
            CodexEntry(
                id="loc2", title="江南", entry_type=CodexEntryType.LOCATION,
                description="水乡", track_references=True, aliases=["江南水乡"]
            ),
            CodexEntry(
                id="loc3", title="北京城", entry_type=CodexEntryType.LOCATION,
                description="首都", track_references=True, aliases=["京城", "帝都"]
            ),
            # 物品
            CodexEntry(
                id="obj1", title="倚天剑", entry_type=CodexEntryType.OBJECT,
                description="神剑", track_references=True, aliases=["神剑", "宝剑"]
            ),
            CodexEntry(
                id="obj2", title="九阴真经", entry_type=CodexEntryType.OBJECT,
                description="武功秘籍", track_references=True, aliases=["真经", "秘籍"]
            )
        ]
        
        # 配置mock方法
        self.mock_codex_manager.get_all_entries.return_value = self.test_entries
        self.mock_codex_manager.get_entry.side_effect = lambda entry_id: next(
            (entry for entry in self.test_entries if entry.id == entry_id), None
        )
        
        # 创建检测器实例
        self.detector = OptimizedEntityDetector(self.mock_codex_manager)
    
    def test_simple_narrative_scenario(self):
        """测试简单叙述场景"""
        text = "张三来到天山，寻找传说中的倚天剑。"
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        self.assertIn("张三", matched_texts, "应该识别角色名")
        self.assertIn("天山", matched_texts, "应该识别地点名")
        self.assertIn("倚天剑", matched_texts, "应该识别物品名")
        
        # 验证置信度
        for ref in references:
            self.assertGreaterEqual(ref.confidence, 0.6, f"{ref.matched_text}的置信度应该足够高")
    
    def test_dialogue_scenario(self):
        """测试对话场景"""
        text = '张三说："我要去天山找倚天剑。"李四回答："那里很危险。"'
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        self.assertIn("张三", matched_texts, "对话中应该识别说话者")
        self.assertIn("李四", matched_texts, "对话中应该识别回答者")
        self.assertIn("天山", matched_texts, "对话内容中应该识别地点")
        self.assertIn("倚天剑", matched_texts, "对话内容中应该识别物品")
    
    def test_time_expression_filtering(self):
        """测试时间表达式过滤场景"""
        text = "这是第三次了，张三又来到天山。昨天李四也来过。"
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        
        # 时间表达式应该被过滤
        self.assertNotIn("第三次", matched_texts, "时间表达式应该被过滤")
        self.assertNotIn("昨天", matched_texts, "时间词应该被过滤")
        
        # 真实实体应该被保留
        self.assertIn("张三", matched_texts, "角色名应该被保留")
        self.assertIn("天山", matched_texts, "地点名应该被保留")
        self.assertIn("李四", matched_texts, "角色名应该被保留")
    
    def test_quantity_expression_filtering(self):
        """测试数量表达式过滤场景"""
        text = "张三拿了三个苹果，和两个朋友一起去天山。"
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        
        # 数量表达式应该被过滤
        self.assertNotIn("三个", matched_texts, "数量表达式应该被过滤")
        self.assertNotIn("两个", matched_texts, "数量表达式应该被过滤")
        
        # 真实实体应该被保留
        self.assertIn("张三", matched_texts, "角色名应该被保留")
        self.assertIn("天山", matched_texts, "地点名应该被保留")
    
    def test_negative_context_scenario(self):
        """测试否定语境场景"""
        text = "这不是张三，而是李四。但天山确实很美。"
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        
        # 否定语境中的实体应该被过滤或置信度很低
        zhang_san_refs = [ref for ref in references if ref.matched_text == "张三"]
        if zhang_san_refs:
            self.assertLess(zhang_san_refs[0].confidence, 0.6, "否定语境中的实体置信度应该很低")
        
        # 正常语境中的实体应该被保留
        self.assertIn("李四", matched_texts, "正常语境中的角色应该被保留")
        self.assertIn("天山", matched_texts, "正常语境中的地点应该被保留")
    
    def test_alias_recognition_scenario(self):
        """测试别名识别场景"""
        text = "小张和张公子都很厉害，他们在雪山上找到了神剑。"
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        
        # 别名应该被正确识别
        self.assertIn("小张", matched_texts, "角色别名应该被识别")
        self.assertIn("张公子", matched_texts, "角色别名应该被识别")
        self.assertIn("雪山", matched_texts, "地点别名应该被识别")
        self.assertIn("神剑", matched_texts, "物品别名应该被识别")
        
        # 验证别名对应的实体类型
        for ref in references:
            if ref.matched_text in ["小张", "张公子"]:
                self.assertEqual(ref.entry_type, CodexEntryType.CHARACTER)
            elif ref.matched_text == "雪山":
                self.assertEqual(ref.entry_type, CodexEntryType.LOCATION)
            elif ref.matched_text == "神剑":
                self.assertEqual(ref.entry_type, CodexEntryType.OBJECT)
    
    def test_complex_narrative_scenario(self):
        """测试复杂叙述场景"""
        text = """
        在一个风雪交加的夜晚，张三独自来到了天山脚下。
        他手持倚天剑，心中想着李四曾经说过的话："真正的勇士不畏惧任何困难。"
        突然，王五从雪山深处走了出来，手中拿着九阴真经。
        """
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        
        # 验证所有实体都被正确识别
        expected_entities = ["张三", "天山", "倚天剑", "李四", "王五", "雪山", "九阴真经"]
        for entity in expected_entities:
            self.assertIn(entity, matched_texts, f"应该识别实体: {entity}")
        
        # 验证置信度分布
        high_confidence_count = len([ref for ref in references if ref.confidence >= 0.8])
        medium_confidence_count = len([ref for ref in references if 0.6 <= ref.confidence < 0.8])
        
        self.assertGreater(high_confidence_count + medium_confidence_count, 0, "应该有高或中等置信度的实体")
    
    def test_context_relevance_scenario(self):
        """测试上下文相关性场景"""
        # 角色相关上下文
        character_text = "张三走过来说道：'你好，我是张三。'然后他笑了笑。"
        char_refs = self.detector.detect_references(character_text)
        
        # 地点相关上下文
        location_text = "他们来到天山脚下，在天山上建立了营地。"
        loc_refs = self.detector.detect_references(location_text)
        
        # 物品相关上下文
        object_text = "张三拿起倚天剑，仔细擦拭着这把神剑。"
        obj_refs = self.detector.detect_references(object_text)
        
        # 验证相关上下文中的实体有更高置信度
        zhang_san_refs = [ref for ref in char_refs if ref.matched_text == "张三"]
        if zhang_san_refs:
            self.assertGreater(zhang_san_refs[0].confidence, 0.7, "相关上下文中的角色应该有高置信度")
        
        tian_shan_refs = [ref for ref in loc_refs if ref.matched_text == "天山"]
        if tian_shan_refs:
            self.assertGreater(tian_shan_refs[0].confidence, 0.7, "相关上下文中的地点应该有高置信度")
        
        sword_refs = [ref for ref in obj_refs if ref.matched_text in ["倚天剑", "神剑"]]
        if sword_refs:
            self.assertGreater(sword_refs[0].confidence, 0.7, "相关上下文中的物品应该有高置信度")
    
    def test_mixed_content_scenario(self):
        """测试混合内容场景"""
        text = """
        第一章：天山之行
        
        这是第三次了，张三决定前往天山。他准备了三个包裹，
        里面装着必需品和倚天剑。
        
        "这不是普通的旅行，"李四提醒他说，"天山上有很多危险。"
        
        但张三已经下定决心。昨天晚上，他梦见了九阴真经的秘密。
        """
        references = self.detector.detect_references(text)
        
        matched_texts = [ref.matched_text for ref in references]
        
        # 应该识别的实体
        expected_entities = ["张三", "天山", "倚天剑", "李四", "九阴真经"]
        for entity in expected_entities:
            self.assertIn(entity, matched_texts, f"应该识别实体: {entity}")
        
        # 不应该识别的表达式
        unwanted_expressions = ["第一章", "第三次", "三个", "昨天"]
        for expr in unwanted_expressions:
            self.assertNotIn(expr, matched_texts, f"不应该识别表达式: {expr}")
    
    def test_confidence_threshold_scenarios(self):
        """测试不同置信度阈值场景"""
        text = "可能是张三吧，不太确定。天山确实很美。"
        
        # 测试高阈值
        original_threshold = self.detector.min_confidence_threshold
        self.detector.min_confidence_threshold = 0.8
        
        high_threshold_refs = self.detector.detect_references(text)
        high_threshold_texts = [ref.matched_text for ref in high_threshold_refs]
        
        # 测试低阈值
        self.detector.min_confidence_threshold = 0.4
        low_threshold_refs = self.detector.detect_references(text)
        low_threshold_texts = [ref.matched_text for ref in low_threshold_refs]
        
        # 恢复原始阈值
        self.detector.min_confidence_threshold = original_threshold
        
        # 验证阈值效果
        self.assertLessEqual(len(high_threshold_texts), len(low_threshold_texts), 
                           "高阈值应该过滤更多低置信度实体")
        
        # "天山"在明确上下文中应该被保留
        self.assertIn("天山", low_threshold_texts, "明确的实体应该被保留")
    
    def test_context_keywords_extraction_scenario(self):
        """测试上下文关键词提取场景"""
        text = "在一个月黑风高的夜晚，张三独自一人踏上了前往天山的危险旅程，寻找传说中的倚天剑。"
        references = self.detector.detect_references(text)
        
        # 检查关键词提取
        for ref in references:
            if hasattr(ref, 'context_keywords') and ref.matched_text == "张三":
                self.assertIsInstance(ref.context_keywords, list)
                keywords_text = " ".join(ref.context_keywords)
                
                # 应该包含相关的上下文关键词
                relevant_keywords = ["夜晚", "独自", "旅程", "寻找", "传说"]
                found_relevant = any(kw in keywords_text for kw in relevant_keywords)
                self.assertTrue(found_relevant, "应该提取到相关的上下文关键词")
    
    def test_entity_type_consistency_scenario(self):
        """测试实体类型一致性场景"""
        text = "张三、李四和王五三人来到天山和江南，寻找倚天剑和九阴真经。"
        references = self.detector.detect_references(text)
        
        # 按类型分组验证
        characters = [ref for ref in references if ref.entry_type == CodexEntryType.CHARACTER]
        locations = [ref for ref in references if ref.entry_type == CodexEntryType.LOCATION]
        objects = [ref for ref in references if ref.entry_type == CodexEntryType.OBJECT]
        
        # 验证角色
        character_names = [ref.matched_text for ref in characters]
        expected_characters = ["张三", "李四", "王五"]
        for char in expected_characters:
            self.assertIn(char, character_names, f"应该识别角色: {char}")
        
        # 验证地点
        location_names = [ref.matched_text for ref in locations]
        expected_locations = ["天山", "江南"]
        for loc in expected_locations:
            self.assertIn(loc, location_names, f"应该识别地点: {loc}")
        
        # 验证物品
        object_names = [ref.matched_text for ref in objects]
        expected_objects = ["倚天剑", "九阴真经"]
        for obj in expected_objects:
            self.assertIn(obj, object_names, f"应该识别物品: {obj}")


if __name__ == '__main__':
    unittest.main()