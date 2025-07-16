# -*- coding: utf-8 -*-
"""
Ghost Text Esc键处理测试
验证Esc键处理逻辑的正确性和状态管理
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.ghost_text_esc_key_handler import EscKeyHandlerValidator, validate_esc_key_handling


class TestEscKeyHandlerValidator(unittest.TestCase):
    """测试Esc键处理验证器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_editor = Mock()
        self.validator = EscKeyHandlerValidator(self.mock_editor)
    
    def test_validator_without_editor(self):
        """测试没有编辑器实例的验证器"""
        validator = EscKeyHandlerValidator(None)
        results = validator.validate_esc_key_handling()
        
        self.assertFalse(results['editor_available'])
        self.assertIn("文本编辑器实例不可用", results['issues_found'])
    
    def test_validator_without_ghost_system(self):
        """测试没有Ghost Text系统的编辑器"""
        # 模拟没有_ghost_completion属性的编辑器
        mock_editor = Mock(spec=[])
        
        validator = EscKeyHandlerValidator(mock_editor)
        results = validator.validate_esc_key_handling()
        
        self.assertTrue(results['editor_available'])
        self.assertFalse(results['ghost_system_available'])
        self.assertIn("_ghost_completion为None", str(results['issues_found']))
    
    def test_validator_with_incomplete_ghost_system(self):
        """测试不完整的Ghost Text系统"""
        # 创建一个缺少某些方法的模拟Ghost Text系统
        mock_ghost = Mock(spec=['show_completion'])  # 只有show_completion方法
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        self.assertTrue(results['ghost_system_available'])
        self.assertIn("缺少必需方法", str(results['issues_found']))
    
    def test_validator_with_complete_ghost_system(self):
        """测试完整的Ghost Text系统"""
        # 创建一个完整的模拟Ghost Text系统
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(return_value=True)
        mock_ghost.reject_ghost_text = Mock(return_value=True)
        mock_ghost.has_active_ghost_text = Mock(return_value=True)
        
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        self.assertTrue(results['ghost_system_available'])
        self.assertTrue(results['handle_key_press_works'])
        self.assertTrue(results['reject_ghost_text_works'])
    
    def test_handle_key_press_returns_false(self):
        """测试handle_key_press返回False的情况"""
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(return_value=False)  # 返回False
        mock_ghost.reject_ghost_text = Mock(return_value=True)
        mock_ghost.has_active_ghost_text = Mock(return_value=True)
        
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        self.assertTrue(results['handle_key_press_works'])  # 方法工作，但返回False
        self.assertIn("handle_key_press对Esc键返回False", str(results['issues_found']))
    
    def test_reject_ghost_text_state_not_cleared(self):
        """测试reject_ghost_text状态未清理的情况"""
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(return_value=True)
        mock_ghost.reject_ghost_text = Mock(return_value=True)
        
        # 模拟状态未清理：调用前后都返回True
        mock_ghost.has_active_ghost_text = Mock(side_effect=[True, True])  # 调用前True，调用后仍然True
        
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        self.assertTrue(results['reject_ghost_text_works'])
        self.assertIn("reject_ghost_text执行后Ghost Text状态未清理", str(results['issues_found']))
    
    def test_state_consistency_check(self):
        """测试状态一致性检查"""
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(return_value=True)
        mock_ghost.reject_ghost_text = Mock(return_value=True)
        
        # 模拟不一致的状态方法
        mock_ghost.has_active_ghost_text = Mock(return_value=True)
        mock_ghost.is_showing = Mock(return_value=False)  # 不一致！
        
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        self.assertFalse(results['state_consistency'])
        self.assertIn("不同状态检查方法返回不一致的结果", str(results['issues_found']))
    
    def test_handle_key_press_exception(self):
        """测试handle_key_press抛出异常的情况"""
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(side_effect=Exception("测试异常"))
        mock_ghost.reject_ghost_text = Mock(return_value=True)
        mock_ghost.has_active_ghost_text = Mock(return_value=True)
        
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        self.assertFalse(results['handle_key_press_works'])
        self.assertIn("handle_key_press执行异常", str(results['issues_found']))
    
    def test_reject_ghost_text_exception(self):
        """测试reject_ghost_text抛出异常的情况"""
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(return_value=True)
        mock_ghost.reject_ghost_text = Mock(side_effect=Exception("测试异常"))
        mock_ghost.has_active_ghost_text = Mock(return_value=True)
        
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        self.assertFalse(results['reject_ghost_text_works'])
        self.assertIn("reject_ghost_text执行异常", str(results['issues_found']))
    
    def test_recommendations_generation(self):
        """测试修复建议生成"""
        # 模拟一个有多个问题的系统
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(return_value=False)  # 返回False
        mock_ghost.reject_ghost_text = Mock(return_value=True)
        mock_ghost.has_active_ghost_text = Mock(side_effect=[True, True])  # 状态未清理
        
        self.mock_editor._ghost_completion = mock_ghost
        
        results = self.validator.validate_esc_key_handling()
        
        recommendations = results['recommendations']
        self.assertGreater(len(recommendations), 0)
        
        # 检查是否包含相关建议
        rec_text = ' '.join(recommendations)
        self.assertIn("handle_key_press", rec_text)
        self.assertIn("reject_ghost_text", rec_text)
    
    def test_mock_esc_event_creation(self):
        """测试模拟Esc事件创建"""
        esc_event = self.validator._create_mock_esc_event()
        
        self.assertEqual(esc_event.key(), Qt.Key.Key_Escape)
        self.assertEqual(esc_event.modifiers(), Qt.KeyboardModifier.NoModifier)
        self.assertEqual(esc_event.text(), "")
    
    def test_setup_mock_ghost_text(self):
        """测试设置模拟Ghost Text状态"""
        mock_ghost = Mock()
        
        # 添加各种可能的属性
        mock_ghost._is_active = False
        mock_ghost._ghost_text = ""
        mock_ghost._ghost_blocks = set()
        mock_ghost._current_ghost_text = ""
        
        self.validator._setup_mock_ghost_text(mock_ghost)
        
        # 验证状态被设置
        self.assertTrue(mock_ghost._is_active)
        self.assertEqual(mock_ghost._ghost_text, "test ghost text")
        self.assertEqual(mock_ghost._ghost_blocks, {1})
        self.assertEqual(mock_ghost._current_ghost_text, "test ghost text")
    
    def test_check_ghost_active_state(self):
        """测试检查Ghost Text活跃状态"""
        mock_ghost = Mock()
        
        # 测试has_active_ghost_text方法
        mock_ghost.has_active_ghost_text = Mock(return_value=True)
        result = self.validator._check_ghost_active_state(mock_ghost)
        self.assertTrue(result)
        
        # 测试is_showing方法（当has_active_ghost_text不存在时）
        mock_ghost2 = Mock(spec=['is_showing'])
        mock_ghost2.is_showing = Mock(return_value=False)
        result = self.validator._check_ghost_active_state(mock_ghost2)
        self.assertFalse(result)
        
        # 测试_is_active属性（当方法都不存在时）
        mock_ghost3 = Mock()
        mock_ghost3._is_active = True
        del mock_ghost3.has_active_ghost_text  # 确保方法不存在
        del mock_ghost3.is_showing
        result = self.validator._check_ghost_active_state(mock_ghost3)
        self.assertTrue(result)
    
    def test_print_validation_report(self):
        """测试打印验证报告"""
        # 设置一些验证结果
        self.validator.validation_results = {
            'timestamp': '2024-01-01 12:00:00',
            'editor_available': True,
            'ghost_system_available': True,
            'handle_key_press_works': False,
            'reject_ghost_text_works': True,
            'state_consistency': False,
            'issues_found': ['测试问题1', '测试问题2'],
            'recommendations': ['测试建议1', '测试建议2']
        }
        
        # 这个方法主要是打印，我们只验证它不会抛出异常
        try:
            self.validator.print_validation_report()
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success)


class TestValidateEscKeyHandlingFunction(unittest.TestCase):
    """测试便捷函数"""
    
    def test_validate_esc_key_handling_function(self):
        """测试validate_esc_key_handling便捷函数"""
        mock_editor = Mock()
        mock_ghost = Mock()
        mock_ghost.handle_key_press = Mock(return_value=True)
        mock_ghost.reject_ghost_text = Mock(return_value=True)
        mock_ghost.has_active_ghost_text = Mock(return_value=False)
        
        mock_editor._ghost_completion = mock_ghost
        
        # 这个函数应该能正常运行而不抛出异常
        results = validate_esc_key_handling(mock_editor)
        
        self.assertIsInstance(results, dict)
        self.assertIn('editor_available', results)
        self.assertIn('ghost_system_available', results)
        self.assertIn('issues_found', results)
        self.assertIn('recommendations', results)


class TestRealWorldScenarios(unittest.TestCase):
    """测试真实世界场景"""
    
    def test_optimal_ghost_text_scenario(self):
        """测试OptimalGhostText场景"""
        mock_editor = Mock()
        
        # 模拟OptimalGhostText的行为
        mock_optimal = Mock()
        mock_optimal.handle_key_press = Mock(return_value=True)
        mock_optimal.reject_ghost_text = Mock(return_value=True)
        mock_optimal.has_active_ghost_text = Mock(side_effect=[True, False])  # 调用前True，调用后False
        mock_optimal._is_active = True
        mock_optimal._ghost_text = "test"
        
        mock_editor._ghost_completion = mock_optimal
        
        validator = EscKeyHandlerValidator(mock_editor)
        results = validator.validate_esc_key_handling()
        
        self.assertTrue(results['ghost_system_available'])
        self.assertTrue(results['handle_key_press_works'])
        self.assertTrue(results['reject_ghost_text_works'])
        self.assertEqual(len(results['issues_found']), 0)
    
    def test_deep_integrated_ghost_text_scenario(self):
        """测试DeepIntegratedGhostText场景"""
        mock_editor = Mock()
        
        # 模拟DeepIntegratedGhostText的行为
        mock_deep = Mock()
        mock_deep.handle_key_press = Mock(return_value=True)
        mock_deep.reject_ghost_text = Mock(return_value=True)
        mock_deep.has_active_ghost_text = Mock(side_effect=[True, False])  # 调用前True，调用后False
        mock_deep._ghost_blocks = {1}
        mock_deep._current_ghost_text = "test"
        
        mock_editor._ghost_completion = mock_deep
        
        validator = EscKeyHandlerValidator(mock_editor)
        results = validator.validate_esc_key_handling()
        
        self.assertTrue(results['ghost_system_available'])
        self.assertTrue(results['handle_key_press_works'])
        self.assertTrue(results['reject_ghost_text_works'])
        self.assertEqual(len(results['issues_found']), 0)
    
    def test_broken_ghost_text_scenario(self):
        """测试损坏的Ghost Text系统场景"""
        mock_editor = Mock()
        
        # 模拟一个损坏的Ghost Text系统
        mock_broken = Mock()
        mock_broken.handle_key_press = Mock(side_effect=AttributeError("方法不存在"))
        mock_broken.reject_ghost_text = Mock(return_value=False)  # 返回False表示失败
        mock_broken.has_active_ghost_text = Mock(return_value=True)
        
        mock_editor._ghost_completion = mock_broken
        
        validator = EscKeyHandlerValidator(mock_editor)
        results = validator.validate_esc_key_handling()
        
        self.assertTrue(results['ghost_system_available'])
        self.assertFalse(results['handle_key_press_works'])
        self.assertTrue(results['reject_ghost_text_works'])  # 方法工作但返回False
        self.assertGreater(len(results['issues_found']), 0)
        self.assertGreater(len(results['recommendations']), 0)


if __name__ == '__main__':
    # 设置日志级别以减少测试输出
    import logging
    logging.getLogger().setLevel(logging.WARNING)
    
    # 运行测试
    unittest.main(verbosity=2)