"""
提示词系统集成测试 - 验证新系统的完整功能和兼容性
测试新旧系统的无缝集成和基础补全功能
"""

import logging
import time
import sys
from typing import Dict, Any, List
from PyQt6.QtCore import QObject, QTimer, QApplication
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class PromptSystemIntegrationTest:
    """提示词系统集成测试类"""
    
    def __init__(self):
        self.test_results = []
        self.setup_logging()
    
    def setup_logging(self):
        """设置测试日志"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有集成测试"""
        logger.info("开始运行提示词系统集成测试")
        
        test_methods = [
            self.test_simple_prompt_service,
            self.test_event_bus_system,
            self.test_tag_system,
            self.test_context_injection,
            self.test_legacy_compatibility,
            self.test_ui_components,
            self.test_performance,
            self.test_error_handling
        ]
        
        results = {
            'total_tests': len(test_methods),
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        for test_method in test_methods:
            try:
                test_name = test_method.__name__
                logger.info(f"运行测试: {test_name}")
                
                start_time = time.time()
                test_result = test_method()
                duration = time.time() - start_time
                
                if test_result:
                    results['passed'] += 1
                    status = "PASS"
                else:
                    results['failed'] += 1
                    status = "FAIL"
                
                results['details'].append({
                    'test': test_name,
                    'status': status,
                    'duration': duration,
                    'details': test_result
                })
                
                logger.info(f"测试 {test_name}: {status} ({duration:.3f}s)")
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'test': test_method.__name__,
                    'status': 'ERROR',
                    'error': str(e)
                })
                logger.error(f"测试 {test_method.__name__} 出错: {e}")
        
        logger.info(f"测试完成: {results['passed']}/{results['total_tests']} 通过")
        return results
    
    def test_simple_prompt_service(self) -> bool:
        """测试简化提示词服务"""
        try:
            from .simple_prompt_service import (
                SinglePromptManager, SimplePromptContext, 
                PromptMode, CompletionType
            )
            
            # 创建管理器
            manager = SinglePromptManager()
            
            # 创建测试上下文
            context = SimplePromptContext(
                text="这是一个测试文本，用于验证提示词生成功能。",
                cursor_position=20,
                selected_tags=["科幻", "悬疑"],
                prompt_mode=PromptMode.BALANCED,
                completion_type=CompletionType.TEXT,
                word_count=300
            )
            
            # 生成提示词
            prompt = manager.generate_prompt(context)
            
            # 验证结果
            assert len(prompt) > 0, "提示词不应为空"
            assert "科幻" in prompt or "科技" in prompt, "应包含科幻风格指导"
            assert "悬疑" in prompt, "应包含悬疑风格指导"
            assert "300" in prompt, "应包含字数要求"
            
            logger.info(f"生成的提示词长度: {len(prompt)}")
            return True
            
        except Exception as e:
            logger.error(f"SimplePromptService测试失败: {e}")
            return False
    
    def test_event_bus_system(self) -> bool:
        """测试事件总线系统"""
        try:
            from .prompt_events import (
                PromptEventBus, PromptEvent, EventType,
                PromptServiceContainer
            )
            
            # 创建事件总线
            event_bus = PromptEventBus()
            
            # 测试事件发布和订阅
            received_events = []
            
            def test_handler(event):
                received_events.append(event)
            
            # 订阅事件
            event_bus.subscribe(EventType.TAGS_CHANGED, test_handler)
            
            # 发布事件
            test_event = PromptEvent(
                event_type=EventType.TAGS_CHANGED,
                data=["科幻", "武侠"],
                source="test"
            )
            event_bus.emit_event(test_event)
            
            # 验证事件接收
            assert len(received_events) == 1, "应接收到1个事件"
            assert received_events[0].data == ["科幻", "武侠"], "事件数据应正确"
            
            # 测试服务容器
            container = PromptServiceContainer()
            container.initialize()
            
            assert container.has_service('event_bus'), "应包含事件总线服务"
            assert container.has_service('prompt_manager'), "应包含提示词管理器服务"
            
            return True
            
        except Exception as e:
            logger.error(f"EventBus测试失败: {e}")
            return False
    
    def test_tag_system(self) -> bool:
        """测试标签系统"""
        try:
            from .simple_prompt_service import TaggedPromptSystem
            
            tag_system = TaggedPromptSystem()
            
            # 测试获取可用标签
            available_tags = tag_system.get_available_tags()
            assert "风格" in available_tags, "应包含风格标签分类"
            assert "科幻" in available_tags["风格"], "风格分类应包含科幻标签"
            
            # 测试标签应用
            base_prompt = "这是基础提示词模板 {style_guidance}"
            selected_tags = ["科幻", "悬疑"]
            enhanced_prompt = tag_system.apply_tags(base_prompt, selected_tags)
            
            assert len(enhanced_prompt) > len(base_prompt), "应用标签后提示词应更长"
            assert "科技" in enhanced_prompt, "应包含科幻相关内容"
            assert "悬疑" in enhanced_prompt, "应包含悬疑相关内容"
            
            return True
            
        except Exception as e:
            logger.error(f"TagSystem测试失败: {e}")
            return False
    
    def test_context_injection(self) -> bool:
        """测试上下文注入"""
        try:
            from .simple_prompt_service import AutoContextInjector, SimplePromptContext
            
            injector = AutoContextInjector()
            
            # 创建测试上下文
            context = SimplePromptContext(
                text="小明走进了房间，看到桌子上放着一本书。他拿起书本翻阅。",
                cursor_position=20,
                word_count=200
            )
            
            base_prompt = "当前文本：{current_text}\n续写{word_count}"
            
            # 注入上下文
            enhanced_prompt = injector.inject_context(base_prompt, context)
            
            assert "{current_text}" not in enhanced_prompt, "变量应被替换"
            assert "{word_count}" not in enhanced_prompt, "变量应被替换"
            assert "小明" in enhanced_prompt, "应包含上下文文本"
            assert "200" in enhanced_prompt, "应包含字数要求"
            
            return True
            
        except Exception as e:
            logger.error(f"ContextInjection测试失败: {e}")
            return False
    
    def test_legacy_compatibility(self) -> bool:
        """测试遗留系统兼容性"""
        try:
            from .prompt_adapter import (
                LegacyPromptAdapter, LegacyInterfaceWrapper,
                get_legacy_prompt_manager
            )
            from .simple_prompt_service import SinglePromptManager
            
            # 创建新系统
            new_manager = SinglePromptManager()
            
            # 创建兼容包装器
            wrapper = LegacyInterfaceWrapper(new_manager)
            
            # 测试兼容接口
            prompt = wrapper.generate_prompt("测试文本", 0)
            assert isinstance(prompt, str), "应返回字符串类型的提示词"
            
            # 测试全局兼容函数
            legacy_manager = get_legacy_prompt_manager()
            assert legacy_manager is not None, "应能获取兼容管理器"
            
            return True
            
        except Exception as e:
            logger.error(f"LegacyCompatibility测试失败: {e}")
            return False
    
    def test_ui_components(self) -> bool:
        """测试UI组件"""
        try:
            # 检查是否有Qt应用实例
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            from gui.prompt.simple_prompt_widget import (
                SimplePromptWidget, TagPanel, AdvancedSettingsPanel, 
                PromptPreviewPanel
            )
            from .prompt_events import PromptServiceContainer
            
            # 创建服务容器
            container = PromptServiceContainer()
            container.initialize()
            
            # 创建UI组件
            widget = SimplePromptWidget(container)
            
            # 测试基本功能
            assert widget.tag_panel is not None, "应包含标签面板"
            assert widget.advanced_panel is not None, "应包含高级设置面板"
            assert widget.preview_panel is not None, "应包含预览面板"
            
            # 测试标签选择
            widget.set_selected_tags(["科幻", "武侠"])
            selected = widget.get_selected_tags()
            assert "科幻" in selected, "应能设置和获取标签"
            
            return True
            
        except Exception as e:
            logger.error(f"UI组件测试失败: {e}")
            return False
    
    def test_performance(self) -> bool:
        """测试性能"""
        try:
            from .simple_prompt_service import SinglePromptManager, SimplePromptContext
            
            manager = SinglePromptManager()
            
            # 性能测试：批量生成提示词
            start_time = time.time()
            
            for i in range(50):  # 生成50个提示词
                context = SimplePromptContext(
                    text=f"测试文本 {i}",
                    cursor_position=i,
                    selected_tags=["科幻"] if i % 2 == 0 else ["武侠"],
                    word_count=300
                )
                prompt = manager.generate_prompt(context)
                assert len(prompt) > 0, f"第{i}个提示词不应为空"
            
            duration = time.time() - start_time
            avg_time = duration / 50
            
            logger.info(f"平均生成时间: {avg_time:.4f}s")
            
            # 性能要求：平均每个提示词生成时间应小于0.1秒
            assert avg_time < 0.1, f"生成时间过长: {avg_time}s"
            
            # 测试缓存效果
            cache_stats = manager.get_cache_stats()
            logger.info(f"缓存统计: {cache_stats}")
            
            return True
            
        except Exception as e:
            logger.error(f"Performance测试失败: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """测试错误处理"""
        try:
            from .simple_prompt_service import SinglePromptManager, SimplePromptContext
            
            manager = SinglePromptManager()
            
            # 测试异常输入
            try:
                # 空上下文
                empty_context = SimplePromptContext()
                prompt = manager.generate_prompt(empty_context)
                assert isinstance(prompt, str), "即使空上下文也应返回有效提示词"
                
                # 超长文本
                long_text = "测试" * 10000  # 4万字符
                long_context = SimplePromptContext(text=long_text)
                prompt = manager.generate_prompt(long_context)
                assert isinstance(prompt, str), "超长文本应能正常处理"
                
                # 无效标签
                invalid_context = SimplePromptContext(selected_tags=["不存在的标签"])
                prompt = manager.generate_prompt(invalid_context)
                assert isinstance(prompt, str), "无效标签应能正常处理"
                
            except Exception as e:
                logger.error(f"错误处理测试中遇到异常: {e}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"ErrorHandling测试失败: {e}")
            return False


def run_integration_test() -> Dict[str, Any]:
    """运行集成测试的便捷函数"""
    test_runner = PromptSystemIntegrationTest()
    return test_runner.run_all_tests()


def quick_functionality_test():
    """快速功能测试 - 验证核心功能"""
    logger.info("开始快速功能测试")
    
    try:
        # 1. 测试核心服务创建
        from .prompt_events import get_global_container
        container = get_global_container()
        assert container is not None
        
        # 2. 测试提示词生成
        prompt_manager = container.get_service('prompt_manager')
        assert prompt_manager is not None
        
        from .simple_prompt_service import create_simple_prompt_context
        context = create_simple_prompt_context(
            text="这是一个小说片段，主角正在探索神秘的古堡。",
            cursor_pos=15,
            tags=["奇幻", "悬疑"],
            mode="balanced"
        )
        
        prompt = prompt_manager.generate_prompt(context)
        assert len(prompt) > 100  # 生成的提示词应有一定长度
        
        logger.info("✓ 核心功能测试通过")
        logger.info(f"生成的提示词预览: {prompt[:200]}...")
        
        # 3. 测试事件系统
        event_bus = container.get_service('event_bus')
        assert event_bus is not None
        
        from .prompt_events import emit_tags_changed
        emit_tags_changed(["科幻", "动作"])
        
        logger.info("✓ 事件系统测试通过")
        
        # 4. 测试缓存
        cache_stats = prompt_manager.get_cache_stats()
        logger.info(f"缓存统计: {cache_stats}")
        
        logger.info("✅ 快速功能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 快速功能测试失败: {e}")
        return False


if __name__ == "__main__":
    # 运行快速测试
    quick_test_result = quick_functionality_test()
    
    if quick_test_result:
        # 运行完整测试
        full_test_results = run_integration_test()
        
        print("\n" + "="*50)
        print("集成测试结果")
        print("="*50)
        print(f"总测试数: {full_test_results['total_tests']}")
        print(f"通过: {full_test_results['passed']}")
        print(f"失败: {full_test_results['failed']}")
        print(f"成功率: {full_test_results['passed']/full_test_results['total_tests']*100:.1f}%")
        
        print("\n详细结果:")
        for detail in full_test_results['details']:
            status_symbol = "✅" if detail['status'] == 'PASS' else "❌"
            print(f"{status_symbol} {detail['test']}: {detail['status']}")
            if 'duration' in detail:
                print(f"   耗时: {detail['duration']:.3f}s")
    else:
        print("❌ 快速测试失败，跳过完整测试")