#!/usr/bin/env python3
"""
测试Esc键处理的完整链路
重点检查keyPressEvent中的处理逻辑
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_esc_key_processing():
    """测试Esc键处理的完整链路"""
    
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    # 创建编辑器
    from core.config import Config
    from core.shared import Shared
    from gui.editor.text_editor import IntelligentTextEditor
    
    config = Config()
    shared = Shared()
    editor = IntelligentTextEditor(config, shared)
    
    # 检查Ghost Text系统初始化状态
    print("=== Ghost Text 系统状态检查 ===")
    print(f"_ghost_completion: {getattr(editor, '_ghost_completion', 'Not found')}")
    print(f"_optimal_ghost_text: {getattr(editor, '_optimal_ghost_text', 'Not found')}")
    print(f"_deep_ghost_text: {getattr(editor, '_deep_ghost_text', 'Not found')}")
    print(f"_use_optimal_ghost_text: {getattr(editor, '_use_optimal_ghost_text', 'Not found')}")
    
    # 检查Ghost Text系统是否有handle_key_press方法
    ghost_completion = getattr(editor, '_ghost_completion', None)
    if ghost_completion:
        print(f"Ghost completion type: {type(ghost_completion)}")
        print(f"Has handle_key_press: {hasattr(ghost_completion, 'handle_key_press')}")
        print(f"Has has_active_ghost_text: {hasattr(ghost_completion, 'has_active_ghost_text')}")
        print(f"Has show_completion: {hasattr(ghost_completion, 'show_completion')}")
    
    # 检查smart_completion是否正确初始化
    smart_completion = getattr(editor, '_smart_completion', None)
    if smart_completion:
        print(f"Smart completion type: {type(smart_completion)}")
        print(f"Smart completion ghost_completion: {getattr(smart_completion, '_ghost_completion', 'Not found')}")
    
    # 检查completion_widget状态
    completion_widget = getattr(editor, '_completion_widget', None)
    if completion_widget:
        print(f"Completion widget type: {type(completion_widget)}")
        print(f"Completion widget visible: {completion_widget.isVisible()}")
    
    print("\n=== 测试Esc键处理链路 ===")
    
    # 创建Esc键事件
    esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    
    # 测试场景1：没有Ghost Text时按Esc键
    print("\n--- 场景1：没有Ghost Text时按Esc键 ---")
    result1 = test_key_press_scenario(editor, esc_event, "无Ghost Text")
    
    # 测试场景2：有Ghost Text时按Esc键
    print("\n--- 场景2：有Ghost Text时按Esc键 ---")
    if ghost_completion and hasattr(ghost_completion, 'show_completion'):
        try:
            # 先显示一个Ghost Text
            ghost_completion.show_completion("这是一个测试的Ghost Text补全")
            print(f"Ghost Text显示后状态: {ghost_completion.has_active_ghost_text()}")
            
            result2 = test_key_press_scenario(editor, esc_event, "有Ghost Text")
            
            # 检查Ghost Text是否被正确清理
            if hasattr(ghost_completion, 'has_active_ghost_text'):
                print(f"Esc键处理后Ghost Text状态: {ghost_completion.has_active_ghost_text()}")
        except Exception as e:
            print(f"Ghost Text显示测试失败: {e}")
    
    # 测试场景3：completion_widget可见时按Esc键
    print("\n--- 场景3：completion_widget可见时按Esc键 ---")
    if completion_widget:
        try:
            # 模拟显示completion_widget
            completion_widget.show()
            print(f"Completion widget显示后状态: {completion_widget.isVisible()}")
            
            result3 = test_key_press_scenario(editor, esc_event, "completion_widget可见")
            
            # 检查completion_widget是否被隐藏
            print(f"Esc键处理后completion_widget状态: {completion_widget.isVisible()}")
        except Exception as e:
            print(f"Completion widget测试失败: {e}")
    
    print("\n=== 测试完成 ===")
    
    app.quit()

def test_key_press_scenario(editor, event, scenario_name):
    """测试特定场景下的键盘事件处理"""
    print(f"测试场景: {scenario_name}")
    
    # 模拟keyPressEvent处理
    try:
        # 记录处理前的状态
        ghost_completion = getattr(editor, '_ghost_completion', None)
        smart_completion = getattr(editor, '_smart_completion', None)
        completion_widget = getattr(editor, '_completion_widget', None)
        
        print("处理前状态:")
        if ghost_completion and hasattr(ghost_completion, 'has_active_ghost_text'):
            print(f"  Ghost Text active: {ghost_completion.has_active_ghost_text()}")
        if completion_widget:
            print(f"  Completion widget visible: {completion_widget.isVisible()}")
        
        # 模拟keyPressEvent的处理流程
        handled = False
        
        # 第一优先级：Ghost Text系统处理
        if ghost_completion and hasattr(ghost_completion, 'handle_key_press'):
            print("  尝试Ghost Text处理...")
            if ghost_completion.handle_key_press(event):
                print("  ✅ Ghost Text处理了事件")
                handled = True
            else:
                print("  ❌ Ghost Text未处理事件")
        
        # 第二优先级：智能补全管理器处理
        if not handled and smart_completion and hasattr(smart_completion, 'handle_key_press'):
            print("  尝试Smart Completion处理...")
            if smart_completion.handle_key_press(event):
                print("  ✅ Smart Completion处理了事件")
                handled = True
            else:
                print("  ❌ Smart Completion未处理事件")
        
        # 第三优先级：弹出式补全组件处理
        if not handled and completion_widget and completion_widget.isVisible():
            print("  尝试Completion Widget处理...")
            if event.key() == Qt.Key.Key_Escape:
                completion_widget.hide()
                print("  ✅ Completion Widget隐藏了")
                handled = True
            else:
                print("  ❌ Completion Widget未处理事件")
        
        # 记录处理后的状态
        print("处理后状态:")
        if ghost_completion and hasattr(ghost_completion, 'has_active_ghost_text'):
            print(f"  Ghost Text active: {ghost_completion.has_active_ghost_text()}")
        if completion_widget:
            print(f"  Completion widget visible: {completion_widget.isVisible()}")
        
        return handled
        
    except Exception as e:
        print(f"测试场景 '{scenario_name}' 失败: {e}")
        return False

if __name__ == "__main__":
    test_esc_key_processing()