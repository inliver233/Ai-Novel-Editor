"""
CodexIntegrator安全包装器单元测试
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.codex_integrator import CodexIntegrator


class MockCodexEntry:
    """模拟Codex条目"""
    def __init__(self, id, title, entry_type, description="", is_global=False, aliases=None):
        self.id = id
        self.title = title
        self.entry_type = Mock()
        self.entry_type.value = entry_type
        self.description = description
        self.is_global = is_global
        self.aliases = aliases or []
        self.track_references = True


class TestCodexIntegrator(unittest.TestCase):
    """CodexIntegrator测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_codex_manager = Mock()
        self.integrator = CodexIntegrator(self.mock_codex_manager)
    
    def test_init_with_valid_codex_manager(self):
        """测试使用有效Codex管理器初始化"""
        # 设置必要的方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_global_entries = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        self.assertTrue(integrator.is_available())
        self.assertEqual(integrator.codex_manager, self.mock_codex_manager)
    
    def test_init_with_none_codex_manager(self):
        """测试使用None初始化"""
        integrator = CodexIntegrator(None)
        
        self.assertFalse(integrator.is_available())
        self.assertIsNone(integrator.codex_manager)
    
    def test_init_with_incomplete_codex_manager(self):
        """测试使用不完整的Codex管理器初始化"""
        incomplete_manager = Mock()
        # 只有部分必要方法
        incomplete_manager.detect_references_in_text = Mock()
        # 缺少get_global_entries和get_entry
        # 明确删除这些方法以确保它们不存在
        if hasattr(incomplete_manager, 'get_global_entries'):
            delattr(incomplete_manager, 'get_global_entries')
        if hasattr(incomplete_manager, 'get_entry'):
            delattr(incomplete_manager, 'get_entry')
        
        integrator = CodexIntegrator(incomplete_manager)
        
        self.assertFalse(integrator.is_available())
    
    def test_detect_references_safely_success(self):
        """测试成功的引用检测"""
        # 设置模拟返回值
        expected_references = [
            ("entry1", "张三", 0, 2),
            ("entry2", "李四", 5, 7)
        ]
        self.mock_codex_manager.detect_references_in_text.return_value = expected_references
        
        # 设置必要方法
        self.mock_codex_manager.get_global_entries = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.detect_references_safely("张三和李四", "doc1")
        
        self.assertEqual(result, expected_references)
        self.mock_codex_manager.detect_references_in_text.assert_called_once_with("张三和李四", "doc1")
    
    def test_detect_references_safely_with_empty_document_id(self):
        """测试空document_id的引用检测"""
        expected_references = [("entry1", "张三", 0, 2)]
        self.mock_codex_manager.detect_references_in_text.return_value = expected_references
        
        # 设置必要方法
        self.mock_codex_manager.get_global_entries = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.detect_references_safely("张三", "")
        
        # 应该使用默认document_id
        self.mock_codex_manager.detect_references_in_text.assert_called_once_with("张三", "default_document")
        self.assertEqual(result, expected_references)
    
    def test_detect_references_safely_with_empty_text(self):
        """测试空文本的引用检测"""
        # 设置必要方法
        self.mock_codex_manager.get_global_entries = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.detect_references_safely("", "doc1")
        
        self.assertEqual(result, [])
        self.mock_codex_manager.detect_references_in_text.assert_not_called()
    
    def test_detect_references_safely_type_error(self):
        """测试参数类型错误的处理"""
        # 模拟TypeError（方法签名不匹配）
        self.mock_codex_manager.detect_references_in_text.side_effect = TypeError("参数不匹配")
        
        # 设置必要方法
        self.mock_codex_manager.get_global_entries = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.detect_references_safely("张三", "doc1")
        
        self.assertEqual(result, [])
    
    def test_detect_references_safely_general_exception(self):
        """测试一般异常的处理"""
        # 模拟一般异常
        self.mock_codex_manager.detect_references_in_text.side_effect = Exception("未知错误")
        
        # 设置必要方法
        self.mock_codex_manager.get_global_entries = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.detect_references_safely("张三", "doc1")
        
        self.assertEqual(result, [])
    
    def test_detect_references_safely_invalid_return_format(self):
        """测试无效返回格式的处理"""
        # 返回无效格式的数据
        self.mock_codex_manager.detect_references_in_text.return_value = [
            ("entry1", "张三", 0, 2),  # 有效格式
            ("invalid",),  # 无效格式
            "not_a_tuple",  # 无效格式
        ]
        
        # 设置必要方法
        self.mock_codex_manager.get_global_entries = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.detect_references_safely("张三", "doc1")
        
        # 应该只返回有效格式的引用
        self.assertEqual(result, [("entry1", "张三", 0, 2)])
    
    def test_detect_references_safely_unavailable_service(self):
        """测试服务不可用时的处理"""
        integrator = CodexIntegrator(None)
        
        result = integrator.detect_references_safely("张三", "doc1")
        
        self.assertEqual(result, [])
    
    def test_get_global_entries_safely_success(self):
        """测试成功获取全局条目"""
        # 创建模拟条目
        mock_entries = [
            MockCodexEntry("entry1", "张三", "CHARACTER", "主角", True, ["小张"]),
            MockCodexEntry("entry2", "北京", "LOCATION", "首都", True)
        ]
        
        self.mock_codex_manager.get_global_entries.return_value = mock_entries
        
        # 设置必要方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.get_global_entries_safely()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['title'], "张三")
        self.assertEqual(result[0]['type'], "CHARACTER")
        self.assertEqual(result[0]['aliases'], ["小张"])
        self.assertEqual(result[1]['title'], "北京")
        self.assertEqual(result[1]['type'], "LOCATION")
    
    def test_get_global_entries_safely_empty_result(self):
        """测试空结果的处理"""
        self.mock_codex_manager.get_global_entries.return_value = []
        
        # 设置必要方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.get_global_entries_safely()
        
        self.assertEqual(result, [])
    
    def test_get_global_entries_safely_exception(self):
        """测试异常处理"""
        self.mock_codex_manager.get_global_entries.side_effect = Exception("获取失败")
        
        # 设置必要方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.get_global_entries_safely()
        
        self.assertEqual(result, [])
    
    def test_get_global_entries_safely_unavailable_service(self):
        """测试服务不可用时的处理"""
        integrator = CodexIntegrator(None)
        
        result = integrator.get_global_entries_safely()
        
        self.assertEqual(result, [])
    
    def test_get_entry_safely_success(self):
        """测试成功获取单个条目"""
        mock_entry = MockCodexEntry("entry1", "张三", "CHARACTER", "主角", True, ["小张"])
        
        self.mock_codex_manager.get_entry.return_value = mock_entry
        
        # 设置必要方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_global_entries = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.get_entry_safely("entry1")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "张三")
        self.assertEqual(result['type'], "CHARACTER")
        self.assertEqual(result['aliases'], ["小张"])
    
    def test_get_entry_safely_not_found(self):
        """测试条目不存在的处理"""
        self.mock_codex_manager.get_entry.return_value = None
        
        # 设置必要方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_global_entries = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.get_entry_safely("nonexistent")
        
        self.assertIsNone(result)
    
    def test_get_entry_safely_empty_id(self):
        """测试空ID的处理"""
        # 设置必要方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_global_entries = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        result = integrator.get_entry_safely("")
        
        self.assertIsNone(result)
        self.mock_codex_manager.get_entry.assert_not_called()
    
    def test_validate_document_id(self):
        """测试document_id验证"""
        integrator = CodexIntegrator(None)
        
        # 测试正常ID
        self.assertEqual(integrator.validate_document_id("doc123"), "doc123")
        
        # 测试空ID
        self.assertEqual(integrator.validate_document_id(""), "default_document")
        self.assertEqual(integrator.validate_document_id(None), "default_document")
        
        # 测试包含特殊字符的ID
        self.assertEqual(integrator.validate_document_id("doc/123<>"), "doc_123__")
        
        # 测试只有空白字符的ID
        self.assertEqual(integrator.validate_document_id("   "), "default_document")
    
    def test_get_detection_statistics(self):
        """测试获取检测统计信息"""
        # 设置模拟数据
        mock_global_entries = [MockCodexEntry("1", "张三", "CHARACTER", is_global=True)]
        mock_all_entries = [
            MockCodexEntry("1", "张三", "CHARACTER", is_global=True),
            MockCodexEntry("2", "李四", "CHARACTER", is_global=False),
        ]
        
        self.mock_codex_manager.get_global_entries.return_value = mock_global_entries
        self.mock_codex_manager.get_all_entries.return_value = mock_all_entries
        
        # 设置必要方法
        self.mock_codex_manager.detect_references_in_text = Mock()
        self.mock_codex_manager.get_entry = Mock()
        
        integrator = CodexIntegrator(self.mock_codex_manager)
        
        stats = integrator.get_detection_statistics()
        
        self.assertTrue(stats['codex_available'])
        self.assertEqual(stats['global_entries'], 1)
        self.assertEqual(stats['total_entries'], 2)
        self.assertEqual(stats['trackable_entries'], 2)
    
    def test_get_detection_statistics_unavailable(self):
        """测试服务不可用时的统计信息"""
        integrator = CodexIntegrator(None)
        
        stats = integrator.get_detection_statistics()
        
        self.assertFalse(stats['codex_available'])
        self.assertEqual(stats['total_entries'], 0)
        self.assertEqual(stats['global_entries'], 0)
        self.assertEqual(stats['trackable_entries'], 0)
    
    def test_update_codex_manager(self):
        """测试更新Codex管理器"""
        integrator = CodexIntegrator(None)
        self.assertFalse(integrator.is_available())
        
        # 更新为有效的管理器
        new_manager = Mock()
        new_manager.detect_references_in_text = Mock()
        new_manager.get_global_entries = Mock()
        new_manager.get_entry = Mock()
        
        integrator.update_codex_manager(new_manager)
        
        self.assertTrue(integrator.is_available())
        self.assertEqual(integrator.codex_manager, new_manager)


if __name__ == '__main__':
    unittest.main()