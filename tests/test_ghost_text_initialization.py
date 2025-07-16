# -*- coding: utf-8 -*-
"""
Ghost Text系统初始化测试
验证Ghost Text系统的初始化过程和状态管理
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.ghost_text_system_validator import GhostTextSystemValidator, validate_ghost_text_system
from core.ghost_text_initialization_logger import (
    GhostTextInitializationLogger, 
    enhanced_ghost_text_initialization,
    get_ghost_init_logger
)


class TestGhostTextSystemValidator(unittest.TestCase):
    """测试Ghost Text系统验证器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_editor = Mock()
        self.validator = GhostTextSystemValidator(self.mock_editor)
    
    def test_validator_without_editor(self):
        """测试没有编辑器实例的验证器"""
        validator = GhostTextSystemValidator(None)
        results = validator.validate_initialization()
        
        self.assertFalse(results['editor_available'])
        self.assertIn("文本编辑器实例不可用", results['initialization_issues'])
    
    def test_validator_with_no_ghost_systems(self):
        """测试没有Ghost Text系统的编辑器"""
        # 模拟一个没有任何Ghost Text属性的编辑器
        mock_editor = Mock(spec=[])  # 空的spec，没有任何属性
        
        validator = GhostTextSystemValidator(mock_editor)
        results = validator.validate_initialization()
        
        self.assertTrue(results['editor_available'])
        self.assertIsNone(results['active_system'])
        
        # 检查所有系统都标记为不存在
        for attr_name in ['_ghost_completion', '_optimal_ghost_text', '_deep_ghost_text']:
            self.assertFalse(results['systems_found'][attr_name]['exists'])
    
    def test_validator_with_optimal_ghost_text(self):
        """测试有OptimalGhostText系统的编辑器"""
        # 创建模拟的OptimalGhostText实例
        mock_optimal = Mock()
        mock_optimal.show_completion = Mock()
        mock_optimal.has_active_ghost_text = Mock(return_value=False)
        mock_optimal.handle_key_press = Mock()
        
        # 设置编辑器属性
        self.mock_editor._ghost_completion = mock_optimal
        self.mock_editor._optimal_ghost_text = mock_optimal
        self.mock_editor._deep_ghost_text = None
        self.mock_editor._use_optimal_ghost_text = True
        
        results = self.validator.validate_initialization()
        
        self.assertTrue(results['editor_available'])
        self.assertIsNotNone(results['active_system'])
        self.assertEqual(results['active_system']['type'], 'Mock')
        
        # 检查方法可用性
        method_availability = results['method_availability']
        self.assertTrue(method_availability['show_completion']['exists'])
        self.assertTrue(method_availability['has_active_ghost_text']['exists'])
        self.assertTrue(method_availability['handle_key_press']['exists'])
    
    def test_validator_with_inconsistent_system(self):
        """测试系统不一致的情况"""
        mock_optimal = Mock()
        mock_deep = Mock()
        
        # 设置不一致的状态：_ghost_completion指向optimal但use_optimal为False
        self.mock_editor._ghost_completion = mock_optimal
        self.mock_editor._optimal_ghost_text = mock_optimal
        self.mock_editor._deep_ghost_text = mock_deep
        self.mock_editor._use_optimal_ghost_text = False  # 不一致！
        
        results = self.validator.validate_initialization()
        
        # 应该检测到一致性问题
        issues = results['initialization_issues']
        consistency_issue = any("_ghost_completion指向OptimalGhostText但_use_optimal_ghost_text为False" in issue 
                              for issue in issues)
        self.assertTrue(consistency_issue)
    
    def test_validator_with_missing_methods(self):
        """测试缺少必需方法的系统"""
        # 创建一个缺少某些方法的模拟对象
        mock_incomplete = Mock(spec=['show_completion'])  # 只有show_completion方法
        
        self.mock_editor._ghost_completion = mock_incomplete
        
        results = self.validator.validate_initialization()
        
        # 检查缺失的方法
        method_availability = results['method_availability']
        self.assertTrue(method_availability['show_completion']['exists'])
        self.assertFalse(method_availability['has_active_ghost_text']['exists'])
        self.assertFalse(method_availability['handle_key_press']['exists'])
        
        # 应该有关于缺失方法的问题报告
        issues = results['initialization_issues']
        missing_method_issues = [issue for issue in issues if "必需方法" in issue and "不存在" in issue]
        self.assertTrue(len(missing_method_issues) > 0)


class TestGhostTextInitializationLogger(unittest.TestCase):
    """测试Ghost Text初始化日志记录器"""
    
    def setUp(self):
        """设置测试环境"""
        self.logger = GhostTextInitializationLogger()
    
    def test_logger_initialization(self):
        """测试日志记录器初始化"""
        self.assertIsNotNone(self.logger.ghost_logger)
        self.assertEqual(len(self.logger.initialization_log), 0)
    
    def test_log_initialization_start(self):
        """测试记录初始化开始"""
        self.logger.log_initialization_start("TestEditor")
        
        self.assertEqual(len(self.logger.initialization_log), 1)
        log_entry = self.logger.initialization_log[0]
        self.assertEqual(log_entry['event_type'], 'start')
        self.assertIn("TestEditor", log_entry['message'])
    
    def test_log_initialization_success(self):
        """测试记录初始化成功"""
        mock_ghost = Mock()
        mock_ghost.show_completion = Mock()
        mock_ghost.handle_key_press = Mock()
        
        self.logger.log_initialization_success("OptimalGhostText", mock_ghost)
        
        self.assertEqual(len(self.logger.initialization_log), 1)
        log_entry = self.logger.initialization_log[0]
        self.assertEqual(log_entry['event_type'], 'initialization_success')
        self.assertEqual(log_entry['system_type'], 'OptimalGhostText')
        self.assertTrue(log_entry['has_show_completion'])
        self.assertTrue(log_entry['has_handle_key_press'])
    
    def test_log_initialization_failure(self):
        """测试记录初始化失败"""
        errors = ["模块导入失败", "集成函数返回None"]
        self.logger.log_initialization_failure(errors)
        
        self.assertEqual(len(self.logger.initialization_log), 1)
        log_entry = self.logger.initialization_log[0]
        self.assertEqual(log_entry['event_type'], 'initialization_failure')
        self.assertEqual(log_entry['errors'], errors)
    
    def test_get_initialization_summary(self):
        """测试获取初始化摘要"""
        # 添加一些日志条目
        self.logger.log_initialization_start("TestEditor")
        self.logger.log_initialization_success("OptimalGhostText", Mock())
        
        summary = self.logger.get_initialization_summary()
        
        self.assertEqual(summary['total_events'], 2)
        self.assertEqual(summary['success_events'], 1)
        self.assertEqual(summary['error_events'], 0)
        self.assertEqual(summary['final_status'], 'success')


class TestEnhancedGhostTextInitialization(unittest.TestCase):
    """测试增强的Ghost Text初始化函数"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_editor = Mock()
    
    @patch('core.ghost_text_initialization_logger.get_ghost_init_logger')
    def test_enhanced_initialization_no_modules(self, mock_get_logger):
        """测试没有可用模块的初始化"""
        mock_logger = Mock()
        mock_logger.initialization_log = []
        mock_get_logger.return_value = mock_logger
        
        # 模拟模块导入失败
        mock_logger.log_optimal_ghost_text_attempt.return_value = None
        mock_logger.log_deep_ghost_text_attempt.return_value = None
        
        result, use_optimal, log = enhanced_ghost_text_initialization(self.mock_editor)
        
        self.assertIsNone(result)
        self.assertFalse(use_optimal)
        self.assertEqual(log, [])
        
        # 验证日志记录器被正确调用
        mock_logger.log_initialization_start.assert_called_once()
        mock_logger.log_initialization_failure.assert_called_once()
    
    @patch('core.ghost_text_initialization_logger.get_ghost_init_logger')
    def test_enhanced_initialization_optimal_success(self, mock_get_logger):
        """测试OptimalGhostText成功初始化"""
        mock_logger = Mock()
        mock_logger.initialization_log = ['test_log']
        mock_get_logger.return_value = mock_logger
        
        # 模拟OptimalGhostText成功
        mock_integrate_func = Mock()
        mock_ghost_instance = Mock()
        mock_logger.log_optimal_ghost_text_attempt.return_value = mock_integrate_func
        mock_logger.log_optimal_integration_attempt.return_value = mock_ghost_instance
        
        result, use_optimal, log = enhanced_ghost_text_initialization(self.mock_editor)
        
        self.assertEqual(result, mock_ghost_instance)
        self.assertTrue(use_optimal)
        self.assertEqual(log, ['test_log'])
        
        # 验证日志记录器被正确调用
        mock_logger.log_initialization_start.assert_called_once()
        mock_logger.log_initialization_success.assert_called_once_with('OptimalGhostText', mock_ghost_instance)
    
    @patch('core.ghost_text_initialization_logger.get_ghost_init_logger')
    def test_enhanced_initialization_fallback_to_deep(self, mock_get_logger):
        """测试回退到DeepIntegratedGhostText"""
        mock_logger = Mock()
        mock_logger.initialization_log = ['test_log']
        mock_get_logger.return_value = mock_logger
        
        # 模拟OptimalGhostText失败，DeepIntegratedGhostText成功
        mock_logger.log_optimal_ghost_text_attempt.return_value = None
        
        mock_integrate_func = Mock()
        mock_ghost_instance = Mock()
        mock_logger.log_deep_ghost_text_attempt.return_value = mock_integrate_func
        mock_logger.log_deep_integration_attempt.return_value = mock_ghost_instance
        
        result, use_optimal, log = enhanced_ghost_text_initialization(self.mock_editor)
        
        self.assertEqual(result, mock_ghost_instance)
        self.assertFalse(use_optimal)
        self.assertEqual(log, ['test_log'])
        
        # 验证日志记录器被正确调用
        mock_logger.log_initialization_success.assert_called_once_with('DeepIntegratedGhostText', mock_ghost_instance)


class TestGhostTextSystemIntegration(unittest.TestCase):
    """Ghost Text系统集成测试"""
    
    def test_validate_ghost_text_system_function(self):
        """测试validate_ghost_text_system便捷函数"""
        mock_editor = Mock()
        mock_editor._ghost_completion = Mock()
        mock_editor._ghost_completion.show_completion = Mock()
        
        # 这个函数应该能正常运行而不抛出异常
        results = validate_ghost_text_system(mock_editor)
        
        self.assertIsInstance(results, dict)
        self.assertIn('editor_available', results)
        self.assertIn('systems_found', results)
        self.assertIn('active_system', results)
    
    def test_get_ghost_init_logger_singleton(self):
        """测试全局日志记录器单例"""
        logger1 = get_ghost_init_logger()
        logger2 = get_ghost_init_logger()
        
        # 应该返回同一个实例
        self.assertIs(logger1, logger2)
        self.assertIsInstance(logger1, GhostTextInitializationLogger)


if __name__ == '__main__':
    # 设置日志级别以减少测试输出
    import logging
    logging.getLogger().setLevel(logging.WARNING)
    
    # 运行测试
    unittest.main(verbosity=2)