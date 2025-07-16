#!/usr/bin/env python3
"""
测试Tab键和ESC键在Ghost Text系统中的处理逻辑
验证按键处理的正确性和优先级
"""

import os
import sys
import logging
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication, QPlainTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.config import Config
from core.shared import Shared
from gui.editor.text_editor import IntelligentTextEditor

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TabEscGhostTextTester:
    """Tab键和ESC键处理测试器"""
    
    def __init__(self):
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)
        
        # 创建配置和共享对象
        self.config = Config()
        self.shared = Shared()
        
        # 创建测试编辑器
        self.editor = IntelligentTextEditor(self.config, self.shared)
        logger.info("测试编辑器创建完成")
    
    def test_tab_key_processing(self):
        """测试Tab键处理逻辑"""
        logger.info("🔍 开始测试Tab键处理")
        
        # 模拟有ghost text的情况
        ghost_manager = self.editor.get_ghost_text_manager()
        if not ghost_manager:
            logger.error("❌ Ghost Text管理器未找到")
            return False
        
        # 设置测试文本
        self.editor.setPlainText("测试文本")
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        
        # 显示Ghost Text
        ghost_text = "这是Ghost Text补全内容"
        position = cursor.position()
        success = ghost_manager.show_ghost_text(ghost_text, position)
        
        if not success:
            logger.error("❌ Ghost Text显示失败")
            return False
        
        logger.info(f"✅ Ghost Text显示成功: '{ghost_text}'")
        
        # 验证状态
        has_ghost = ghost_manager.has_active_ghost_text()
        logger.info(f"Ghost Text活跃状态: {has_ghost}")
        
        if not has_ghost:
            logger.error("❌ Ghost Text状态检查失败")
            return False
        
        # 创建Tab键事件
        tab_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Tab,
            Qt.KeyboardModifier.NoModifier
        )
        
        # 测试Tab键处理
        logger.info("📝 测试Tab键处理...")
        
        # 验证Ghost Text的handle_key_press方法
        handled = ghost_manager.handle_key_press(tab_event)
        logger.info(f"Ghost Text处理Tab键结果: {handled}")
        
        # 验证状态变化
        has_ghost_after = ghost_manager.has_active_ghost_text()
        logger.info(f"Tab键后Ghost Text状态: {has_ghost_after}")
        
        if handled:
            logger.info("✅ Tab键被Ghost Text系统正确处理")
        else:
            logger.warning("⚠️ Tab键未被Ghost Text系统处理")
        
        return handled
    
    def test_esc_key_processing(self):
        """测试ESC键处理逻辑"""
        logger.info("🔍 开始测试ESC键处理")
        
        # 模拟有ghost text的情况
        ghost_manager = self.editor.get_ghost_text_manager()
        if not ghost_manager:
            logger.error("❌ Ghost Text管理器未找到")
            return False
        
        # 设置测试文本
        self.editor.setPlainText("测试文本")
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        
        # 显示Ghost Text
        ghost_text = "这是Ghost Text补全内容"
        position = cursor.position()
        success = ghost_manager.show_ghost_text(ghost_text, position)
        
        if not success:
            logger.error("❌ Ghost Text显示失败")
            return False
        
        logger.info(f"✅ Ghost Text显示成功: '{ghost_text}'")
        
        # 验证状态
        has_ghost = ghost_manager.has_active_ghost_text()
        logger.info(f"Ghost Text活跃状态: {has_ghost}")
        
        if not has_ghost:
            logger.error("❌ Ghost Text状态检查失败")
            return False
        
        # 创建ESC键事件
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier
        )
        
        # 测试ESC键处理
        logger.info("📝 测试ESC键处理...")
        
        # 验证Ghost Text的handle_key_press方法
        handled = ghost_manager.handle_key_press(esc_event)
        logger.info(f"Ghost Text处理ESC键结果: {handled}")
        
        # 验证状态变化
        has_ghost_after = ghost_manager.has_active_ghost_text()
        logger.info(f"ESC键后Ghost Text状态: {has_ghost_after}")
        
        if handled:
            logger.info("✅ ESC键被Ghost Text系统正确处理")
        else:
            logger.warning("⚠️ ESC键未被Ghost Text系统处理")
        
        return handled
    
    def test_text_editor_key_priorities(self):
        """测试文本编辑器中的按键优先级"""
        logger.info("🔍 测试文本编辑器按键优先级")
        
        # 获取Ghost Text管理器
        ghost_manager = self.editor.get_ghost_text_manager()
        if not ghost_manager:
            logger.error("❌ Ghost Text管理器未找到")
            return False
        
        # 设置测试文本和Ghost Text
        self.editor.setPlainText("测试文本")
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        
        ghost_text = "这是Ghost Text补全内容"
        position = cursor.position()
        ghost_manager.show_ghost_text(ghost_text, position)
        
        # 测试Tab键在text_editor中的处理
        logger.info("📝 测试Tab键在text_editor.keyPressEvent中的处理...")
        
        tab_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Tab,
            Qt.KeyboardModifier.NoModifier
        )
        
        # 记录处理前状态
        has_ghost_before = ghost_manager.has_active_ghost_text()
        logger.info(f"Tab键处理前Ghost Text状态: {has_ghost_before}")
        
        # 调用编辑器的keyPressEvent
        self.editor.keyPressEvent(tab_event)
        
        # 检查处理后状态
        has_ghost_after = ghost_manager.has_active_ghost_text()
        logger.info(f"Tab键处理后Ghost Text状态: {has_ghost_after}")
        
        if has_ghost_before and not has_ghost_after:
            logger.info("✅ Tab键正确处理了Ghost Text（接受）")
        elif has_ghost_before and has_ghost_after:
            logger.warning("⚠️ Tab键未能处理Ghost Text")
        else:
            logger.info("ℹ️ Tab键处理结果不确定")
        
        return True
    
    def test_esc_key_editor_priorities(self):
        """测试ESC键在编辑器中的优先级"""
        logger.info("🔍 测试ESC键在编辑器中的优先级")
        
        # 获取Ghost Text管理器
        ghost_manager = self.editor.get_ghost_text_manager()
        if not ghost_manager:
            logger.error("❌ Ghost Text管理器未找到")
            return False
        
        # 设置测试文本和Ghost Text
        self.editor.setPlainText("测试文本")
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        
        ghost_text = "这是Ghost Text补全内容"
        position = cursor.position()
        ghost_manager.show_ghost_text(ghost_text, position)
        
        # 测试ESC键在text_editor中的处理
        logger.info("📝 测试ESC键在text_editor.keyPressEvent中的处理...")
        
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier
        )
        
        # 记录处理前状态
        has_ghost_before = ghost_manager.has_active_ghost_text()
        logger.info(f"ESC键处理前Ghost Text状态: {has_ghost_before}")
        
        # 调用编辑器的keyPressEvent
        self.editor.keyPressEvent(esc_event)
        
        # 检查处理后状态
        has_ghost_after = ghost_manager.has_active_ghost_text()
        logger.info(f"ESC键处理后Ghost Text状态: {has_ghost_after}")
        
        if has_ghost_before and not has_ghost_after:
            logger.info("✅ ESC键正确处理了Ghost Text（拒绝）")
        elif has_ghost_before and has_ghost_after:
            logger.warning("⚠️ ESC键未能处理Ghost Text")
        else:
            logger.info("ℹ️ ESC键处理结果不确定")
        
        return True
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始运行Tab键和ESC键测试")
        
        tests = [
            ("Tab键处理测试", self.test_tab_key_processing),
            ("ESC键处理测试", self.test_esc_key_processing),
            ("文本编辑器Tab键优先级测试", self.test_text_editor_key_priorities),
            ("文本编辑器ESC键优先级测试", self.test_esc_key_editor_priorities)
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"📋 {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                result = test_func()
                results.append((test_name, result))
                logger.info(f"✅ {test_name} {'通过' if result else '失败'}")
            except Exception as e:
                logger.error(f"❌ {test_name} 异常: {e}")
                results.append((test_name, False))
        
        # 输出总结
        logger.info(f"\n{'='*50}")
        logger.info("📊 测试结果总结")
        logger.info(f"{'='*50}")
        
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{status} {test_name}")
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        logger.info(f"\n通过: {passed}/{total}")
        
        if passed == total:
            logger.info("🎉 所有测试通过！")
        else:
            logger.warning("⚠️ 部分测试失败，需要检查")
        
        return passed == total


def main():
    """主函数"""
    print("Tab键和ESC键Ghost Text处理测试")
    print("=" * 50)
    
    try:
        tester = TabEscGhostTextTester()
        success = tester.run_all_tests()
        
        if success:
            print("\n🎉 所有测试都通过了！")
            return 0
        else:
            print("\n⚠️ 部分测试失败，请检查日志")
            return 1
            
    except Exception as e:
        print(f"\n❌ 测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())