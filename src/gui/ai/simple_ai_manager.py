"""
简化的AI管理器 - 统一AI补全和配置功能
移除重复组件，提供稳定可靠的AI集成
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
import time
import queue

logger = logging.getLogger(__name__)

# 尝试导入AI客户端
try:
    from core.ai_qt_client import QtAIClient
    from core.config import Config
    AI_CLIENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI客户端不可用: {e}")
    AI_CLIENT_AVAILABLE = False


class SimpleAIManager(QObject):
    """
    简化的AI管理器
    
    整合原有的ai_manager和enhanced_ai_manager功能，
    提供稳定的AI补全、配置和上下文管理。
    """
    
    # 信号定义
    completionReady = pyqtSignal(str, str)  # (completion_text, context)
    completionReceived = pyqtSignal(str, dict)  # 兼容性信号 (response, metadata)
    completionError = pyqtSignal(str)       # (error_message)
    streamUpdate = pyqtSignal(str)          # (partial_text)
    configChanged = pyqtSignal()            # 配置更改信号
    
    def __init__(self, config: Config, parent: QWidget = None):
        super().__init__(parent)
        self._config = config
        self._parent = parent
        
        # AI客户端
        self._ai_client = None
        self._completion_enabled = True
        self._auto_trigger_enabled = True
        self._trigger_delay = 1000  # ms
        
        # 缓存和性能
        self._completion_cache = {}  # 简单的内存缓存
        self._cache_size_limit = 100
        
        # 初始化AI客户端
        self._init_ai_client()
        
        # 补全触发定时器
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._trigger_completion)
        
        logger.info("SimpleAIManager initialized")
    
    def _init_ai_client(self):
        """初始化AI客户端"""
        if not AI_CLIENT_AVAILABLE:
            logger.warning("AI客户端不可用，禁用AI功能")
            return
        
        try:
            # 获取AI配置（使用Config的get_ai_config方法）
            ai_config = self._config.get_ai_config()
            
            if ai_config:
                # 清理旧的AI客户端
                if self._ai_client:
                    try:
                        self._ai_client.cleanup()
                    except:
                        pass
                    self._ai_client = None
                
                # 创建AI客户端
                self._ai_client = QtAIClient(ai_config, self)
                
                # 连接信号（使用正确的信号名称）
                self._ai_client.responseReceived.connect(self._on_completion_ready)
                self._ai_client.errorOccurred.connect(self._on_completion_error)
                if hasattr(self._ai_client, 'streamChunkReceived'):
                    self._ai_client.streamChunkReceived.connect(self._on_stream_update)
                
                logger.info(f"AI客户端初始化成功: {ai_config.provider.value if hasattr(ai_config, 'provider') else 'unknown'}")
            else:
                logger.warning("AI配置无效，无法初始化AI客户端")
                
        except Exception as e:
            logger.error(f"AI客户端初始化失败: {e}")
            self._ai_client = None
    
    # 补全功能
    def request_completion(self, context_or_mode=None, cursor_position: int = -1) -> bool:
        """
        请求AI补全
        
        Args:
            context_or_mode: 上下文文本或模式 ('manual', 'auto')
            cursor_position: 光标位置
            
        Returns:
            bool: 是否成功发起请求
        """
        # 兼容旧的调用方式：request_completion('manual') 或 request_completion('auto')
        if isinstance(context_or_mode, str) and context_or_mode in ['manual', 'auto']:
            if hasattr(self, '_current_editor') and self._current_editor:
                cursor = self._current_editor.textCursor()
                context = self._current_editor.toPlainText()
                cursor_position = cursor.position()
                logger.debug(f"补全请求模式: {context_or_mode}, 从编辑器获取上下文")
            else:
                logger.warning("编辑器未设置，无法获取上下文")
                return False
        else:
            # 新的调用方式：request_completion(context, cursor_position)
            context = context_or_mode or ""
        
        if not self._completion_enabled or not self._ai_client:
            return False
        
        # 检查缓存
        cache_key = self._get_cache_key(context, cursor_position)
        if cache_key in self._completion_cache:
            cached_result = self._completion_cache[cache_key]
            self.completionReady.emit(cached_result, context)
            return True
        
        try:
            # 准备补全请求
            prompt = self._prepare_prompt(context, cursor_position)
            
            # 发送请求（使用QtAIClient的正确方法）
            request_context = {
                'context': context,
                'cursor_position': cursor_position,
                'prompt': prompt
            }
            
            # 从配置获取max_tokens
            try:
                ai_config = self._config.get_ai_config()
                if ai_config and hasattr(ai_config, 'max_tokens'):
                    max_tokens = min(ai_config.max_tokens, 1000)  # 限制在合理范围
                else:
                    ai_section = self._config.get_section('ai')
                    max_tokens = min(ai_section.get('max_tokens', 500), 1000)
            except Exception:
                max_tokens = 500  # 合理的默认值
            
            self._ai_client.complete_async(
                prompt=prompt,
                context=request_context,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            logger.debug(f"AI补全请求已发送")
            return True
            
        except Exception as e:
            logger.error(f"AI补全请求失败: {e}")
            self.completionError.emit(f"补全请求失败: {str(e)}")
            return False
    
    def _prepare_prompt(self, context: str, cursor_position: int) -> str:
        """
        准备AI提示词
        
        简化的提示词生成，移除复杂的模板系统
        """
        # 获取光标前后的文本
        if cursor_position >= 0:
            before = context[:cursor_position]
            after = context[cursor_position:]
        else:
            before = context
            after = ""
        
        # 简单的上下文窗口（最后500字符）
        if len(before) > 500:
            before = "..." + before[-500:]
        
        # 构建简单有效的提示词
        prompt = f"""请根据以下小说文本的上下文，生成自然连贯的续写内容：

【上文】
{before}

【续写要求】
- 保持文风和语调一致
- 情节发展自然合理
- 控制在50字以内
- 不要添加方括号或标记

【续写】"""
        
        return prompt
    
    def _get_cache_key(self, context: str, cursor_position: int) -> str:
        """生成缓存键"""
        # 使用最后100字符作为缓存键
        key_text = context[-100:] if len(context) > 100 else context
        return f"{hash(key_text)}_{cursor_position}"
    
    def _add_to_cache(self, context: str, cursor_position: int, result: str):
        """添加到缓存"""
        cache_key = self._get_cache_key(context, cursor_position)
        
        # 缓存大小限制
        if len(self._completion_cache) >= self._cache_size_limit:
            # 移除最旧的条目
            oldest_key = next(iter(self._completion_cache))
            del self._completion_cache[oldest_key]
        
        self._completion_cache[cache_key] = result
    
    # 自动触发功能
    def schedule_completion(self, context: str, cursor_position: int = -1):
        """
        调度自动补全
        
        Args:
            context: 上下文文本
            cursor_position: 光标位置
        """
        if not self._auto_trigger_enabled:
            return
        
        # 存储参数供定时器使用
        self._scheduled_context = context
        self._scheduled_cursor_position = cursor_position
        
        # 重启定时器
        self._completion_timer.stop()
        self._completion_timer.start(self._trigger_delay)
    
    def _trigger_completion(self):
        """定时器触发的补全"""
        if hasattr(self, '_scheduled_context'):
            self.request_completion(
                self._scheduled_context,
                self._scheduled_cursor_position
            )
    
    # 信号处理
    @pyqtSlot(str, dict)
    def _on_completion_ready(self, response: str, context: dict):
        """处理补全完成"""
        try:
            # 简单的响应处理
            completion = response.strip()
            
            # 移除常见的AI响应前缀
            prefixes_to_remove = ["续写：", "续写:", "【续写】", "[续写]"]
            for prefix in prefixes_to_remove:
                if completion.startswith(prefix):
                    completion = completion[len(prefix):].strip()
            
            # 从上下文中获取原始请求信息
            original_context = context.get('context', '')
            cursor_pos = context.get('cursor_position', -1)
            
            # 添加到缓存
            if original_context:
                self._add_to_cache(original_context, cursor_pos, completion)
            
            # 发送信号
            self.completionReady.emit(completion, original_context)
            
            # 发送兼容性信号（主窗口期望的格式）
            metadata = {
                'context': original_context,
                'cursor_position': cursor_pos,
                'completion_type': 'auto'
            }
            self.completionReceived.emit(completion, metadata)
            
        except Exception as e:
            logger.error(f"处理补全响应失败: {e}")
            self.completionError.emit(f"处理响应失败: {str(e)}")
    
    @pyqtSlot(str, dict)
    def _on_completion_error(self, error: str, context: dict):
        """处理补全错误"""
        logger.error(f"AI补全错误: {error}")
        self.completionError.emit(error)
    
    @pyqtSlot(str, dict)
    def _on_stream_update(self, partial_text: str, context: dict):
        """处理流式更新"""
        self.streamUpdate.emit(partial_text)
    
    # 配置管理
    def set_completion_enabled(self, enabled: bool):
        """设置补全是否启用"""
        self._completion_enabled = enabled
        logger.info(f"AI补全{'启用' if enabled else '禁用'}")
    
    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发是否启用"""
        self._auto_trigger_enabled = enabled
        if not enabled:
            self._completion_timer.stop()
        logger.info(f"自动触发{'启用' if enabled else '禁用'}")
    
    def set_trigger_delay(self, delay_ms: int):
        """设置触发延迟"""
        self._trigger_delay = max(100, min(5000, delay_ms))  # 限制在100ms-5s
        logger.info(f"触发延迟设置为: {self._trigger_delay}ms")
    
    def set_punctuation_assist_enabled(self, enabled: bool):
        """设置标点辅助是否启用"""
        # 简化实现：记录设置但不实现复杂逻辑
        self._punctuation_assist_enabled = getattr(self, '_punctuation_assist_enabled', True)
        self._punctuation_assist_enabled = enabled
        logger.info(f"标点辅助{'启用' if enabled else '禁用'}")
    
    def set_completion_mode(self, mode: str):
        """设置补全模式"""
        # 简化实现：记录模式但使用统一的补全逻辑
        self._completion_mode = getattr(self, '_completion_mode', 'balanced')
        self._completion_mode = mode
        logger.info(f"补全模式设置为: {mode}")
    
    def show_config_dialog(self, parent=None):
        """显示配置对话框"""
        try:
            from .unified_ai_config_dialog import UnifiedAIConfigDialog
            dialog = UnifiedAIConfigDialog(parent or self._parent, self._config)
            if dialog.exec():
                # 重新初始化AI客户端
                self._init_ai_client()
                self.configChanged.emit()
                logger.info("AI配置已更新")
        except ImportError:
            # fallback: 显示简单的消息框
            QMessageBox.information(
                parent or self._parent,
                "AI配置",
                "AI配置功能暂时不可用。\n请检查配置文件或联系开发者。"
            )
    
    # 实用方法
    def is_available(self) -> bool:
        """检查AI功能是否可用"""
        return AI_CLIENT_AVAILABLE and self._ai_client is not None
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            'available': self.is_available(),
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'trigger_delay': self._trigger_delay,
            'cache_size': len(self._completion_cache)
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._completion_cache.clear()
        logger.info("AI补全缓存已清空")
    
    def cleanup(self):
        """清理资源"""
        self._completion_timer.stop()
        self.clear_cache()
        if self._ai_client:
            self._ai_client.deleteLater()
        logger.info("SimpleAIManager已清理")
    
    # 编辑器管理方法
    def set_editor(self, editor):
        """设置当前编辑器"""
        if hasattr(self, '_current_editor') and self._current_editor:
            # 断开旧编辑器的信号
            try:
                self._current_editor.textChanged.disconnect(self._on_text_changed)
                self._current_editor.cursorPositionChanged.disconnect(self._on_cursor_changed)
                # 断开智能补全管理器的信号
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
                logger.debug("Connected smart completion AI request signal")

            logger.debug("Editor set for SimpleAIManager")
    
    def _on_text_changed(self):
        """处理文本变化"""
        if not self._auto_trigger_enabled or not self._current_editor:
            return
        
        # 获取当前文本和光标位置
        cursor = self._current_editor.textCursor()
        context = self._current_editor.toPlainText()
        cursor_pos = cursor.position()
        
        # 调度自动补全
        self.schedule_completion(context, cursor_pos)
    
    def _on_cursor_changed(self):
        """处理光标位置变化"""
        # 简化实现：光标变化时停止当前补全计时器
        if hasattr(self, '_completion_timer'):
            self._completion_timer.stop()
    
    def _on_ai_completion_requested(self, text: str, context: dict):
        """处理AI补全请求 - 修复参数传递问题"""
        cursor_pos = context.get('cursor_position', -1)
        trigger_type = context.get('trigger_type', 'auto')
        mode = context.get('mode', 'auto')
        
        # 根据mode和trigger_type确定调用方式
        if trigger_type == 'manual':
            # 手动触发：使用'manual'模式调用
            self.request_completion('manual')
        elif mode == 'manual':
            # 手动模式：使用'manual'模式调用
            self.request_completion('manual')
        else:
            # 其他情况：使用上下文调用
            self.request_completion(text, cursor_pos)
    
    # 兼容性方法 - 为了支持原有接口
    def set_context_mode(self, mode: str):
        """设置上下文模式（兼容性方法）"""
        self._context_mode = getattr(self, '_context_mode', 'balanced')
        self._context_mode = mode
        logger.info(f"上下文模式设置为: {mode}")
    
    def set_style_tags(self, tags: List[str]):
        """设置风格标签（兼容性方法）"""
        self._style_tags = getattr(self, '_style_tags', [])
        self._style_tags = tags
        logger.info(f"风格标签设置为: {tags}")
    
    def update_completion_settings(self, settings: Dict[str, Any]):
        """更新补全设置（兼容性方法）"""
        if 'enabled' in settings:
            self.set_completion_enabled(settings['enabled'])
        if 'auto_trigger' in settings:
            self.set_auto_trigger_enabled(settings['auto_trigger'])
        if 'trigger_delay' in settings:
            self.set_trigger_delay(settings['trigger_delay'])
        logger.info(f"补全设置已更新: {settings}")
    
    def integrate_codex_system(self, codex_manager=None, reference_detector=None, prompt_function_registry=None):
        """集成Codex系统（兼容性方法）"""
        self._codex_manager = codex_manager
        self._reference_detector = reference_detector
        self._prompt_function_registry = prompt_function_registry
        logger.info("Codex系统集成完成（简化实现）")
    
    def diagnose_ai_completion_issues(self) -> Dict[str, Any]:
        """诊断AI补全问题（兼容性方法）"""
        issues = []
        
        if not self.is_available():
            issues.append("AI客户端不可用")
        if not self._completion_enabled:
            issues.append("AI补全已禁用")
        if not hasattr(self, '_current_editor') or not self._current_editor:
            issues.append("编辑器未设置")
            
        return {
            'issues': issues,
            'ai_available': self.is_available(),
            'completion_enabled': self._completion_enabled,
            'editor_set': hasattr(self, '_current_editor') and self._current_editor is not None
        }
    
    def get_context_mode(self) -> str:
        """获取上下文模式"""
        return getattr(self, '_context_mode', 'balanced')
    
    def get_completion_stats(self) -> dict:
        """获取补全统计信息"""
        return {
            'total_requests': getattr(self, '_total_requests', 0),
            'successful_completions': getattr(self, '_successful_completions', 0),
            'cache_hits': getattr(self, '_cache_hits', 0),
            'cache_size': len(self._completion_cache),
            'enabled': self._completion_enabled
        }
    
    # 大纲分析方法（简化实现）
    def analyze_outline(self, text: str, analysis_type: str = 'auto') -> str:
        """分析大纲（简化实现）"""
        logger.info(f"大纲分析请求: {analysis_type}")
        return "大纲分析功能正在开发中，请使用AI补全功能。"
    
    def get_outline_suggestions(self, outline: str) -> List[str]:
        """获取大纲建议（简化实现）"""
        return ["建议1: 增加角色描述", "建议2: 完善情节线", "建议3: 优化章节结构"]
    
    def generate_outline_continuation(self, existing_docs: List, generation_params: Dict[str, Any]) -> Dict[str, Any]:
        """生成大纲续写（简化实现）"""
        return {
            'success': False,
            'message': '大纲生成功能正在开发中',
            'content': ''
        }
    
    def get_outline_extension(self):
        """获取大纲扩展（兼容性方法）"""
        return None
    
    # RAG和索引方法（简化实现）
    def index_document(self, document_id: str, content: str):
        """索引文档（简化实现）"""
        logger.info(f"文档索引请求: {document_id}")
        # 简化实现：暂不实际索引
    
    def index_document_sync(self, document_id: str, content: str) -> bool:
        """同步索引文档（简化实现）"""
        logger.info(f"同步文档索引: {document_id}")
        return True  # 简化实现：总是返回成功
    
    def delete_document_index(self, document_id: str):
        """删除文档索引（简化实现）"""
        logger.info(f"删除文档索引: {document_id}")
        # 简化实现：暂不实际删除
    
    def search_similar_content(self, query: str, max_results: int = 30) -> str:
        """搜索相似内容（简化实现）"""
        logger.info(f"相似内容搜索: {query}")
        return ""  # 简化实现：返回空结果
    
    def build_rag_context(self, current_text: str, cursor_position: int) -> str:
        """构建RAG上下文（简化实现）"""
        return ""  # 简化实现：返回空上下文
    
    # 状态和配置方法
    def get_ai_status(self):
        """获取AI状态"""
        ai_config = self._config.get_section('ai')
        return {
            'available': self.is_available(),
            'ai_client_available': self.is_available(),  # 兼容性键
            'rag_service_available': False,  # 简化AI系统中RAG不可用
            'enabled': self._completion_enabled,
            'provider': ai_config.get('provider', 'unknown'),
            'model': ai_config.get('model', 'unknown')
        }
    
    def get_index_stats(self):
        """获取索引统计（简化实现）"""
        return {
            'total_documents': 0,
            'indexed_documents': 0,
            'index_size': 0
        }
    
    def clear_all_indexes(self) -> bool:
        """清空所有索引（简化实现）"""
        logger.info("清空所有索引")
        return True
    
    def rebuild_all_indexes(self, documents: Dict[str, str]) -> bool:
        """重建所有索引（简化实现）"""
        logger.info(f"重建索引，文档数量: {len(documents)}")
        return True
    
    def rebuild_all_indexes_sync(self, documents: Dict[str, str]) -> bool:
        """同步重建所有索引（简化实现）"""
        return self.rebuild_all_indexes(documents)
    
    def force_reinit_ai(self):
        """强制重新初始化AI客户端"""
        try:
            self._init_ai_client()
            logger.info("AI客户端已重新初始化")
            return True
        except Exception as e:
            logger.error(f"重新初始化AI客户端失败: {e}")
            return False
    
    def force_reinit_rag(self):
        """强制重新初始化RAG（兼容性方法）"""
        logger.info("RAG重新初始化（简化实现中暂不支持）")
        return True
    
    def start_stream_response(self, text: str):
        """开始流式响应（兼容性方法）"""
        logger.info(f"流式响应请求: {text[:50]}...")
        # 简化实现：使用普通的补全请求
        if hasattr(self, '_current_editor') and self._current_editor:
            cursor = self._current_editor.textCursor()
            context = self._current_editor.toPlainText()
            cursor_position = cursor.position()
            self.request_completion(context, cursor_position)
        else:
            logger.warning("编辑器未设置，无法处理流式响应请求")
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """获取可用模板列表（兼容性方法）"""
        # 简化实现：返回基础模板列表
        return [
            {
                'id': 'creative_writing',
                'name': '创意写作',
                'description': '适合小说创作的通用模板',
                'category': 'writing'
            },
            {
                'id': 'dialogue',
                'name': '对话生成',
                'description': '专门用于生成角色对话',
                'category': 'dialogue'
            },
            {
                'id': 'description',
                'name': '场景描述',
                'description': '生成环境和场景描述',
                'category': 'description'
            }
        ]
    
    def get_current_template_id(self, mode: str) -> str:
        """获取当前模板ID（兼容性方法）"""
        # 简化实现：默认使用创意写作模板
        return 'creative_writing'
    
    def _on_unified_config_saved(self, config_data: Dict[str, Any]):
        """处理统一配置保存（兼容性方法）"""
        logger.info("统一配置已保存（简化AI系统）")
        # 简化实现：重新初始化AI客户端
        try:
            self._init_ai_client()
            self.configChanged.emit()
            logger.info("AI配置已更新")
        except Exception as e:
            logger.error(f"更新AI配置失败: {e}")
    
    def open_template_manager(self, parent=None):
        """打开模板管理器（兼容性方法）"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            parent or self._parent,
            "模板管理",
            "模板管理功能在简化AI系统中暂不可用。"
        )
    
    def get_completion_widget(self, parent):
        """获取补全组件（兼容性方法）"""
        try:
            from .completion_widget import CompletionWidget
            return CompletionWidget(parent)
        except ImportError:
            logger.warning("CompletionWidget不可用")
            return None
    
    def get_stream_widget(self, parent):
        """获取流式响应组件（兼容性方法）"""
        try:
            from .stream_widget import StreamResponseWidget
            return StreamResponseWidget(parent)
        except ImportError:
            logger.warning("StreamResponseWidget不可用")
            return None
    
    def show_index_manager(self, parent=None, project_manager=None):
        """显示索引管理器（基础版本）"""
        try:
            from ..dialogs.rag_index_dialog import RAGIndexDialog
            
            dialog = RAGIndexDialog(
                ai_manager=self,
                project_manager=project_manager,
                parent=parent or self._parent
            )
            dialog.exec()
            
        except ImportError as e:
            logger.error(f"导入索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                parent or self._parent,
                "索引管理",
                "索引管理功能在简化AI系统中的完整版本暂不可用。"
            )
        except Exception as e:
            logger.error(f"显示索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent or self._parent,
                "错误", 
                f"无法打开索引管理对话框：{str(e)}"
            )
    
    def show_batch_index_dialog(self, parent=None, project_manager=None):
        """显示批量索引对话框（兼容性方法）"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            parent or self._parent,
            "批量索引",
            "批量索引功能在简化AI系统中暂不可用。"
        )
    
    def show_rag_config_dialog(self, parent=None):
        """显示RAG配置对话框（兼容性方法）"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            parent or self._parent,
            "RAG配置", 
            "RAG配置功能在简化AI系统中暂不可用。\\n使用主配置对话框进行AI设置。"
        )
    
    # 配置更新方法
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        # 更新内部配置
        if 'completion' in config:
            comp_config = config['completion']
            self.set_completion_enabled(comp_config.get('enabled', True))
            self.set_auto_trigger_enabled(comp_config.get('auto_trigger', True))
            self.set_trigger_delay(comp_config.get('trigger_delay', 1000))
        
        logger.info("配置已更新")
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            'completion': {
                'enabled': self._completion_enabled,
                'auto_trigger': self._auto_trigger_enabled,
                'trigger_delay': self._trigger_delay
            }
        }
    
    def update_performance_settings(self, settings: Dict[str, Any]):
        """更新性能设置（兼容性方法）"""
        logger.info(f"性能设置更新: {settings}")
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """获取性能设置"""
        return {
            'cache_enabled': True,
            'cache_size': len(self._completion_cache),
            'auto_trigger': self._auto_trigger_enabled
        }