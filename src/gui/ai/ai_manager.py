"""
AI功能管理器
协调AI补全、配置、流式响应等功能组件
"""

import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QPoint, QThread
from PyQt6.QtGui import QTextCursor
import queue
import time
import threading
import hashlib

from .completion_widget import CompletionWidget
from .unified_ai_config_dialog import UnifiedAIConfigDialog
from .stream_widget import StreamResponseWidget
from .literary_formatter import literary_formatter

logger = logging.getLogger(__name__)

# 导入AI客户端和提示词系统
try:
    from core.ai_qt_client import QtAIClient
    from core.config import Config
    from core.prompt_engineering import EnhancedPromptManager, PromptMode, CompletionType, PromptRenderer
    from core.builtin_templates import BuiltinTemplateLibrary
    AI_CLIENT_AVAILABLE = True
    PROMPT_SYSTEM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI客户端或提示词系统不可用: {e}")
    AI_CLIENT_AVAILABLE = False
    PROMPT_SYSTEM_AVAILABLE = False


class AsyncIndexingWorker(QThread):
    """异步索引工作线程"""
    
    indexStarted = pyqtSignal(str)  # 开始索引文档信号
    indexProgress = pyqtSignal(str, int, int)  # 索引进度信号 (doc_id, current, total)
    indexCompleted = pyqtSignal(str, bool)  # 索引完成信号 (doc_id, success)
    batchCompleted = pyqtSignal(int, int)  # 批量索引完成信号 (success_count, total_count)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._index_queue = queue.Queue()
        self._should_stop = False
        self._rag_service = None
        self._vector_store = None
        self._config = None
        
    def set_services(self, rag_service, vector_store, config):
        """设置RAG服务引用"""
        self._rag_service = rag_service
        self._vector_store = vector_store
        self._config = config
    
    def queue_document_index(self, document_id: str, content: str):
        """将文档加入索引队列"""
        if content and content.strip():
            self._index_queue.put(('single', document_id, content))
            logger.info(f"文档已加入异步索引队列: {document_id}")
        
    def queue_batch_index(self, documents: Dict[str, str]):
        """将批量文档加入索引队列"""
        if documents:
            self._index_queue.put(('batch', documents, None))
            logger.info(f"批量文档已加入异步索引队列: {len(documents)} 个文档")
    
    def run(self):
        """工作线程主循环"""
        logger.info("异步索引工作线程启动")
        
        while not self._should_stop:
            try:
                # 等待索引任务，超时时间1秒
                try:
                    task_type, data, content = self._index_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if not self._rag_service or not self._vector_store:
                    logger.warning("RAG服务未初始化，跳过索引任务")
                    continue
                
                if task_type == 'single':
                    # 单个文档索引
                    document_id = data
                    self._index_single_document(document_id, content)
                elif task_type == 'batch':
                    # 批量文档索引
                    documents = data
                    self._index_batch_documents(documents)
                
                self._index_queue.task_done()
                
            except Exception as e:
                logger.error(f"异步索引处理错误: {e}", exc_info=True)
                time.sleep(0.1)  # 短暂休息防止死循环
        
        logger.info("异步索引工作线程停止")
    
    def _index_single_document(self, document_id: str, content: str):
        """索引单个文档"""
        try:
            self.indexStarted.emit(document_id)
            
            logger.info(f"异步索引文档: {document_id}, 内容长度: {len(content)}")
            
            # 直接调用RAG服务的索引方法
            if self._rag_service:
                success = self._rag_service.index_document(document_id, content)
                
                if success:
                    logger.info(f"异步索引完成: {document_id}")
                    self.indexCompleted.emit(document_id, True)
                else:
                    logger.error(f"异步索引失败: {document_id}")
                    self.indexCompleted.emit(document_id, False)
            else:
                logger.error(f"RAG服务不可用，异步索引失败: {document_id}")
                self.indexCompleted.emit(document_id, False)
            
        except Exception as e:
            logger.error(f"异步索引文档失败: {document_id}, 错误: {e}", exc_info=True)
            self.indexCompleted.emit(document_id, False)
    
    def _index_batch_documents(self, documents: Dict[str, str]):
        """批量索引文档"""
        total_count = len(documents)
        success_count = 0
        
        for i, (doc_id, content) in enumerate(documents.items()):
            if self._should_stop:
                break
                
            self.indexProgress.emit(doc_id, i + 1, total_count)
            
            try:
                # 直接调用RAG服务索引方法
                if self._rag_service and self._rag_service.index_document(doc_id, content):
                    success_count += 1
                    logger.info(f"批量索引成功: {doc_id}")
                else:
                    logger.error(f"批量索引失败: {doc_id}")
                    
            except Exception as e:
                logger.error(f"批量索引文档失败: {doc_id}, 错误: {e}")
        
        self.batchCompleted.emit(success_count, total_count)
        logger.info(f"批量异步索引完成: {success_count}/{total_count}")
    
    def stop(self):
        """停止工作线程"""
        self._should_stop = True
        
        # 清空队列防止阻塞
        try:
            while not self._index_queue.empty():
                try:
                    self._index_queue.get_nowait()
                except queue.Empty:
                    break
        except Exception as e:
            logger.debug(f"清空索引队列时出错: {e}")
        
        logger.info("异步索引工作线程收到停止信号")


class AIManager(QObject):
    """AI功能管理器"""
    
    # 信号定义
    completionRequested = pyqtSignal(str, dict)  # 补全请求信号
    configChanged = pyqtSignal(dict)  # 配置变更信号
    
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)

        self._config = config
        self._completion_widget = None
        self._stream_widget = None
        self._config_dialog = None

        # AI补全控制设置
        self._completion_enabled = True
        self._auto_trigger_enabled = True
        self._punctuation_assist_enabled = True
        self._trigger_delay = 1200  # 增加到1.2秒，减少频繁触发
        self._completion_mode = "智能"
        self._context_mode = "balanced"  # 新增上下文模式：fast, balanced, full

        # 性能优化设置
        self._debounce_delay = 1200  # 防抖延迟（毫秒）
        self._throttle_interval = 2000  # 节流间隔（毫秒）
        self._last_completion_time = 0
        self._min_trigger_chars = 3  # 最少输入字符数才触发
        self._last_text_hash = ""
        
        # 补全触发定时器（防抖）
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._debounced_trigger_completion)
        
        # 节流定时器
        self._throttle_timer = QTimer()
        self._throttle_timer.setSingleShot(True)

        # 当前编辑器引用
        self._current_editor = None

        # 统计信息
        self._completion_count = 0
        self._acceptance_count = 0

        # 初始化AI客户端
        self._ai_client = None
        self._init_ai_client()
        
        # 初始化RAG服务
        self._rag_service = None
        self._vector_store = None
        self._init_rag_service()
        
        # 初始化提示词管理系统
        self._prompt_manager = None
        self._prompt_renderer = None
        self._current_template_ids = {
            'fast': 'ai_fast_completion',
            'balanced': 'ai_balanced_completion', 
            'full': 'ai_full_completion'
        }
        self._init_prompt_system()
        
        # 初始化异步索引工作线程
        self._async_indexer = AsyncIndexingWorker(self)
        self._async_indexer.indexStarted.connect(self._on_async_index_started)
        self._async_indexer.indexCompleted.connect(self._on_async_index_completed)
        self._async_indexer.batchCompleted.connect(self._on_async_batch_completed)
        self._async_indexer.start()
        logger.info("异步索引工作线程已启动")
        
        # 保存shared引用（防止在项目变化时丢失）
        self._shared = self.parent()._shared if hasattr(self.parent(), '_shared') else None
        
        # 连接项目变化信号，用于重新初始化RAG服务
        if self._shared and hasattr(self._shared, 'projectChanged'):
            self._shared.projectChanged.connect(self._on_project_changed)

        # 活跃线程管理
        self._active_threads = set()  # 跟踪活跃的搜索线程
        self._is_shutting_down = False  # 关闭标志
        self._thread_stop_events = {}  # 线程停止事件映射

        # 初始化大纲分析扩展
        self._outline_extension = None
        self._init_outline_extension()

        # 初始化现代AI状态指示器
        self._modern_ai_indicators = {}  # 存储每个编辑器的指示器
        self._init_modern_indicators()

        logger.info("AI manager initialized")

    def _init_modern_indicators(self):
        """初始化现代AI状态指示器系统"""
        try:
            # 导入现代AI指示器
            from gui.editor.modern_ai_indicator import AIStatusManager
            self._ai_status_manager_class = AIStatusManager
            logger.info("现代AI状态指示器系统已初始化")
        except ImportError as e:
            logger.error(f"无法导入现代AI状态指示器: {e}")
            self._ai_status_manager_class = None

    def _create_modern_indicator_for_editor(self, editor):
        """为编辑器创建现代AI状态指示器"""
        if not self._ai_status_manager_class:
            logger.warning("现代AI状态指示器类不可用，跳过创建")
            return
            
        try:
            # 为每个编辑器创建独立的指示器管理器
            editor_id = id(editor)
            
            # 清理旧的指示器（如果存在）
            if editor_id in self._modern_ai_indicators:
                old_indicator = self._modern_ai_indicators[editor_id]
                if hasattr(old_indicator, 'hide'):
                    old_indicator.hide()
                del self._modern_ai_indicators[editor_id]
            
            # 创建新的现代指示器管理器
            status_manager = self._ai_status_manager_class(editor)
            
            # 连接取消信号（如果用户点击指示器取消操作）
            if hasattr(status_manager, 'connect_cancel_signal'):
                status_manager.connect_cancel_signal(self._on_ai_operation_cancelled)
            
            # 保存到字典中
            self._modern_ai_indicators[editor_id] = status_manager
            
            logger.info(f"为编辑器 {editor_id} 创建了现代AI状态指示器")
            
        except Exception as e:
            logger.error(f"创建现代AI状态指示器失败: {e}")

    def _on_ai_operation_cancelled(self):
        """AI操作被用户取消"""
        logger.info("用户取消了AI操作")
        
        # 停止当前的AI请求
        if self._ai_client and hasattr(self._ai_client, 'cancel_request'):
            try:
                self._ai_client.cancel_request()
                logger.debug("AI请求已取消")
            except Exception as e:
                logger.warning(f"取消AI请求失败: {e}")
        
        # 重置状态
        self._is_completing = False
        
        # 隐藏所有现代指示器
        for status_manager in self._modern_ai_indicators.values():
            if hasattr(status_manager, 'hide'):
                status_manager.hide()

    def _get_current_modern_indicator(self):
        """获取当前编辑器的现代状态指示器"""
        if not self._current_editor:
            return None
            
        editor_id = id(self._current_editor)
        return self._modern_ai_indicators.get(editor_id)

    def set_completion_enabled(self, enabled: bool):
        """设置AI补全开关"""
        self._completion_enabled = enabled
        logger.info(f"AI补全{'启用' if enabled else '禁用'}")

    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发开关"""
        self._auto_trigger_enabled = enabled
        logger.info(f"自动触发{'启用' if enabled else '禁用'}")

    def set_punctuation_assist_enabled(self, enabled: bool):
        """设置标点符号辅助开关"""
        self._punctuation_assist_enabled = enabled
        logger.info(f"标点符号辅助{'启用' if enabled else '禁用'}")

    def set_trigger_delay(self, delay: int):
        """设置触发延迟"""
        self._trigger_delay = delay
        self._debounce_delay = max(delay, 800)  # 防抖延迟至少800ms
        logger.info(f"触发延迟设置为 {delay}ms，防抖延迟: {self._debounce_delay}ms")

    def set_context_mode(self, mode: str):
        """设置上下文模式"""
        self._context_mode = mode
        logger.info(f"上下文模式设置为 {mode}")

    def _init_outline_extension(self):
        """初始化大纲分析扩展"""
        try:
            self._outline_extension = OutlineAnalysisExtension(self)
            
            # 连接大纲扩展信号（如果需要全局响应）
            if hasattr(self._outline_extension, 'outlineAnalysisCompleted'):
                self._outline_extension.outlineAnalysisCompleted.connect(self._on_outline_analysis_completed)
            if hasattr(self._outline_extension, 'outlineAnalysisError'):
                self._outline_extension.outlineAnalysisError.connect(self._on_outline_analysis_error)
            
            logger.info("大纲分析扩展初始化成功")
        except Exception as e:
            logger.error(f"初始化大纲分析扩展失败: {e}")
            self._outline_extension = None

    def _on_outline_analysis_completed(self, result: str, original_text: str):
        """大纲分析完成回调"""
        logger.debug(f"大纲分析完成，结果长度: {len(result)}")

    def _on_outline_analysis_error(self, error_msg: str):
        """大纲分析错误回调"""
        logger.warning(f"大纲分析出错: {error_msg}")

    # 大纲功能公共接口方法
    def analyze_outline(self, text: str, analysis_type: str = 'auto') -> str:
        """大纲分析公共接口"""
        try:
            if not self._outline_extension:
                raise RuntimeError("大纲分析扩展未初始化")
            
            return self._outline_extension.analyze_outline_structure(text, analysis_type)
        except Exception as e:
            logger.error(f"大纲分析调用失败: {e}")
            raise

    def get_outline_suggestions(self, outline: str) -> List[str]:
        """获取大纲建议"""
        try:
            if not self._outline_extension:
                logger.warning("大纲分析扩展未初始化，返回空建议")
                return []
            
            return self._outline_extension.suggest_outline_improvements(outline)
        except Exception as e:
            logger.error(f"获取大纲建议失败: {e}")
            return []

    def generate_outline_continuation(self, existing_docs: List, generation_params: Dict[str, Any]) -> Dict[str, Any]:
        """生成大纲续写内容"""
        try:
            if not self._outline_extension:
                raise RuntimeError("大纲分析扩展未初始化")
            
            return self._outline_extension.generate_outline_continuation(existing_docs, generation_params)
        except Exception as e:
            logger.error(f"生成大纲续写失败: {e}")
            return {'error': str(e)}

    def get_outline_extension(self):
        """获取大纲扩展实例（用于直接访问信号）"""
        return self._outline_extension

    def get_context_mode(self) -> str:
        """获取当前上下文模式"""
        return self._context_mode

    def set_completion_mode(self, mode: str):
        """设置补全模式"""
        self._completion_mode = mode
        logger.info(f"补全模式设置为 {mode}")

        # 将模式传递给当前编辑器的智能补全管理器
        if self._current_editor and hasattr(self._current_editor, '_smart_completion'):
            self._current_editor._smart_completion.set_completion_mode(mode)
            
        # 同时更新编辑器的状态指示器显示
        if (self._current_editor and 
            hasattr(self._current_editor, '_status_indicator') and 
            self._current_editor._status_indicator):
            self._current_editor._status_indicator.set_completion_mode(mode)
            logger.debug(f"状态指示器模式已更新为: {mode}")

    def get_completion_stats(self) -> dict:
        """获取补全统计信息"""
        acceptance_rate = (self._acceptance_count / self._completion_count * 100) if self._completion_count > 0 else 0
        return {
            'completion_count': self._completion_count,
            'acceptance_count': self._acceptance_count,
            'acceptance_rate': acceptance_rate
        }

    def _init_ai_client(self):
        """初始化AI客户端"""
        if not AI_CLIENT_AVAILABLE:
            logger.warning("AI客户端不可用，跳过初始化")
            return

        try:
            # 获取AI配置
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

                # 连接信号
                self._ai_client.responseReceived.connect(self._on_ai_response_received)
                self._ai_client.streamChunkReceived.connect(self._on_ai_stream_chunk)
                self._ai_client.errorOccurred.connect(self._on_ai_error)
                self._ai_client.requestStarted.connect(self._on_ai_request_started)
                self._ai_client.requestCompleted.connect(self._on_ai_request_completed)

                logger.info(f"AI客户端已初始化: {ai_config.provider.value}")
            else:
                logger.warning("AI配置无效，无法初始化AI客户端")

        except Exception as e:
            logger.error(f"初始化AI客户端失败: {e}")
            self._ai_client = None

    def set_editor(self, editor):
        """设置当前编辑器"""
        if self._current_editor:
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

            # 为编辑器创建现代AI状态指示器
            self._create_modern_indicator_for_editor(editor)

            logger.debug("Editor set for AI manager")
    
    def get_completion_widget(self, parent: QWidget) -> CompletionWidget:
        """获取补全组件"""
        if not self._completion_widget:
            self._completion_widget = CompletionWidget(parent)
            self._completion_widget.suggestionAccepted.connect(self._on_suggestion_accepted)
            self._completion_widget.suggestionRejected.connect(self._on_suggestion_rejected)
            self._completion_widget.moreOptionsRequested.connect(self._on_more_options_requested)
        
        return self._completion_widget
    
    def get_stream_widget(self, parent: QWidget) -> StreamResponseWidget:
        """获取流式响应组件"""
        if not self._stream_widget:
            self._stream_widget = StreamResponseWidget(parent)
            self._stream_widget.responseCompleted.connect(self._on_response_completed)
            self._stream_widget.responseCancelled.connect(self._on_response_cancelled)
            self._stream_widget.responseAccepted.connect(self._on_response_accepted)
        
        return self._stream_widget
    
    def show_config_dialog(self, parent: QWidget):
        """显示统一配置对话框"""
        try:
            from .unified_ai_config_dialog import UnifiedAIConfigDialog
            
            # 确保AI客户端已初始化
            if not self._ai_client:
                logger.info("AI客户端未初始化，正在初始化...")
                self._init_ai_client()
                
            # 如果AI客户端仍未初始化，继续尝试创建对话框（可能只是配置问题）
            if not self._ai_client:
                logger.warning("AI客户端初始化失败，但仍允许打开配置对话框")
            
            # 每次都创建新的配置对话框（避免状态不一致）
            self._config_dialog = UnifiedAIConfigDialog(parent, self._config)
            self._config_dialog.configSaved.connect(self._on_unified_config_saved)
            
            # 连接补全设置信号到AI管理器
            completion_widget = self._config_dialog.get_completion_widget()
            if completion_widget:
                completion_widget.completionEnabledChanged.connect(self.set_completion_enabled)
                completion_widget.autoTriggerEnabledChanged.connect(self.set_auto_trigger_enabled)
                completion_widget.punctuationAssistChanged.connect(self.set_punctuation_assist_enabled)
                completion_widget.triggerDelayChanged.connect(self.set_trigger_delay)
                completion_widget.completionModeChanged.connect(self.set_completion_mode)
                completion_widget.contextModeChanged.connect(self.set_context_mode)  # 新增上下文模式信号
                logger.info("AI管理器已连接统一配置对话框的信号")
            
            self._config_dialog.exec()
            
        except ImportError as e:
            logger.warning(f"统一配置对话框不可用，使用原有对话框: {e}")
            # 回退到原有对话框
            from .config_dialog import AIConfigDialog
            fallback_config_dialog = AIConfigDialog(parent, self._config.get_ai_config())
            fallback_config_dialog.configSaved.connect(self._on_config_saved)
            fallback_config_dialog.exec()
        except Exception as e:
            logger.error(f"显示配置对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(parent, "错误", f"无法打开AI配置: {str(e)}")
    
    def request_completion(self, mode: str = 'smart'):
        """请求补全（优化版本：防抖+节流+快速失败+RAG阻塞保护）"""
        # 快速检查：如果补全功能被禁用，立即返回
        if not self._completion_enabled:
            logger.debug("AI补全已禁用，跳过请求")
            return
        
        # 节流检查：防止过于频繁的API调用
        if mode != 'manual':  # 手动触发不受节流限制
            current_time = time.time() * 1000
            if current_time - self._last_completion_time < self._throttle_interval:
                logger.debug(f"节流限制：距离上次补全仅 {current_time - self._last_completion_time:.0f}ms，跳过")
                return
        
        # 检查和修复AI客户端
        if not self._ai_client:
            logger.warning("AI客户端未初始化，尝试重新初始化")
            self._init_ai_client()
            if not self._ai_client:
                logger.error("AI客户端初始化失败，无法提供补全")
                # 尝试显示错误信息给用户
                if hasattr(self.parent(), 'statusBar'):
                    self.parent().statusBar().showMessage("⚠️ AI服务不可用，请检查配置", 5000)
                return
        
        # 检查自动触发是否启用（手动模式除外）
        if mode != 'manual' and not self._auto_trigger_enabled:
            logger.debug("自动触发已禁用，跳过请求")
            return

        logger.info(f"AI补全请求: mode={mode}")

        if not self._current_editor:
            logger.warning("AI补全失败: 没有设置当前编辑器")
            return

        # 获取当前上下文
        cursor = self._current_editor.textCursor()
        text = self._current_editor.toPlainText()
        position = cursor.position()

        # 智能触发判断（除了手动模式）
        if mode != 'manual':
            should_trigger = literary_formatter.should_trigger_new_completion(text, position)
            if not should_trigger:
                logger.debug("智能触发判断：当前不适合触发补全")
                return

        # 更新统计
        self._completion_count += 1

        # 显示现代AI状态指示器 - 准备状态
        modern_indicator = self._get_current_modern_indicator()
        if modern_indicator:
            modern_indicator.show_requesting("准备AI请求...")
            logger.debug("现代AI状态指示器已显示：准备中")
        
        # 同时更新工具栏状态
        self._update_toolbar_ai_status("准备中...")
        logger.debug("工具栏AI状态已更新为准备中")

        # 确保补全组件已初始化
        if not self._completion_widget:
            logger.info("初始化补全组件")
            self._completion_widget = self.get_completion_widget(self.parent())

        logger.info(f"编辑器状态: 文本长度={len(text)}, 光标位置={position}")

        context = {
            'text': text,
            'position': position,
            'mode': mode,
            'cursor_line': cursor.blockNumber(),
            'cursor_column': cursor.columnNumber()
        }

        # 如果有AI客户端，直接调用AI
        if self._ai_client:
            logger.info("使用AI客户端进行补全")

            # 显示现代AI状态指示器 - 思考状态
            modern_indicator = self._get_current_modern_indicator()
            if modern_indicator:
                modern_indicator.show_thinking("AI思考中...")
                logger.debug("现代AI状态指示器已显示：思考中")
            
            # 同时更新工具栏状态
            self._update_toolbar_ai_status("思考中")
            logger.debug("工具栏AI状态已更新为思考中")

            # 显示加载状态
            self._completion_widget.show_loading("AI正在思考...")
            self._position_completion_widget()

            # 构建智能补全提示词 - 发送完整章节内容
            prompt_text = self._extract_full_chapter_context(text, position)
            if len(prompt_text) > 8000:  # 大幅增加上下文长度
                prompt_text = prompt_text[-8000:]  # 取最后8000字符，包含完整章节

            # 分析当前上下文类型
            completion_type = self._detect_completion_type(text, position)
            
            # 获取RAG上下文（如果启用）- 带阻塞保护和模式选择
            rag_context = ""
            rag_enabled = self._config._config_data.get('rag', {}).get('enabled', False)
            
            # 添加RAG阻塞保护选项
            rag_anti_blocking = self._config._config_data.get('rag', {}).get('anti_blocking', True)
            
            if (self._rag_service and rag_enabled and mode != 'instant' and 
                not self._has_recent_rag_timeout()):  # 检查最近是否有RAG超时
                
                logger.debug(f"RAG功能已启用，开始构建上下文（模式: {self._context_mode}）")
                try:
                    if rag_anti_blocking:
                        # 使用非阻塞方式，严格超时控制
                        rag_context = self._build_rag_context_with_mode(text, position, self._context_mode)
                    else:
                        # 使用原有的快速方式
                        rag_context = self._build_rag_context_fast(text, position)
                        
                    if rag_context:
                        logger.debug(f"RAG上下文已构建，长度: {len(rag_context)} 字符，模式: {self._context_mode}")
                        
                except Exception as e:
                    logger.warning(f"RAG上下文构建失败，跳过: {e}")
                    # 记录RAG失败时间，用于后续避免
                    self._record_rag_timeout()
                    rag_context = ""
            else:
                reason = "未启用" if not rag_enabled else ("即时模式" if mode == 'instant' else "最近超时")
                logger.debug(f"RAG功能跳过: {reason}")

            # 构建专业的补全提示词（根据上下文模式调整）
            prompt = self._build_completion_prompt_with_mode(prompt_text, completion_type, position, rag_context, self._context_mode)

            # 根据补全类型调整token数量
            max_tokens = self._get_max_tokens_for_type(completion_type)

            self._ai_client.complete_async(
                prompt=prompt,
                max_tokens=max_tokens,
                context={'mode': mode, 'source': 'completion'}
            )
        else:
            logger.warning("AI客户端不可用，使用传统补全")
            # 显示加载状态
            if self._completion_widget:
                self._completion_widget.show_loading()
                self._position_completion_widget()

            # 发出请求信号
            self.completionRequested.emit(text, context)

        logger.debug(f"Completion requested: mode={mode}, position={position}")

    def _has_recent_rag_timeout(self) -> bool:
        """检查最近是否有RAG超时"""
        if not hasattr(self, '_last_rag_timeout'):
            return False
        
        current_time = time.time()
        # 如果最近5分钟内有超时，暂时跳过RAG
        return (current_time - self._last_rag_timeout) < 300
    
    def _record_rag_timeout(self):
        """记录RAG超时时间"""
        self._last_rag_timeout = time.time()
        logger.info("记录RAG超时，将在5分钟内跳过RAG功能")

    @pyqtSlot(str, dict)
    def _on_ai_completion_requested(self, text: str, context: dict):
        """处理智能补全管理器的AI补全请求"""
        logger.debug("Received AI completion request from smart completion manager")
        # 直接调用AI补全，使用manual模式表示这是手动触发的
        self.request_completion('manual')

    def _detect_completion_type(self, text: str, position: int) -> str:
        """检测补全类型"""
        # 获取光标前的文本
        before_cursor = text[:position]

        # 检查是否在@标记后
        if before_cursor.endswith('@char:') or before_cursor.endswith('@char: '):
            return 'character'
        elif before_cursor.endswith('@location:') or before_cursor.endswith('@location: '):
            return 'location'
        elif before_cursor.endswith('@time:') or before_cursor.endswith('@time: '):
            return 'time'
        elif '@' in before_cursor[-20:]:  # 最近20个字符内有@
            return 'metadata'

        # 检查markdown结构
        lines = before_cursor.split('\n')
        current_line = lines[-1] if lines else ""

        if current_line.startswith('#'):
            return 'heading'
        elif current_line.strip() == "":
            # 空行，可能需要段落补全
            return 'paragraph'
        else:
            # 普通文本补全
            return 'text'

    def _build_completion_prompt_with_mode(self, context_text: str, completion_type: str, position: int, rag_context: str, context_mode: str) -> str:
        """根据上下文模式构建专业的补全提示词（使用模板系统）"""
        
        # 如果提示词系统可用，使用模板系统
        if self._prompt_manager and self._prompt_renderer:
            try:
                return self._build_prompt_with_template_system(
                    context_text, completion_type, position, rag_context, context_mode
                )
            except Exception as e:
                logger.error(f"模板系统构建提示词失败，使用原有方法: {e}")
                # 继续使用原有方法作为备用
        
        # 原有的硬编码方法作为备用（保持兼容性）
        return self._build_completion_prompt_with_mode_fallback(context_text, completion_type, position, rag_context, context_mode)
    
    def _build_prompt_with_template_system(self, context_text: str, completion_type: str, position: int, rag_context: str, context_mode: str) -> str:
        """使用模板系统构建提示词"""
        
        # 获取当前模式的模板ID
        template_id = self.get_current_template_id(context_mode)
        template = self._prompt_manager.get_template(template_id)
        
        if not template:
            logger.error(f"未找到模板 {template_id}，使用默认备用方法")
            return self._build_completion_prompt_with_mode_fallback(context_text, completion_type, position, rag_context, context_mode)
        
        # 构建变量字典
        variables = {
            'context_text': context_text,
            'type_specific_guidance': self._get_enhanced_type_guidance(completion_type, context_mode),
            'context_analysis': self._analyze_writing_context(context_text, position),
            'rag_section': self._format_rag_section(rag_context, context_mode) if rag_context else "",
        }
        
        # 根据模式选择合适的用户模板
        mode_mapping = {
            'fast': PromptMode.FAST,
            'balanced': PromptMode.BALANCED,
            'full': PromptMode.FULL
        }
        
        prompt_mode = mode_mapping.get(context_mode, PromptMode.BALANCED)
        
        try:
            # 使用模板渲染器生成提示词
            return self._prompt_renderer.render_template(template, variables, prompt_mode)
        except Exception as e:
            logger.error(f"渲染模板失败: {e}")
            return self._build_completion_prompt_with_mode_fallback(context_text, completion_type, position, rag_context, context_mode)
    
    def _format_rag_section(self, rag_context: str, context_mode: str) -> str:
        """格式化RAG部分"""
        if not rag_context:
            return ""
        
        rag_prefix = {
            'fast': "🔍 关键背景信息",
            'balanced': "📚 项目相关资料", 
            'full': "🌟 丰富创作背景"
        }.get(context_mode, "📚 相关资料")
        
        return f"""# {rag_prefix}
```
{rag_context}
```
"""
    
    def _build_completion_prompt_with_mode_fallback(self, context_text: str, completion_type: str, position: int, rag_context: str, context_mode: str) -> str:
        """原有的硬编码提示词构建方法（作为备用）"""
        
        # 根据模式调整基础约束和期望输出（大幅优化）
        mode_configs = {
            'fast': {
                'max_completion': '15-30个字符',
                'context_type': '快速智能补全',
                'detail_level': '简洁精准',
                'output_style': '流畅的词语、短语或半句话',
                'instruction': '提供最快速、最自然的文字补全',
                'quality_focus': '流畅性和即时性',
                'tone': '自然流畅'
            },
            'balanced': {
                'max_completion': '50-120个字符',
                'context_type': '智能创作补全',
                'detail_level': '适度丰富',
                'output_style': '完整的句子或小段落，包含恰当的细节描写',
                'instruction': '提供高质量的创作补全，兼顾速度和文学性',
                'quality_focus': '文学性和连贯性',
                'tone': '生动自然'
            },
            'full': {
                'max_completion': '150-400个字符',
                'context_type': '深度文学创作',
                'detail_level': '丰富细腻',
                'output_style': '多句话或完整段落，可包含对话、动作、心理、环境等多层描写',
                'instruction': '提供最高质量的文学创作，追求艺术性和情节推进',
                'quality_focus': '文学性、情节推进和人物塑造',
                'tone': '富有文学感染力'
            }
        }
        
        config = mode_configs.get(context_mode, mode_configs['balanced'])
        
        # 【核心提示词系统】基于最佳实践的多层次提示词架构
        
        # 【第一层：角色设定与能力定义】
        role_definition = f"""你是一位经验丰富的小说创作大师，专精于{config['context_type']}。你具备以下核心能力：
✅ 深度理解故事脉络和人物关系
✅ 创作{config['tone']}的文学文本
✅ 精准把握故事节奏和情感张力
✅ 熟练运用各种文学技巧和修辞手法
✅ 能够根据上下文推进情节发展
✅ 善于塑造立体生动的人物形象"""

        # 【第二层：创作原则和质量标准】
        creation_principles = f"""核心创作原则：
1. 【连贯性】确保与前文的逻辑连贯和风格一致
2. 【自然性】语言流畅自然，符合中文表达习惯
3. 【情节性】适度推进故事发展，增加故事张力
4. 【人物性】保持角色性格的一致性和真实性
5. 【文学性】运用恰当的修辞手法，提升文字感染力
6. 【{config['quality_focus']}】重点关注{config['quality_focus']}"""

        # 【第三层：模式专用创作指导】
        if context_mode == 'fast':
            mode_guidance = """快速补全专用指导：
📝 输出要求：{max_completion}，{output_style}
🎯 创作重点：确保补全内容能够无缝衔接，优先考虑语言的流畅性
⚡ 速度优先：直接给出最符合语境的续写，无需过多修饰
✨ 质量控制：虽然追求速度，但仍需保证基本的文学质量""".format(**config)
        
        elif context_mode == 'balanced':
            mode_guidance = """智能补全专用指导：
📝 输出要求：{max_completion}，{output_style}
🎯 创作重点：平衡文学性和实用性，既要有文采又要推进情节
⚖️ 均衡发展：适度运用环境描写、心理描写、对话等技巧
🌟 品质保证：确保每个句子都有存在的意义，避免冗余表达
💡 创新性：在保持连贯的前提下，适当增加新颖的表达方式""".format(**config)
        
        else:  # full mode
            mode_guidance = """深度创作专用指导：
📝 输出要求：{max_completion}，{output_style}
🎯 创作重点：追求文学性和艺术性，可以大胆发挥创作才能
🎨 文学技巧：充分运用比喻、拟人、对比、烘托等修辞手法
🔮 情节发展：可以引入新的情节转折、人物冲突或环境变化
💫 情感深度：深入刻画人物的内心世界和情感变化
🌈 多元描写：综合运用：
   • 环境描写（营造氛围）
   • 心理描写（展现内心）
   • 动作描写（推进情节）
   • 对话描写（展现性格）
   • 感官描写（增强代入感）""".format(**config)

        # 【第四层：补全类型专业化处理】
        type_specific_guidance = self._get_enhanced_type_guidance(completion_type, context_mode)

        # 【第五层：智能上下文分析】
        context_analysis = self._analyze_writing_context(context_text, position)
        
        # 【第六层：构建最终提示词】
        prompt_sections = [
            f"# 🎯 {config['context_type']}任务",
            "",
            role_definition,
            "",
            creation_principles,
            "",
            mode_guidance,
            "",
            type_specific_guidance,
            "",
            "# 📖 当前创作上下文",
            f"```\n{context_text}\n```",
            "",
            context_analysis,
        ]
        
        # 【第七层：RAG增强背景信息】
        if rag_context and rag_context.strip():
            rag_prefix = {
                'fast': "🔍 关键背景信息",
                'balanced': "📚 项目相关资料", 
                'full': "🌟 丰富创作背景"
            }.get(context_mode, "📚 相关资料")
            
            prompt_sections.extend([
                f"# {rag_prefix}",
                f"```\n{rag_context}\n```",
                "",
            ])
        
        # 【第八层：输出格式和最终要求】
        final_requirements = f"""# ✍️ 创作输出要求

🎨 创作任务：基于以上上下文，创作{config['max_completion']}的{config['context_type']}内容
📏 输出规范：{config['output_style']}
🎭 风格要求：{config['tone']}，确保与原文风格保持一致
⚡ 特别注意：
   • 直接输出续写内容，无需任何解释或说明
   • 确保开头能够无缝衔接当前文本
   • 保持人物性格和故事逻辑的连贯性
   • 语言要{config['detail_level']}，符合小说创作标准

🔖 开始创作："""

        prompt_sections.append(final_requirements)
        
        final_prompt = "\n".join(prompt_sections)
        
        logger.debug(f"构建优化提示词({context_mode}模式): {len(final_prompt)} 字符")
        return final_prompt

    def _get_enhanced_type_guidance(self, completion_type: str, context_mode: str) -> str:
        """获取增强的类型专用指导（融合最佳实践）"""
        
        type_guidance_map = {
            'character': {
                'fast': """# 👤 角色快速补全指导
• 补全角色姓名或简短特征
• 确保名称符合故事背景和时代设定
• 优先使用简洁有力的描述""",
                
                'balanced': """# 👤 角色智能补全指导
• 可包含角色的外貌、性格或行为特征
• 注重角色的独特性和个性化描写
• 适当融入角色与情节的关联
• 使用生动具体的形容词和动词""",
                
                'full': """# 👤 角色深度补全指导
• 全方位塑造角色形象：外貌、性格、背景、情感状态
• 运用对比、细节、象征等手法突出角色特色
• 可加入角色与环境、其他人物的互动描写
• 通过行为、语言、心理活动展现角色深度
• 考虑角色在故事中的作用和发展轨迹"""
            },
            
            'location': {
                'fast': """# 🏛️ 场景快速补全指导
• 补全地点名称或关键场景特征
• 使用简洁的空间定位词汇
• 突出场景的功能性特点""",
                
                'balanced': """# 🏛️ 场景智能补全指导
• 描绘场景的视觉特征和空间布局
• 融入恰当的氛围营造和环境细节
• 考虑场景与情节发展的关系
• 运用感官描写增强代入感""",
                
                'full': """# 🏛️ 场景深度补全指导
• 多维度场景构建：视觉、听觉、嗅觉、触觉、味觉
• 场景与情绪氛围的深度结合
• 环境对人物心理和行为的影响
• 场景的象征意义和隐喻作用
• 通过环境细节推进情节发展
• 营造身临其境的阅读体验"""
            },
            
            'paragraph': {
                'fast': """# 📝 段落快速补全指导
• 提供1-2个词语或短句
• 确保语法正确，逻辑清晰
• 保持与前文的自然衔接""",
                
                'balanced': """# 📝 段落智能补全指导
• 创作1-2句完整的叙述或对话
• 平衡叙述节奏，适度推进情节
• 注重句式变化和语言节奏
• 可适当运用修辞手法增色""",
                
                'full': """# 📝 段落深度补全指导
• 创作完整段落，可包含多个层次的内容：
  - 📝 叙述：推进故事情节
  - 💬 对话：展现人物性格和关系
  - 🧠 心理：深入人物内心世界
  - 🌄 环境：营造场景氛围
  - 🎭 动作：展现人物行为和状态
• 运用多样化的句式结构
• 注重段落的内在逻辑和情感流向
• 可引入适度的情节转折或新元素"""
            },
            
            'text': {
                'fast': """# ✨ 文本快速补全指导
• 提供几个关键词或简短表达
• 确保用词准确，表意清晰
• 符合语境和语体风格""",
                
                'balanced': """# ✨ 文本智能补全指导
• 创作完整的表达或句子
• 平衡描写和叙述的比重
• 注重语言的韵律和美感
• 适当使用文学技巧提升品质""",
                
                'full': """# ✨ 文本深度补全指导
• 根据上下文灵活选择创作重点：
  - 🎪 情节推进：引入新的故事发展
  - 👥 人物刻画：深化角色形象
  - 🎨 环境渲染：营造独特氛围
  - 💭 情感表达：传递深层情感
  - 🔀 结构转换：实现场景或视角转换
• 充分运用各种文学表现手法
• 创造富有感染力的阅读体验
• 在创新性和连贯性之间找到平衡"""
            }
        }
        
        return type_guidance_map.get(completion_type, type_guidance_map['text']).get(context_mode, type_guidance_map['text']['balanced'])

    def _analyze_writing_context(self, context_text: str, position: int) -> str:
        """智能分析写作上下文，提供创作指导（新增功能）"""
        try:
            analysis_points = []
            
            # 分析文本特征
            if len(context_text) > 100:
                # 情感基调分析
                emotional_words = {
                    '积极': ['开心', '高兴', '快乐', '兴奋', '满意', '成功', '胜利', '希望', '光明', '温暖'],
                    '消极': ['难过', '伤心', '痛苦', '失望', '绝望', '愤怒', '恐惧', '黑暗', '寒冷', '孤独'],
                    '紧张': ['紧张', '焦虑', '担心', '急迫', '危险', '冲突', '激烈', '快速', '匆忙', '压力'],
                    '平和': ['平静', '安静', '和谐', '舒适', '温和', '缓慢', '稳定', '轻松', '自然', '平衡']
                }
                
                tone_scores = {}
                for tone, words in emotional_words.items():
                    score = sum(context_text.count(word) for word in words)
                    if score > 0:
                        tone_scores[tone] = score
                
                if tone_scores:
                    dominant_tone = max(tone_scores, key=tone_scores.get)
                    analysis_points.append(f"🎭 情感基调：{dominant_tone}氛围，继续保持这种情绪节奏")
            
            # 对话识别
            if '"' in context_text or '"' in context_text:
                quote_count = context_text.count('"') + context_text.count('"')
                if quote_count % 2 == 1:
                    analysis_points.append("💬 当前在对话中，优先考虑对话内容或对话后的动作描写")
                else:
                    analysis_points.append("💬 检测到对话内容，可考虑人物反应或新的对话")
            
            # 段落结构分析
            paragraphs = context_text.split('\n\n')
            if len(paragraphs) > 1:
                last_para = paragraphs[-1].strip()
                if len(last_para) > 200:
                    analysis_points.append("📄 当前段落较长，可考虑分段或转换场景")
                elif len(last_para) < 50:
                    analysis_points.append("📄 当前段落较短，适合继续扩展内容")
            
            # 场景转换检测
            transition_words = ['突然', '这时', '接着', '然后', '于是', '不久', '随后', '过了一会儿']
            for word in transition_words:
                if word in context_text[-100:]:  # 检查最后100字符
                    analysis_points.append("🔄 检测到场景转换词，适合引入新的情节发展")
                    break
            
            # 时间推进分析
            time_words = ['早上', '中午', '下午', '晚上', '深夜', '昨天', '今天', '明天']
            recent_time_refs = [word for word in time_words if word in context_text[-200:]]
            if recent_time_refs:
                analysis_points.append(f"⏰ 时间背景：{recent_time_refs[-1]}，可考虑时间推进或时间相关的情节")
            
            if analysis_points:
                return "# 🔍 上下文智能分析\n" + "\n".join(f"• {point}" for point in analysis_points)
            else:
                return "# 🔍 上下文智能分析\n• 📝 标准创作情境，发挥创作才能，保持与前文的连贯性"
                
        except Exception as e:
            logger.debug(f"上下文分析失败: {e}")
            return "# 🔍 上下文智能分析\n• 📝 基于当前上下文进行创作，保持故事的连贯性和文学性"

    def _build_completion_prompt(self, context_text: str, completion_type: str, position: int, rag_context: str = "") -> str:
        """构建专业的补全提示词 - 支持多行补全和RAG上下文"""

        # 基础约束
        base_constraints = """请提供智能文本补全，遵循以下规则：
1. 只补全当前光标位置后的内容，不要重复已有文本
2. 补全长度控制：通常1-2句话，最多50个字符
3. 保持与上下文的连贯性和一致性
4. 遵循中文写作习惯，注意标点符号和语法
5. 不要添加不必要的解释或额外内容
6. 如果是对话，注意对话格式和换行"""

        # 根据补全类型定制提示词
        if completion_type == 'character':
            specific_prompt = "补全角色名称，例如：李明、王小雨等。只返回角色名称。"
        elif completion_type == 'location':
            specific_prompt = "补全地点名称，例如：咖啡厅、公园、学校等。只返回地点名称。"
        elif completion_type == 'time':
            specific_prompt = "补全时间描述，例如：2024年春天、上午十点、黄昏时分等。只返回时间描述。"
        elif completion_type == 'metadata':
            specific_prompt = "补全元数据标记的值，保持简洁。"
        elif completion_type == 'heading':
            specific_prompt = "补全章节标题，保持简洁有意义。"
        elif completion_type == 'paragraph':
            specific_prompt = """提供段落级补全，可以包含：
- 完整的句子或段落
- 对话内容（如果上下文是对话）
- 场景描述（如果上下文是叙述）
- 适当的换行和结构"""
        else:
            specific_prompt = """根据上下文智能补全：
- 如果是句子中间：补全词语或短语
- 如果是句子结尾：提供下一句话
- 如果是段落结尾：提供下一段内容
- 支持多行补全，保持自然的文本结构"""

        # 构建完整提示词
        prompt_parts = [base_constraints, "", specific_prompt, "", "上下文：", context_text]
        
        # 如果有RAG上下文，添加到提示词中
        if rag_context:
            prompt_parts.extend(["", rag_context])
        
        prompt_parts.extend(["", "补全内容："])
        
        return "\n".join(prompt_parts)

    def _get_max_tokens_for_type(self, completion_type: str) -> int:
        """根据补全类型和上下文模式获取最大token数量"""
        # 基础token限制
        base_limits = {
            'character': 20,    # 角色名称：短
            'location': 20,     # 地点名称：短
            'time': 30,         # 时间描述：中等
            'metadata': 25,     # 元数据：短
            'heading': 40,      # 标题：中等
            'paragraph': 120,   # 段落：长
            'text': 80          # 普通文本：中等
        }
        
        base_tokens = base_limits.get(completion_type, 80)
        
        # 根据上下文模式调整token数量
        mode_multipliers = {
            'fast': 0.6,        # 快速模式：减少60%
            'balanced': 1.0,    # 平衡模式：标准
            'full': 2.5         # 全局模式：增加150%
        }
        
        multiplier = mode_multipliers.get(self._context_mode, 1.0)
        adjusted_tokens = int(base_tokens * multiplier)
        
        # 设置合理的上下限
        min_tokens = 15
        max_tokens = 300 if self._context_mode == 'full' else 150
        
        return max(min_tokens, min(adjusted_tokens, max_tokens))

    def _format_ai_response(self, response: str) -> str:
        """格式化AI响应，应用文学写作规则"""
        if not response or not self._current_editor:
            return response

        try:
            # 获取光标前的上下文
            cursor = self._current_editor.textCursor()
            text = self._current_editor.toPlainText()
            position = cursor.position()
            context_before = text[:position]

            # 应用文学格式化，传递当前的上下文模式
            formatted_response = literary_formatter.format_completion(
                response, 
                context_before, 
                self._context_mode  # 传递上下文模式
            )

            # 如果启用了标点符号辅助，检查是否需要添加标点
            if self._punctuation_assist_enabled and not formatted_response.strip():
                punctuation = literary_formatter.suggest_punctuation(text, position)
                if punctuation:
                    formatted_response = punctuation
                    logger.debug(f"标点符号建议: '{punctuation}'")

            logger.debug(f"文学格式化({self._context_mode}模式): '{response}' -> '{formatted_response}'")
            return formatted_response

        except Exception as e:
            logger.error(f"文学格式化失败: {e}")
            return response

    def show_completion_suggestions(self, suggestions: List[Dict[str, Any]]):
        """显示补全建议"""
        if not self._completion_widget:
            return
        
        self._completion_widget.hide_loading()
        self._completion_widget.show_suggestions(suggestions)
        self._position_completion_widget()
        
        logger.debug(f"Showing {len(suggestions)} completion suggestions")
    
    def start_stream_response(self, prompt: str = ""):
        """开始流式响应"""
        logger.info(f"AI流式响应请求: {prompt[:50]}...")

        if not self._stream_widget:
            logger.info("初始化流式组件")
            self._stream_widget = self.get_stream_widget(self.parent())

        # 如果有AI客户端，使用真实的AI调用
        if self._ai_client and prompt:
            logger.info(f"使用AI客户端进行流式响应: {prompt[:50]}...")
            self._ai_client.complete_stream_async(
                prompt=prompt,
                context={'stream': True, 'source': 'stream_widget'}
            )
        else:
            logger.warning("AI客户端不可用或无提示词，使用模拟流式响应")
            # 回退到原有的模拟流式响应
            self._stream_widget.start_streaming(prompt)

        self._position_stream_widget()
        logger.debug("Stream response started")
    
    def append_stream_text(self, text: str):
        """追加流式文本"""
        if self._stream_widget:
            self._stream_widget.append_text(text)
    
    def complete_stream_response(self):
        """完成流式响应"""
        if self._stream_widget:
            self._stream_widget.complete_streaming()
    
    def _position_completion_widget(self):
        """定位补全组件"""
        if not self._completion_widget or not self._current_editor:
            return
        
        # 获取光标位置
        cursor = self._current_editor.textCursor()
        cursor_rect = self._current_editor.cursorRect(cursor)
        
        # 转换为全局坐标
        global_pos = self._current_editor.mapToGlobal(cursor_rect.bottomLeft())
        
        # 调整位置避免超出屏幕
        widget_size = self._completion_widget.size()
        screen_geometry = self._current_editor.screen().geometry()
        
        x = global_pos.x()
        y = global_pos.y() + 5
        
        # 确保不超出屏幕右边界
        if x + widget_size.width() > screen_geometry.right():
            x = screen_geometry.right() - widget_size.width()
        
        # 确保不超出屏幕下边界
        if y + widget_size.height() > screen_geometry.bottom():
            y = global_pos.y() - widget_size.height() - 5
        
        self._completion_widget.move(x, y)
    
    def _position_stream_widget(self):
        """定位流式响应组件"""
        if not self._stream_widget or not self._current_editor:
            return
        
        # 在编辑器右侧显示
        editor_geometry = self._current_editor.geometry()
        parent_pos = self._current_editor.parent().mapToGlobal(editor_geometry.topRight())
        
        x = parent_pos.x() + 10
        y = parent_pos.y()
        
        self._stream_widget.move(x, y)
    
    @pyqtSlot()
    def _on_text_changed(self):
        """文本变化处理（优化版本：debouncing + 智能过滤）"""
        if not self._auto_trigger_enabled or not self._current_editor:
            return

        # 检查当前补全模式
        if hasattr(self._current_editor, '_smart_completion'):
            current_mode = getattr(self._current_editor._smart_completion, '_completion_mode', 'auto_ai')
            # 只有在自动AI模式下才自动触发
            if current_mode != 'auto_ai':
                return
        
        # 智能过滤：检查文本变化是否值得触发AI补全
        if not self._should_trigger_on_text_change():
            return
        
        # 实现debouncing：重启定时器，只有在用户停止输入后才触发
        self._completion_timer.stop()
        self._completion_timer.start(self._debounce_delay)
        
        logger.debug(f"文本变化触发防抖计时器: {self._debounce_delay}ms")
    
    @pyqtSlot()
    def _on_cursor_changed(self):
        """光标位置变化处理"""
        # 隐藏补全建议
        if self._completion_widget and self._completion_widget.isVisible():
            self._completion_widget.hide()
    
    def _should_trigger_on_text_change(self) -> bool:
        """判断文本变化是否应该触发AI补全"""
        if not self._current_editor:
            return False
        
        try:
            # 获取当前文本和光标位置
            text = self._current_editor.toPlainText()
            cursor = self._current_editor.textCursor()
            position = cursor.position()
            
            # 文本过短，不触发
            if len(text) < self._min_trigger_chars:
                return False
            
            # 计算文本哈希，避免重复处理相同内容
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()
            if text_hash == self._last_text_hash:
                return False
            self._last_text_hash = text_hash
            
            # 检查光标前的文本，判断是否在合适的位置触发
            text_before_cursor = text[:position]
            
            # 如果光标前的文本太短，不触发
            if len(text_before_cursor.strip()) < self._min_trigger_chars:
                return False
            
            # 检查是否在输入过程中（如连续输入中文、英文等）
            # 如果刚刚输入了标点符号或换行，更适合触发
            last_char = text_before_cursor[-1] if text_before_cursor else ''
            if last_char in '。！？，；\n ':  # 句子结束或段落换行
                return True
            
            # 检查光标前最近的几个字符，如果都是字母或中文，可能还在输入中
            recent_text = text_before_cursor[-5:] if len(text_before_cursor) >= 5 else text_before_cursor
            if recent_text.isalnum() and len(recent_text) >= 3:  # 连续输入字母数字
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"检查触发条件时出错: {e}")
            return False
    
    def _debounced_trigger_completion(self):
        """防抖触发补全（用户停止输入后调用）"""
        if not self._current_editor:
            return
        
        # Throttling检查：限制补全请求频率
        current_time = time.time() * 1000  # 转换为毫秒
        if current_time - self._last_completion_time < self._throttle_interval:
            logger.debug(f"节流限制：距离上次补全仅 {current_time - self._last_completion_time:.0f}ms，跳过")
            return
        
        # 最终检查：确保此时仍然适合触发补全
        if not self._should_trigger_on_text_change():
            logger.debug("最终检查：当前不适合触发补全")
            return
        
        logger.debug("防抖计时器触发AI补全")
        self._last_completion_time = current_time
        
        # 异步触发补全，避免阻塞主线程
        QTimer.singleShot(0, lambda: self.request_completion('smart'))
    
    def _trigger_completion(self):
        """触发补全（旧方法，保持兼容性）"""
        self._debounced_trigger_completion()
    
    @pyqtSlot(str, dict)
    def _on_suggestion_accepted(self, content: str, suggestion_data: dict):
        """建议接受处理"""
        if not self._current_editor:
            return

        # 更新接受统计
        self._acceptance_count += 1

        # 插入建议内容
        cursor = self._current_editor.textCursor()
        cursor.insertText(content)

        # 触发新的补全
        if self._auto_trigger_enabled:
            self.request_completion('instant')

        acceptance_rate = self._acceptance_count/self._completion_count*100 if self._completion_count > 0 else 0
        logger.info(f"Suggestion accepted: {content[:50]}... (接受率: {acceptance_rate:.1f}%)")
    
    @pyqtSlot(dict)
    def _on_suggestion_rejected(self, suggestion_data: dict):
        """建议拒绝处理"""
        logger.debug("Suggestion rejected")
    
    @pyqtSlot()
    def _on_more_options_requested(self):
        """更多选项请求处理"""
        self.request_completion('smart')
    
    @pyqtSlot(str)
    def _on_response_completed(self, response: str):
        """流式响应完成处理"""
        logger.info(f"Stream response completed: {len(response)} characters")
    
    @pyqtSlot()
    def _on_response_cancelled(self):
        """流式响应取消处理"""
        logger.info("Stream response cancelled")
    
    @pyqtSlot(str)
    def _on_response_accepted(self, response: str):
        """流式响应接受处理"""
        if not self._current_editor:
            return
        
        # 插入响应内容
        cursor = self._current_editor.textCursor()
        cursor.insertText(response)
        
        logger.info(f"Stream response accepted: {len(response)} characters")
    
    @pyqtSlot(dict)
    def _on_unified_config_saved(self, config: dict):
        """处理统一配置保存"""
        try:
            # 处理API配置
            api_config = config.get('api', {})
            if api_config:
                # 重新初始化AI客户端
                self._init_ai_client()
                logger.info("AI客户端配置已更新")
            
            # 处理补全配置
            completion_config = config.get('completion', {})
            if completion_config:
                # 应用补全设置
                self.set_completion_enabled(completion_config.get('completion_enabled', True))
                self.set_auto_trigger_enabled(completion_config.get('auto_trigger_enabled', True))
                self.set_punctuation_assist_enabled(completion_config.get('punctuation_assist', True))
                self.set_trigger_delay(completion_config.get('trigger_delay', 500))
                
                # 设置补全模式
                mode_mapping = {
                    '自动AI补全': 'auto_ai',
                    '手动AI补全': 'manual_ai', 
                    '禁用补全': 'disabled'
                }
                mode_text = completion_config.get('completion_mode', '自动AI补全')
                mode = mode_mapping.get(mode_text, 'auto_ai')
                self.set_completion_mode(mode)
                
                logger.info("AI补全设置已更新")
            
            # 发出配置变更信号
            self.configChanged.emit(config)
            
        except Exception as e:
            logger.error(f"处理统一配置保存失败: {e}")

    @pyqtSlot(dict)
    def _on_config_saved(self, config: dict):
        """配置保存处理"""
        self._config = config
        self.configChanged.emit(config)
        
        logger.info("AI config updated")
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self._config = config
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._config.get_ai_config()
    
    def cleanup(self):
        """清理资源"""
        if self._completion_timer:
            self._completion_timer.stop()

        if self._completion_widget:
            self._completion_widget.hide()
            self._completion_widget.deleteLater()
            self._completion_widget = None

        if self._stream_widget:
            self._stream_widget.hide()
            self._stream_widget.deleteLater()
            self._stream_widget = None

        if self._config_dialog:
            self._config_dialog.deleteLater()
            self._config_dialog = None

        # 清理AI客户端
        if self._ai_client:
            self._ai_client.cleanup()
            self._ai_client = None

        logger.info("AI manager cleaned up")

    # AI客户端响应处理方法
    @pyqtSlot(str, dict)
    def _on_ai_response_received(self, response: str, context: dict):
        """AI响应接收处理"""
        logger.info(f"AI响应接收: {len(response)} 字符")

        # 显示现代AI状态指示器 - 完成状态
        modern_indicator = self._get_current_modern_indicator()
        if modern_indicator:
            modern_indicator.show_completed("AI生成完成")
            logger.debug("现代AI状态指示器已显示：完成")
        
        # 同时更新工具栏状态
        self._update_toolbar_ai_status("就绪")
        logger.debug("工具栏AI状态已更新为就绪")

        # 根据上下文类型处理响应
        if context.get('stream', False):
            # 流式响应完成
            if self._stream_widget:
                self._stream_widget.set_final_response(response)
        else:
            # 应用文学格式化
            formatted_response = self._format_ai_response(response)

            # 同步响应 - 优先使用Ghost Text补全
            if self._current_editor and hasattr(self._current_editor, 'show_ghost_ai_completion'):
                # 第一优先级：Ghost Text补全（最佳用户体验）
                self._current_editor.show_ghost_ai_completion(formatted_response)
                logger.info(f"Ghost Text AI补全已显示: {formatted_response[:50]}...")
            elif self._current_editor and hasattr(self._current_editor, '_smart_completion'):
                # 第二优先级：智能补全管理器
                self._current_editor._smart_completion.show_ai_completion(formatted_response)
                logger.info(f"智能AI补全已显示: {formatted_response[:50]}...")
            elif self._current_editor and hasattr(self._current_editor, 'show_inline_ai_completion'):
                # 第三优先级：内联补全
                self._current_editor.show_inline_ai_completion(formatted_response)
                logger.info(f"内联AI补全已显示: {formatted_response[:50]}...")
            elif self._completion_widget:
                # 最后回退：弹出式补全
                suggestions = [{
                    'content': formatted_response,
                    'type': 'AI补全',
                    'confidence': 0.9,
                    'source': 'ai',
                    'description': '基于上下文的AI续写建议'
                }]

                self._completion_widget.show_suggestions(suggestions)
                self._position_completion_widget()

                logger.info(f"弹出式AI补全已显示: {response[:50]}...")
            else:
                logger.warning("补全组件未初始化，无法显示AI响应")

    @pyqtSlot(str, dict)
    def _on_ai_stream_chunk(self, chunk: str, context: dict):
        """AI流式数据块处理"""
        if self._stream_widget:
            self._stream_widget.append_chunk(chunk)

    @pyqtSlot(str, dict)
    def _on_ai_error(self, error: str, context: dict):
        """AI错误处理"""
        logger.error(f"AI请求错误: {error}")

        # 显示现代AI状态指示器 - 错误状态
        modern_indicator = self._get_current_modern_indicator()
        if modern_indicator:
            error_msg = error[:30] + "..." if len(error) > 30 else error
            modern_indicator.show_error(f"生成失败: {error_msg}")
            logger.debug(f"现代AI状态指示器已显示：错误 - {error_msg}")
        
        # 同时更新工具栏状态
        self._update_toolbar_ai_status("错误")
        logger.debug("工具栏AI状态已更新为错误")

        # 根据上下文显示错误信息
        if context.get('stream', False):
            # 流式响应错误
            if self._stream_widget:
                self._stream_widget.show_error(error)
        else:
            # 补全响应错误
            if self._completion_widget:
                self._completion_widget.show_error(error)
            else:
                logger.warning("补全组件未初始化，无法显示错误信息")

    @pyqtSlot(dict)
    def _on_ai_request_started(self, context: dict):
        """AI请求开始处理"""
        logger.debug("AI请求已开始")

        # 显示现代AI状态指示器 - 生成状态
        modern_indicator = self._get_current_modern_indicator()
        if modern_indicator:
            if context.get('stream', False):
                modern_indicator.show_generating("流式生成中...")
            else:
                modern_indicator.show_generating("内容生成中...")
            logger.debug("现代AI状态指示器已显示：生成中")

        # 显示加载状态
        if context.get('stream', False) and self._stream_widget:
            self._stream_widget.show_loading()

    @pyqtSlot(dict)
    def _on_ai_request_completed(self, context: dict):
        """AI请求完成处理"""
        logger.debug("AI请求已完成")

        # 现代AI状态指示器会在响应接收时自动显示完成状态
        # 这里不需要额外处理，因为完成状态会在_on_ai_response_received中显示

        # 隐藏加载状态
        if context.get('stream', False):
            # 流式响应完成
            if self._stream_widget and hasattr(self._stream_widget, 'hide_loading'):
                self._stream_widget.hide_loading()
        else:
            # 补全响应完成
            if self._completion_widget and hasattr(self._completion_widget, 'hide_loading'):
                self._completion_widget.hide_loading()
    
    def _init_rag_service(self):
        """初始化RAG服务"""
        try:
            # 获取RAG配置
            rag_config = self._config._config_data.get('rag', {})
            
            # 如果没有配置，尝试获取默认配置
            if not rag_config:
                logger.info("未找到RAG配置，跳过初始化")
                return
            
            # 检查是否启用RAG
            rag_enabled = rag_config.get('enabled', False)
            
            # 如果未启用但有API key，自动启用
            if not rag_enabled and rag_config.get('api_key', '').strip():
                logger.info("发现RAG API配置，自动启用RAG功能")
                rag_config['enabled'] = True
                self._config._config_data['rag'] = rag_config
                self._config.save()
                rag_enabled = True
            
            if not rag_enabled:
                logger.info("RAG功能未启用")
                return
            
            # 导入必要的模块
            from core.rag_service import RAGService, RAGContext
            from core.sqlite_vector_store import SQLiteVectorStore
            
            # 获取当前项目路径
            project_path = None
            
            # 方法1：从共享对象获取
            if self._shared and hasattr(self._shared, 'current_project_path') and self._shared.current_project_path:
                project_path = str(self._shared.current_project_path)
                logger.debug(f"从共享对象获取项目路径: {project_path}")
            
            # 方法2：从主窗口获取项目管理器
            if not project_path and hasattr(self.parent(), '_project_manager'):
                project_manager = self.parent()._project_manager
                current_project = project_manager.get_current_project()
                if current_project and current_project.project_path:
                    project_path = current_project.project_path
                    logger.debug(f"从项目管理器获取项目路径: {project_path}")
            
            if not project_path:
                logger.warning("无法获取项目路径，RAG功能暂时不可用")
                return
            
            # 清理旧的RAG服务
            if self._rag_service:
                self._rag_service = None
            if self._vector_store:
                self._vector_store = None
            
            # 初始化向量存储
            db_path = f"{project_path}/rag_vectors.db"
            self._vector_store = SQLiteVectorStore(db_path)
            logger.info(f"SQLite向量存储已初始化: {db_path}")
            
            # 初始化RAG服务
            self._rag_service = RAGService(rag_config)
            
            # 设置向量存储引用
            self._rag_service.set_vector_store(self._vector_store)
            
            logger.info(f"RAG服务已初始化，使用模型: {rag_config.get('embedding', {}).get('model', 'N/A')}")
            
        except Exception as e:
            logger.error(f"初始化RAG服务失败: {e}")
            self._rag_service = None
            self._vector_store = None
    
    def _init_prompt_system(self):
        """初始化提示词管理系统"""
        try:
            if not PROMPT_SYSTEM_AVAILABLE:
                logger.warning("提示词系统不可用，使用默认配置")
                return
            
            # 初始化提示词管理器
            self._prompt_manager = EnhancedPromptManager()
            self._prompt_renderer = PromptRenderer()
            
            # 加载内置模板
            try:
                builtin_templates = BuiltinTemplateLibrary.load_all_templates()
                for template in builtin_templates:
                    self._prompt_manager.add_template(template)
                logger.info(f"已加载 {len(builtin_templates)} 个内置提示词模板")
            except Exception as e:
                logger.error(f"加载内置模板失败: {e}")
                
            # 验证当前选择的模板是否存在
            for mode, template_id in self._current_template_ids.items():
                if not self._prompt_manager.get_template(template_id):
                    logger.warning(f"模板 {template_id} 不存在，使用默认模板")
                    # 使用第一个可用的AI补全模板作为默认
                    templates = [t for t in self._prompt_manager.templates.values() 
                               if t.category == "AI补全"]
                    if templates:
                        self._current_template_ids[mode] = templates[0].id
                        logger.info(f"为 {mode} 模式设置默认模板: {templates[0].id}")
                        
            logger.info("提示词管理系统初始化完成")
            
        except Exception as e:
            logger.error(f"初始化提示词系统失败: {e}")
            self._prompt_manager = None
            self._prompt_renderer = None
    
    def get_available_templates(self, completion_type: str = None) -> List[Dict[str, str]]:
        """获取可用的提示词模板列表"""
        if not self._prompt_manager:
            return []
        
        templates = []
        for template in self._prompt_manager.templates.values():
            # 如果指定了类型，只返回匹配的类型
            if completion_type and template.category != completion_type:
                continue
                
            templates.append({
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'category': template.category,
                'is_builtin': template.is_builtin
            })
        
        return sorted(templates, key=lambda x: (not x['is_builtin'], x['name']))
    
    def set_template_for_mode(self, mode: str, template_id: str):
        """为指定模式设置提示词模板"""
        if mode in self._current_template_ids:
            # 验证模板是否存在
            if self._prompt_manager and self._prompt_manager.get_template(template_id):
                self._current_template_ids[mode] = template_id
                logger.info(f"为 {mode} 模式设置模板: {template_id}")
                
                # 保存到配置
                template_config = self._config._config_data.get('ai_templates', {})
                template_config[mode] = template_id
                self._config._config_data['ai_templates'] = template_config
                self._config.save()
            else:
                logger.error(f"模板 {template_id} 不存在")
    
    def get_current_template_id(self, mode: str) -> str:
        """获取指定模式的当前模板ID"""
        return self._current_template_ids.get(mode, f'ai_{mode}_completion')
    
    def _on_project_changed(self, project_path: str):
        """当项目变化时重新初始化RAG服务"""
        logger.info(f"项目变化，项目路径: {project_path}")
        
        try:
            if project_path and project_path.strip():
                # 项目打开，重新初始化RAG服务
                logger.info(f"项目打开，重新初始化RAG服务: {project_path}")
                self._init_rag_service()
                
                # 确保AI客户端仍然可用（防止项目切换时丢失）
                if not self._ai_client:
                    logger.warning("项目变化时发现AI客户端丢失，重新初始化")
                    self._init_ai_client()
            else:
                # 项目关闭，清理RAG服务但保持AI客户端
                logger.info("项目关闭，清理RAG服务但保持AI客户端")
                if self._rag_service:
                    self._rag_service = None
                if self._vector_store:
                    self._vector_store = None
                
                # 确保AI客户端在项目关闭后仍然可用
                if not self._ai_client:
                    logger.info("项目关闭后重新初始化AI客户端")
                    self._init_ai_client()
                    
        except Exception as e:
            logger.error(f"项目变化处理失败: {e}")
            # 尝试恢复AI客户端
            try:
                self._init_ai_client()
            except Exception as recovery_error:
                logger.error(f"AI客户端恢复失败: {recovery_error}")
    
    def update_rag_config(self, config: Dict[str, Any]):
        """更新RAG配置"""
        self._config._config_data['rag'] = config
        self._config.save()
        
        # 重新初始化RAG服务
        self._init_rag_service()
    
    def index_document(self, document_id: str, content: str):
        """索引文档内容（异步，支持增量更新）"""
        logger.debug(f"尝试异步索引文档: {document_id}")
        
        if not self._rag_service or not self._vector_store:
            logger.warning("RAG服务未初始化，无法索引文档")
            return
            
        if not content or not content.strip():
            logger.info(f"文档内容为空，跳过索引: {document_id}")
            return
        
        # 检查文档是否发生变化（增量更新）
        try:
            if not self._vector_store.has_document_changed(document_id, content):
                logger.info(f"文档内容未变化，跳过索引: {document_id}")
                return
        except Exception as e:
            logger.warning(f"检查文档变化失败，继续索引: {e}")
        
        # 更新异步索引器的服务引用
        self._async_indexer.set_services(self._rag_service, self._vector_store, self._config)
        
        # 将文档加入异步索引队列
        self._async_indexer.queue_document_index(document_id, content)
        logger.info(f"文档已提交异步索引（增量更新）: {document_id}, 内容长度: {len(content)}")
    
    def _update_toolbar_ai_status(self, status: str):
        """更新工具栏AI状态指示器"""
        try:
            # 查找主窗口的工具栏管理器
            main_window = self.parent()
            while main_window and not hasattr(main_window, '_toolbar_manager'):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, '_toolbar_manager'):
                toolbar_manager = main_window._toolbar_manager
                ai_toolbar = toolbar_manager.get_toolbar('ai')
                
                if ai_toolbar and hasattr(ai_toolbar, 'update_ai_status'):
                    ai_toolbar.update_ai_status(status)
                    logger.debug(f"工具栏AI状态已更新: {status}")
                else:
                    logger.warning("未找到AI工具栏或update_ai_status方法")
            else:
                logger.warning("未找到主窗口或工具栏管理器")
                
            # 同时更新现代AI状态指示器
            modern_indicator = self._get_current_modern_indicator()
            if modern_indicator:
                if "thinking" in status.lower() or "思考" in status or "工作" in status:
                    modern_indicator.show_thinking(status)
                elif "error" in status.lower() or "错误" in status:
                    modern_indicator.show_error(status)
                elif "就绪" in status or "ready" in status.lower():
                    modern_indicator.hide()
                else:
                    modern_indicator.show_requesting(status)
                logger.debug(f"现代AI状态指示器已更新: {status}")
                
        except Exception as e:
            logger.error(f"更新工具栏AI状态失败: {e}")
    
    def index_document_sync(self, document_id: str, content: str) -> bool:
        """同步索引文档内容（用于需要立即完成的场景）"""
        logger.debug(f"尝试同步索引文档: {document_id}")
        
        if not self._rag_service:
            logger.warning("RAG服务未初始化，无法索引文档")
            return False
            
        if not content or not content.strip():
            logger.info(f"文档内容为空，跳过索引: {document_id}")
            return True
        
        # 直接调用RAG服务的索引方法
        try:
            success = self._rag_service.index_document(document_id, content)
            if success:
                logger.info(f"同步索引完成: {document_id}")
            else:
                logger.error(f"同步索引失败: {document_id}")
            return success
            
        except Exception as e:
            logger.error(f"同步索引文档失败: {document_id}, 错误: {e}", exc_info=True)
            return False
    
    def delete_document_index(self, document_id: str):
        """删除文档索引"""
        if not self._vector_store:
            return
        
        try:
            count = self._vector_store.delete_document_embeddings(document_id)
            logger.info(f"已删除文档 {document_id} 的 {count} 个嵌入向量")
        except Exception as e:
            logger.error(f"删除文档索引失败: {e}")
    
    def search_similar_content(self, query: str, max_results: int = 30) -> str:
        """搜索相似内容（大幅增强版本：返回更多结果，提高精准度）"""
        if not self._rag_service or not self._vector_store:
            logger.warning("RAG服务未初始化，无法搜索")
            return ""
        
        # 性能保护：限制查询长度但增加结果数量
        if len(query) > 2000:  # 增加查询长度限制
            logger.warning("查询文本过长，截取前2000字符")
            query = query[:2000]
        
        max_results = min(max_results, 50)  # 最多50个结果，大幅提高
        
        try:
            # 快速检查向量存储是否有数据
            stats = self._vector_store.get_stats()
            if not stats or stats.get('total_documents', 0) == 0:
                logger.info("向量存储为空，使用降级搜索")
                return self._fallback_similar_search(query, max_results)
            
            # 性能监控：记录开始时间
            import time
            start_time = time.time()
            
            # 获取查询向量（带超时保护）
            query_embedding = None
            try:
                query_embedding = self._rag_service.create_embedding(query)
            except Exception as e:
                logger.warning(f"创建查询向量失败: {e}")
            
            if not query_embedding:
                logger.warning("无法创建查询向量，使用降级搜索")
                return self._fallback_similar_search(query, max_results)
            
            # 执行向量搜索（大幅增强参数）
            results = self._vector_store.similarity_search(
                query_embedding,
                limit=max_results,
                min_similarity=0.25  # 降低相似度要求，获得更多结果
            )
            
            # 性能检查：如果搜索用时过长，记录警告
            search_time = time.time() - start_time
            if search_time > 2.0:  # 增加到2秒，因为我们要更多结果
                logger.warning(f"向量搜索耗时过长: {search_time:.2f}秒")
            
            # 如果没有结果，尝试降级搜索
            if not results:
                logger.info("向量搜索无结果，尝试降级搜索")
                return self._fallback_similar_search(query, max_results)
            
            # 重排序优化（如果启用且网络可用）
            if (self._rag_service.rerank_enabled and 
                len(results) > 3 and  # 结果足够多时才重排序
                getattr(self._rag_service, '_network_available', True) and
                search_time < 1.0):  # 只有搜索很快时才重排序
                try:
                    rerank_start = time.time()
                    documents = [r[0]['chunk_text'] for r in results]
                    reranked = self._rag_service.rerank(query, documents, top_k=min(len(results), 40))
                    
                    rerank_time = time.time() - rerank_start
                    if rerank_time > 2.0:
                        logger.warning(f"重排序耗时过长: {rerank_time:.2f}秒，跳过重排序")
                    else:
                        # 重新排序结果
                        reranked_results = []
                        for idx, score in reranked:
                            if idx < len(results):
                                reranked_results.append((results[idx][0], score))
                        results = reranked_results
                except Exception as e:
                    logger.warning(f"重排序失败，使用原始搜索结果: {e}")
            
            # 构建上下文（增强版本，支持更长内容）
            context_parts = []
            total_length = 0
            max_context_length = 3000  # 大幅增加上下文总长度
            
            for emb_data, score in results[:max_results]:
                chunk_text = emb_data['chunk_text']
                # 增加单个块的长度限制
                if len(chunk_text) > 600:
                    chunk_text = chunk_text[:600] + "..."
                
                part = f"[{emb_data['document_id']} - 块{emb_data['chunk_index']} (相似度: {score:.2f})]\n{chunk_text}"
                
                if total_length + len(part) > max_context_length:
                    break
                
                context_parts.append(part)
                total_length += len(part)
            
            if context_parts:
                return "\n\n---\n\n".join(context_parts)
            else:
                return ""
            
        except Exception as e:
            logger.error(f"搜索相似内容失败，尝试降级搜索: {e}")
            return self._fallback_similar_search(query, max_results)
    
    def _fallback_similar_search(self, query: str, max_results: int = 10) -> str:
        """降级搜索策略：基于关键词匹配项目文档"""
        try:
            # 获取当前项目的所有文档
            if not hasattr(self.parent(), '_project_manager'):
                return ""
                
            project_manager = self.parent()._project_manager
            current_project = project_manager.get_current_project()
            if not current_project:
                return ""
            
            # 使用简单的关键词搜索
            query_words = set(query.lower().split())
            document_scores = []
            
            for doc_id, doc in current_project.documents.items():
                if not doc.content:
                    continue
                    
                content_words = set(doc.content.lower().split())
                # 计算词汇重叠度
                intersection = len(query_words.intersection(content_words))
                union = len(query_words.union(content_words))
                score = intersection / union if union > 0 else 0.0
                
                if score > 0.1:  # 最低相似度阈值
                    document_scores.append((doc_id, doc.name, doc.content[:500], score))
            
            # 排序并返回前N个结果
            document_scores.sort(key=lambda x: x[3], reverse=True)
            
            context_parts = []
            for doc_id, doc_name, content_preview, score in document_scores[:max_results]:
                context_parts.append(
                    f"[{doc_name} ({doc_id[:8]}...) - 关键词匹配度: {score:.2f}]\n"
                    f"{content_preview}..."
                )
            
            if context_parts:
                logger.info(f"降级搜索找到 {len(context_parts)} 个相关文档")
                return "\n\n---\n\n".join(context_parts)
            else:
                logger.info("降级搜索未找到相关内容")
                return ""
                
        except Exception as e:
            logger.error(f"降级搜索失败: {e}")
            return ""
    
    def _has_recent_rag_timeout(self) -> bool:
        """检查最近是否发生RAG超时"""
        if not hasattr(self, '_last_rag_timeout_time'):
            return False
        return time.time() - self._last_rag_timeout_time < 30  # 30秒内不再尝试
    
    def _record_rag_timeout(self):
        """记录RAG超时时间"""
        self._last_rag_timeout_time = time.time()
        logger.warning("已记录RAG超时，30秒内将跳过RAG")
    
    def _simple_text_match(self, query_text: str) -> str:
        """简单文本匹配（备用方案）"""
        try:
            # 获取当前项目的文档，简单关键词匹配
            if not hasattr(self.parent(), '_project_manager'):
                return ""
                
            project_manager = self.parent()._project_manager
            current_project = project_manager.get_current_project()
            if not current_project:
                return ""
            
            # 简单的关键词匹配
            query_words = set(query_text.lower().split()[:3])  # 只取前3个词
            if not query_words:
                return ""
            
            # 快速扫描最多3个文档
            for i, (doc_id, doc) in enumerate(current_project.documents.items()):
                if i >= 3:  # 最多检查3个文档
                    break
                    
                if not doc.content or len(doc.content) < 20:
                    continue
                    
                # 快速关键词匹配
                content_sample = doc.content[:200].lower()  # 只检查前200字符
                if any(word in content_sample for word in query_words if len(word) > 1):
                    # 找到匹配，返回简短片段
                    return doc.content[:100] + "..."
            
            return ""
            
        except Exception as e:
            logger.debug(f"简单文本匹配失败: {e}")
            return ""
    
    def _build_rag_context_with_mode(self, current_text: str, cursor_position: int, context_mode: str) -> str:
        """根据上下文模式构建RAG上下文（大幅优化版本）"""
        if not self._rag_service or not self._vector_store:
            return ""
        
        try:
            import time
            start_time = time.time()
            
            # 根据模式设置不同的参数（大幅增强）
            mode_configs = {
                'fast': {
                    'max_length': 8000,     # 大幅增加文本长度限制
                    'query_length': 200,    # 增加查询长度
                    'max_results': 15,      # 增加到15个结果
                    'timeout': 2.0,         # 增加超时时间
                    'context_limit': 800,   # 增加上下文长度
                    'min_similarity': 0.3   # 降低相似度要求
                },
                'balanced': {
                    'max_length': 15000,    # 大幅增加文本长度
                    'query_length': 400,    # 增加查询长度
                    'max_results': 35,      # 增加到35个结果
                    'timeout': 3.0,         # 增加超时时间
                    'context_limit': 1500,  # 大幅增加上下文长度
                    'min_similarity': 0.25  # 降低相似度要求
                },
                'full': {
                    'max_length': 25000,    # 允许更长文本
                    'query_length': 600,    # 大幅增加查询长度
                    'max_results': 50,      # 增加到50个结果
                    'timeout': 4.0,         # 增加超时时间
                    'context_limit': 2500,  # 大幅增加上下文长度
                    'min_similarity': 0.2   # 进一步降低相似度要求
                }
            }
            
            config = mode_configs.get(context_mode, mode_configs['balanced'])
            
            # 性能保护：检查文本长度
            if cursor_position > config['max_length']:
                logger.debug(f"文本过长（>{config['max_length']}字符），跳过RAG检索（{context_mode}模式）")
                return ""
            
            # 提取查询文本 - 使用更智能的上下文提取
            query_text = self._extract_smart_query_context(current_text, cursor_position, config['query_length'])
            
            if not query_text or len(query_text) < 3:
                return ""
            
            # 使用优化的异步RAG检索
            result = self._fast_rag_search_with_timeout(
                query_text, 
                config['max_results'], 
                config['timeout'],
                config['min_similarity']
            )
            
            if result:
                # 限制上下文长度
                context = result[:config['context_limit']] if len(result) > config['context_limit'] else result
                
                search_time = time.time() - start_time
                logger.info(f"{context_mode}模式RAG成功: {len(context)} 字符，用时 {search_time:.3f}秒")
                
                # 根据模式添加不同的前缀
                mode_prefixes = {
                    'fast': "快速参考:",
                    'balanced': "相关内容:",
                    'full': "深度背景资料:"
                }
                prefix = mode_prefixes.get(context_mode, "参考:")
                
                return f"\n\n{prefix}\n{context}"
                
            return ""
            
        except Exception as e:
            logger.error(f"{context_mode}模式RAG构建失败: {e}")
            return ""

    def _extract_full_chapter_context(self, text: str, cursor_position: int) -> str:
        """提取完整章节上下文，包含当前章节的上文、下文内容"""
        try:
            # 查找当前章节的边界
            lines = text.split('\n')
            cursor_line = text[:cursor_position].count('\n')
            
            # 寻找章节标记（如 # 标题、## 标题 或其他格式）
            chapter_patterns = [
                r'^#{1,3}\s+',      # Markdown 章节标题
                r'^第[一二三四五六七八九十\d]+章',  # 中文章节标记
                r'^Chapter\s+\d+',   # 英文章节标记
                r'^第[一二三四五六七八九十\d]+节',  # 中文节标记
            ]
            
            chapter_start = 0
            chapter_end = len(lines)
            
            # 向上查找章节开始
            for i in range(cursor_line, -1, -1):
                line = lines[i].strip()
                if any(re.match(pattern, line) for pattern in chapter_patterns):
                    chapter_start = i
                    break
            
            # 向下查找章节结束
            for i in range(cursor_line + 1, len(lines)):
                line = lines[i].strip()
                if any(re.match(pattern, line) for pattern in chapter_patterns):
                    chapter_end = i
                    break
            
            # 提取完整章节内容
            chapter_lines = lines[chapter_start:chapter_end]
            chapter_text = '\n'.join(chapter_lines)
            
            # 如果章节太长，智能截取
            if len(chapter_text) > 12000:
                # 优先保留光标附近的内容
                cursor_in_chapter = cursor_position - len('\n'.join(lines[:chapter_start]))
                context_radius = 6000  # 光标前后各6000字符
                
                start_pos = max(0, cursor_in_chapter - context_radius)
                end_pos = min(len(chapter_text), cursor_in_chapter + context_radius)
                
                chapter_text = chapter_text[start_pos:end_pos]
            
            logger.debug(f"提取完整章节上下文：{len(chapter_text)} 字符，章节范围: {chapter_start}-{chapter_end} 行")
            return chapter_text
            
        except Exception as e:
            logger.error(f"提取完整章节上下文失败: {e}")
            # 降级为简单上下文提取
            context_radius = 2000
            start_pos = max(0, cursor_position - context_radius)
            end_pos = min(len(text), cursor_position + context_radius)
            return text[start_pos:end_pos]

    def _extract_smart_query_context(self, text: str, cursor_position: int, max_length: int) -> str:
        """智能提取RAG查询上下文，包含更多关键信息（大幅增强版本）"""
        try:
            # 【增强1】扩大查询范围，提取更多关键词
            # 将查询范围扩展到光标前后更大的区域
            expanded_range = max(max_length * 2, 1500)  # 至少1500字符的分析范围
            start_pos = max(0, cursor_position - expanded_range)
            end_pos = min(len(text), cursor_position + expanded_range // 2)
            expanded_context = text[start_pos:end_pos]
            
            # 【增强2】多层次关键词提取
            keywords = self._extract_enhanced_keywords(expanded_context, cursor_position - start_pos)
            
            # 【增强3】智能段落和章节边界识别
            paragraphs = expanded_context.split('\n\n')
            current_pos = 0
            target_paragraph_idx = 0
            
            # 找到光标所在段落（在扩展上下文中的相对位置）
            relative_cursor_pos = cursor_position - start_pos
            for i, paragraph in enumerate(paragraphs):
                if current_pos + len(paragraph) >= relative_cursor_pos:
                    target_paragraph_idx = i
                    break
                current_pos += len(paragraph) + 2  # +2 for \n\n
            
            # 【增强4】扩展段落提取范围，包含更多上下文
            # 前后各取更多段落，确保有足够的关键词信息
            context_radius = 4  # 前后各4个段落
            start_idx = max(0, target_paragraph_idx - context_radius)
            end_idx = min(len(paragraphs), target_paragraph_idx + context_radius + 1)
            context_paragraphs = paragraphs[start_idx:end_idx]
            
            # 【增强5】智能内容优先级排序
            # 优先包含包含关键词的段落
            prioritized_paragraphs = []
            keyword_paragraphs = []
            normal_paragraphs = []
            
            for para in context_paragraphs:
                has_keywords = any(keyword.lower() in para.lower() for keyword in keywords[:10])
                if has_keywords:
                    keyword_paragraphs.append(para)
                else:
                    normal_paragraphs.append(para)
            
            # 优先包含关键词段落，然后补充普通段落
            prioritized_paragraphs = keyword_paragraphs + normal_paragraphs
            context_text = '\n\n'.join(prioritized_paragraphs)
            
            # 【增强6】如果上下文仍然太短，使用窗口扩展方法
            if len(context_text) < max_length * 1.5:  # 期望获得更长的上下文
                # 使用更大的窗口，包含光标前后更多内容
                window_start = max(0, cursor_position - max_length)
                window_end = min(len(text), cursor_position + max_length // 2)
                window_context = text[window_start:window_end]
                
                # 合并窗口上下文和段落上下文，去重
                combined_context = context_text + '\n\n' + window_context
                context_text = combined_context
            
            # 【增强7】智能边界截断，保持语义完整性
            if len(context_text) > max_length:
                # 优先在章节、段落边界截断
                chapter_markers = ['# ', '## ', '### ', '第', '章', '节']
                truncated = context_text[:max_length]
                
                # 尝试在章节标记处截断
                for marker in chapter_markers:
                    last_marker = truncated.rfind(marker)
                    if last_marker > max_length * 0.6:
                        # 找到标记行的结束
                        line_end = truncated.find('\n', last_marker)
                        if line_end != -1:
                            context_text = truncated[:line_end]
                            break
                else:
                    # 在段落边界截断
                    last_paragraph = truncated.rfind('\n\n')
                    if last_paragraph > max_length * 0.7:
                        context_text = truncated[:last_paragraph]
                    else:
                        # 在句子边界截断
                        for separator in ['。', '！', '？', '\n']:
                            last_sep = truncated.rfind(separator)
                            if last_sep > max_length * 0.8:
                                context_text = truncated[:last_sep + 1]
                                break
                        else:
                            context_text = truncated
            
            # 【增强8】添加关键词总结到上下文开头
            if keywords:
                keyword_summary = "关键信息：" + "、".join(keywords[:15]) + "\n\n"
                context_text = keyword_summary + context_text
            
            logger.debug(f"增强查询上下文提取：{len(context_text)} 字符，关键词: {len(keywords)} 个")
            return context_text.strip()
            
        except Exception as e:
            logger.error(f"增强查询上下文提取失败: {e}")
            # 降级为扩展简单提取
            expanded_start = max(0, cursor_position - max_length * 2)
            return text[expanded_start:cursor_position].strip()
    
    def _extract_enhanced_keywords(self, text: str, cursor_pos: int) -> List[str]:
        """增强关键词提取（大幅提升关键词数量和质量）"""
        keywords = set()
        
        try:
            # 【关键词类型1】人物名称提取（增强版本）
            # 匹配中文人名模式
            name_patterns = [
                r'[李王张刘陈杨黄吴赵孙周徐朱马胡郭何高林罗郑梁谢宋唐许邓陆姜沈余潘卢石廖姚方金戴贾韦夏付邹程萧蔡董邮田任孟范汪][\u4e00-\u9fff]{1,3}',  # 常见姓氏
                r'[A-Z][a-z]+\s+[A-Z][a-z]+',  # 英文人名
                r'@char:\s*([^\s,，。！？\n]+)',  # @char: 标记的角色
            ]
            
            for pattern in name_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, str) and len(match) >= 2:
                        keywords.add(match.strip())
            
            # 【关键词类型2】地点场所提取（大幅增强）
            location_keywords = [
                '学校', '家', '房间', '客厅', '卧室', '厨房', '办公室', '公司', '医院', '商店', '餐厅', '咖啡厅',
                '公园', '街道', '城市', '乡村', '山', '河', '海', '森林', '草原', '沙漠', '雪地',
                '教室', '图书馆', '宿舍', '食堂', '操场', '体育馆', '游泳池', '电影院', '剧院', '博物馆',
                '机场', '火车站', '地铁站', '公交站', '码头', '高速公路', '小巷', '广场', '桥梁',
                '酒店', '宾馆', '旅馆', '民宿', '度假村', '温泉', '景区', '古镇', '村庄', '小镇'
            ]
            
            location_patterns = [
                r'@location:\s*([^\s,，。！？\n]+)',  # @location: 标记
                r'在([^\s,，的]{2,8})',  # "在...地方"模式
                r'到([^\s,，的]{2,8})',  # "到...地方"模式
                r'从([^\s,，的]{2,8})',  # "从...地方"模式
            ]
            
            # 添加位置关键词
            for keyword in location_keywords:
                if keyword in text:
                    keywords.add(keyword)
            
            # 匹配位置模式
            for pattern in location_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if len(match) >= 2:
                        keywords.add(match.strip())
            
            # 【关键词类型3】物品道具提取（新增）
            object_keywords = [
                '手机', '电脑', '书', '笔', '钱包', '钥匙', '包', '衣服', '鞋子', '帽子', '眼镜',
                '车', '自行车', '摩托车', '公交车', '出租车', '地铁', '飞机', '火车', '船',
                '桌子', '椅子', '床', '沙发', '门', '窗户', '电视', '冰箱', '洗衣机', '空调',
                '食物', '水', '咖啡', '茶', '酒', '饮料', '面包', '米饭', '面条', '水果'
            ]
            
            for keyword in object_keywords:
                if keyword in text:
                    keywords.add(keyword)
            
            # 【关键词类型4】动作行为提取（新增）
            action_patterns = [
                r'(走|跑|坐|站|躺|睡|吃|喝|看|听|说|笑|哭|想|做|写|读|买|卖|开|关|拿|放)([着了]|[^\s]{0,2})',
                r'(正在|正|在)([^\s]{1,3})',
                r'(开始|结束|继续|停止|准备)([^\s]{1,3})',
            ]
            
            for pattern in action_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        action = match[0] + match[1]
                        if len(action) >= 2:
                            keywords.add(action)
            
            # 【关键词类型5】情感状态提取（新增）
            emotion_keywords = [
                '高兴', '开心', '快乐', '兴奋', '满意', '得意', '骄傲', '自豪',
                '难过', '伤心', '悲伤', '痛苦', '失落', '绝望', '哭泣',
                '愤怒', '生气', '恼火', '暴躁', '愤恨', '仇恨',
                '害怕', '恐惧', '紧张', '焦虑', '担心', '忧虑', '不安',
                '惊讶', '震惊', '意外', '困惑', '疑惑', '奇怪',
                '冷静', '平静', '安静', '淡定', '轻松', '舒适'
            ]
            
            for keyword in emotion_keywords:
                if keyword in text:
                    keywords.add(keyword)
            
            # 【关键词类型6】时间相关提取（增强）
            time_patterns = [
                r'(今天|昨天|明天|前天|后天|今晚|昨晚|明晚)',
                r'([上下]午|晚上|深夜|凌晨|黎明|傍晚|中午)',
                r'(春天|夏天|秋天|冬天|春|夏|秋|冬)',
                r'(周一|周二|周三|周四|周五|周六|周日|星期[一二三四五六日天])',
                r'(\d{1,2}点|\d{1,2}[：:]\d{2})',
                r'@time:\s*([^\s,，。！？\n]+)',
            ]
            
            for pattern in time_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    keywords.add(match.strip())
            
            # 【关键词类型7】关键短语提取（新增）
            # 提取重要的短语和词组
            important_phrases = []
            sentences = re.split(r'[。！？\n]', text)
            
            for sentence in sentences:
                if len(sentence) > 10:
                    # 提取含有重要词汇的短语
                    important_words = ['突然', '忽然', '终于', '果然', '竟然', '居然', '原来', '没想到', 
                                     '决定', '选择', '发现', '意识到', '记起', '想起', '明白', '理解',
                                     '重要', '关键', '必须', '应该', '不能', '可能', '也许', '或许']
                    
                    for word in important_words:
                        if word in sentence:
                            # 提取包含关键词的短语（前后各5个字符）
                            word_pos = sentence.find(word)
                            start = max(0, word_pos - 5)
                            end = min(len(sentence), word_pos + len(word) + 5)
                            phrase = sentence[start:end].strip()
                            if len(phrase) >= 3:
                                keywords.add(phrase)
            
            # 【关键词类型8】光标附近重点词汇（新增）
            # 特别关注光标前后的重要词汇
            if 0 <= cursor_pos < len(text):
                context_radius = 200  # 光标前后200字符
                nearby_start = max(0, cursor_pos - context_radius)
                nearby_end = min(len(text), cursor_pos + context_radius)
                nearby_text = text[nearby_start:nearby_end]
                
                # 分词并提取较长的词汇
                words = re.findall(r'[\u4e00-\u9fff]{2,}', nearby_text)  # 中文词汇
                for word in words:
                    if len(word) >= 2:
                        keywords.add(word)
            
            # 去除过短或无意义的关键词
            filtered_keywords = []
            for keyword in keywords:
                keyword = keyword.strip()
                if (len(keyword) >= 2 and 
                    keyword not in ['的', '了', '是', '在', '有', '和', '与', '或', '但', '而', '也', '都', '很', '非常', '这', '那', '这个', '那个']):
                    filtered_keywords.append(keyword)
            
            # 按重要性排序（更常出现的关键词优先级更高）
            keyword_counts = {}
            for keyword in filtered_keywords:
                keyword_counts[keyword] = text.lower().count(keyword.lower())
            
            sorted_keywords = sorted(filtered_keywords, key=lambda x: keyword_counts[x], reverse=True)
            
            logger.debug(f"提取关键词 {len(sorted_keywords)} 个: {sorted_keywords[:20]}")  # 记录前20个
            return sorted_keywords[:50]  # 返回前50个最重要的关键词
            
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []

    def _fast_rag_search_with_timeout(self, query_text: str, max_results: int, timeout: float, min_similarity: float = 0.5) -> str:
        """快速RAG搜索（带严格超时控制和线程管理）"""
        import threading
        import queue
        import time
        
        # 如果正在关闭，直接返回
        if getattr(self, '_is_shutting_down', False):
            logger.debug("AI管理器正在关闭，跳过RAG搜索")
            return ""
        
        result_queue = queue.Queue()
        thread_id = None
        
        def search_worker():
            """搜索工作线程"""
            nonlocal thread_id
            thread_id = threading.current_thread().ident
            
            try:
                # 添加到活跃线程集合
                if hasattr(self, '_active_threads'):
                    self._active_threads.add(threading.current_thread())
                
                start_time = time.time()
                
                # 检查是否正在关闭
                if getattr(self, '_is_shutting_down', False):
                    result_queue.put(('shutdown', ""))
                    return
                
                # 快速检查向量存储状态
                stats = self._vector_store.get_stats()
                if not stats or stats.get('total_documents', 0) == 0:
                    result_queue.put(('empty', ""))
                    return
                
                # 创建查询向量（最大的性能瓶颈）
                query_embedding = self._rag_service.create_embedding(query_text)
                if not query_embedding:
                    result_queue.put(('error', "无法创建查询向量"))
                    return
                
                embedding_time = time.time() - start_time
                if embedding_time > timeout * 0.7:  # 如果embedding就用了70%时间，直接返回
                    result_queue.put(('timeout', f"向量生成耗时过长: {embedding_time:.2f}s"))
                    return
                
                # 再次检查是否正在关闭
                if getattr(self, '_is_shutting_down', False):
                    result_queue.put(('shutdown', ""))
                    return
                
                # 执行向量搜索
                results = self._vector_store.similarity_search(
                    query_embedding,
                    limit=max_results,
                    min_similarity=min_similarity
                )
                
                if not results:
                    result_queue.put(('empty', ""))
                    return
                
                # 构建上下文
                context_parts = []
                for emb_data, score in results:
                    chunk_text = emb_data.get('chunk_text', '')
                    if chunk_text:
                        doc_id = emb_data.get('document_id', 'unknown')
                        part = f"[{doc_id[:8]}... 相似度:{score:.2f}]\n{chunk_text[:200]}..."
                        context_parts.append(part)
                
                context = "\n---\n".join(context_parts)
                result_queue.put(('success', context))
                
            except Exception as e:
                result_queue.put(('error', str(e)))
            finally:
                # 从活跃线程集合中移除
                if hasattr(self, '_active_threads'):
                    try:
                        self._active_threads.discard(threading.current_thread())
                    except:
                        pass
        
        # 启动搜索线程
        search_thread = threading.Thread(target=search_worker, daemon=True, name=f"RAGSearch-{time.time():.0f}")
        search_thread.start()
        
        # 等待结果
        try:
            result_type, result_data = result_queue.get(timeout=timeout)
            
            if result_type == 'success':
                return result_data
            elif result_type == 'empty':
                logger.debug("RAG搜索结果为空")
                return ""
            elif result_type == 'shutdown':
                logger.debug("RAG搜索被关闭信号中断")
                return ""
            elif result_type == 'timeout':
                logger.warning(f"RAG搜索超时: {result_data}")
                self._record_rag_timeout()
                return ""
            else:  # error
                logger.warning(f"RAG搜索失败: {result_data}")
                return ""
                
        except queue.Empty:
            logger.warning(f"RAG搜索严格超时（{timeout}s），避免阻塞")
            self._record_rag_timeout()
            return ""
        finally:
            # 确保线程被清理
            if search_thread.is_alive():
                logger.debug(f"等待RAG搜索线程结束: {search_thread.name}")
                search_thread.join(timeout=0.1)  # 短暂等待

    def _build_rag_context_non_blocking(self, current_text: str, cursor_position: int) -> str:
        """非阻塞构建RAG上下文（防卡死专用，带线程管理）"""
        if not self._rag_service or not self._vector_store:
            return ""
        
        # 如果正在关闭，直接返回
        if getattr(self, '_is_shutting_down', False):
            logger.debug("AI管理器正在关闭，跳过非阻塞RAG搜索")
            return ""
        
        try:
            # 超严格的性能控制
            if cursor_position > 3000:  # 进一步减少文本长度限制
                logger.debug("文本过长，跳过RAG检索（防卡死）")
                return ""
            
            # 提取极短的查询文本
            query_start = max(0, cursor_position - 30)  # 只取30字符
            query_text = current_text[query_start:cursor_position].strip()
            
            if not query_text or len(query_text) < 3:
                return ""
            
            # 使用线程超时机制，绝对不允许阻塞
            import threading
            import queue
            
            result_queue = queue.Queue()
            
            def ultra_quick_search():
                """超快速搜索线程"""
                try:
                    # 添加到活跃线程集合
                    if hasattr(self, '_active_threads'):
                        self._active_threads.add(threading.current_thread())
                    
                    # 检查是否正在关闭
                    if getattr(self, '_is_shutting_down', False):
                        result_queue.put(('shutdown', ""))
                        return
                    
                    # 只搜索一个结果，最快返回
                    start_time = time.time()
                    
                    # 使用最快的搜索方式
                    if hasattr(self._vector_store, 'similarity_search_ultra_fast'):
                        result = self._vector_store.similarity_search_ultra_fast(query_text)
                    else:
                        # 备用方案：简单的文本匹配
                        result = self._simple_text_match(query_text)
                    
                    search_time = time.time() - start_time
                    
                    if search_time > 0.2:  # 如果搜索超过200ms，记录为慢查询
                        logger.warning(f"RAG搜索较慢: {search_time:.2f}秒")
                    
                    result_queue.put(('success', result))
                except Exception as e:
                    result_queue.put(('error', str(e)))
                finally:
                    # 从活跃线程集合中移除
                    if hasattr(self, '_active_threads'):
                        try:
                            self._active_threads.discard(threading.current_thread())
                        except:
                            pass
            
            # 启动超快速搜索线程
            search_thread = threading.Thread(target=ultra_quick_search, daemon=True, name=f"NonBlockRAG-{time.time():.0f}")
            search_thread.start()
            
            # 等待结果，严格200ms超时
            try:
                result_type, result_data = result_queue.get(timeout=0.2)
                
                if result_type == 'success' and result_data:
                    # 成功获取结果，快速返回
                    context = result_data[:100] if len(result_data) > 100 else result_data
                    logger.debug(f"非阻塞RAG成功: {len(context)} 字符")
                    return f"\n\n参考: {context}"
                elif result_type == 'shutdown':
                    logger.debug("非阻塞RAG搜索被关闭信号中断")
                    return ""
                    
            except queue.Empty:
                # 超时了，记录并跳过
                logger.warning("RAG搜索超时（200ms），避免卡死")
                self._record_rag_timeout()
                return ""
            finally:
                # 确保线程被清理
                if search_thread.is_alive():
                    search_thread.join(timeout=0.05)  # 短暂等待
            
            return ""
            
        except Exception as e:
            logger.error(f"非阻塞RAG构建失败: {e}")
            # 记录失败时间，避免重复尝试
            self._record_rag_timeout()
            return ""
        
        try:
            import time
            start_time = time.time()
            
            # 极严格的性能和长度限制
            if cursor_position > 5000:  # 进一步降低文本处理长度
                logger.debug("文本过长（>5000字符），跳过RAG检索以避免阻塞")
                return ""
            
            # 提取更短的查询文本，减少处理量
            query_start = max(0, cursor_position - 50)  # 进一步减少到50字符
            query_text = current_text[query_start:cursor_position].strip()
            
            if not query_text or len(query_text) < 3:  # 降低最小长度
                return ""
            
            # 设置严格的超时检查
            def timeout_check():
                elapsed = time.time() - start_time
                if elapsed > 0.5:  # 500ms严格超时
                    raise TimeoutError(f"RAG检索超时: {elapsed:.2f}秒")
                return elapsed
            
            # 快速检查向量存储状态
            timeout_check()
            try:
                stats = self._vector_store.get_stats()
                if not stats or stats.get('total_documents', 0) == 0:
                    logger.debug("向量存储为空，跳过RAG检索")
                    return ""
            except Exception as e:
                logger.debug(f"向量存储状态检查失败: {e}")
                return ""
            
            # 非阻塞方式：只尝试一次，立即失败
            timeout_check()
            try:
                # 使用最快的搜索配置
                rag_context = self._search_similar_content_fast(query_text, max_results=1)
                
                # 最终超时检查
                timeout_check()
                
                if rag_context and len(rag_context) < 200:  # 严格限制返回长度
                    logger.debug(f"非阻塞RAG检索成功: {len(rag_context)} 字符，用时 {time.time() - start_time:.3f}秒")
                    return f"\n\n参考: {rag_context[:150]}..."  # 截断到150字符
                
            except TimeoutError:
                logger.warning("RAG检索超时，跳过以避免阻塞")
                return ""
            except Exception as e:
                logger.debug(f"非阻塞RAG检索失败: {e}")
                return ""
            
            return ""
            
        except Exception as e:
            logger.debug(f"非阻塞RAG构建失败: {e}")
            return ""
    
    def _search_similar_content_fast(self, query: str, max_results: int = 1) -> str:
        """超快速相似内容搜索（专为非阻塞设计）"""
        if not self._rag_service or not self._vector_store:
            return ""
        
        import time
        start_time = time.time()
        
        try:
            # 极严格的性能限制
            if len(query) > 200:
                query = query[:200]
            
            max_results = 1  # 强制只返回1个结果
            
            # 快速创建查询向量（带超时）
            query_embedding = None
            try:
                # 这里可能需要网络请求，是主要的阻塞点
                query_embedding = self._rag_service.create_embedding(query)
                
                # 检查是否超时
                if time.time() - start_time > 0.3:  # 300ms超时
                    logger.warning("创建查询向量超时，放弃搜索")
                    return ""
                    
            except Exception as e:
                logger.debug(f"创建查询向量失败: {e}")
                return ""
            
            if not query_embedding:
                return ""
            
            # 超快速向量搜索（限制处理量）
            try:
                results = self._vector_store.similarity_search(
                    query_embedding,
                    limit=1,  # 只要1个结果
                    min_similarity=0.4  # 提高最小相似度，减少计算量
                )
                
                # 再次检查超时
                if time.time() - start_time > 0.4:  # 400ms总超时
                    logger.warning("向量搜索超时，返回空结果")
                    return ""
                
            except Exception as e:
                logger.debug(f"向量搜索失败: {e}")
                return ""
            
            # 快速构建结果
            if results:
                emb_data, score = results[0]
                chunk_text = emb_data.get('chunk_text', '')
                if chunk_text and len(chunk_text) > 10:
                    # 只返回前100字符，减少后续处理
                    return chunk_text[:100]
            
            return ""
            
        except Exception as e:
            logger.error(f"快速搜索失败: {e}")
            return ""

    def _build_rag_context_fast(self, current_text: str, cursor_position: int) -> str:
        """快速构建RAG上下文（专为性能优化）"""
        if not self._rag_service or not self._vector_store:
            return ""
        
        try:
            # 极其严格的性能限制
            if cursor_position > 10000:  # 进一步降低处理的文本长度限制
                logger.debug("文本过长，跳过RAG检索")
                return ""
            
            # 提取更短的查询文本
            query_start = max(0, cursor_position - 100)  # 减少到100字符
            query_text = current_text[query_start:cursor_position].strip()
            
            if not query_text or len(query_text) < 5:  # 降低最小长度要求
                return ""
            
            # 非阻塞方式：只尝试一次，不等待
            try:
                # 使用更快的搜索，只要1个结果
                rag_context = self.search_similar_content(query_text, max_results=1)
                
                if rag_context and len(rag_context) < 500:  # 限制返回内容长度
                    logger.debug(f"快速RAG检索成功: {len(rag_context)} 字符")
                    return f"\n\n参考: {rag_context[:300]}..."  # 截断到300字符
                
            except Exception as e:
                logger.debug(f"快速RAG检索失败: {e}")
            
            return ""
            
        except Exception as e:
            logger.debug(f"RAG快速构建失败: {e}")
            return ""
    
    def build_rag_context(self, current_text: str, cursor_position: int) -> str:
        """构建RAG增强的上下文（兼容性方法，使用快速版本）"""
        return self._build_rag_context_fast(current_text, cursor_position)
    
    def _quick_fallback_context(self, query_text: str) -> str:
        """快速降级上下文策略（避免复杂计算）"""
        try:
            # 获取当前项目的所有文档
            if not hasattr(self.parent(), '_project_manager'):
                return ""
                
            project_manager = self.parent()._project_manager
            current_project = project_manager.get_current_project()
            if not current_project:
                return ""
            
            # 使用最简单的关键词匹配，限制处理时间
            query_words = set(query_text.lower().split()[:10])  # 只取前10个词
            if not query_words:
                return ""
            
            found_content = []
            processed_docs = 0
            
            for doc_id, doc in current_project.documents.items():
                if processed_docs >= 5:  # 最多处理5个文档
                    break
                    
                if not doc.content or len(doc.content) < 50:
                    continue
                    
                # 只检查文档的前1000字符，提高性能
                content_sample = doc.content[:1000].lower()
                
                # 简单的关键词匹配
                if any(word in content_sample for word in query_words if len(word) > 2):
                    # 提取相关段落（前200字符）
                    found_content.append(f"[{doc.name[:20]}] {doc.content[:200]}...")
                    if len(found_content) >= 2:  # 最多2个结果
                        break
                
                processed_docs += 1
            
            if found_content:
                logger.info(f"快速降级搜索找到 {len(found_content)} 个相关文档")
                return "\n\n相关内容参考：\n" + "\n---\n".join(found_content)
            else:
                return ""
                
        except Exception as e:
            logger.error(f"快速降级策略失败: {e}")
            return ""
    
    def get_index_stats(self):
        """获取索引统计信息"""
        if not self._rag_service:
            return None
        return self._rag_service.get_index_stats()
    
    def clear_all_indexes(self) -> bool:
        """清空所有索引"""
        if not self._rag_service:
            return False
        return self._rag_service.clear_all_indexes()
    
    def rebuild_all_indexes(self, documents: Dict[str, str]) -> bool:
        """重建所有索引（异步）"""
        if not self._rag_service or not self._vector_store:
            return False
        
        # 更新异步索引器的服务引用
        self._async_indexer.set_services(self._rag_service, self._vector_store, self._config)
        
        # 将批量文档加入异步索引队列
        self._async_indexer.queue_batch_index(documents)
        logger.info(f"批量重建索引已提交异步处理: {len(documents)} 个文档")
        return True
    
    def rebuild_all_indexes_sync(self, documents: Dict[str, str]) -> bool:
        """重建所有索引（同步）"""
        if not self._rag_service:
            return False
        return self._rag_service.rebuild_index_for_documents(documents)
    
    def show_index_manager(self, parent=None, project_manager=None):
        """显示索引管理对话框"""
        try:
            from .index_manager_dialog import IndexManagerDialog
            
            dialog = IndexManagerDialog(
                parent=parent,
                ai_manager=self,
                project_manager=project_manager
            )
            dialog.exec()
            
        except Exception as e:
            logger.error(f"显示索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent, "错误", 
                f"无法打开索引管理对话框：{str(e)}"
            )
    
    def show_batch_index_dialog(self, parent=None, project_manager=None):
        """显示批量索引对话框"""
        try:
            from .batch_index_dialog import BatchIndexDialog
            
            dialog = BatchIndexDialog(
                parent=parent,
                ai_manager=self,
                project_manager=project_manager
            )
            dialog.exec()
            
        except Exception as e:
            logger.error(f"显示批量索引对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent, "错误", 
                f"无法打开批量索引对话框：{str(e)}"
            )
    
    def force_reinit_ai(self):
        """强制重新初始化AI客户端（用于调试和恢复）"""
        logger.info("强制重新初始化AI客户端")
        
        # 清理旧的AI客户端
        if self._ai_client:
            try:
                self._ai_client.cleanup()
            except:
                pass
            self._ai_client = None
        
        # 重新初始化
        self._init_ai_client()
        return self._ai_client is not None
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """获取当前性能设置"""
        return {
            'debounce_delay': self._debounce_delay,
            'throttle_interval': self._throttle_interval,
            'min_trigger_chars': self._min_trigger_chars,
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'last_completion_time': self._last_completion_time
        }
    
    def update_performance_settings(self, settings: Dict[str, Any]):
        """更新性能设置"""
        if 'debounce_delay' in settings:
            self._debounce_delay = max(500, settings['debounce_delay'])  # 最小500ms
        
        if 'throttle_interval' in settings:
            self._throttle_interval = max(1000, settings['throttle_interval'])  # 最小1秒
        
        if 'min_trigger_chars' in settings:
            self._min_trigger_chars = max(1, settings['min_trigger_chars'])
        
        logger.info(f"性能设置已更新: 防抖{self._debounce_delay}ms, 节流{self._throttle_interval}ms")
    
    def get_ai_status(self):
        """获取AI服务状态（增强版本）"""
        current_time = time.time() * 1000
        time_since_last_completion = current_time - self._last_completion_time
        
        return {
            'ai_client_available': self._ai_client is not None,
            'rag_service_available': self._rag_service is not None,
            'vector_store_available': self._vector_store is not None,
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'performance': {
                'debounce_delay': self._debounce_delay,
                'throttle_interval': self._throttle_interval,
                'time_since_last_completion': time_since_last_completion,
                'throttle_active': time_since_last_completion < self._throttle_interval
            }
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if self._rag_service:
            return self._rag_service.get_cache_stats()
        else:
            return {"enabled": False}
    
    def clear_cache(self):
        """清空缓存"""
        if self._rag_service:
            self._rag_service.clear_cache()
            logger.info("缓存已清空")
    
    def cleanup_cache(self):
        """清理过期缓存"""
        if self._rag_service:
            self._rag_service.cleanup_cache()
            logger.info("过期缓存已清理")
    
    def force_reinit_rag(self):
        """强制重新初始化RAG服务（用于调试）"""
        logger.info("强制重新初始化RAG服务")
        
        # 关闭旧的RAG服务
        if self._rag_service:
            self._rag_service.close()
        
        self._rag_service = None
        self._vector_store = None
        self._init_rag_service()
        
        # 更新异步索引器的服务引用
        if self._async_indexer:
            self._async_indexer.set_services(self._rag_service, self._vector_store, self._config)
            
        return self._rag_service is not None
    
    # 异步索引信号处理方法
    @pyqtSlot(str)
    def _on_async_index_started(self, document_id: str):
        """异步索引开始处理"""
        logger.debug(f"异步索引开始: {document_id}")
        
        # 可以在这里更新UI状态，比如显示进度指示器
        if hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(f"正在索引文档: {document_id[:8]}...", 2000)
    
    @pyqtSlot(str, bool)
    def _on_async_index_completed(self, document_id: str, success: bool):
        """异步索引完成处理"""
        if success:
            logger.info(f"异步索引完成: {document_id}")
            # 更新UI状态
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage(f"文档索引完成: {document_id[:8]}...", 1000)
        else:
            logger.error(f"异步索引失败: {document_id}")
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage(f"文档索引失败: {document_id[:8]}...", 3000)
    
    @pyqtSlot(int, int)
    def _on_async_batch_completed(self, success_count: int, total_count: int):
        """异步批量索引完成处理"""
        logger.info(f"批量异步索引完成: {success_count}/{total_count}")
        
        # 更新UI状态
        if hasattr(self.parent(), 'statusBar'):
            message = f"批量索引完成: {success_count}/{total_count} 个文档"
            self.parent().statusBar().showMessage(message, 5000)
    
    def cleanup(self):
        """清理资源 - 极速版本，避免任何延迟"""
        logger.info("开始清理AI管理器资源（极速模式）")
        
        # 立即设置关闭标志
        self._is_shutting_down = True
        
        # 第一步：立即停止所有定时器（防止新任务启动）
        if hasattr(self, '_completion_timer') and self._completion_timer:
            self._completion_timer.stop()
            self._completion_timer = None
        
        if hasattr(self, '_throttle_timer') and self._throttle_timer:
            self._throttle_timer.stop()
            self._throttle_timer = None
        
        logger.debug("所有定时器已停止")
        
        # 第二步：极速清理活跃的RAG搜索线程
        if hasattr(self, '_active_threads') and self._active_threads:
            thread_count = len(self._active_threads)
            logger.info(f"发现 {thread_count} 个活跃RAG线程，开始极速清理")
            
            # 创建活跃线程列表快照
            active_threads_snapshot = list(self._active_threads)
            
            # 极速策略：不等待，直接跳过所有线程
            for i, thread in enumerate(active_threads_snapshot):
                try:
                    thread_name = getattr(thread, 'name', f'Thread-{i}')
                    if thread.is_alive():
                        logger.debug(f"线程 {thread_name} 仍在运行，直接跳过（极速模式）")
                    else:
                        logger.debug(f"线程 {thread_name} 已结束")
                except Exception as e:
                    logger.debug(f"检查线程状态时出错: {e}")
            
            # 强制清空活跃线程集合
            self._active_threads.clear()
            logger.info(f"RAG线程清理完成（极速模式）：跳过 {thread_count} 个线程")
        
        # 第三步：改进异步索引工作线程停止
        if hasattr(self, '_async_indexer') and self._async_indexer:
            logger.info("停止异步索引工作线程（极速模式）")
            try:
                # 首先设置停止标志并清空队列
                self._async_indexer.stop()
                
                # 使用更短的等待时间，但更优雅的退出
                if self._async_indexer.isRunning():
                    # 第一次尝试：优雅退出，50ms
                    if not self._async_indexer.wait(50):
                        logger.debug("第一次等待50ms超时，尝试强制终止")
                        self._async_indexer.terminate()
                        # 第二次尝试：强制终止后等待50ms
                        if not self._async_indexer.wait(50):
                            logger.warning("异步索引线程强制终止超时，跳过等待")
                        else:
                            logger.debug("异步索引线程已强制终止")
                    else:
                        logger.debug("异步索引线程已正常停止")
                
                # 断开所有信号连接
                try:
                    self._async_indexer.blockSignals(True)
                    self._async_indexer.disconnect()
                except:
                    pass
                
                # 标记为删除
                self._async_indexer.deleteLater()
                self._async_indexer = None
                logger.debug("异步索引线程清理完成")
                
            except Exception as e:
                logger.warning(f"停止异步索引线程时出错: {e}")
                # 即使出错也要设置为None，防止重复清理
                self._async_indexer = None
        
        # 第四步：快速清理UI组件
        ui_cleanup_start = time.time() * 1000
        
        if self._completion_widget:
            try:
                self._completion_widget.hide()
                self._completion_widget.deleteLater()
                self._completion_widget = None
            except Exception as e:
                logger.debug(f"清理补全组件时出错: {e}")

        if self._stream_widget:
            try:
                self._stream_widget.hide()
                self._stream_widget.deleteLater()
                self._stream_widget = None
            except Exception as e:
                logger.debug(f"清理流式组件时出错: {e}")

        if self._config_dialog:
            try:
                self._config_dialog.deleteLater()
                self._config_dialog = None
            except Exception as e:
                logger.debug(f"清理配置对话框时出错: {e}")
        
        ui_cleanup_time = time.time() * 1000 - ui_cleanup_start
        logger.debug(f"UI组件清理完成，用时: {ui_cleanup_time:.1f}ms")

        # 第五步：清理AI客户端和RAG服务
        service_cleanup_start = time.time() * 1000
        
        if self._ai_client:
            try:
                logger.debug("开始清理AI客户端（强制模式）")
                # 强制模式：立即取消所有活跃请求
                if hasattr(self._ai_client, 'cancel_request'):
                    self._ai_client.cancel_request()
                # 执行清理
                self._ai_client.cleanup()
                self._ai_client = None
                logger.debug("AI客户端清理完成")
            except Exception as e:
                logger.debug(f"清理AI客户端时出错: {e}")
                # 即使出错也要设置为None
                self._ai_client = None
        
        if hasattr(self, '_rag_service') and self._rag_service:
            try:
                if hasattr(self._rag_service, 'close'):
                    self._rag_service.close()
                self._rag_service = None
            except Exception as e:
                logger.debug(f"清理RAG服务时出错: {e}")
                self._rag_service = None
        
        if hasattr(self, '_vector_store') and self._vector_store:
            try:
                if hasattr(self._vector_store, 'close'):
                    self._vector_store.close()
                self._vector_store = None
            except Exception as e:
                logger.debug(f"清理向量存储时出错: {e}")
                self._vector_store = None
        
        service_cleanup_time = time.time() * 1000 - service_cleanup_start
        logger.debug(f"服务组件清理完成，用时: {service_cleanup_time:.1f}ms")

        total_cleanup_time = ui_cleanup_time + service_cleanup_time
        logger.info(f"AI管理器资源清理完成（极速模式），总用时: {total_cleanup_time:.1f}ms")


class OutlineAnalysisExtension(QObject):
    """大纲分析扩展 - 集成到AI管理器中的大纲功能"""
    
    # 大纲专用信号
    outlineAnalysisCompleted = pyqtSignal(str, str)  # (analysis_result, original_text)
    outlineAnalysisError = pyqtSignal(str)           # (error_message)
    outlineSuggestionsReady = pyqtSignal(list)       # (suggestions)
    
    def __init__(self, ai_manager):
        super().__init__(ai_manager)
        self.ai_manager = ai_manager
        self._init_prompt_manager()
        
        logger.info("大纲分析扩展已初始化")
    
    def _init_prompt_manager(self):
        """初始化提示词管理器"""
        try:
            from core.outline_prompts import OutlinePromptManager
            self.prompt_manager = OutlinePromptManager()
            logger.debug("大纲提示词管理器初始化成功")
        except ImportError as e:
            logger.warning(f"无法导入大纲提示词管理器: {e}")
            self.prompt_manager = None
    
    def analyze_outline_structure(self, text: str, analysis_type: str = 'auto') -> str:
        """分析大纲结构"""
        try:
            logger.info(f"开始大纲结构分析，类型: {analysis_type}，文本长度: {len(text)}")
            
            # 构建分析提示词
            if self.prompt_manager and hasattr(self.prompt_manager, 'format_prompt'):
                prompt_data = self.prompt_manager.format_prompt(
                    prompt_type='outline_analysis',
                    text=text,
                    analysis_type=analysis_type,
                    language="chinese"
                )
                
                if prompt_data:
                    prompt = f"{prompt_data.get('system', '')}\n\n{prompt_data.get('user', '')}"
                else:
                    prompt = self._get_fallback_analysis_prompt(text)
            else:
                prompt = self._get_fallback_analysis_prompt(text)
            
            # 使用基础AI客户端进行同步调用
            response = self._call_ai_sync(prompt, max_tokens=1500, temperature=0.7)
            
            if response and len(response.strip()) > 20:
                logger.info(f"大纲分析完成，结果长度: {len(response)}")
                self.outlineAnalysisCompleted.emit(response, text)
                return response
            else:
                raise ValueError("AI返回结果过短或为空")
                
        except Exception as e:
            error_msg = f"大纲结构分析失败: {str(e)}"
            logger.error(error_msg)
            self.outlineAnalysisError.emit(error_msg)
            raise
    
    def suggest_outline_improvements(self, current_outline: str) -> List[str]:
        """建议大纲改进"""
        try:
            if not self.ai_manager._ai_client:
                raise RuntimeError("AI客户端未初始化")
            
            logger.info(f"生成大纲改进建议，文本长度: {len(current_outline)}")
            
            # 利用RAG搜索相关项目内容（如果可用）
            rag_context = ""
            if self.ai_manager._rag_service:
                try:
                    similar_content = self.ai_manager.search_similar_content(current_outline[:500])  # 限制查询长度
                    if similar_content:
                        rag_context = f"\n\n相关项目内容参考:\n{similar_content[:300]}"
                        logger.debug("已获取RAG上下文信息")
                except Exception as rag_error:
                    logger.warning(f"RAG搜索失败，使用基础分析: {rag_error}")
            
            # 构建改进建议提示词
            if self.prompt_manager and hasattr(self.prompt_manager, 'format_prompt'):
                prompt_data = self.prompt_manager.format_prompt(
                    prompt_type='outline_enhance',
                    text=current_outline + rag_context,
                    language="chinese"
                )
                if prompt_data:
                    prompt = f"{prompt_data.get('system', '')}\\n\\n{prompt_data.get('user', '')}"
                else:
                    prompt = self._get_fallback_improvement_prompt(current_outline, rag_context)
            else:
                prompt = self._get_fallback_improvement_prompt(current_outline, rag_context)
            
            # 调用AI生成建议
            response = self._call_ai_sync(prompt, max_tokens=800, temperature=0.8)
            
            if response:
                suggestions = self._parse_suggestions(response)
                logger.info(f"生成了 {len(suggestions)} 条改进建议")
                self.outlineSuggestionsReady.emit(suggestions)
                return suggestions
            else:
                return []
                
        except Exception as e:
            error_msg = f"生成大纲改进建议失败: {str(e)}"
            logger.error(error_msg)
            self.outlineAnalysisError.emit(error_msg)
            return []
    
    def generate_outline_continuation(self, existing_docs: List, generation_params: Dict[str, Any]) -> Dict[str, Any]:
        """生成大纲续写内容（集成上下文感知生成器）"""
        try:
            if not self.ai_manager._ai_client:
                raise RuntimeError("AI客户端未初始化")
            
            logger.info(f"开始生成大纲续写，文档数: {len(existing_docs)}")
            
            # 使用上下文感知生成器
            from core.context_generator import ContextAwareOutlineGenerator, GenerationType, ContextScope
            generator = ContextAwareOutlineGenerator()
            
            # 解析生成参数
            generation_type = GenerationType(generation_params.get('type', 'continuation'))
            context_scope = ContextScope(generation_params.get('scope', 'global'))
            target_length = generation_params.get('length', 3)
            
            # 生成续写内容
            generation_result = generator.generate_outline_continuation(
                existing_docs=existing_docs,
                generation_type=generation_type,
                context_scope=context_scope,
                target_length=target_length
            )
            
            logger.info(f"续写生成完成，质量评分: {generation_result.quality_score:.2f}")
            return {
                'generated_nodes': generation_result.generated_nodes,
                'context_analysis': generation_result.context_analysis,
                'generation_rationale': generation_result.generation_rationale,
                'quality_score': generation_result.quality_score,
                'suggestions': generation_result.continuation_suggestions
            }
            
        except Exception as e:
            error_msg = f"生成大纲续写失败: {str(e)}"
            logger.error(error_msg)
            self.outlineAnalysisError.emit(error_msg)
            return {'error': error_msg}
    
    def _get_fallback_improvement_prompt(self, outline: str, rag_context: str = "") -> str:
        """获取降级改进提示词"""
        return f"""请为以下大纲提供具体的改进建议：

大纲内容：
{outline}

{rag_context}

请从以下角度提供建议：
1. 结构完整性
2. 情节发展
3. 角色塑造
4. 节奏控制
5. 主题深化

请以列表形式提供5-8条具体可行的改进建议。"""
    
    def _call_ai_sync(self, prompt: str, **kwargs) -> str:
        """同步调用AI客户端"""
        try:
            # 获取AI配置
            ai_config = self.ai_manager._config.get_ai_config()
            if not ai_config:
                raise RuntimeError("AI配置未找到")
            
            # 使用基础AI客户端进行同步调用
            from core.ai_client import AIClient
            with AIClient(ai_config) as client:
                response = client.complete(prompt=prompt, **kwargs)
                return response or ""
                
        except Exception as e:
            logger.error(f"同步AI调用失败: {e}")
            raise
    
    def _get_fallback_analysis_prompt(self, text: str) -> str:
        """获取降级分析提示词"""
        return f"""请分析以下大纲的结构并提供优化建议：

{text}

请从以下角度进行分析：
1. 结构完整性分析
2. 内容层次梳理
3. 逻辑关系检查
4. 优化改进建议

请提供详细且具体的分析结果。"""
    
    def _parse_suggestions(self, response: str) -> List[str]:
        """解析AI返回的建议"""
        try:
            suggestions = []
            lines = response.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                # 识别列表项
                if line and (line.startswith('•') or line.startswith('-') or line.startswith('*') or 
                           any(line.startswith(f'{i}.') for i in range(1, 20))):
                    # 清理格式符号
                    clean_line = line.lstrip('•-*0123456789. ').strip()
                    if len(clean_line) > 10:  # 过滤太短的建议
                        suggestions.append(clean_line)
            
            # 如果没有找到列表格式，按句子分割
            if not suggestions:
                sentences = response.replace('\n', ' ').split('。')
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) > 15:
                        suggestions.append(sentence + '。')
            
            return suggestions[:8]  # 限制建议数量
            
        except Exception as e:
            logger.warning(f"解析建议失败: {e}")
            return [response[:200] + "..."] if response else []
