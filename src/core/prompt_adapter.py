"""
提示词系统适配器 - 确保新旧系统的无缝兼容
提供向后兼容的接口，支持渐进式迁移
"""

import logging
from typing import Dict, Any, List, Optional, Union
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from dataclasses import asdict

logger = logging.getLogger(__name__)


class LegacyPromptAdapter(QObject):
    """遗留系统适配器 - 新旧系统之间的桥梁"""
    
    # 向旧系统兼容的信号
    promptGenerated = pyqtSignal(str)          # 兼容EnhancedPromptManager
    contextAnalyzed = pyqtSignal(dict)         # 兼容上下文分析器
    templateProcessed = pyqtSignal(str, dict)  # 兼容模板处理器
    
    def __init__(self, new_prompt_manager, legacy_ai_manager=None):
        super().__init__()
        self.new_manager = new_prompt_manager
        self.legacy_manager = legacy_ai_manager
        
        # 兼容性映射
        self.mode_mapping = {
            'fast': 'FAST',
            'balanced': 'BALANCED', 
            'full': 'FULL'
        }
        
        self.type_mapping = {
            'text': 'TEXT',
            'character': 'CHARACTER',
            'location': 'LOCATION',
            'dialogue': 'DIALOGUE',
            'action': 'ACTION',
            'emotion': 'EMOTION',
            'plot': 'PLOT',
            'description': 'DESCRIPTION',
            'transition': 'TRANSITION'
        }
        
        self._connect_new_system()
        logger.info("LegacyPromptAdapter 初始化完成")
    
    def _connect_new_system(self):
        """连接新系统的信号"""
        if self.new_manager:
            self.new_manager.promptGenerated.connect(self._forward_prompt_generated)
            self.new_manager.contextUpdated.connect(self._forward_context_updated)
    
    def _forward_prompt_generated(self, prompt: str):
        """转发提示词生成信号到旧系统"""
        try:
            # 向旧系统发出兼容信号
            self.promptGenerated.emit(prompt)
            
            # 如果有遗留AI管理器，直接调用其方法
            if self.legacy_manager and hasattr(self.legacy_manager, 'handle_prompt'):
                self.legacy_manager.handle_prompt(prompt)
                
        except Exception as e:
            logger.error(f"转发提示词信号失败: {e}")
    
    def _forward_context_updated(self, context: Dict[str, Any]):
        """转发上下文更新信号"""
        try:
            # 转换为旧系统格式
            legacy_context = self._convert_context_to_legacy(context)
            self.contextAnalyzed.emit(legacy_context)
            
        except Exception as e:
            logger.error(f"转发上下文信号失败: {e}")
    
    def _convert_context_to_legacy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """将新系统上下文转换为旧系统格式"""
        legacy_context = {
            'mode': self.mode_mapping.get(context.get('mode', 'balanced'), 'BALANCED'),
            'tags': context.get('tags', []),
            'entities': context.get('entities', []),
            'analysis_type': 'simplified',
            'timestamp': context.get('timestamp', 0)
        }
        
        return legacy_context
    
    # 向旧系统提供的兼容接口
    def generate_prompt_legacy(self, context_data: Dict[str, Any]) -> str:
        """兼容旧系统的提示词生成接口"""
        try:
            from .simple_prompt_service import SimplePromptContext, PromptMode, CompletionType
            
            # 转换旧格式到新格式
            new_context = SimplePromptContext(
                text=context_data.get('text', ''),
                cursor_position=context_data.get('cursor_position', 0),
                selected_tags=context_data.get('tags', []),
                prompt_mode=self._convert_mode_from_legacy(context_data.get('mode', 'BALANCED')),
                completion_type=self._convert_type_from_legacy(context_data.get('type', 'TEXT')),
                word_count=context_data.get('word_count', 300),
                context_size=context_data.get('context_size', 500)
            )
            
            # 使用新系统生成
            return self.new_manager.generate_prompt(new_context)
            
        except Exception as e:
            logger.error(f"兼容接口生成提示词失败: {e}")
            return ""
    
    def _convert_mode_from_legacy(self, legacy_mode: str):
        """从旧系统模式转换到新系统"""
        from .simple_prompt_service import PromptMode
        
        mapping = {
            'FAST': PromptMode.FAST,
            'BALANCED': PromptMode.BALANCED,
            'FULL': PromptMode.FULL
        }
        
        return mapping.get(legacy_mode, PromptMode.BALANCED)
    
    def _convert_type_from_legacy(self, legacy_type: str):
        """从旧系统类型转换到新系统"""
        from .simple_prompt_service import CompletionType
        
        mapping = {
            'TEXT': CompletionType.TEXT,
            'CHARACTER': CompletionType.CHARACTER,
            'LOCATION': CompletionType.LOCATION,
            'DIALOGUE': CompletionType.DIALOGUE,
            'ACTION': CompletionType.ACTION,
            'EMOTION': CompletionType.EMOTION,
            'PLOT': CompletionType.PLOT,
            'DESCRIPTION': CompletionType.DESCRIPTION,
            'TRANSITION': CompletionType.TRANSITION
        }
        
        return mapping.get(legacy_type, CompletionType.TEXT)


class SmartCompletionAdapter(QObject):
    """SmartCompletionManager适配器"""
    
    def __init__(self, prompt_container, smart_completion_manager=None):
        super().__init__()
        self.container = prompt_container
        self.completion_manager = smart_completion_manager
        self.event_bus = prompt_container.get_service('event_bus') if prompt_container else None
        
        self._connect_signals()
        logger.info("SmartCompletionAdapter 初始化完成")
    
    def _connect_signals(self):
        """连接信号"""
        if self.completion_manager:
            # 监听AI补全请求信号
            self.completion_manager.aiCompletionRequested.connect(self.handle_ai_completion_request)
        
        if self.event_bus:
            # 监听事件总线的提示词生成完成事件
            self.event_bus.promptGenerated.connect(self._on_prompt_ready)
    
    @pyqtSlot(str, dict)
    def handle_ai_completion_request(self, text: str, context: Dict[str, Any]):
        """处理来自SmartCompletionManager的AI补全请求"""
        try:
            logger.debug(f"收到AI补全请求: text长度={len(text)}, context={context}")
            
            # 构建新系统的上下文
            from .simple_prompt_service import create_simple_prompt_context
            from .prompt_events import emit_prompt_request, PromptEvent, EventType
            
            # 从context中提取信息
            cursor_pos = context.get('cursor_position', 0)
            mode = context.get('mode', 'balanced')
            completion_type = context.get('type', 'text')
            
            # 创建提示词上下文
            prompt_context = create_simple_prompt_context(
                text=text,
                cursor_pos=cursor_pos,
                mode=mode,
                completion_type=completion_type
            )
            
            # 通过事件总线请求生成提示词
            if self.event_bus:
                event = PromptEvent(
                    event_type=EventType.PROMPT_REQUESTED,
                    data=prompt_context,
                    source='smart_completion_adapter'
                )
                self.event_bus.emit_event(event)
            
        except Exception as e:
            logger.error(f"处理AI补全请求失败: {e}")
    
    def _on_prompt_ready(self, prompt: str, context: Any = None):
        """提示词准备就绪"""
        try:
            # 将生成的提示词传递给AI管理器进行实际的AI调用
            # 这里需要与EnhancedAIManager或其他AI管理器集成
            logger.info(f"提示词已生成，长度: {len(prompt)}")
            
            # TODO: 调用实际的AI服务
            # 这里应该调用AI管理器的方法来发送请求
            
        except Exception as e:
            logger.error(f"处理生成的提示词失败: {e}")


class EnhancedAIManagerAdapter(QObject):
    """EnhancedAIManager适配器"""
    
    def __init__(self, prompt_container, ai_manager=None):
        super().__init__()
        self.container = prompt_container
        self.ai_manager = ai_manager
        self.prompt_manager = prompt_container.get_service('prompt_manager') if prompt_container else None
        
        # 创建遗留适配器
        self.legacy_adapter = LegacyPromptAdapter(self.prompt_manager, ai_manager)
        
        logger.info("EnhancedAIManagerAdapter 初始化完成")
    
    def integrate_with_ai_manager(self):
        """与AI管理器集成"""
        if not self.ai_manager:
            logger.warning("AI管理器不可用")
            return
        
        try:
            # 替换AI管理器的提示词生成组件
            if hasattr(self.ai_manager, 'prompt_manager'):
                original_manager = self.ai_manager.prompt_manager
                
                # 创建包装器，使新系统兼容旧接口
                wrapper = LegacyInterfaceWrapper(self.prompt_manager, original_manager)
                self.ai_manager.prompt_manager = wrapper
                
                logger.info("AI管理器提示词组件已替换")
            
        except Exception as e:
            logger.error(f"AI管理器集成失败: {e}")


class LegacyInterfaceWrapper:
    """遗留接口包装器 - 让新系统完全兼容旧接口"""
    
    def __init__(self, new_manager, original_manager=None):
        self.new_manager = new_manager
        self.original_manager = original_manager
        
        # 复制原有管理器的所有属性和方法
        if original_manager:
            self._copy_attributes(original_manager)
    
    def _copy_attributes(self, original):
        """复制原有管理器的属性"""
        for attr_name in dir(original):
            if not attr_name.startswith('_'):
                try:
                    attr_value = getattr(original, attr_name)
                    if not callable(attr_value):
                        setattr(self, attr_name, attr_value)
                except:
                    pass
    
    def generate_prompt(self, *args, **kwargs):
        """兼容旧系统的generate_prompt方法"""
        try:
            # 尝试使用新系统
            if hasattr(self.new_manager, 'generate_simple_prompt'):
                # 处理不同的调用方式
                if len(args) >= 1:
                    text = args[0]
                    cursor_pos = args[1] if len(args) > 1 else 0
                    return self.new_manager.generate_simple_prompt(text, cursor_pos)
                
            # 如果新系统不可用，回退到原系统
            if self.original_manager and hasattr(self.original_manager, 'generate_prompt'):
                return self.original_manager.generate_prompt(*args, **kwargs)
                
        except Exception as e:
            logger.error(f"包装器生成提示词失败: {e}")
            
        return ""
    
    def __getattr__(self, name):
        """动态属性访问 - 转发到新系统或原系统"""
        # 优先尝试新系统
        if self.new_manager and hasattr(self.new_manager, name):
            return getattr(self.new_manager, name)
        
        # 回退到原系统
        if self.original_manager and hasattr(self.original_manager, name):
            return getattr(self.original_manager, name)
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class ConfigurationMigrator:
    """配置迁移工具"""
    
    def __init__(self, config=None):
        self.config = config
    
    def migrate_prompt_config(self) -> Dict[str, Any]:
        """迁移提示词相关配置"""
        try:
            if not self.config:
                return self._get_default_config()
            
            # 从旧配置中提取相关设置
            old_config = self.config.get('ai', {})
            
            new_config = {
                'prompt_system': {
                    'use_simplified_system': True,
                    'default_mode': old_config.get('prompt_mode', 'balanced'),
                    'default_word_count': old_config.get('word_count', 300),
                    'enable_rag': old_config.get('enable_rag', True),
                    'enable_entity_detection': True,
                    'cache_size': 100,
                    'selected_tags': []
                }
            }
            
            logger.info("提示词配置迁移完成")
            return new_config
            
        except Exception as e:
            logger.error(f"配置迁移失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'prompt_system': {
                'use_simplified_system': True,
                'default_mode': 'balanced',
                'default_word_count': 300,
                'enable_rag': True,
                'enable_entity_detection': True,
                'cache_size': 100,
                'selected_tags': []
            }
        }


def create_integrated_system(shared=None, config=None, 
                           smart_completion_manager=None, 
                           ai_manager=None):
    """创建完整的集成系统"""
    
    logger.info("开始创建集成的提示词系统")
    
    try:
        # 1. 创建服务容器
        from .prompt_events import PromptServiceContainer
        container = PromptServiceContainer(shared, config)
        container.initialize()
        
        # 2. 迁移配置
        migrator = ConfigurationMigrator(config)
        new_config = migrator.migrate_prompt_config()
        
        # 3. 创建适配器
        adapters = {
            'smart_completion': SmartCompletionAdapter(container, smart_completion_manager),
            'ai_manager': EnhancedAIManagerAdapter(container, ai_manager)
        }
        
        # 4. 执行集成
        if smart_completion_manager:
            adapters['smart_completion']
        
        if ai_manager:
            adapters['ai_manager'].integrate_with_ai_manager()
        
        logger.info("集成系统创建完成")
        
        return {
            'container': container,
            'adapters': adapters,
            'config': new_config
        }
        
    except Exception as e:
        logger.error(f"创建集成系统失败: {e}")
        raise


# 向后兼容的全局函数
def get_legacy_prompt_manager(shared=None, config=None):
    """获取兼容旧系统的提示词管理器"""
    try:
        from .prompt_events import get_global_container
        container = get_global_container(shared, config)
        new_manager = container.get_service('prompt_manager')
        
        return LegacyInterfaceWrapper(new_manager)
        
    except Exception as e:
        logger.error(f"获取兼容提示词管理器失败: {e}")
        return None