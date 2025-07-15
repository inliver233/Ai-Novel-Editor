"""
RAG集成器 - 安全包装器
提供对RAG系统的安全访问，包含完整的错误处理和向后兼容性支持
"""

import logging
from typing import Dict, Any, Optional, List
import time

logger = logging.getLogger(__name__)


class RAGIntegrator:
    """
    RAG集成器 - 安全包装器
    
    提供对RAG系统的安全访问，解决接口不一致问题：
    1. 确保使用正确的方法名search_with_context
    2. 提供向后兼容性支持（支持旧方法名）
    3. 实现RAG服务可用性验证
    4. 提供完整的错误处理和降级机制
    """
    
    def __init__(self, rag_service=None):
        """
        初始化RAG集成器
        
        Args:
            rag_service: RAG服务实例，可以为None
        """
        self.rag_service = rag_service
        self._is_available = self._check_rag_availability()
        self._last_check_time = 0
        self._check_interval = 60  # 60秒检查一次可用性
        
        logger.info(f"RAGIntegrator初始化完成 - 可用性: {self._is_available}")
    
    def _check_rag_availability(self) -> bool:
        """检查RAG系统的可用性"""
        if not self.rag_service:
            logger.debug("RAG服务未提供")
            return False
        
        # 检查必要的方法是否存在
        required_methods = ['search_with_context']
        for method_name in required_methods:
            if not hasattr(self.rag_service, method_name):
                logger.warning(f"RAG服务缺少必要方法: {method_name}")
                return False
        
        return True
    
    def is_available(self) -> bool:
        """
        检查RAG系统是否可用（带缓存）
        
        Returns:
            bool: RAG系统是否可用
        """
        current_time = time.time()
        
        # 如果最近检查过，使用缓存结果
        if current_time - self._last_check_time < self._check_interval:
            return self._is_available
        
        # 重新检查可用性
        self._is_available = self._check_rag_availability()
        self._last_check_time = current_time
        
        return self._is_available
    
    def search_relevant_content_safely(self, query: str, context_mode: str = 'balanced') -> str:
        """
        安全的RAG内容搜索，修复方法名称问题
        
        Args:
            query: 搜索查询
            context_mode: 上下文模式 ('fast', 'balanced', 'full')
            
        Returns:
            str: 搜索到的相关内容，如果失败则返回空字符串
        """
        if not self.is_available():
            logger.debug("RAG系统不可用，返回空内容")
            return ""
        
        if not query or not query.strip():
            logger.debug("查询为空，返回空内容")
            return ""
        
        # 验证context_mode参数
        valid_modes = ['fast', 'balanced', 'full']
        if context_mode not in valid_modes:
            logger.warning(f"无效的上下文模式: {context_mode}，使用默认值'balanced'")
            context_mode = 'balanced'
        
        try:
            # 修复：使用正确的方法名search_with_context
            if hasattr(self.rag_service, 'search_with_context'):
                result = self.rag_service.search_with_context(query, context_mode)
                
                if isinstance(result, str):
                    logger.debug(f"RAG搜索成功: 查询='{query[:50]}...', 结果长度={len(result)}")
                    return result
                else:
                    logger.warning(f"RAG搜索返回了意外的数据类型: {type(result)}")
                    # 如果主方法返回了意外类型，尝试向后兼容方法
                    return self._try_legacy_search_methods(query, context_mode)
            else:
                # 尝试向后兼容的方法名
                return self._try_legacy_search_methods(query, context_mode)
                
        except Exception as e:
            logger.error(f"RAG搜索失败: {e}")
            # 如果主方法失败，尝试向后兼容方法
            return self._try_legacy_search_methods(query, context_mode)
    
    def _try_legacy_search_methods(self, query: str, context_mode: str) -> str:
        """
        尝试向后兼容的搜索方法
        
        Args:
            query: 搜索查询
            context_mode: 上下文模式
            
        Returns:
            str: 搜索结果或空字符串
        """
        # 尝试可能存在的旧方法名
        legacy_methods = [
            'search_relevant_content',
            'search_content',
            'search',
            'query'
        ]
        
        for method_name in legacy_methods:
            if hasattr(self.rag_service, method_name):
                try:
                    method = getattr(self.rag_service, method_name)
                    
                    # 尝试不同的参数组合
                    try:
                        # 尝试带context_mode参数
                        result = method(query, context_mode)
                    except TypeError:
                        try:
                            # 尝试只传query参数
                            result = method(query)
                        except TypeError:
                            # 尝试带top_k参数（旧接口）
                            result = method(query, top_k=3)
                    
                    if isinstance(result, str) and result.strip():
                        logger.info(f"使用向后兼容方法成功: {method_name}")
                        return result
                    
                except Exception as e:
                    logger.debug(f"向后兼容方法 {method_name} 失败: {e}")
                    continue
        
        logger.warning("所有RAG搜索方法都失败了")
        return ""
    
    def validate_rag_service(self) -> Dict[str, Any]:
        """
        验证RAG服务的可用性和功能
        
        Returns:
            Dict[str, Any]: 验证结果
        """
        validation_result = {
            'service_available': False,
            'methods_available': [],
            'methods_missing': [],
            'test_search_success': False,
            'error_messages': []
        }
        
        if not self.rag_service:
            validation_result['error_messages'].append("RAG服务未提供")
            return validation_result
        
        validation_result['service_available'] = True
        
        # 检查方法可用性
        expected_methods = [
            'search_with_context',
            'search_relevant_content',  # 向后兼容
            'create_embedding',
            'chunk_text'
        ]
        
        for method_name in expected_methods:
            if hasattr(self.rag_service, method_name):
                validation_result['methods_available'].append(method_name)
            else:
                validation_result['methods_missing'].append(method_name)
        
        # 测试搜索功能
        try:
            test_result = self.search_relevant_content_safely("测试查询", "fast")
            validation_result['test_search_success'] = True
            validation_result['test_result_length'] = len(test_result)
        except Exception as e:
            validation_result['error_messages'].append(f"测试搜索失败: {e}")
        
        return validation_result
    
    def search_with_timeout(self, query: str, context_mode: str = 'balanced', 
                           timeout_seconds: float = 10.0) -> str:
        """
        带超时的RAG搜索
        
        Args:
            query: 搜索查询
            context_mode: 上下文模式
            timeout_seconds: 超时时间（秒）
            
        Returns:
            str: 搜索结果或空字符串
        """
        import concurrent.futures
        import threading
        
        if not self.is_available():
            return ""
        
        try:
            # 使用线程池执行搜索，带超时控制
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.search_relevant_content_safely, query, context_mode)
                
                try:
                    result = future.result(timeout=timeout_seconds)
                    return result
                except concurrent.futures.TimeoutError:
                    logger.warning(f"RAG搜索超时({timeout_seconds}s): {query[:50]}...")
                    return ""
                    
        except Exception as e:
            logger.error(f"带超时的RAG搜索失败: {e}")
            return ""
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """
        获取RAG服务统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {
            'rag_available': self.is_available(),
            'service_type': type(self.rag_service).__name__ if self.rag_service else None,
            'last_check_time': self._last_check_time,
            'check_interval': self._check_interval
        }
        
        if self.is_available():
            try:
                # 尝试获取服务特定的统计信息
                if hasattr(self.rag_service, 'get_stats'):
                    service_stats = self.rag_service.get_stats()
                    if isinstance(service_stats, dict):
                        stats.update(service_stats)
                
                # 检查缓存状态
                if hasattr(self.rag_service, '_cache') and self.rag_service._cache:
                    cache_stats = self.rag_service._cache.get_stats()
                    stats['cache_stats'] = cache_stats
                    
            except Exception as e:
                logger.debug(f"获取RAG服务统计信息失败: {e}")
                stats['stats_error'] = str(e)
        
        return stats
    
    def clear_cache_safely(self) -> bool:
        """
        安全清理RAG缓存
        
        Returns:
            bool: 是否成功清理
        """
        if not self.is_available():
            return False
        
        try:
            if hasattr(self.rag_service, 'clear_cache'):
                self.rag_service.clear_cache()
                logger.info("RAG缓存已清理")
                return True
            elif hasattr(self.rag_service, '_cache') and self.rag_service._cache:
                if hasattr(self.rag_service._cache, 'clear'):
                    self.rag_service._cache.clear()
                    logger.info("RAG缓存已清理（通过_cache.clear）")
                    return True
                    
        except Exception as e:
            logger.error(f"清理RAG缓存失败: {e}")
            return False
        
        return False
    
    def update_rag_service(self, rag_service):
        """
        更新RAG服务引用
        
        Args:
            rag_service: 新的RAG服务实例
        """
        self.rag_service = rag_service
        self._is_available = self._check_rag_availability()
        self._last_check_time = 0  # 重置检查时间
        logger.info(f"RAG服务已更新 - 可用性: {self._is_available}")
    
    def test_connection(self) -> Dict[str, Any]:
        """
        测试RAG服务连接
        
        Returns:
            Dict[str, Any]: 测试结果
        """
        test_result = {
            'connection_ok': False,
            'response_time': 0.0,
            'test_query': "测试连接",
            'result_length': 0,
            'error_message': None
        }
        
        if not self.is_available():
            test_result['error_message'] = "RAG服务不可用"
            return test_result
        
        start_time = time.time()
        
        try:
            result = self.search_relevant_content_safely("测试连接", "fast")
            test_result['response_time'] = time.time() - start_time
            test_result['result_length'] = len(result)
            # 只有当结果不为空时才认为连接成功
            test_result['connection_ok'] = len(result) > 0
            
        except Exception as e:
            test_result['response_time'] = time.time() - start_time
            test_result['error_message'] = str(e)
        
        return test_result