#!/usr/bin/env python3
"""
Esc键处理逻辑分析测试
验证optimal_ghost_text.py中Esc键处理的各个方面
"""

import pytest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui.editor.optimal_ghost_text import OptimalGhostText


class TestEscKeyHandling:
    """Esc键处理逻辑测试"""
    
    def setup_method(self):
        """测试设置"""
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        self.text_editor = QTextEdit()
        self.ghost_text = OptimalGhostText(self.text_editor)
    
    def test_has_active_ghost_text_logic(self):
        """测试has_active_ghost_text()方法的逻辑"""
        # 初始状态
        assert not self.ghost_text.has_active_ghost_text()
        
        # 只设置_is_active为True
        self.ghost_text._is_active = True
        self.ghost_text._ghost_text = ""
        assert not self.ghost_text.has_active_ghost_text()  # 应该返回False
        
        # 设置_is_active为True和_ghost_text非空
        self.ghost_text._is_active = True
        self.ghost_text._ghost_text = "test"
        assert self.ghost_text.has_active_ghost_text()  # 应该返回True
        
        # 只设置_ghost_text非空
        self.ghost_text._is_active = False
        self.ghost_text._ghost_text = "test"
        assert not self.ghost_text.has_active_ghost_text()  # 应该返回False
    
    def test_esc_key_handling_with_active_ghost_text(self):
        """测试有活跃Ghost Text时的Esc键处理"""
        # 设置活跃状态
        self.ghost_text._is_active = True
        self.ghost_text._ghost_text = "test ghost text"
        
        # 创建Esc键事件
        esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        
        # 模拟reject_ghost_text方法
        with patch.object(self.ghost_text, 'reject_ghost_text', return_value=True) as mock_reject:
            result = self.ghost_text.handle_key_press(esc_event)
            
            # 验证结果
            assert result is True  # 事件应该被处理
            mock_reject.assert_called_once()  # reject_ghost_text应该被调用
    
    def test_esc_key_handling_without_active_ghost_text(self):
        """测试没有活跃Ghost Text时的Esc键处理"""
        # 确保没有活跃状态
        self.ghost_text._is_active = False
        self.ghost_text._ghost_text = ""
        
        # 创建Esc键事件
        esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        
        # 模拟reject_ghost_text方法
        with patch.object(self.ghost_text, 'reject_ghost_text') as mock_reject:
            result = self.ghost_text.handle_key_press(esc_event)
            
            # 验证结果
            assert result is False  # 事件不应该被处理
            mock_reject.assert_not_called()  # reject_ghost_text不应该被调用
    
    def test_reject_ghost_text_with_active_state(self):
        """测试活跃状态下的reject_ghost_text"""
        # 设置活跃状态
        self.ghost_text._is_active = True
        self.ghost_text._ghost_text = "test"
        
        # 模拟clear_ghost_text方法
        with patch.object(self.ghost_text, 'clear_ghost_text') as mock_clear:
            result = self.ghost_text.reject_ghost_text()
            
            # 验证结果
            assert result is True
            mock_clear.assert_called_once()
    
    def test_reject_ghost_text_without_active_state(self):
        """测试非活跃状态下的reject_ghost_text"""
        # 确保非活跃状态
        self.ghost_text._is_active = False
        
        # 模拟clear_ghost_text方法
        with patch.object(self.ghost_text, 'clear_ghost_text') as mock_clear:
            result = self.ghost_text.reject_ghost_text()
            
            # 验证结果
            assert result is False
            mock_clear.assert_not_called()
    
    def test_state_consistency_issue(self):
        """测试状态不一致的问题"""
        # 模拟状态不一致的情况
        self.ghost_text._is_active = True
        self.ghost_text._ghost_text = ""  # 空字符串
        
        # 这种情况下has_active_ghost_text应该返回False
        assert not self.ghost_text.has_active_ghost_text()
        
        # 创建Esc键事件
        esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        
        # 这种情况下Esc键处理应该被跳过
        result = self.ghost_text.handle_key_press(esc_event)
        assert result is False
    
    def test_reset_all_states(self):
        """测试状态重置方法"""
        # 设置一些状态
        self.ghost_text._is_active = True
        self.ghost_text._ghost_text = "test"
        self.ghost_text._ghost_start_pos = 10
        self.ghost_text._ghost_end_pos = 20
        self.ghost_text._undo_position = 5
        
        # 调用重置方法
        self.ghost_text._reset_all_states()
        
        # 验证所有状态都被重置
        assert self.ghost_text._is_active is False
        assert self.ghost_text._ghost_text == ""
        assert self.ghost_text._ghost_start_pos == -1
        assert self.ghost_text._ghost_end_pos == -1
        assert self.ghost_text._undo_position == -1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])