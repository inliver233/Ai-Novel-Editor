"""
RAGIntegrator安全包装器单元测试
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
import time

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.rag_integrator import RAGIntegrator


class TestRAGIntegrator(unittest.TestCase):
    """RAGIntegrator测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_rag_service = Mock()
        self.integrator = RAGIntegrator(self.mock_rag_service)
    
    def test_init_with_valid_rag_service(self):
        """测试使用有效RAG服务初始化"""
        # 设置必要的方法
        self.mock_rag_service.search_with_context = Mock()
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        self.assertTrue(integrator.is_available())
        self.assertEqual(integrator.rag_service, self.mock_rag_service)
    
    def test_init_with_none_rag_service(self):
        """测试使用None初始化"""
        integrator = RAGIntegrator(None)
        
        self.assertFalse(integrator.is_available())
        self.assertIsNone(integrator.rag_service)
    
    def test_init_with_incomplete_rag_service(self):
        """测试使用不完整的RAG服务初始化"""
        incomplete_service = Mock()
        # 缺少search_with_context方法
        # 明确删除这个方法以确保它不存在
        if hasattr(incomplete_service, 'search_with_context'):
            delattr(incomplete_service, 'search_with_context')
        
        integrator = RAGIntegrator(incomplete_service)
        
        self.assertFalse(integrator.is_available())
    
    def test_search_relevant_content_safely_success(self):
        """测试成功的RAG搜索"""
        expected_result = "这是搜索到的相关内容"
        self.mock_rag_service.search_with_context.return_value = expected_result
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.search_relevant_content_safely("测试查询", "balanced")
        
        self.assertEqual(result, expected_result)
        self.mock_rag_service.search_with_context.assert_called_once_with("测试查询", "balanced")
    
    def test_search_relevant_content_safely_empty_query(self):
        """测试空查询的处理"""
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.search_relevant_content_safely("", "balanced")
        
        self.assertEqual(result, "")
        self.mock_rag_service.search_with_context.assert_not_called()
    
    def test_search_relevant_content_safely_invalid_mode(self):
        """测试无效上下文模式的处理"""
        expected_result = "搜索结果"
        self.mock_rag_service.search_with_context.return_value = expected_result
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.search_relevant_content_safely("测试查询", "invalid_mode")
        
        # 应该使用默认的balanced模式
        self.mock_rag_service.search_with_context.assert_called_once_with("测试查询", "balanced")
        self.assertEqual(result, expected_result)
    
    def test_search_relevant_content_safely_exception(self):
        """测试异常处理"""
        self.mock_rag_service.search_with_context.side_effect = Exception("搜索失败")
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.search_relevant_content_safely("测试查询", "balanced")
        
        self.assertEqual(result, "")
    
    def test_search_relevant_content_safely_non_string_result(self):
        """测试非字符串返回结果的处理"""
        self.mock_rag_service.search_with_context.return_value = {"result": "data"}
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.search_relevant_content_safely("测试查询", "balanced")
        
        self.assertEqual(result, "")
    
    def test_search_relevant_content_safely_unavailable_service(self):
        """测试服务不可用时的处理"""
        integrator = RAGIntegrator(None)
        
        result = integrator.search_relevant_content_safely("测试查询", "balanced")
        
        self.assertEqual(result, "")
    
    def test_try_legacy_search_methods(self):
        """测试向后兼容的搜索方法"""
        # 创建一个新的服务对象，包含search_with_context但会失败，然后使用旧方法
        legacy_service = Mock()
        legacy_service.search_with_context = Mock(side_effect=AttributeError("方法不存在"))
        legacy_service.search_relevant_content = Mock(return_value="旧方法结果")
        
        integrator = RAGIntegrator(legacy_service)
        
        result = integrator.search_relevant_content_safely("测试查询", "balanced")
        
        self.assertEqual(result, "旧方法结果")
        legacy_service.search_relevant_content.assert_called()
    
    def test_try_legacy_search_methods_with_different_signatures(self):
        """测试不同签名的旧方法"""
        # 创建一个新的服务对象，包含search_with_context但会失败，然后使用旧方法
        legacy_service = Mock()
        legacy_service.search_with_context = Mock(side_effect=AttributeError("方法不存在"))
        
        # 创建一个只接受query参数的方法
        def mock_search(query):
            return f"搜索结果: {query}"
        
        legacy_service.search = mock_search
        
        integrator = RAGIntegrator(legacy_service)
        
        result = integrator.search_relevant_content_safely("测试查询", "balanced")
        
        self.assertEqual(result, "搜索结果: 测试查询")
    
    def test_validate_rag_service(self):
        """测试RAG服务验证"""
        # 设置完整的服务
        self.mock_rag_service.search_with_context = Mock(return_value="测试结果")
        self.mock_rag_service.create_embedding = Mock()
        self.mock_rag_service.chunk_text = Mock()
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        validation_result = integrator.validate_rag_service()
        
        self.assertTrue(validation_result['service_available'])
        self.assertIn('search_with_context', validation_result['methods_available'])
        self.assertIn('create_embedding', validation_result['methods_available'])
        self.assertTrue(validation_result['test_search_success'])
    
    def test_validate_rag_service_none(self):
        """测试验证None服务"""
        integrator = RAGIntegrator(None)
        
        validation_result = integrator.validate_rag_service()
        
        self.assertFalse(validation_result['service_available'])
        self.assertIn("RAG服务未提供", validation_result['error_messages'])
    
    def test_validate_rag_service_missing_methods(self):
        """测试验证缺少方法的服务"""
        incomplete_service = Mock()
        # 只有部分方法
        incomplete_service.search_with_context = Mock(return_value="测试结果")
        # 明确删除其他方法
        if hasattr(incomplete_service, 'create_embedding'):
            delattr(incomplete_service, 'create_embedding')
        if hasattr(incomplete_service, 'chunk_text'):
            delattr(incomplete_service, 'chunk_text')
        
        integrator = RAGIntegrator(incomplete_service)
        
        validation_result = integrator.validate_rag_service()
        
        self.assertTrue(validation_result['service_available'])
        self.assertIn('search_with_context', validation_result['methods_available'])
        self.assertIn('create_embedding', validation_result['methods_missing'])
    
    def test_search_with_timeout_success(self):
        """测试带超时的成功搜索"""
        expected_result = "搜索结果"
        self.mock_rag_service.search_with_context.return_value = expected_result
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.search_with_timeout("测试查询", "balanced", 5.0)
        
        self.assertEqual(result, expected_result)
    
    def test_search_with_timeout_unavailable_service(self):
        """测试服务不可用时的超时搜索"""
        integrator = RAGIntegrator(None)
        
        result = integrator.search_with_timeout("测试查询", "balanced", 5.0)
        
        self.assertEqual(result, "")
    
    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_search_with_timeout_timeout_error(self, mock_executor):
        """测试超时错误处理"""
        # 模拟超时
        mock_future = Mock()
        mock_future.result.side_effect = TimeoutError()
        mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.search_with_timeout("测试查询", "balanced", 1.0)
        
        self.assertEqual(result, "")
    
    def test_get_service_statistics(self):
        """测试获取服务统计信息"""
        integrator = RAGIntegrator(self.mock_rag_service)
        
        stats = integrator.get_service_statistics()
        
        self.assertTrue(stats['rag_available'])
        self.assertIsNotNone(stats['service_type'])
        self.assertIsInstance(stats['last_check_time'], float)
        self.assertIsInstance(stats['check_interval'], int)
    
    def test_get_service_statistics_unavailable(self):
        """测试服务不可用时的统计信息"""
        integrator = RAGIntegrator(None)
        
        stats = integrator.get_service_statistics()
        
        self.assertFalse(stats['rag_available'])
        self.assertIsNone(stats['service_type'])
    
    def test_get_service_statistics_with_cache(self):
        """测试包含缓存统计的服务统计"""
        # 模拟带缓存的服务
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {'cache_size': 100, 'hit_rate': 0.8}
        self.mock_rag_service._cache = mock_cache
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        stats = integrator.get_service_statistics()
        
        self.assertIn('cache_stats', stats)
        self.assertEqual(stats['cache_stats']['cache_size'], 100)
    
    def test_clear_cache_safely_success(self):
        """测试成功清理缓存"""
        self.mock_rag_service.clear_cache = Mock()
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.clear_cache_safely()
        
        self.assertTrue(result)
        self.mock_rag_service.clear_cache.assert_called_once()
    
    def test_clear_cache_safely_via_cache_object(self):
        """测试通过缓存对象清理缓存"""
        # 没有clear_cache方法，但有_cache对象
        delattr(self.mock_rag_service, 'clear_cache')
        mock_cache = Mock()
        self.mock_rag_service._cache = mock_cache
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.clear_cache_safely()
        
        self.assertTrue(result)
        mock_cache.clear.assert_called_once()
    
    def test_clear_cache_safely_no_cache_method(self):
        """测试没有缓存清理方法时的处理"""
        # 移除缓存相关方法和属性
        if hasattr(self.mock_rag_service, 'clear_cache'):
            delattr(self.mock_rag_service, 'clear_cache')
        if hasattr(self.mock_rag_service, '_cache'):
            delattr(self.mock_rag_service, '_cache')
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.clear_cache_safely()
        
        self.assertFalse(result)
    
    def test_clear_cache_safely_exception(self):
        """测试清理缓存时的异常处理"""
        self.mock_rag_service.clear_cache.side_effect = Exception("清理失败")
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.clear_cache_safely()
        
        self.assertFalse(result)
    
    def test_clear_cache_safely_unavailable_service(self):
        """测试服务不可用时的缓存清理"""
        integrator = RAGIntegrator(None)
        
        result = integrator.clear_cache_safely()
        
        self.assertFalse(result)
    
    def test_update_rag_service(self):
        """测试更新RAG服务"""
        integrator = RAGIntegrator(None)
        self.assertFalse(integrator.is_available())
        
        # 更新为有效的服务
        new_service = Mock()
        new_service.search_with_context = Mock()
        
        integrator.update_rag_service(new_service)
        
        # 检查服务是否正确更新
        self.assertEqual(integrator.rag_service, new_service)
        # 检查可用性（这会更新_last_check_time，所以我们不检查时间重置）
        self.assertTrue(integrator.is_available())
    
    def test_test_connection_success(self):
        """测试成功的连接测试"""
        self.mock_rag_service.search_with_context.return_value = "连接测试结果"
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.test_connection()
        
        self.assertTrue(result['connection_ok'])
        self.assertEqual(result['test_query'], "测试连接")
        self.assertGreaterEqual(result['response_time'], 0)  # 改为>=0，因为可能非常快
        self.assertGreater(result['result_length'], 0)
        self.assertIsNone(result['error_message'])
    
    def test_test_connection_failure(self):
        """测试连接测试失败"""
        self.mock_rag_service.search_with_context.side_effect = Exception("连接失败")
        
        integrator = RAGIntegrator(self.mock_rag_service)
        
        result = integrator.test_connection()
        
        # 由于search_relevant_content_safely捕获了异常并返回空字符串，
        # connection_ok会是False（因为结果长度为0），但error_message会是None
        self.assertFalse(result['connection_ok'])
        self.assertEqual(result['result_length'], 0)  # 结果长度应该为0
        self.assertGreaterEqual(result['response_time'], 0)
    
    def test_test_connection_unavailable_service(self):
        """测试服务不可用时的连接测试"""
        integrator = RAGIntegrator(None)
        
        result = integrator.test_connection()
        
        self.assertFalse(result['connection_ok'])
        self.assertEqual(result['error_message'], "RAG服务不可用")
        self.assertEqual(result['response_time'], 0.0)
    
    def test_is_available_with_caching(self):
        """测试可用性检查的缓存机制"""
        integrator = RAGIntegrator(self.mock_rag_service)
        
        # 第一次检查
        result1 = integrator.is_available()
        first_check_time = integrator._last_check_time
        
        # 立即第二次检查（应该使用缓存）
        result2 = integrator.is_available()
        second_check_time = integrator._last_check_time
        
        self.assertEqual(result1, result2)
        self.assertEqual(first_check_time, second_check_time)
    
    def test_is_available_cache_expiry(self):
        """测试可用性检查缓存过期"""
        integrator = RAGIntegrator(self.mock_rag_service)
        integrator._check_interval = 0.1  # 设置很短的缓存间隔
        
        # 第一次检查
        result1 = integrator.is_available()
        
        # 等待缓存过期
        time.sleep(0.2)
        
        # 第二次检查（应该重新检查）
        result2 = integrator.is_available()
        
        self.assertEqual(result1, result2)


if __name__ == '__main__':
    unittest.main()