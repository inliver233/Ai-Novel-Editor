"""
增强AI管理器 - 集成所有AI子系统的完整解决方案

整合SimpleAIManager的基础功能，并集成：
- 简化提示词系统 (SinglePromptManager)
- Codex系统访问
- RAG服务集成
- 智能上下文构建
- 动态提示词生成

解决当前AI补全系统的4大关键问题
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
import time
import hashlib

logger = logging.getLogger(__name__)

# 尝试导入必要组件
try:
    from core.ai_qt_client import QtAIClient
    from core.config import Config
    from core.simple_prompt_service import (
        SinglePromptManager, SimplePromptContext, 
        PromptMode, CompletionType
    )
    from core.prompt_functions import PromptFunctionRegistry, PromptContext
    AI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI组件不可用: {e}")
    AI_AVAILABLE = False


from application.ai_completion_service import AICompletionService
from application.ai_context import DynamicPromptGenerator, IntelligentContextBuilder


class EnhancedAIManager(QObject):
    """
    增强AI管理器 - 集成所有AI子系统的完整解决方案
    
    解决当前系统的4大关键问题：
    1. 集成简化提示词系统
    2. 修复Codex系统集成
    3. 集成RAG配置和功能
    4. 实现智能上下文构建
    """
    
    # 信号定义 - 保持与SimpleAIManager兼容
    completionReady = pyqtSignal(str, str)      # (completion_text, context)
    completionReceived = pyqtSignal(str, dict)  # (response, metadata)
    completionError = pyqtSignal(str)           # (error_message)
    streamUpdate = pyqtSignal(str)              # (partial_text)
    configChanged = pyqtSignal()                # 配置更改信号
    
    def __init__(self, config: Config, shared=None, parent: QWidget = None):
        super().__init__(parent)
        self._config = config
        self._shared = shared
        self._parent = parent
        self._task_manager = getattr(shared, "task_manager", None) if shared else None
        self._cancelled_task_keys: set[str] = set()
        self._ai_service = AICompletionService(
            config,
            shared,
            task_manager=self._task_manager,
            cancelled_task_keys=self._cancelled_task_keys,
        )

        if self._shared and hasattr(self._shared, "projectChanged"):
            try:
                self._shared.projectChanged.connect(self._on_project_changed)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                logger.debug("EnhancedAIManager: failed to connect projectChanged: %s", exc)
        
        # 基础AI组件
        self._ai_client = None
        self._completion_enabled = True
        self._auto_trigger_enabled = True
        self._trigger_delay = 1000  # ms
        self._punctuation_assist_enabled = True
        self._completion_mode = "manual_ai"  # 修复：默认为手动模式
        self._context_mode = "balanced"
        self._style_tags = []
        
        # 增强功能组件
        # 由应用层服务统一管理上下文/提示词/请求调度
        
        # Codex系统组件
        self._codex_manager = None
        self._reference_detector = None
        self._prompt_function_registry = None
        
        # 性能管理
        self._current_editor = None
        
        # 配置缓存
        self._rag_config = {}
        self._prompt_config = {}
        self._completion_config = {}
        
        # 初始化所有子系统
        self._init_ai_client()
        self._init_enhanced_components()
        self._load_configurations()
        
        # 补全触发定时器
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._trigger_completion)
        
        logger.info("EnhancedAIManager初始化完成")

    @pyqtSlot(str)
    def _on_project_changed(self, project_path: str) -> None:
        if not self._shared or not self._ai_service:
            return

        try:
            context_builder = getattr(self._ai_service, "context_builder", None)
            if context_builder is None:
                return
            context_builder.rag_service = getattr(self._shared, "rag_service", None)
            context_builder.codex_manager = getattr(self._shared, "codex_manager", None)
            context_builder.reference_detector = getattr(self._shared, "reference_detector", None)
        except Exception:  # noqa: BLE001
            logger.exception("EnhancedAIManager: failed to refresh shared references on projectChanged")
    
    def _init_ai_client(self):
        """初始化AI客户端"""
        if not AI_AVAILABLE:
            logger.warning("AI组件不可用，禁用AI功能")
            return
        
        try:
            ai_config = self._config.get_ai_config()
            
            if ai_config:
                # 清理旧客户端
                if self._ai_client:
                    try:
                        self._ai_client.cleanup()
                    except:
                        pass
                    self._ai_client = None
                
                # 创建新的AI客户端
                self._ai_client = QtAIClient(ai_config, self)
                if self._ai_service:
                    self._ai_service.update_ai_client(self._ai_client)
                
                # 连接信号
                self._ai_client.responseReceived.connect(self._on_completion_ready)
                self._ai_client.errorOccurred.connect(self._on_completion_error)
                if hasattr(self._ai_client, 'streamChunkReceived'):
                    self._ai_client.streamChunkReceived.connect(self._on_stream_update)
                
                logger.info(f"AI客户端初始化成功: {ai_config.provider.value if hasattr(ai_config, 'provider') else 'unknown'}")
            else:
                logger.warning("AI配置无效，无法初始化AI客户端")
                if self._ai_service:
                    self._ai_service.update_ai_client(None)
                
        except Exception as e:
            logger.error(f"AI客户端初始化失败: {e}")
            self._ai_client = None
            if self._ai_service:
                self._ai_service.update_ai_client(None)
    
    def _init_enhanced_components(self):
        """初始化增强功能组件"""
        if not self._shared:
            logger.warning("Shared对象未提供，增强功能可能受限")
            return
        
        # 获取Codex系统组件
        self._codex_manager = getattr(self._shared, 'codex_manager', None)
        
        # 初始化提示词函数注册表
        if hasattr(self._shared, 'prompt_function_registry'):
            self._prompt_function_registry = self._shared.prompt_function_registry
        
        logger.info(f"增强组件初始化 - Codex: {bool(self._codex_manager)}, 函数注册表: {bool(self._prompt_function_registry)}")
    
    def _load_configurations(self):
        """加载所有配置"""
        try:
            self._rag_config = self._config.get_rag_config()
            self._prompt_config = self._config.get_prompt_config()
            self._completion_config = self._config.get_completion_config()
            
            logger.info(f"配置加载完成 - RAG: {self._rag_config.get('enabled', False)}, 提示词标签: {len(self._prompt_config.get('style_tags', []))}")
            
            # 更新子组件配置
            if self._ai_service:
                self._ai_service.update_configs(self._rag_config, self._prompt_config)
                
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        self._load_configurations()
        # 重新初始化AI客户端以应用新配置
        self._init_ai_client()
        self.configChanged.emit()
    
    def get_rag_config(self) -> Dict[str, Any]:
        """获取RAG配置"""
        return getattr(self, '_rag_config', {}).copy()
    
    def get_prompt_config(self) -> Dict[str, Any]:
        """获取提示词配置"""
        return getattr(self, '_prompt_config', {}).copy()
    
    def get_completion_config(self) -> Dict[str, Any]:
        """获取补全配置"""
        return getattr(self, '_completion_config', {}).copy()
    
    def integrate_codex_system(self, codex_manager=None, reference_detector=None, prompt_function_registry=None):
        """
        集成Codex系统 - 修复原有的集成问题
        
        Args:
            codex_manager: Codex管理器实例
            reference_detector: 引用检测器实例
            prompt_function_registry: 提示词函数注册表
        """
        if codex_manager:
            self._codex_manager = codex_manager
            
        if reference_detector:
            self._reference_detector = reference_detector
            
        if prompt_function_registry:
            self._prompt_function_registry = prompt_function_registry

        if self._ai_service:
            self._ai_service.integrate_codex_system(
                codex_manager=codex_manager,
                reference_detector=reference_detector,
            )
        
        logger.info("Codex系统集成完成 - 增强AI管理器现在可以完全访问Codex数据")

    def set_task_manager(self, task_manager) -> None:
        """绑定TaskManager实例（用于统一取消/去重/错误上报）"""
        self._task_manager = task_manager
        if self._ai_service:
            self._ai_service.update_task_manager(task_manager)

    def _get_ai_task_key(self, editor=None) -> str:
        editor_obj = editor or getattr(self, "_current_editor", None)
        editor_id = None
        if editor_obj is not None:
            editor_id = getattr(editor_obj, "objectName", None) or str(id(editor_obj))
        if not editor_id:
            editor_id = "unknown"
        return f"ai/complete/request:{editor_id}"

    def cancel_ai_completion(self, editor=None) -> bool:
        """取消当前AI补全请求（协作式取消 + TaskManager统一通道）"""
        task_key = self._get_ai_task_key(editor)
        self._cancelled_task_keys.add(task_key)
        cancelled = False
        if self._task_manager:
            try:
                cancelled = self._task_manager.cancel(task_key) or cancelled
            except Exception as e:
                logger.warning(f"TaskManager cancel failed for {task_key}: {e}")
        if self._ai_client:
            try:
                self._ai_client.cancel_request()
                cancelled = True
            except Exception as e:
                logger.warning(f"AI client cancel failed: {e}")
        return cancelled
    
    def request_completion(self, context_or_mode=None, cursor_position: int = -1, 
                         user_tags: List[str] = None, completion_type: str = "text") -> bool:
        """
        请求AI补全 - 增强版本，支持完整的上下文分析
        
        Args:
            context_or_mode: 上下文文本或兼容模式
            cursor_position: 光标位置
            user_tags: 用户选择的风格标签
            completion_type: 补全类型
        
        Returns:
            bool: 是否成功发起请求
        """
        # 兼容性处理
        if isinstance(context_or_mode, str) and context_or_mode in ['manual', 'auto']:
            if hasattr(self, '_current_editor') and self._current_editor:
                cursor = self._current_editor.textCursor()
                context = self._current_editor.toPlainText()
                cursor_position = cursor.position()
                logger.debug(f"补全请求模式: {context_or_mode}")
            else:
                logger.warning("编辑器未设置，无法获取上下文")
                return False
        else:
            context = context_or_mode or ""
        
        if not self._completion_enabled or not self._ai_client:
            logger.warning("AI补全不可用")
            return False
        
        # 缓存系统已移除，直接进行AI请求
        
        try:
            # 如果已有任务在跑，先取消（可取消/去重）
            self.cancel_ai_completion(self._current_editor)

            # 1. 由应用层服务统一完成上下文、提示词与请求调度
            context_mode = self._get_context_mode()
            task_key = self._get_ai_task_key(self._current_editor)

            if not self._ai_service:
                raise RuntimeError("AI补全服务未初始化")

            dispatched = self._ai_service.dispatch_completion(
                context=context,
                cursor_position=cursor_position,
                user_tags=user_tags or [],
                completion_type=completion_type,
                context_mode=context_mode,
                task_key=task_key,
            )

            if not dispatched:
                return False
            
            logger.info(f"增强AI补全请求已发送 - 类型: {completion_type}, 标签: {user_tags}")
            return True
            
        except Exception as e:
            logger.error(f"增强AI补全请求失败: {e}")
            self.completionError.emit(f"补全请求失败: {str(e)}")
            return False
    
    def request_completion_with_tags(self, context: str, cursor_position: int,
                                   tags: List[str], completion_type: str = "text") -> bool:
        """
        带标签的补全请求 - 新增接口
        
        Args:
            context: 文本上下文
            cursor_position: 光标位置
            tags: 风格标签列表
            completion_type: 补全类型
        
        Returns:
            bool: 是否成功发起请求
        """
        return self.request_completion(context, cursor_position, tags, completion_type)
    
    def _get_context_mode(self) -> str:
        """获取当前上下文模式"""
        # 从配置或shared获取用户设置的上下文模式
        if hasattr(self, '_context_mode'):
            return self._context_mode
        
        # 默认平衡模式
        return "balanced"
    
    # 缓存系统已完全移除
    
    # 信号处理 - 增强版本
    @pyqtSlot(str, dict)
    def _on_completion_ready(self, response: str, context: dict):
        """处理补全完成 - 增强版本"""
        try:
            cancel_token = context.get("cancel_token")
            task_key = context.get("task_key")
            if cancel_token is not None and getattr(cancel_token, "cancelled", False):
                logger.info("AI补全已取消，忽略响应")
                if self._task_manager and task_key:
                    self._task_manager.finish_external(task_key, result=None)
                return
            if task_key and task_key in self._cancelled_task_keys:
                logger.info("AI补全已取消（标记），忽略响应")
                self._cancelled_task_keys.discard(task_key)
                if self._task_manager and task_key:
                    self._task_manager.finish_external(task_key, result=None)
                return

            # 清理和格式化响应（交给应用层渲染）
            if not self._ai_service:
                raise RuntimeError("AI补全服务未初始化")
            completion, metadata = self._ai_service.format_completion(response, context)

            # 发送信号
            self.completionReady.emit(completion, metadata.get('context', ''))
            self.completionReceived.emit(completion, metadata)

            if self._task_manager and task_key:
                self._task_manager.finish_external(task_key, result=completion)
            
            logger.info(f"增强AI补全完成 - 长度: {len(completion)}, 类型: {metadata.get('completion_type', 'text')}")
            
        except Exception as e:
            logger.error(f"处理增强补全响应失败: {e}")
            self.completionError.emit(f"处理响应失败: {str(e)}")
    
    @pyqtSlot(str, dict)
    def _on_completion_error(self, error: str, context: dict):
        """处理补全错误"""
        cancel_token = context.get("cancel_token")
        task_key = context.get("task_key")
        if cancel_token is not None and getattr(cancel_token, "cancelled", False):
            logger.info("AI补全错误已取消，忽略错误上报")
            if self._task_manager and task_key:
                self._task_manager.finish_external(task_key, result=None)
            return
        if task_key and task_key in self._cancelled_task_keys:
            logger.info("AI补全错误已取消（标记），忽略错误上报")
            self._cancelled_task_keys.discard(task_key)
            if self._task_manager and task_key:
                self._task_manager.finish_external(task_key, result=None)
            return
        logger.error(f"AI补全错误: {error}")
        if self._task_manager and task_key:
            details = {
                "exception_type": "AIClientError",
                "message": error,
                "description": "AI completion request",
            }
            self._task_manager.fail_external(task_key, error, details)
        self.completionError.emit(error)
    
    @pyqtSlot(str, dict)
    def _on_stream_update(self, partial_text: str, context: dict):
        """处理流式更新"""
        cancel_token = context.get("cancel_token")
        if cancel_token is not None and getattr(cancel_token, "cancelled", False):
            return
        self.streamUpdate.emit(partial_text)
    
    # 兼容性方法 - 保持与SimpleAIManager的接口兼容
    def set_completion_enabled(self, enabled: bool):
        """设置补全是否启用"""
        self._completion_enabled = enabled
        logger.info(f"增强AI补全{'启用' if enabled else '禁用'}")
    
    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发是否启用"""
        self._auto_trigger_enabled = enabled
        if not enabled:
            self._completion_timer.stop()
        logger.info(f"自动触发{'启用' if enabled else '禁用'}")
    
    def set_context_mode(self, mode: str):
        """设置上下文模式"""
        self._context_mode = mode
        logger.info(f"上下文模式设置为: {mode}")
    
    def set_style_tags(self, tags: List[str]):
        """设置默认风格标签"""
        self._default_style_tags = tags
        logger.info(f"默认风格标签: {tags}")
    
    def get_available_tags(self) -> Dict[str, List[str]]:
        """获取可用的风格标签"""
        if self._ai_service:
            return self._ai_service.get_available_tags()
        
        # 降级返回基础标签
        return {
            "风格": ["科幻", "武侠", "都市", "奇幻", "历史"],
            "情节": ["悬疑", "浪漫", "动作", "日常", "高潮"],
            "视角": ["第一人称", "第三人称", "全知视角"]
        }
    
    def is_available(self) -> bool:
        """检查增强AI功能是否可用"""
        return AI_AVAILABLE and self._ai_client is not None
    
    def get_status(self) -> Dict[str, Any]:
        """获取增强状态信息"""
        return {
            'available': self.is_available(),
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'trigger_delay': self._trigger_delay,
            'cache_enabled': False,  # 缓存已禁用
            'enhanced_features': {
                'codex_integration': bool(self._codex_manager),
                'rag_available': bool(self._ai_service and self._ai_service.has_rag_service()),
                'prompt_manager': bool(self._ai_service and self._ai_service.has_prompt_manager())
            }
        }
    
    def cleanup(self):
        """清理资源"""
        self._completion_timer.stop()
        self.clear_cache()
        if self._ai_client:
            self._ai_client.deleteLater()
        logger.info("EnhancedAIManager已清理")
    
    def clear_cache(self):
        """清空缓存（缓存已移除，保持接口兼容性）"""
        if self._ai_service:
            self._ai_service.clear_cache()
        logger.info("增强AI补全缓存已移除，此方法保持兼容性")
    
    # 自动触发功能
    def schedule_completion(self, context: str, cursor_position: int = -1, 
                          tags: List[str] = None, completion_type: str = "text"):
        """调度自动补全 - 增强版本"""
        if not self._auto_trigger_enabled:
            return
        
        # 存储参数供定时器使用
        self._scheduled_context = context
        self._scheduled_cursor_position = cursor_position
        self._scheduled_tags = tags
        self._scheduled_completion_type = completion_type
        
        # 重启定时器
        self._completion_timer.stop()
        self._completion_timer.start(self._trigger_delay)
    
    def _trigger_completion(self):
        """定时器触发的补全"""
        if hasattr(self, '_scheduled_context'):
            self.request_completion(
                self._scheduled_context,
                self._scheduled_cursor_position,
                getattr(self, '_scheduled_tags', None),
                getattr(self, '_scheduled_completion_type', 'text')
            )
    
    # 编辑器管理
    def set_editor(self, editor):
        """设置当前编辑器"""
        if hasattr(self, '_current_editor') and self._current_editor:
            # 断开旧编辑器的信号
            try:
                self._current_editor.textChanged.disconnect(self._on_text_changed)
                self._current_editor.cursorPositionChanged.disconnect(self._on_cursor_changed)
                if hasattr(self._current_editor, '_smart_completion'):
                    self._current_editor._smart_completion.aiCompletionRequested.disconnect(self._on_ai_completion_requested)
            except:
                pass

        self._current_editor = editor

        if editor:
            # 连接新编辑器的信号
            editor.textChanged.connect(self._on_text_changed)
            editor.cursorPositionChanged.connect(self._on_cursor_changed)

            # 连接智能补全管理器的AI补全请求信号
            if hasattr(editor, '_smart_completion'):
                editor._smart_completion.aiCompletionRequested.connect(self._on_ai_completion_requested)
                logger.debug("Connected enhanced smart completion AI request signal")

            logger.debug("Editor set for EnhancedAIManager")
    
    def _on_text_changed(self):
        """处理文本变化"""
        # 修复：只有在自动AI模式下才允许自动触发
        if (not self._auto_trigger_enabled or 
            not self._current_editor or 
            getattr(self, '_completion_mode', 'manual_ai') != 'auto_ai'):
            return
        
        # 获取当前文本和光标位置
        cursor = self._current_editor.textCursor()
        context = self._current_editor.toPlainText() or ""
        cursor_pos = cursor.position()

        # 空/短文本不触发自动补全（避免空白项目“自发补全”和无意义RAG查询）
        try:
            min_chars = int(self._config.get("ai", "min_chars", 3) or 3)
        except Exception:
            min_chars = 3
        if len(context.strip()) < max(1, min_chars):
            return

        # 无项目路径时不触发自动补全（避免跨项目检索泄露/污染）
        project_path = getattr(self._shared, "current_project_path", None) if self._shared else None
        if not project_path:
            return
        
        # 调度自动补全
        self.schedule_completion(context, cursor_pos)
    
    def _on_cursor_changed(self):
        """处理光标位置变化"""
        # 光标变化时停止当前补全计时器
        if hasattr(self, '_completion_timer'):
            self._completion_timer.stop()
    
    def _on_ai_completion_requested(self, text: str, context: dict):
        """处理AI补全请求 - 增强版本"""
        cursor_pos = context.get('cursor_position', -1)
        tags = context.get('user_tags', [])
        completion_type = context.get('completion_type', 'text')
        
        self.request_completion(text, cursor_pos, tags, completion_type)
    
    # 为了保持完全兼容性，添加SimpleAIManager的所有公共方法
    def get_ai_status(self):
        """获取AI状态（兼容性方法）"""
        ai_config = self._config.get_section('ai')
        status = self.get_status()
        return {
            'available': status['available'],
            'ai_client_available': status['available'],
            'rag_service_available': status['enhanced_features']['rag_available'],
            'enabled': self._completion_enabled,
            'provider': ai_config.get('provider', 'unknown'),
            'model': ai_config.get('model', 'unknown'),
            'enhanced': True  # 标记为增强版本
        }
    
    def diagnose_ai_completion_issues(self) -> Dict[str, Any]:
        """诊断AI补全问题 - 增强版本"""
        issues = []
        
        if not self.is_available():
            issues.append("AI客户端不可用")
        if not self._completion_enabled:
            issues.append("AI补全已禁用")
        if not hasattr(self, '_current_editor') or not self._current_editor:
            issues.append("编辑器未设置")
        if not self._codex_manager:
            issues.append("Codex系统未集成")
        if not self._ai_service or not self._ai_service.has_rag_service():
            issues.append("RAG服务不可用")
            
        return {
            'issues': issues,
            'ai_available': self.is_available(),
            'completion_enabled': self._completion_enabled,
            'editor_set': hasattr(self, '_current_editor') and self._current_editor is not None,
            'enhanced_features': self.get_status()['enhanced_features']
        }

    # ============== 关键兼容性方法 ==============
    
    def set_punctuation_assist_enabled(self, enabled: bool):
        """设置标点辅助功能启用状态"""
        if not hasattr(self, '_punctuation_assist_enabled'):
            self._punctuation_assist_enabled = True
        self._punctuation_assist_enabled = enabled
        logger.debug(f"标点辅助设置为: {enabled}")
        self.configChanged.emit()
    
    def set_completion_enabled(self, enabled: bool):
        """设置AI补全启用状态"""
        self._completion_enabled = enabled
        logger.debug(f"AI补全设置为: {enabled}")
        self.configChanged.emit()
    
    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发启用状态"""
        self._auto_trigger_enabled = enabled
        logger.debug(f"自动触发设置为: {enabled}")
        self.configChanged.emit()
    
    def set_trigger_delay(self, delay_ms: int):
        """设置触发延迟"""
        self._trigger_delay = max(100, min(5000, delay_ms))
        logger.debug(f"触发延迟设置为: {self._trigger_delay}ms")
        self.configChanged.emit()
    
    def set_completion_mode(self, mode: str):
        """设置补全模式"""
        if not hasattr(self, '_completion_mode'):
            self._completion_mode = "manual_ai"  # 修复：默认为手动模式
        self._completion_mode = mode
        logger.debug(f"补全模式设置为: {mode}")
        self.configChanged.emit()
    
    def set_context_mode(self, mode: str):
        """设置上下文模式"""
        if not hasattr(self, '_context_mode'):
            self._context_mode = "balanced"
        self._context_mode = mode
        logger.debug(f"上下文模式设置为: {mode}")
        self.configChanged.emit()
    
    def set_style_tags(self, tags: List[str]):
        """设置风格标签"""
        if not hasattr(self, '_style_tags'):
            self._style_tags = []
        self._style_tags = tags.copy() if tags else []
        logger.debug(f"风格标签设置为: {self._style_tags}")
        self.configChanged.emit()
    
    def show_config_dialog(self, parent=None):
        """显示配置对话框"""
        try:
            from .unified_ai_config_dialog import UnifiedAIConfigDialog
            dialog = UnifiedAIConfigDialog(parent, self._config)
            dialog.configSaved.connect(self._on_unified_config_saved)
            return dialog.exec()
        except Exception as e:
            logger.error(f"显示配置对话框失败: {e}")
            return False
    
    def _on_unified_config_saved(self, config: Dict[str, Any]):
        """处理统一配置保存"""
        try:
            logger.info("处理统一配置保存...")
            self.reload_config()
            self.configChanged.emit()
            logger.info("配置保存处理完成")
        except Exception as e:
            logger.error(f"处理配置保存失败: {e}")
    
    def show_index_manager(self, parent=None, project_manager=None):
        """显示索引管理器"""
        try:
            from ..dialogs.rag_index_dialog import RAGIndexDialog
            
            # 使用传入的project_manager或从shared获取
            if not project_manager and hasattr(self._shared, 'project_manager'):
                project_manager = self._shared.project_manager
                
            dialog = RAGIndexDialog(
                ai_manager=self,
                project_manager=project_manager,
                parent=parent or self._parent
            )
            dialog.exec()
            
        except ImportError as e:
            logger.error(f"导入索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                parent or self._parent,
                "索引管理",
                "索引管理对话框不可用。\n请通过AI配置对话框中的'RAG向量搜索'页面进行基本配置。"
            )
        except Exception as e:
            logger.error(f"显示索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent or self._parent,
                "错误",
                f"无法打开索引管理对话框：{str(e)}"
            )
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """获取可用模板列表"""
        try:
            # 如果有prompt_manager且支持模板，使用其功能
            if self.prompt_manager and hasattr(self.prompt_manager, 'get_all_templates'):
                return self.prompt_manager.get_all_templates()
            
            # 否则返回增强版的默认模板列表
            return [
                {
                    'id': 'enhanced_creative',
                    'name': '增强创意写作',
                    'description': '集成Codex知识库的高级创意写作模板',
                    'category': 'enhanced'
                },
                {
                    'id': 'context_aware_dialogue',
                    'name': '上下文感知对话',
                    'description': '基于角色背景和情境的智能对话生成',
                    'category': 'dialogue'
                },
                {
                    'id': 'scene_continuation',
                    'name': '场景续写',
                    'description': '考虑前文情节和角色状态的场景续写',
                    'category': 'continuation'
                },
                {
                    'id': 'rag_enhanced_writing',
                    'name': 'RAG增强写作',
                    'description': '利用历史内容检索的智能写作助手',
                    'category': 'rag'
                }
            ]
        except Exception as e:
            logger.error(f"获取模板列表失败: {e}")
            return []
    
    def get_current_template_id(self, mode: str) -> str:
        """获取当前模板ID"""
        try:
            if self.prompt_manager and hasattr(self.prompt_manager, 'get_current_template'):
                return self.prompt_manager.get_current_template(mode)
            
            # 根据模式返回默认模板
            mode_templates = {
                'creative': 'enhanced_creative',
                'dialogue': 'context_aware_dialogue', 
                'continuation': 'scene_continuation',
                'rag': 'rag_enhanced_writing'
            }
            return mode_templates.get(mode, 'enhanced_creative')
        except Exception as e:
            logger.error(f"获取当前模板ID失败: {e}")
            return 'enhanced_creative'
    
    def open_template_manager(self, parent=None):
        """打开模板管理器"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            parent or self._parent,
            "模板管理",
            "增强AI系统的模板管理已集成到统一配置对话框中。\n"
            "请通过AI配置对话框中的'智能提示词'页面管理模板。"
        )
    
    def index_document_sync(self, document_id: str, content: str, cancel_token=None) -> bool:
        """同步索引文档"""
        try:
            logger.info(f"增强AI管理器同步索引文档: {document_id}")
            
            # 检查RAG服务是否可用
            if not self.rag_service:
                logger.warning(f"RAG服务不可用，无法索引文档: {document_id}")
                return False

            if cancel_token is not None and getattr(cancel_token, "cancelled", False):
                logger.info("索引任务已取消，跳过: %s", document_id)
                return False
                
            # 使用RAG服务的index_document方法
            success = self.rag_service.index_document(document_id, content, cancel_token=cancel_token)
            
            if success:
                logger.info(f"文档索引成功: {document_id}")
            else:
                logger.warning(f"文档索引失败: {document_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"同步索引文档异常 {document_id}: {e}")
            return False
    
    def delete_document_index(self, document_id: str):
        """删除文档索引"""
        try:
            logger.info(f"删除文档索引: {document_id}")
            
            if not self.rag_service or not self.rag_service._vector_store:
                logger.warning(f"RAG服务或向量存储不可用，无法删除索引: {document_id}")
                return
                
            # 如果向量存储有删除方法，使用它
            if hasattr(self.rag_service._vector_store, 'delete_document'):
                self.rag_service._vector_store.delete_document(document_id)
                logger.info(f"文档索引删除成功: {document_id}")
            else:
                logger.warning(f"向量存储不支持文档删除: {document_id}")
                
        except Exception as e:
            logger.error(f"删除文档索引异常 {document_id}: {e}")
    
    def force_reinit_ai(self) -> bool:
        """强制重新初始化AI客户端"""
        try:
            logger.info("强制重新初始化AI客户端...")
            self._init_ai_client()
            return self._ai_client is not None
        except Exception as e:
            logger.error(f"强制重新初始化AI客户端失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止定时器
            if hasattr(self, '_completion_timer'):
                self._completion_timer.stop()
            
            # 清理AI客户端
            if self._ai_client:
                try:
                    self._ai_client.cleanup()
                except:
                    pass
                self._ai_client = None
            
            # 断开编辑器连接
            if hasattr(self, '_current_editor') and self._current_editor:
                try:
                    self._current_editor.textChanged.disconnect(self._on_text_changed)
                    self._current_editor.cursorPositionChanged.disconnect(self._on_cursor_changed)
                except:
                    pass
                self._current_editor = None
            
            # 缓存已移除，无需清理
            
            logger.info("EnhancedAIManager资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
    
    # ============== 额外兼容性方法 ==============
    
    def update_completion_settings(self, settings: Dict[str, Any]):
        """更新补全设置"""
        try:
            if 'completion_enabled' in settings:
                self.set_completion_enabled(settings['completion_enabled'])
            if 'auto_trigger_enabled' in settings:
                self.set_auto_trigger_enabled(settings['auto_trigger_enabled'])
            if 'punctuation_assist' in settings:
                self.set_punctuation_assist_enabled(settings['punctuation_assist'])
            if 'trigger_delay' in settings:
                self.set_trigger_delay(settings['trigger_delay'])
            if 'completion_mode' in settings:
                self.set_completion_mode(settings['completion_mode'])
            if 'context_mode' in settings:
                self.set_context_mode(settings['context_mode'])
            
            logger.info("补全设置更新完成")
        except Exception as e:
            logger.error(f"更新补全设置失败: {e}")
    
    def schedule_completion(self, context: str, cursor_position: int = -1):
        """调度自动补全"""
        try:
            # 重置并启动定时器
            self._completion_timer.stop()
            self._completion_timer.timeout.disconnect()
            self._completion_timer.timeout.connect(
                lambda: self.request_completion(context, cursor_position)
            )
            self._completion_timer.start(self._trigger_delay)
        except Exception as e:
            logger.error(f"调度补全失败: {e}")
    
    def start_stream_response(self, text: str):
        """开始流式响应"""
        try:
            logger.debug(f"开始流式响应: {text[:50]}...")
            # 发送流式更新信号
            self.streamUpdate.emit(text)
        except Exception as e:
            logger.error(f"流式响应失败: {e}")
    
    def get_context_mode(self) -> str:
        """获取当前上下文模式"""
        return getattr(self, '_context_mode', 'balanced')
    
    def get_completion_stats(self) -> Dict[str, Any]:
        """获取补全统计信息"""
        return {
            'cache_enabled': False,  # 缓存已禁用
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'punctuation_assist_enabled': getattr(self, '_punctuation_assist_enabled', True),
            'trigger_delay': self._trigger_delay
        }
    
    def clear_cache(self):
        """清空补全缓存（缓存已移除，保持接口兼容性）"""
        logger.info("补全缓存已移除，此方法保持兼容性")
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return {
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'punctuation_assist_enabled': getattr(self, '_punctuation_assist_enabled', True),
            'trigger_delay': self._trigger_delay,
            'completion_mode': getattr(self, '_completion_mode', 'auto_ai'),
            'context_mode': getattr(self, '_context_mode', 'balanced'),
            'style_tags': getattr(self, '_style_tags', []),
            'rag_config': self.get_rag_config(),
            'prompt_config': self.get_prompt_config(),
            'completion_config': self.get_completion_config()
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置完整配置"""
        try:
            if 'completion_enabled' in config:
                self.set_completion_enabled(config['completion_enabled'])
            if 'auto_trigger_enabled' in config:
                self.set_auto_trigger_enabled(config['auto_trigger_enabled'])
            if 'punctuation_assist_enabled' in config:
                self.set_punctuation_assist_enabled(config['punctuation_assist_enabled'])
            if 'trigger_delay' in config:
                self.set_trigger_delay(config['trigger_delay'])
            if 'completion_mode' in config:
                self.set_completion_mode(config['completion_mode'])
            if 'context_mode' in config:
                self.set_context_mode(config['context_mode'])
            if 'style_tags' in config:
                self.set_style_tags(config['style_tags'])
            
            logger.info("配置设置完成")
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
    
    @property
    def prompt_manager(self):
        """获取提示词管理器"""
        if self._ai_service:
            return self._ai_service.get_prompt_manager()
        return None
    
    @property
    def rag_service(self):
        """获取RAG服务（用于兼容性访问）"""
        if self._ai_service:
            return self._ai_service.get_rag_service()
        return None
