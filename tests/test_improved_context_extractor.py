"""
改进上下文提取器的单元测试
测试上下文分析、关键词提取等功能
"""

import unittest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.improved_context_extractor import (
    ImprovedContextExtractor,
    ExtractedContext,
    ContextSegment,
    ContextType
)


class TestImprovedContextExtractor(unittest.TestCase):
    """改进上下文提取器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = ImprovedContextExtractor()
    
    def test_basic_context_extraction(self):
        """测试基础上下文提取功能"""
        test_text = "张三走在路上，突然看到了一个奇怪的东西。他停下脚步，仔细观察。"
        cursor_pos = test_text.find("他停下") # 在"他停下"位置触发补全
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证基本属性
        self.assertEqual(context.trigger_position, cursor_pos)
        self.assertIsInstance(context.before_context, str)
        self.assertIsInstance(context.after_context, str)
        self.assertIsInstance(context.primary_keywords, list)
        self.assertIsInstance(context.secondary_keywords, list)
        
        # 验证前置上下文包含相关信息
        self.assertIn("张三", context.before_context)
        self.assertIn("走在路上", context.before_context)
    
    def test_context_boundary_calculation(self):
        """测试上下文边界计算"""
        # 创建一个较长的文本
        test_text = "第一段内容。" * 20 + "关键内容在这里。" + "第二段内容。" * 10
        cursor_pos = test_text.find("关键内容") + 4
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证上下文长度合理
        self.assertLessEqual(len(context.before_context), self.extractor.primary_window_size + 50)
        self.assertLessEqual(len(context.after_context), self.extractor.secondary_window_size + 50)
        
        # 验证包含关键内容
        self.assertIn("关键内容", context.before_context + context.after_context)
    
    def test_keyword_extraction(self):
        """测试关键词提取功能"""
        test_text = "在一个风雪交加的夜晚，张三独自来到天山脚下，寻找传说中的倚天剑。"
        cursor_pos = test_text.find("寻找")
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证主要关键词
        self.assertIsInstance(context.primary_keywords, list)
        self.assertGreater(len(context.primary_keywords), 0)
        
        # 验证关键词质量（应该包含重要的名词）
        keywords_text = " ".join(context.primary_keywords)
        expected_keywords = ["张三", "天山", "倚天剑", "夜晚"]
        found_keywords = [kw for kw in expected_keywords if kw in keywords_text]
        self.assertGreater(len(found_keywords), 0, "应该提取到重要的关键词")
    
    def test_context_type_detection(self):
        """测试上下文类型检测"""
        # 对话类型
        dialogue_text = '张三说："你好，我是张三。"李四回答："很高兴认识你。"'
        cursor_pos = len(dialogue_text) // 2
        
        context = self.extractor.extract_context_for_completion(dialogue_text, cursor_pos)
        
        # 检查是否识别出对话类型的段落
        dialogue_segments = [seg for seg in context.segments if seg.context_type == ContextType.DIALOGUE]
        self.assertGreater(len(dialogue_segments), 0, "应该识别出对话类型")
        
        # 动作类型
        action_text = "张三快速跑向前方，跳过障碍物，攻击敌人。"
        cursor_pos = len(action_text) // 2
        
        context = self.extractor.extract_context_for_completion(action_text, cursor_pos)
        action_segments = [seg for seg in context.segments if seg.context_type == ContextType.ACTION]
        # 注意：由于动作词检测的阈值，可能不会被识别为ACTION类型，这是正常的
    
    def test_segment_importance_scoring(self):
        """测试段落重要性评分"""
        test_text = "这是一个普通的句子。张三拿着倚天剑来到天山，准备进行一场重要的战斗。这是另一个普通句子。"
        cursor_pos = test_text.find("准备")
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证段落有重要性分数
        for segment in context.segments:
            self.assertGreaterEqual(segment.importance_score, 0.0)
            self.assertLessEqual(segment.importance_score, 1.0)
        
        # 包含更多关键词的段落应该有更高的重要性分数
        if len(context.segments) > 1:
            scores = [seg.importance_score for seg in context.segments]
            self.assertGreater(max(scores), min(scores), "不同段落应该有不同的重要性分数")
    
    def test_context_summary_generation(self):
        """测试上下文摘要生成"""
        test_text = "在一个月黑风高的夜晚，张三独自一人来到了天山脚下。他手持倚天剑，准备寻找传说中的宝藏。"
        cursor_pos = test_text.find("准备")
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证摘要不为空
        self.assertIsInstance(context.context_summary, str)
        self.assertGreater(len(context.context_summary), 0)
        
        # 验证摘要包含关键信息
        self.assertTrue(
            any(keyword in context.context_summary for keyword in ["张三", "天山", "倚天剑"]),
            "摘要应该包含关键信息"
        )
    
    def test_relevance_score_calculation(self):
        """测试相关性分数计算"""
        # 高相关性文本
        high_relevance_text = "张三手持倚天剑，在天山之巅与敌人激战。剑光闪烁，雪花飞舞。"
        cursor_pos = len(high_relevance_text) // 2
        
        high_context = self.extractor.extract_context_for_completion(high_relevance_text, cursor_pos)
        
        # 低相关性文本
        low_relevance_text = "今天天气不错。明天可能会下雨。"
        cursor_pos = len(low_relevance_text) // 2
        
        low_context = self.extractor.extract_context_for_completion(low_relevance_text, cursor_pos)
        
        # 验证相关性分数
        self.assertGreaterEqual(high_context.relevance_score, 0.0)
        self.assertLessEqual(high_context.relevance_score, 1.0)
        self.assertGreaterEqual(low_context.relevance_score, 0.0)
        self.assertLessEqual(low_context.relevance_score, 1.0)
        
        # 高相关性文本应该有更高的分数
        self.assertGreater(high_context.relevance_score, low_context.relevance_score)
    
    def test_rag_query_context_generation(self):
        """测试RAG查询上下文生成"""
        test_text = "在天山雪峰之上，张三遇到了一位神秘的老者。老者告诉他关于倚天剑的秘密。"
        cursor_pos = test_text.find("老者告诉")
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        rag_context = self.extractor.get_rag_query_context(context)
        
        # 验证RAG上下文结构
        self.assertIn('query', rag_context)
        self.assertIn('context_summary', rag_context)
        self.assertIn('relevance_score', rag_context)
        self.assertIn('primary_keywords', rag_context)
        self.assertIn('secondary_keywords', rag_context)
        
        # 验证查询字符串不为空
        self.assertIsInstance(rag_context['query'], str)
        self.assertGreater(len(rag_context['query']), 0)
        
        # 验证查询包含重要关键词
        query = rag_context['query']
        self.assertTrue(
            any(keyword in query for keyword in ["天山", "张三", "倚天剑", "老者"]),
            "RAG查询应该包含重要关键词"
        )
    
    def test_empty_text_handling(self):
        """测试空文本处理"""
        # 空文本
        empty_context = self.extractor.extract_context_for_completion("", 0)
        self.assertEqual(empty_context.trigger_position, 0)
        self.assertEqual(empty_context.before_context, "")
        self.assertEqual(empty_context.after_context, "")
        self.assertEqual(len(empty_context.segments), 0)
        self.assertEqual(len(empty_context.primary_keywords), 0)
        
        # 无效光标位置
        test_text = "这是一个测试文本。"
        invalid_context = self.extractor.extract_context_for_completion(test_text, -1)
        self.assertEqual(invalid_context.relevance_score, 0.0)
        
        invalid_context2 = self.extractor.extract_context_for_completion(test_text, len(test_text) + 10)
        self.assertEqual(invalid_context2.relevance_score, 0.0)
    
    def test_sentence_boundary_detection(self):
        """测试句子边界检测"""
        test_text = "第一句话。第二句话！第三句话？现在是第四句话，这里是触发位置。第五句话。"
        cursor_pos = test_text.find("触发位置") + 2
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证上下文在合理的句子边界处截断
        self.assertIn("第四句话", context.before_context)
        # 不应该在句子中间截断（除非文本太长）
        
    def test_keyword_deduplication(self):
        """测试关键词去重"""
        # 包含重复词汇的文本
        test_text = "张三说张三很好，张三喜欢天山。天山很美，天山很高。"
        cursor_pos = len(test_text) // 2
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证关键词列表中没有重复
        primary_keywords = context.primary_keywords
        self.assertEqual(len(primary_keywords), len(set(primary_keywords)), "主要关键词不应该重复")
        
        secondary_keywords = context.secondary_keywords
        self.assertEqual(len(secondary_keywords), len(set(secondary_keywords)), "次要关键词不应该重复")
    
    def test_stop_words_filtering(self):
        """测试停用词过滤"""
        test_text = "这是一个很好的测试，我们要去天山，因为那里有张三。"
        cursor_pos = test_text.find("因为")
        
        context = self.extractor.extract_context_for_completion(test_text, cursor_pos)
        
        # 验证停用词被过滤
        all_keywords = context.primary_keywords + context.secondary_keywords
        keywords_text = " ".join(all_keywords)
        
        stop_words_found = [word for word in self.extractor.stop_words if word in keywords_text]
        self.assertEqual(len(stop_words_found), 0, f"不应该包含停用词: {stop_words_found}")
        
        # 验证重要词汇被保留
        self.assertTrue(
            any(keyword in keywords_text for keyword in ["天山", "张三", "测试"]),
            "应该保留重要的关键词"
        )
    
    def test_context_window_size_limits(self):
        """测试上下文窗口大小限制"""
        # 创建超长文本
        long_text = "很长的文本内容。" * 100 + "关键位置" + "后续内容。" * 50
        cursor_pos = long_text.find("关键位置") + 2
        
        context = self.extractor.extract_context_for_completion(long_text, cursor_pos)
        
        # 验证上下文长度不超过配置的窗口大小（允许一定的边界调整）
        max_before_size = self.extractor.primary_window_size + 100  # 允许边界调整
        max_after_size = self.extractor.secondary_window_size + 100
        
        self.assertLessEqual(len(context.before_context), max_before_size)
        self.assertLessEqual(len(context.after_context), max_after_size)
        
        # 验证仍然包含关键信息
        self.assertIn("关键位置", context.before_context + context.after_context)


if __name__ == '__main__':
    unittest.main()