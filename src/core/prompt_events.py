"""
提示词系统事件总线 - 实现组件间完全解耦
使用观察者模式和Qt信号槽，替代复杂的直接依赖关系
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    # 提示词相关事件
    PROMPT_REQUESTED = "prompt_requested"         # 请求生成提示词
    PROMPT_GENERATED = "prompt_generated"         # 提示词已生成
    PROMPT_APPLIED = "prompt_applied"             # 提示词已应用
    
    # 标签相关事件
    TAGS_CHANGED = "tags_changed"                 # 标签选择变化
    TAG_ADDED = "tag_added"                       # 添加新标签
    TAG_REMOVED = "tag_removed"                   # 移除标签
    
    # 上下文相关事件
    CONTEXT_UPDATED = "context_updated"           # 上下文更新
    RAG_DATA_READY = "rag_data_ready"            # RAG数据就绪
    ENTITIES_DETECTED = "entities_detected"       # 实体检测完成
    
    # 配置相关事件
    MODE_CHANGED = "mode_changed"                 # 模式变化
    CONFIG_UPDATED = "config_updated"             # 配置更新
    
    # UI相关事件
    UI_STATE_CHANGED = "ui_state_changed"         # UI状态变化
    COMPLETION_TRIGGERED = "completion_triggered" # 补全触发


@dataclass
class PromptEvent:
    """提示词系统事件数据结构"""
    event_type: EventType                         # 事件类型
    data: Any = None                             # 事件数据
    source: str = ""                             # 事件源
    timestamp: float = None                       # 事件时间戳
    metadata: Dict[str, Any] = None              # 额外元数据
    
    def __post_init__(self):
        import time
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}


class PromptEventBus(QObject):
    """提示词系统事件总线 - 中央事件分发器"""
    
    # 主要事件信号
    promptRequested = pyqtSignal(object)          # 提示词请求 - PromptEvent
    promptGenerated = pyqtSignal(str, object)     # 提示词生成 - (prompt, context)
    promptApplied = pyqtSignal(str)               # 提示词应用 - prompt
    
    tagsChanged = pyqtSignal(list)                # 标签变化 - tag_list
    tagAdded = pyqtSignal(str)                    # 标签添加 - tag_name
    tagRemoved = pyqtSignal(str)                  # 标签移除 - tag_name
    
    contextUpdated = pyqtSignal(dict)             # 上下文更新 - context_dict
    ragDataReady = pyqtSignal(str)                # RAG数据 - rag_context
    entitiesDetected = pyqtSignal(list)           # 实体检测 - entity_list
    
    modeChanged = pyqtSignal(str)                 # 模式变化 - mode_name
    configUpdated = pyqtSignal(dict)              # 配置更新 - config_dict
    
    uiStateChanged = pyqtSignal(str, dict)        # UI状态变化 - (component, state)
    completionTriggered = pyqtSignal(str, int)    # 补全触发 - (text, cursor_pos)
    
    def __init__(self):
        super().__init__()
        self._event_history = []                  # 事件历史记录
        self._max_history = 1000                  # 最大历史记录数
        self._event_handlers = {}                 # 自定义事件处理器
        
        logger.info("PromptEventBus 初始化完成")
    
    def emit_event(self, event: PromptEvent):
        """发布事件到总线"""
        
        # 记录事件历史
        self._record_event(event)
        
        # 分发到对应的信号
        try:
            if event.event_type == EventType.PROMPT_REQUESTED:
                self.promptRequested.emit(event)
                
            elif event.event_type == EventType.PROMPT_GENERATED:
                prompt = event.data.get('prompt', '') if isinstance(event.data, dict) else str(event.data)
                context = event.data.get('context', {}) if isinstance(event.data, dict) else {}
                self.promptGenerated.emit(prompt, context)
                
            elif event.event_type == EventType.PROMPT_APPLIED:
                self.promptApplied.emit(str(event.data))
                
            elif event.event_type == EventType.TAGS_CHANGED:
                tags = event.data if isinstance(event.data, list) else []
                self.tagsChanged.emit(tags)
                
            elif event.event_type == EventType.TAG_ADDED:
                self.tagAdded.emit(str(event.data))
                
            elif event.event_type == EventType.TAG_REMOVED:
                self.tagRemoved.emit(str(event.data))
                
            elif event.event_type == EventType.CONTEXT_UPDATED:
                context = event.data if isinstance(event.data, dict) else {}
                self.contextUpdated.emit(context)
                
            elif event.event_type == EventType.RAG_DATA_READY:
                self.ragDataReady.emit(str(event.data))
                
            elif event.event_type == EventType.ENTITIES_DETECTED:
                entities = event.data if isinstance(event.data, list) else []
                self.entitiesDetected.emit(entities)
                
            elif event.event_type == EventType.MODE_CHANGED:
                self.modeChanged.emit(str(event.data))
                
            elif event.event_type == EventType.CONFIG_UPDATED:
                config = event.data if isinstance(event.data, dict) else {}
                self.configUpdated.emit(config)
                
            elif event.event_type == EventType.UI_STATE_CHANGED:
                component = event.metadata.get('component', 'unknown')
                state = event.data if isinstance(event.data, dict) else {}
                self.uiStateChanged.emit(component, state)
                
            elif event.event_type == EventType.COMPLETION_TRIGGERED:
                text = event.data.get('text', '') if isinstance(event.data, dict) else ''
                cursor_pos = event.data.get('cursor_pos', 0) if isinstance(event.data, dict) else 0
                self.completionTriggered.emit(text, cursor_pos)
            
            # 处理自定义事件处理器
            if event.event_type in self._event_handlers:
                for handler in self._event_handlers[event.event_type]:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"自定义事件处理器错误: {e}")
                        
        except Exception as e:
            logger.error(f"事件分发错误: {e}, 事件类型: {event.event_type}")
    
    def subscribe(self, event_type: EventType, handler: Callable[[PromptEvent], None]):
        """订阅特定类型的事件"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        
        self._event_handlers[event_type].append(handler)
        logger.debug(f"订阅事件类型: {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[PromptEvent], None]):
        """取消订阅事件"""
        if event_type in self._event_handlers:
            if handler in self._event_handlers[event_type]:
                self._event_handlers[event_type].remove(handler)
                logger.debug(f"取消订阅事件类型: {event_type.value}")
    
    def _record_event(self, event: PromptEvent):
        """记录事件历史"""
        self._event_history.append(event)
        
        # 保持历史记录在限制范围内
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
    
    def get_event_history(self, event_type: EventType = None, 
                         limit: int = 100) -> List[PromptEvent]:
        """获取事件历史记录"""
        history = self._event_history
        
        # 按事件类型过滤
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        # 限制返回数量
        return history[-limit:] if limit else history
    
    def clear_history(self):
        """清空事件历史"""
        self._event_history.clear()
        logger.info("事件历史已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取事件总线统计信息"""
        event_counts = {}
        for event in self._event_history:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        return {
            'total_events': len(self._event_history),
            'event_counts': event_counts,
            'subscribers': {et.value: len(handlers) for et, handlers in self._event_handlers.items()},
            'max_history': self._max_history
        }


class PromptServiceContainer:
    """提示词服务容器 - 依赖注入和服务管理"""
    
    def __init__(self, shared=None, config=None):
        self.shared = shared
        self.config = config
        self._services = {}
        self._initialized = False
        
        logger.info("PromptServiceContainer 初始化开始")
    
    def initialize(self):
        """初始化所有服务"""
        if self._initialized:
            logger.warning("服务容器已经初始化")
            return
        
        try:
            # 1. 创建事件总线 - 核心通信机制
            self._services['event_bus'] = PromptEventBus()
            
            # 2. 导入并创建提示词管理器
            from .simple_prompt_service import SinglePromptManager
            self._services['prompt_manager'] = SinglePromptManager(self.shared, self.config)
            
            # 3. 连接服务间的事件通信
            self._connect_services()
            
            self._initialized = True
            logger.info("PromptServiceContainer 初始化完成")
            
        except Exception as e:
            logger.error(f"PromptServiceContainer 初始化失败: {e}")
            raise
    
    def _connect_services(self):
        """连接服务间的事件通信"""
        event_bus = self._services['event_bus']
        prompt_manager = self._services['prompt_manager']
        
        # 提示词请求处理
        def handle_prompt_request(event: PromptEvent):
            try:
                context = event.data
                prompt = prompt_manager.generate_prompt(context)
                
                # 发布提示词生成完成事件
                generated_event = PromptEvent(
                    event_type=EventType.PROMPT_GENERATED,
                    data={'prompt': prompt, 'context': context},
                    source='prompt_manager'
                )
                event_bus.emit_event(generated_event)
                
            except Exception as e:
                logger.error(f"提示词请求处理失败: {e}")
        
        # 订阅提示词请求事件
        event_bus.subscribe(EventType.PROMPT_REQUESTED, handle_prompt_request)
        
        # 连接提示词管理器的信号到事件总线
        prompt_manager.promptGenerated.connect(
            lambda prompt: event_bus.emit_event(
                PromptEvent(EventType.PROMPT_GENERATED, prompt, 'prompt_manager')
            )
        )
        
        prompt_manager.contextUpdated.connect(
            lambda context: event_bus.emit_event(
                PromptEvent(EventType.CONTEXT_UPDATED, context, 'prompt_manager')
            )
        )
        
        prompt_manager.tagsChanged.connect(
            lambda tags: event_bus.emit_event(
                PromptEvent(EventType.TAGS_CHANGED, tags, 'prompt_manager')
            )
        )
        
        logger.info("服务间事件通信连接完成")
    
    def get_service(self, name: str):
        """获取服务实例"""
        if not self._initialized:
            self.initialize()
        
        return self._services.get(name)
    
    def register_service(self, name: str, service: Any):
        """注册新服务"""
        self._services[name] = service
        logger.info(f"服务已注册: {name}")
    
    def has_service(self, name: str) -> bool:
        """检查服务是否存在"""
        return name in self._services
    
    def get_all_services(self) -> Dict[str, Any]:
        """获取所有服务"""
        return self._services.copy()
    
    def shutdown(self):
        """关闭服务容器"""
        logger.info("PromptServiceContainer 关闭中...")
        
        # 清理事件总线
        if 'event_bus' in self._services:
            self._services['event_bus'].clear_history()
        
        # 清理缓存
        if 'prompt_manager' in self._services:
            self._services['prompt_manager'].clear_cache()
        
        self._services.clear()
        self._initialized = False
        logger.info("PromptServiceContainer 已关闭")


# 全局服务容器实例 - 单例模式
_global_container = None


def get_global_container(shared=None, config=None) -> PromptServiceContainer:
    """获取全局服务容器实例"""
    global _global_container
    
    if _global_container is None:
        _global_container = PromptServiceContainer(shared, config)
        _global_container.initialize()
    
    return _global_container


def get_event_bus() -> Optional[PromptEventBus]:
    """获取全局事件总线实例"""
    container = get_global_container()
    return container.get_service('event_bus')


def get_prompt_manager():
    """获取全局提示词管理器实例"""
    container = get_global_container()
    return container.get_service('prompt_manager')


# 便捷的事件发布函数
def emit_prompt_request(context):
    """发布提示词请求事件"""
    event_bus = get_event_bus()
    if event_bus:
        event = PromptEvent(EventType.PROMPT_REQUESTED, context, 'api')
        event_bus.emit_event(event)


def emit_tags_changed(tags: List[str]):
    """发布标签变化事件"""
    event_bus = get_event_bus()
    if event_bus:
        event = PromptEvent(EventType.TAGS_CHANGED, tags, 'ui')
        event_bus.emit_event(event)


def emit_mode_changed(mode: str):
    """发布模式变化事件"""
    event_bus = get_event_bus()
    if event_bus:
        event = PromptEvent(EventType.MODE_CHANGED, mode, 'ui')
        event_bus.emit_event(event)