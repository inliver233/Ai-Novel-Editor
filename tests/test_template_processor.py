"""
TemplateProcessor 单元测试
测试模板变量识别、替换和格式化功能
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.template_processor import TemplateProcessor, TemplateVariable, VariableType


class TestTemplateProcessor(unittest.TestCase):
    """TemplateProcessor测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.processor = TemplateProcessor()
    
    def test_extract_variables_simple(self):
        """测试简单变量提取"""
        template = "Hello {name}, welcome to {place}!"
        variables = self.processor.extract_variables(template)
        
        self.assertEqual(len(variables), 2)
        self.assertEqual(variables[0].name, "name")
        self.assertEqual(variables[0].var_type, VariableType.SIMPLE)
        self.assertEqual(variables[1].name, "place")
        self.assertEqual(variables[1].var_type, VariableType.SIMPLE)
    
    def test_extract_variables_conditional(self):
        """测试条件变量提取"""
        template = "Hello {name?Guest}, today is {date?unknown}!"
        variables = self.processor.extract_variables(template)
        
        self.assertEqual(len(variables), 2)
        self.assertEqual(variables[0].name, "name")
        self.assertEqual(variables[0].var_type, VariableType.CONDITIONAL)
        self.assertEqual(variables[0].default_value, "Guest")
        self.assertFalse(variables[0].is_required)
    
    def test_extract_variables_formatted(self):
        """测试格式化变量提取"""
        template = "Content: {content:max:100}, Status: {status:upper}"
        variables = self.processor.extract_variables(template)
        
        self.assertEqual(len(variables), 2)
        self.assertEqual(variables[0].name, "content")
        self.assertEqual(variables[0].var_type, VariableType.FORMATTED)
        self.assertEqual(variables[0].format_spec, "max:100")
        self.assertEqual(variables[1].format_spec, "upper")
    
    def test_extract_variables_function(self):
        """测试函数调用变量提取"""
        template = "Current time: {time()}, User count: {count(active=true)}"
        variables = self.processor.extract_variables(template)
        
        self.assertEqual(len(variables), 2)
        self.assertEqual(variables[0].var_type, VariableType.FUNCTION)
        self.assertEqual(variables[1].var_type, VariableType.FUNCTION)
    
    def test_process_template_simple_replacement(self):
        """测试简单模板替换"""
        template = "Hello {name}, you have {count} messages."
        context = {
            'name': 'Alice',
            'count': 5
        }
        
        result = self.processor.process_template(template, context)
        expected = "Hello Alice, you have 5 messages."
        self.assertEqual(result, expected)
    
    def test_process_template_with_defaults(self):
        """测试带默认值的模板处理"""
        template = "Hello {name?Guest}, welcome to {place?our site}!"
        context = {'name': 'Bob'}
        
        result = self.processor.process_template(template, context)
        expected = "Hello Bob, welcome to our site!"
        self.assertEqual(result, expected)
    
    def test_process_template_missing_variables(self):
        """测试缺少变量的模板处理"""
        template = "Hello {name}, you have {count} messages."
        context = {'name': 'Alice'}
        
        # 默认策略是保留未知变量
        result = self.processor.process_template(template, context)
        expected = "Hello Alice, you have {count} messages."
        self.assertEqual(result, expected)
    
    def test_unknown_variable_strategies(self):
        """测试未知变量处理策略"""
        template = "Hello {name}, you have {count} messages."
        context = {'name': 'Alice'}
        
        # 测试移除策略
        self.processor.set_unknown_variable_strategy("remove")
        result = self.processor.process_template(template, context)
        expected = "Hello Alice, you have  messages."
        self.assertEqual(result, expected)
        
        # 测试占位符策略
        self.processor.set_unknown_variable_strategy("placeholder")
        result = self.processor.process_template(template, context)
        expected = "Hello Alice, you have [count] messages."
        self.assertEqual(result, expected)
        
        # 恢复默认策略
        self.processor.set_unknown_variable_strategy("keep")
    
    def test_style_guidance_handler(self):
        """测试风格指导处理器"""
        template = "写作要求：{style_guidance}"
        
        # 测试单个指导
        context = {'style_guidance': ['使用现代都市风格']}
        result = self.processor.process_template(template, context)
        expected = "写作要求：使用现代都市风格"
        self.assertEqual(result, expected)
        
        # 测试多个指导
        context = {'style_guidance': ['使用现代都市风格', '注重对话描写']}
        result = self.processor.process_template(template, context)
        expected = "写作要求：- 使用现代都市风格\n- 注重对话描写"
        self.assertEqual(result, expected)
        
        # 测试空指导
        context = {'style_guidance': []}
        result = self.processor.process_template(template, context)
        expected = "写作要求：保持自然流畅的写作风格"
        self.assertEqual(result, expected)
    
    def test_rag_context_handler(self):
        """测试RAG上下文处理器"""
        template = "背景信息：{rag_context}"
        
        # 测试字符串RAG内容
        context = {'rag_context': '这是一个科幻小说的背景设定。'}
        result = self.processor.process_template(template, context)
        expected = "背景信息：**相关背景信息**：\n这是一个科幻小说的背景设定。"
        self.assertEqual(result, expected)
        
        # 测试空RAG内容
        context = {'rag_context': ''}
        result = self.processor.process_template(template, context)
        expected = "背景信息："
        self.assertEqual(result, expected)
        
        # 测试列表形式的RAG内容
        context = {'rag_context': [
            {'title': '角色设定', 'content': '主角是一名程序员'},
            {'title': '世界观', 'content': '故事发生在2050年的未来世界'}
        ]}
        result = self.processor.process_template(template, context)
        self.assertIn("**相关背景信息**：", result)
        self.assertIn("角色设定", result)
        self.assertIn("世界观", result)
    
    def test_current_text_handler_with_format(self):
        """测试当前文本处理器的格式化功能"""
        template = "当前文本：{current_text:max:50}"
        long_text = "这是一段很长的文本内容，用来测试文本截断功能是否正常工作。" * 3
        context = {'current_text': long_text}
        
        result = self.processor.process_template(template, context)
        self.assertIn("当前文本：", result)
        self.assertTrue(len(result.split("：")[1]) <= 53)  # 50 + "..."
        self.assertIn("...", result)
    
    def test_word_count_handler(self):
        """测试字数要求处理器"""
        template = "续写要求：{word_count}"
        
        # 测试数字
        context = {'word_count': 300}
        result = self.processor.process_template(template, context)
        expected = "续写要求：300字左右"
        self.assertEqual(result, expected)
        
        # 测试字符串
        context = {'word_count': '200-300字'}
        result = self.processor.process_template(template, context)
        expected = "续写要求：200-300字"
        self.assertEqual(result, expected)
    
    def test_completion_type_handler(self):
        """测试补全类型处理器"""
        template = "补全类型：{completion_type}"
        
        # 测试英文类型转中文
        test_cases = [
            ('character', '角色描写'),
            ('location', '场景描写'),
            ('dialogue', '对话续写'),
            ('action', '动作描写'),
            ('emotion', '情感描写'),
            ('text', '文本续写'),
            ('unknown_type', 'unknown_type')  # 未知类型保持原样
        ]
        
        for input_type, expected_output in test_cases:
            context = {'completion_type': input_type}
            result = self.processor.process_template(template, context)
            expected = f"补全类型：{expected_output}"
            self.assertEqual(result, expected)
    
    def test_detected_entities_handler(self):
        """测试检测实体处理器"""
        template = "检测到的实体：{detected_entities}"
        
        # 测试实体列表
        context = {'detected_entities': ['张三', '李四', '北京']}
        result = self.processor.process_template(template, context)
        expected = "检测到的实体：张三, 李四, 北京"
        self.assertEqual(result, expected)
        
        # 测试空实体
        context = {'detected_entities': []}
        result = self.processor.process_template(template, context)
        expected = "检测到的实体：暂无检测到的角色或地点"
        self.assertEqual(result, expected)
    
    def test_template_validation(self):
        """测试模板验证功能"""
        # 测试有效模板
        valid_template = "Hello {name}, you have {count} messages."
        result = self.processor.validate_template(valid_template)
        
        self.assertTrue(result['is_valid'])
        self.assertEqual(len(result['variables']), 2)
        self.assertIn('name', result['variables'])
        self.assertIn('count', result['variables'])
        
        # 测试包含未知变量的模板
        template_with_unknown = "Hello {name}, today is {unknown_var}."
        result = self.processor.validate_template(template_with_unknown)
        
        self.assertTrue(result['is_valid'])  # 语法有效
        self.assertIn('unknown_var', result['unknown_variables'])
    
    def test_cleanup_template(self):
        """测试模板清理功能"""
        messy_template = """
        
        Hello {name}
        
        
        Welcome to {place}
        
        
        """
        
        context = {'name': 'Alice', 'place': 'Wonderland'}
        result = self.processor.process_template(messy_template, context)
        
        # 检查是否移除了多余的空行
        lines = result.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # 应该只有两行有内容
        self.assertEqual(len(non_empty_lines), 2)
        self.assertIn('Hello Alice', result)
        self.assertIn('Welcome to Wonderland', result)
    
    def test_register_custom_handler(self):
        """测试注册自定义变量处理器"""
        def custom_handler(context, variable):
            return f"Custom: {context.get('custom_var', 'default')}"
        
        self.processor.register_variable_handler('custom_var', custom_handler)
        
        template = "Result: {custom_var}"
        context = {'custom_var': 'test_value'}
        result = self.processor.process_template(template, context)
        
        expected = "Result: Custom: test_value"
        self.assertEqual(result, expected)
    
    def test_format_value_with_specs(self):
        """测试值格式化功能"""
        template = "Name: {name:upper}, Content: {content:max:10}, Text: {text:clean}"
        context = {
            'name': 'alice',
            'content': 'This is a very long content that should be truncated',
            'text': '  Multiple   spaces   text  '
        }
        
        result = self.processor.process_template(template, context)
        
        self.assertIn('ALICE', result)  # 测试upper格式
        self.assertIn('This is a ...', result)  # 测试max格式
        self.assertIn('Multiple spaces text', result)  # 测试clean格式
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试空模板
        result = self.processor.process_template("", {})
        self.assertEqual(result, "")
        
        # 测试None值
        template = "Value: {value}"
        context = {'value': None}
        result = self.processor.process_template(template, context)
        self.assertEqual(result, "Value: None")
        
        # 测试嵌套大括号（应该不被处理）
        template = "Code: {{not_a_variable}}"
        result = self.processor.process_template(template, {})
        self.assertEqual(result, "Code: {{not_a_variable}}")
    
    def test_rag_content_cleaning(self):
        """测试RAG内容清理功能"""
        # 测试长内容截断
        long_content = "这是一段很长的RAG内容。" * 50
        cleaned = self.processor._clean_rag_content(long_content)
        self.assertTrue(len(cleaned) <= 503)  # 500 + "..."
        self.assertTrue(cleaned.endswith("..."))
        
        # 测试添加句号
        content_without_period = "这是没有句号的内容"
        cleaned = self.processor._clean_rag_content(content_without_period)
        self.assertTrue(cleaned.endswith("。"))
        
        # 测试空白字符清理
        messy_content = "  这是   有很多   空格的   内容  "
        cleaned = self.processor._clean_rag_content(messy_content)
        self.assertEqual(cleaned, "这是 有很多 空格的 内容。")


class TestTemplateProcessorIntegration(unittest.TestCase):
    """TemplateProcessor集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.processor = TemplateProcessor()
    
    def test_complete_prompt_processing(self):
        """测试完整的提示词处理流程"""
        template = """你是一个专业的小说写作助手。

**当前写作上下文**：
{current_text:max:200}

**写作要求**：
{style_guidance}

**续写指导**：
- 续写长度：{word_count}
- 补全类型：{completion_type}
- 场景类型：{scene_type}
- 情感基调：{emotional_tone}

{rag_context}

**检测到的角色/地点**：{detected_entities}

请基于以上信息进行续写。"""
        
        context = {
            'current_text': '这是一个关于未来世界的科幻小说开头。主角张三是一名程序员，生活在2050年的北京。' * 5,
            'style_guidance': ['使用科技感的描述风格', '注重未来科技元素'],
            'word_count': 300,
            'completion_type': 'character',
            'scene_type': '描写场景',
            'emotional_tone': '中性情感',
            'rag_context': '故事背景：2050年，人工智能已经高度发达，人类与AI共存。',
            'detected_entities': ['张三', '北京', '程序员']
        }
        
        result = self.processor.process_template(template, context)
        
        # 验证所有变量都被正确替换
        self.assertNotIn('{', result)  # 不应该有未替换的变量
        self.assertIn('张三', result)
        self.assertIn('北京', result)
        self.assertIn('300字左右', result)
        self.assertIn('角色描写', result)
        self.assertIn('科技感的描述风格', result)
        self.assertIn('相关背景信息', result)
        self.assertIn('2050年', result)
        
        # 验证模板结构完整
        self.assertIn('当前写作上下文', result)
        self.assertIn('写作要求', result)
        self.assertIn('续写指导', result)
        self.assertIn('检测到的角色/地点', result)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)