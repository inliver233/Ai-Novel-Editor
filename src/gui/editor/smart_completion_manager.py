"""
智能补全管理器
统一管理所有补全功能，实现智能的分层补全策略
"""

import logging
import re
import time
from typing import Optional, List, Dict, Any, Tuple
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QTextCursor, QKeyEvent

from .completion_engine import CompletionEngine, CompletionSuggestion
from .completion_widget import CompletionWidget  # editor popup widget (not gui.ai.completion_widget)
from .inline_completion import InlineCompletionManager
from .completion_renderers import (
    DirectInsertRenderer,
    GhostTextRenderer,
    InlineCompletionRenderer,
)
from .timeout_manager import TimeoutManager
from .ghost_text_state_manager import GhostTextStateManager, GhostTextState
# Ghost text completion 通过 text_editor._ghost_completion 访问
# from .completion_status_indicator import FloatingStatusIndicator  # 已移除，避免状态指示器冲突

from domain.completion_state_machine import (
    CompletionEventType,
    CompletionState,
    CompletionStateMachine,
)

logger = logging.getLogger(__name__)

DEFAULT_AI_RENDERER_ORDER = ("ghost_text", "inline", "direct_insert")


class SmartCompletionManager(QObject):
    """智能补全管理器 - 统一所有补全功能"""
    
    # 信号定义
    aiCompletionRequested = pyqtSignal(str, dict)  # AI补全请求
    
    def __init__(self, text_editor, completion_engine: CompletionEngine):
        super().__init__()
        
        self._text_editor = text_editor
        self._completion_engine = completion_engine
        self._popup_widget = CompletionWidget(text_editor)
        self._inline_manager = InlineCompletionManager(text_editor)
        # 使用 text_editor 中已集成的 ghost completion - 增强检测逻辑
        self._ghost_completion = None
        
        # 按优先级检查可用的Ghost Text系统
        ghost_candidates = [
            ('_ghost_completion', 'Ghost Completion'),
            ('_optimal_ghost_text', 'Optimal Ghost Text'),
            ('_deep_ghost_text', 'Deep Ghost Text')
        ]
        
        for attr_name, display_name in ghost_candidates:
            if hasattr(text_editor, attr_name):
                candidate = getattr(text_editor, attr_name)
                if candidate is not None and hasattr(candidate, 'show_completion'):
                    self._ghost_completion = candidate
                    logger.info(f"✅ {display_name}已找到并初始化: type={type(self._ghost_completion)}")
                    break
                elif candidate is not None:
                    logger.warning(f"⚠️ {display_name}存在但缺少show_completion方法: type={type(candidate)}")
                    
        if self._ghost_completion is None:
            logger.warning("❌ 未找到可用的Ghost Text系统!")
            # 详细检查编辑器状态用于调试
            attrs_to_check = ['_ghost_completion', '_optimal_ghost_text', '_deep_ghost_text', '_use_optimal_ghost_text']
            for attr in attrs_to_check:
                if hasattr(text_editor, attr):
                    value = getattr(text_editor, attr)
                    logger.info(f"Editor.{attr} = {value} (type: {type(value)})")
                else:
                    logger.info(f"Editor.{attr} = <不存在>")

        # 统一的 Ghost Text 状态机（用于避免重复触发/残留 UI）
        existing_ghost_state = getattr(self._text_editor, "_ghost_state_manager", None)
        if existing_ghost_state is None:
            self._ghost_state_manager = GhostTextStateManager(parent=self)
            self._text_editor._ghost_state_manager = self._ghost_state_manager
        else:
            self._ghost_state_manager = existing_ghost_state

        # 纯状态机（domain/application 层）用于描述 completion 生命周期
        self._completion_state_machine = CompletionStateMachine()

        # 连接 Ghost Text 接受/拒绝信号到状态机，确保 Esc/Tab/输入 等路径一致收口
        self._bind_ghost_signals()
        # 移除FloatingStatusIndicator以避免状态指示器冲突
        # self._status_indicator = FloatingStatusIndicator(text_editor)
        
        # 补全状态
        self._is_completing = False
        self._last_completion_pos = -1
        self._completion_mode = 'manual_ai'  # manual_ai, disabled, auto_ai - 修复：默认手动模式
        
        # 🔧 修复：初始化动态超时管理器，传递用户配置的超时时间
        try:
            from core.config import get_config
            config = get_config()
            user_timeout = config.get('ai', 'timeout', 30) if config else 30
            self._timeout_manager = TimeoutManager(user_timeout=user_timeout)
        except Exception as e:
            logger.warning(f"获取用户超时配置失败，使用默认值: {e}")
            self._timeout_manager = TimeoutManager()
        
        # 定时器
        self._auto_completion_timer = QTimer()
        self._auto_completion_timer.setSingleShot(True)
        self._auto_completion_timer.timeout.connect(self._trigger_auto_completion)
        
        self._init_connections()
        QTimer.singleShot(0, self._bind_cancel_signal)
        
        # FloatingStatusIndicator已被移除，状态显示由ModernAIStatusIndicator负责
        logger.info("SmartCompletionManager initialized without FloatingStatusIndicator")

    def _bind_ghost_signals(self) -> None:
        ghost = self._ghost_completion
        if not ghost:
            return

        try:
            accepted_signal = getattr(ghost, "completionAccepted", None)
            if accepted_signal is not None and hasattr(accepted_signal, "connect"):
                accepted_signal.connect(self._on_ghost_completion_accepted)

            rejected_signal = getattr(ghost, "completionRejected", None)
            if rejected_signal is not None and hasattr(rejected_signal, "connect"):
                rejected_signal.connect(self._on_ghost_completion_rejected)
        except Exception as e:
            logger.warning(f"绑定Ghost Text信号失败: {e}")

    def _on_ghost_completion_accepted(self, accepted_text: str) -> None:
        try:
            if self._ghost_state_manager:
                self._ghost_state_manager.accept_with_text(accepted_text)
            self._completion_state_machine.set_state(CompletionState.APPLIED)
        except Exception as e:
            logger.debug(f"Ghost Text接受状态同步失败: {e}")

    def _on_ghost_completion_rejected(self) -> None:
        try:
            if self._ghost_state_manager:
                self._ghost_state_manager.force_idle()
            self._completion_state_machine.set_state(CompletionState.CANCELLED)
        except Exception as e:
            logger.debug(f"Ghost Text拒绝状态同步失败: {e}")
        
    def _init_connections(self):
        """初始化信号连接"""
        # 弹出式补全信号
        self._popup_widget.suggestionAccepted.connect(self._on_popup_suggestion_accepted)
        self._popup_widget.cancelled.connect(self._on_popup_cancelled)
        
        # 内联补全信号
        self._inline_manager._completion_widget.suggestionAccepted.connect(self._on_inline_suggestion_accepted)
        self._inline_manager._completion_widget.suggestionRejected.connect(self._on_inline_suggestion_rejected)

        # 移除状态指示器信号连接，因为不再使用FloatingStatusIndicator
        # self._status_indicator.modeChangeRequested.connect(self.set_completion_mode)

        # 文本编辑器信号
        self._text_editor.textChanged.connect(self._on_text_changed)

    def get_popup_widget(self) -> CompletionWidget:
        """统一的弹出式补全组件（唯一实例）。"""
        return self._popup_widget

    def get_inline_manager(self) -> InlineCompletionManager:
        """统一的内联补全管理器（唯一实例）。"""
        return self._inline_manager

    def _bind_cancel_signal(self):
        """延迟绑定AI取消信号（等待AIStatusManager初始化）"""
        try:
            if hasattr(self._text_editor, '_ai_status_manager'):
                self._text_editor._ai_status_manager.connect_cancel_signal(self._on_ai_cancel_requested)
                logger.debug("AI取消信号已连接到SmartCompletionManager")
        except Exception as e:
            logger.warning(f"绑定AI取消信号失败: {e}")

    def _on_ai_cancel_requested(self):
        """处理AI取消请求（来自状态指示器）"""
        logger.info("收到AI取消请求")
        self.cancel_current_completion()
        try:
            shared = getattr(self._text_editor, "_shared", None)
            ai_manager = getattr(shared, "ai_manager", None) if shared else None
            if ai_manager and hasattr(ai_manager, "cancel_ai_completion"):
                ai_manager.cancel_ai_completion(self._text_editor)
        except Exception as e:
            logger.warning(f"调用AI管理器取消失败: {e}")

    def cancel_current_completion(self):
        """取消当前补全并重置状态"""
        if hasattr(self, '_ai_timeout_timer') and self._ai_timeout_timer.isActive():
            self._ai_timeout_timer.stop()
        if hasattr(self, "_auto_completion_timer") and self._auto_completion_timer.isActive():
            self._auto_completion_timer.stop()
        self.hide_all_completions()
        self._is_completing = False
        self._last_completion_pos = -1
        if hasattr(self._text_editor, "_ai_status_manager"):
            self._text_editor._ai_status_manager.hide()
        self._ghost_state_manager.force_idle()
        try:
            self._completion_state_machine.handle_event(CompletionEventType.ESC)
        except Exception:
            pass
        
    def set_completion_mode(self, mode: str):
        """设置补全模式

        Args:
            mode: 'manual_ai', 'disabled', 'auto_ai'
        """
        self._completion_mode = mode
        logger.info(f"补全模式设置为: {mode}")

        # FloatingStatusIndicator已被移除
        # 状态显示由ModernAIStatusIndicator和嵌入式指示器负责
        
        # 向父窗口发送模式变更通知，用于同步工具栏显示
        self._notify_mode_change(mode)
        
        logger.debug(f"Completion mode set to {mode}, FloatingStatusIndicator remains disabled")
        
        if mode == 'disabled':
            self.hide_all_completions()
    
    def _notify_mode_change(self, mode: str):
        """通知父窗口补全模式发生变化，用于同步工具栏"""
        try:
            # 映射内部模式到显示名称
            mode_display_map = {
                "auto_ai": "自动",
                "manual_ai": "手动",
                "disabled": "禁用"
            }
            
            display_mode = mode_display_map.get(mode, mode)
            
            # 向上查找主窗口
            parent = self._text_editor.parent()
            while parent:
                if hasattr(parent, '_sync_completion_mode_to_toolbar'):
                    parent._sync_completion_mode_to_toolbar(display_mode)
                    logger.debug(f"通知主窗口同步补全模式: {display_mode}")
                    break
                parent = parent.parent()
                
        except Exception as e:
            logger.warning(f"Failed to notify mode change: {e}")

    def _get_ghost_system(self):
        """获取当前可用的 Ghost Text 系统实例（必要时重新探测）。"""
        if self._ghost_completion is not None:
            return self._ghost_completion

        # 动态回查编辑器上的 Ghost Text 相关属性，避免指针不同步
        ghost_candidates = [
            ('_ghost_completion', 'Ghost Completion'),
            ('_optimal_ghost_text', 'Optimal Ghost Text'),
            ('_deep_ghost_text', 'Deep Ghost Text')
        ]

        for attr_name, display_name in ghost_candidates:
            if hasattr(self._text_editor, attr_name):
                candidate = getattr(self._text_editor, attr_name)
                if candidate is not None and hasattr(candidate, 'show_completion'):
                    self._ghost_completion = candidate
                    logger.info(f"重新绑定 {display_name} 作为 Ghost Text 系统: type={type(self._ghost_completion)}")
                    return self._ghost_completion

        return None

    def _has_active_ghost_text(self) -> bool:
        """统一判断当前是否存在可见的 Ghost Text。"""
        ghost = self._get_ghost_system()
        if not ghost:
            return False

        try:
            if hasattr(ghost, 'has_active_ghost_text'):
                return bool(ghost.has_active_ghost_text())
            if hasattr(ghost, 'is_showing'):
                return bool(ghost.is_showing())
        except Exception as e:
            logger.error(f"检测 Ghost Text 状态失败: {e}")

        return False
            
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """处理按键事件
        
        Returns:
            bool: 如果事件被处理则返回True
        """
        if self._completion_mode == 'disabled':
            return False
            
        # ❌ 移除重复的Ghost Text处理 - 避免双重调用冲突
        # Ghost Text事件处理已在text_editor.keyPressEvent中处理
        # 此处重复调用导致Tab键被处理两次，引起状态混乱

        # 处理内联补全
        if self._inline_manager.handle_key_press(event):
            return True
            
        # 处理弹出式补全
        if self._popup_widget.isVisible():
            key = event.key()
            if key in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return, 
                      Qt.Key.Key_Enter, Qt.Key.Key_Tab]:
                self._popup_widget.keyPressEvent(event)
                return True
            elif key == Qt.Key.Key_Escape:
                self._popup_widget.hide()
                # 🔧 修复：检查是否有活跃的Ghost Text需要处理
                try:
                    if self._ghost_completion and self._ghost_completion.has_active_ghost_text():
                        self._ghost_completion.reject_ghost_text()
                except Exception as e:
                    logger.error(f"Smart补全管理器Esc键处理Ghost Text失败: {e}")
                return True
                
        # Tab键处理 - 🔧 修复手动模式状态管理
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            if self._completion_mode == 'manual_ai':
                # 🔧 修复：只有在没有活跃Ghost Text时才触发新补全
                if not (self._ghost_completion and self._ghost_completion.has_active_ghost_text()):
                    logger.debug("🎯 手动模式：触发AI补全")
                    self.trigger_completion('ai')
                    return True
                else:
                    logger.debug("⚠️ 手动模式：有活跃Ghost Text，Tab键应该被Ghost Text处理")
                    return False  # 让上层的Ghost Text处理Tab键
            elif self._completion_mode == 'auto_ai':
                # 自动AI补全模式：Tab键触发智能补全
                self.trigger_completion('smart')
                return True
            # disabled模式：不处理Tab键，让默认补全处理
            
        # Ctrl+Space强制AI补全
        elif (event.key() == Qt.Key.Key_Space and 
              event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            self.trigger_completion('ai')
            return True
            
        return False
        
    def trigger_completion(self, trigger_type: str = 'auto'):
        """触发补全

        Args:
            trigger_type: 'auto', 'manual', 'smart' - 触发方式
        """
        if self._completion_mode == 'disabled':
            return

        cursor = self._text_editor.textCursor()
        text = self._text_editor.toPlainText()
        position = cursor.position()

        logger.debug(f"触发补全: completion_mode={self._completion_mode}, trigger_type={trigger_type}, position={position}")

        # 🔧 修复：防止重复触发，并清理旧状态
        if self._is_completing and self._last_completion_pos == position:
            logger.debug(f"防止重复触发: position={position}")
            return

        # 🔧 修复：增强重复检查 - 检查时间间隔
        import time
        current_time = time.time()
        if hasattr(self, '_last_trigger_time'):
            time_diff = current_time - self._last_trigger_time
            if time_diff < 0.3:  # 300ms内重复触发
                logger.debug(f"⚠️ 触发间隔过短({time_diff:.3f}s)，跳过重复触发")
                return
        self._last_trigger_time = current_time

        # 🔧 修复：确保清理任何残留的Ghost Text状态
        if self._ghost_completion and self._ghost_completion.has_active_ghost_text():
            logger.debug("🧹 触发新补全前清理残留的Ghost Text状态")
            self._ghost_completion.clear_ghost_text()

        self._is_completing = True
        self._last_completion_pos = position

        # 根据当前补全模式和触发方式选择策略
        if self._completion_mode == 'manual_ai':
            # 手动AI模式：只有手动触发（包括Tab键和Ctrl+Space）时才进行AI补全
            if trigger_type in ['manual', 'ai']:
                self._ai_complete(text, position, trigger_type)
            else:
                # 自动触发时不做任何补全
                self._is_completing = False
        elif self._completion_mode == 'auto_ai':
            # 自动AI模式：优先AI补全，兜底智能补全
            if trigger_type == 'manual':
                # 手动触发：直接AI补全
                self._ai_complete(text, position, trigger_type)
            else:
                # 自动触发：智能补全（混合策略）
                self._smart_complete(text, position)
        else:
            # 兜底：使用传统补全策略
            if trigger_type == 'auto':
                self._auto_complete(text, position)
            elif trigger_type == 'word':
                self._word_complete(text, position)
            elif trigger_type == 'ai':
                self._ai_complete(text, position, trigger_type)
            elif trigger_type == 'smart':
                self._smart_complete(text, position)
            
    def _auto_complete(self, text: str, position: int):
        """自动补全 - 根据上下文智能选择"""
        # 分析上下文决定补全类型
        completion_type = self._analyze_completion_context(text, position)
        
        if completion_type == 'tag':
            self._word_complete(text, position)
        elif completion_type == 'concept':
            self._word_complete(text, position)
        elif completion_type == 'content':
            self._ai_complete(text, position)
        else:
            self._word_complete(text, position)
            
    def _word_complete(self, text: str, position: int):
        """单词级补全 - 使用本地补全引擎"""
        suggestions = self._completion_engine.get_completions(text, position)
        
        if suggestions:
            # 使用弹出式补全显示多个选项
            self._show_popup_completion(suggestions)
        else:
            # 没有本地建议，尝试AI补全
            self._ai_complete(text, position)
            
        self._is_completing = False
        
    def _ai_complete(self, text: str, position: int, trigger_type: str = 'auto'):
        """AI补全 - 使用Ghost Text补全
        
        Args:
            text: 文档文本
            position: 光标位置  
            trigger_type: 触发类型 ('auto', 'manual', 'ai')
        """
        # 状态机：仅允许在空闲状态发起新的 AI 请求
        if self._ghost_state_manager and not self._ghost_state_manager.request_completion():
            logger.debug("🚫 Ghost Text状态非空闲，跳过新的AI补全请求")
            self._is_completing = False
            return

        try:
            self._completion_state_machine.reset()
            self._completion_state_machine.set_state(CompletionState.REQUESTING)
        except Exception:
            pass

        # 显示请求状态 - 使用现代状态指示器
        if hasattr(self._text_editor, '_ai_status_manager'):
            self._text_editor._ai_status_manager.show_requesting("发送AI补全请求")
        
        # FloatingStatusIndicator已被移除
        # 状态显示由ModernAIStatusIndicator负责

        # 构建AI提示 - 传递trigger_type以正确设置模式
        context = self._build_ai_context(text, position, trigger_type)
        
        # 🔧 修复：保存上下文用于超时处理和记录
        self._last_ai_context = context

        # 🔧 修复：记录AI请求时间，用于超时处理
        self._ai_request_time = time.time()
        self._ai_request_completed = False  # 重置完成标记
        
        # 🔧 修复：使用动态超时管理器计算超时时间
        dynamic_timeout = self._timeout_manager.calculate_dynamic_timeout(context)
        
        # 🔧 修复：设置动态超时定时器，防止AI请求hanging导致状态无法重置
        if not hasattr(self, '_ai_timeout_timer'):
            self._ai_timeout_timer = QTimer()
            self._ai_timeout_timer.setSingleShot(True)
            self._ai_timeout_timer.timeout.connect(self._on_ai_timeout)
        
        # 使用动态计算的超时时间
        timeout_ms = int(dynamic_timeout * 1000)  # 转换为毫秒
        self._ai_timeout_timer.start(timeout_ms)
        
        logger.debug(f"🕐 设置动态超时: {dynamic_timeout:.1f}秒 ({timeout_ms}ms)")

        # 发出AI补全请求
        self.aiCompletionRequested.emit(text, context)

        # AI补全是异步的，_is_completing状态将在show_ai_completion或超时时重置
        
    def _on_ai_timeout(self):
        """AI请求超时处理 - 增强版本，支持状态同步"""
        # 🔧 修复：检查是否实际已经成功，避免状态冲突
        if hasattr(self, '_ai_request_completed') and self._ai_request_completed:
            logger.info("⏰ 超时触发但AI请求实际已完成，跳过超时处理")
            return
            
        # 记录超时到动态超时管理器
        if hasattr(self, '_ai_request_time'):
            timeout_duration = time.time() - self._ai_request_time
            # 构建上下文用于记录
            context = getattr(self, '_last_ai_context', {})
            self._timeout_manager.record_request_time(timeout_duration, context, success=False)
            logger.warning(f"⏰ AI补全请求超时: {timeout_duration:.1f}秒")
        else:
            logger.warning("⏰ AI补全请求超时，无法获取请求时间")
            
        self._reset_completion_state(success=False, reason="timeout")
        if hasattr(self._text_editor, '_ai_status_manager'):
            self._text_editor._ai_status_manager.show_error("AI补全请求超时")
        self._ghost_state_manager.force_idle()
        try:
            self._completion_state_machine.handle_event(CompletionEventType.TIMEOUT)
        except Exception:
            pass
        
    def _smart_complete(self, text: str, position: int):
        """智能补全 - 混合策略"""
        # 先尝试本地补全
        suggestions = self._completion_engine.get_completions(text, position)
        
        if suggestions:
            # 有本地建议，显示弹出式补全
            self._show_popup_completion(suggestions)
            self._is_completing = False
        else:
            # 没有本地建议，使用AI补全
            self._ai_complete(text, position)
            
    def _analyze_completion_context(self, text: str, position: int) -> str:
        """分析补全上下文"""
        # 获取光标前的文本
        before_cursor = text[:position]
        
        # 检查是否在@标记中
        if re.search(r'@\w*$', before_cursor):
            return 'tag'
            
        # 检查是否在概念名称中
        words = re.findall(r'\w+', before_cursor[-50:])  # 最后50字符中的单词
        if words and len(words[-1]) >= 2:
            return 'concept'
            
        # 检查是否在句子中间（需要内容补全）
        if before_cursor.strip() and not before_cursor.strip().endswith(('.', '!', '?', '\n')):
            return 'content'
            
        return 'general'
        
    def _build_ai_context(self, text: str, position: int, trigger_type: str = 'auto') -> Dict[str, Any]:
        """构建AI补全上下文
        
        Args:
            text: 文档文本
            position: 光标位置
            trigger_type: 触发类型，用于确定补全模式
        """
        # 获取光标前的文本作为上下文
        before_cursor = text[:position]
        after_cursor = text[position:]
        
        # 限制上下文长度
        if len(before_cursor) > 500:
            before_cursor = before_cursor[-500:]
            
        if len(after_cursor) > 100:
            after_cursor = after_cursor[:100]
            
        # 根据触发类型确定补全模式
        if trigger_type == 'manual':
            mode = 'manual'
        elif trigger_type == 'auto':
            mode = 'auto'
        else:
            mode = 'inline'  # 保持兼容性
            
        return {
            'before_cursor': before_cursor,
            'after_cursor': after_cursor,
            'position': position,
            'mode': mode,
            'trigger_type': trigger_type,
            'source': 'smart_completion'
        }
        
    def _show_popup_completion(self, suggestions: List[CompletionSuggestion]):
        """显示弹出式补全"""
        # 定位到光标位置
        cursor_rect = self._text_editor.cursorRect()
        global_pos = self._text_editor.mapToGlobal(cursor_rect.bottomLeft())

        # 调整位置确保在屏幕内
        self._popup_widget.move(global_pos)
        self._popup_widget.show_suggestions(suggestions)
        
    def show_ai_completion(self, suggestion: str):
        """显示AI补全建议 - 增强版本，支持多种显示模式和状态同步"""
        # 🔧 修复：标记请求已完成，防止超时处理冲突
        self._ai_request_completed = True
        
        # 🔧 修复：停止超时定时器
        if hasattr(self, '_ai_timeout_timer'):
            self._ai_timeout_timer.stop()
            
        # 🔧 修复：记录请求完成时间到动态超时管理器
        if hasattr(self, '_ai_request_time'):
            request_duration = time.time() - self._ai_request_time
            # 获取上下文用于记录
            context = getattr(self, '_last_ai_context', {})
            self._timeout_manager.record_request_time(request_duration, context, success=True)
            logger.debug(f"📊 AI请求完成，耗时: {request_duration:.2f}秒")
            
        if not suggestion or not suggestion.strip():
            logger.warning("AI补全建议为空，跳过显示")
            if hasattr(self._text_editor, '_ai_status_manager'):
                self._text_editor._ai_status_manager.show_error("AI补全生成失败")
            self._reset_completion_state(success=False, reason="empty_suggestion")
            self._ghost_state_manager.force_idle()
            try:
                self._completion_state_machine.set_state(CompletionState.CANCELLED)
            except Exception:
                pass
            return

        suggestion = suggestion.strip()
        logger.info(f"开始显示AI补全建议: {suggestion[:50]}...")
        
        # 显示完成状态
        if hasattr(self._text_editor, '_ai_status_manager'):
            self._text_editor._ai_status_manager.show_completed("AI补全生成完成")
        
        # 尝试多种显示方式，按优先级排列
        if not self._ghost_completion:
            self._redetect_ghost_text_system()

        renderer_map = {
            "ghost_text": GhostTextRenderer(self._ghost_completion, self._ghost_state_manager),
            "inline": InlineCompletionRenderer(self._inline_manager),
            "direct_insert": DirectInsertRenderer(self._text_editor),
        }
        renderers = [renderer_map[key] for key in DEFAULT_AI_RENDERER_ORDER]
        
        for renderer in renderers:
            try:
                if renderer.render(suggestion):
                    logger.info(f"✅ AI补全使用{renderer.display_name}显示成功")
                    # 🔧 修复：成功显示后确保状态正确重置
                    self._reset_completion_state(success=True)
                    try:
                        if renderer.key in ("ghost_text", "inline"):
                            self._completion_state_machine.set_suggestion_ready(suggestion)
                        else:
                            self._completion_state_machine.set_state(CompletionState.APPLIED)
                    except Exception:
                        pass
                    # 只有 Ghost Text 显示会进入 VISIBLE；其它显示方式保持 IDLE
                    if renderer.key != "ghost_text":
                        self._ghost_state_manager.force_idle()
                    return
                else:
                    logger.debug(f"⚠️ {renderer.display_name}显示方法不可用，尝试下一种")
            except Exception as e:
                logger.error(f"❌ {renderer.display_name}显示方法失败: {e}")
                
        logger.error("所有AI补全显示方法都失败了")
        # 🔧 修复：失败时也要正确重置状态
        self._reset_completion_state(success=False, reason="display_failed")
        self._ghost_state_manager.force_idle()
        try:
            self._completion_state_machine.set_state(CompletionState.CANCELLED)
        except Exception:
            pass
    
    def _reset_completion_state(self, success: bool = True, reason: str = ""):
        """重置补全状态 - 统一的状态管理和同步
        
        Args:
            success: 是否成功完成
            reason: 重置原因，用于日志记录
        """
        # 🔧 修复：详细的状态变更日志记录
        old_state = {
            'is_completing': self._is_completing,
            'has_timeout_timer': hasattr(self, '_ai_timeout_timer') and self._ai_timeout_timer.isActive(),
            'request_completed': getattr(self, '_ai_request_completed', False)
        }
        
        # 重置核心状态
        self._is_completing = False
        self._ai_request_completed = False
        
        # 🔧 修复：确保超时定时器被正确停止
        if hasattr(self, '_ai_timeout_timer') and self._ai_timeout_timer.isActive():
            self._ai_timeout_timer.stop()
            logger.debug("🛑 超时定时器已停止")
        
        # 🔧 修复：状态同步机制 - 以实际结果为准
        if not success:
            # 失败时清理所有补全状态
            self.hide_all_completions()
            # 清理请求相关的临时状态
            if hasattr(self, '_last_ai_context'):
                delattr(self, '_last_ai_context')
            if hasattr(self, '_ai_request_time'):
                delattr(self, '_ai_request_time')
        
        # 详细的状态变更日志
        new_state = {
            'is_completing': self._is_completing,
            'has_timeout_timer': hasattr(self, '_ai_timeout_timer') and self._ai_timeout_timer.isActive(),
            'request_completed': getattr(self, '_ai_request_completed', False)
        }
        
        logger.info(f"🔄 补全状态已重置: success={success}, reason='{reason}'")
        logger.debug(f"   状态变更: {old_state} -> {new_state}")
        
        # 🔧 修复：通知状态管理器状态变更
        if hasattr(self._text_editor, '_ai_status_manager'):
            if success:
                # 成功时不需要额外通知，因为已经在show_ai_completion中处理
                pass
            else:
                # 失败时确保状态指示器显示正确状态
                if reason == "timeout":
                    self._text_editor._ai_status_manager.show_error("请求超时")
                elif reason == "error":
                    self._text_editor._ai_status_manager.show_error("请求失败")
                else:
                    self._text_editor._ai_status_manager.hide()
            self._ghost_state_manager.force_idle()
        
    def _try_ghost_text_display(self, suggestion: str) -> bool:
        """尝试使用Ghost Text显示补全"""
        # 检查当前Ghost Text系统
        if not self._ghost_completion:
            # 动态重新检测Ghost Text系统
            self._redetect_ghost_text_system()
            
        if self._ghost_completion and hasattr(self._ghost_completion, 'show_completion'):
            try:
                result = self._ghost_completion.show_completion(suggestion)
                logger.info(f"Ghost Text显示成功: {result}")
                if result and self._ghost_state_manager:
                    # 正常路径：GENERATING -> VISIBLE
                    if not self._ghost_state_manager.show(suggestion):
                        self._ghost_state_manager.mark_visible(suggestion)
                return bool(result)
            except Exception as e:
                logger.error(f"Ghost Text显示失败: {e}")
                
        return False
        
    def _try_inline_display(self, suggestion: str) -> bool:
        """尝试使用内联补全显示"""
        try:
            if self._inline_manager and hasattr(self._inline_manager, 'show_completion'):
                self._inline_manager.show_completion(suggestion)
                return True
        except Exception as e:
            logger.error(f"内联补全显示失败: {e}")
        return False
        
    def _try_direct_insert(self, suggestion: str) -> bool:
        """直接插入文本作为最后的回退"""
        try:
            cursor = self._text_editor.textCursor()
            cursor.insertText(suggestion)
            logger.warning(f"使用直接插入模式显示AI补全: {suggestion[:50]}...")
            return True
        except Exception as e:
            logger.error(f"直接插入失败: {e}")
            return False
            
    def _redetect_ghost_text_system(self):
        """重新检测Ghost Text系统"""
        logger.info("重新检测Ghost Text系统...")
        
        # 按优先级检查可用的Ghost Text系统
        ghost_candidates = [
            ('_ghost_completion', 'Ghost Completion'),
            ('_optimal_ghost_text', 'Optimal Ghost Text'),
            ('_deep_ghost_text', 'Deep Ghost Text')
        ]
        
        for attr_name, display_name in ghost_candidates:
            if hasattr(self._text_editor, attr_name):
                candidate = getattr(self._text_editor, attr_name)
                if candidate is not None and hasattr(candidate, 'show_completion'):
                    self._ghost_completion = candidate
                    logger.info(f"✅ 重新检测到{display_name}: type={type(self._ghost_completion)}")
                    return
                    
        logger.warning("❌ 重新检测未找到可用的Ghost Text系统")
        
    def hide_all_completions(self):
        """隐藏所有补全"""
        self._popup_widget.hide()
        self._inline_manager.hide_completion()
        if self._ghost_completion:
            self._ghost_completion.hide_completion()
        self._is_completing = False
        if self._ghost_state_manager:
            self._ghost_state_manager.force_idle()
        
    def _trigger_auto_completion(self):
        """自动触发补全"""
        if self._completion_mode == 'auto_ai':
            self.trigger_completion('auto')
            
    def _on_text_changed(self):
        """文本变化处理"""
        if self._completion_mode == 'disabled':
            return

        # 🔧 修复：防止Ghost Text更新触发的循环
        if self._ghost_completion and self._ghost_completion.has_active_ghost_text():
            logger.debug("🚫 检测到活跃的Ghost Text，跳过textChanged处理以防止循环")
            return

        # 🔧 修复：检查是否正在进行AI补全，防止重复触发
        if self._is_completing:
            logger.debug("🚫 正在进行补全，跳过textChanged处理")
            return

        # 手动AI模式：用户修改文本后清除所有补全
        if self._completion_mode == 'manual_ai':
            self.hide_all_completions()
            return

        # 自动AI模式：检查是否需要自动补全
        if self._completion_mode == 'auto_ai':
            cursor = self._text_editor.textCursor()
            text = self._text_editor.toPlainText()
            position = cursor.position()

            # 🔧 修复：增强触发条件检查，确保是真实的用户输入
            if position > 0 and self._should_trigger_auto_completion(text, position):
                logger.debug(f"🎯 auto_ai模式：条件满足，准备触发自动补全 (pos={position})")
                # 设置补全状态防止重复触发
                self._is_completing = True
                # 延迟触发自动补全
                self._auto_completion_timer.start(300)
    
    def _should_trigger_auto_completion(self, text: str, position: int) -> bool:
        """检查是否应该触发自动补全 - 增强版本"""
        # 基本条件：在@标记后输入
        if not (position > 0 and text[position-1:position+1] in ['@', '@c', '@l', '@t']):
            return False
            
        # 🔧 修复：检查是否是用户真实输入而非程序化更新
        # 获取更大的上下文来判断
        context_start = max(0, position - 20)
        context = text[context_start:position + 5]
        
        # 如果上下文中包含大量连续的相同内容，可能是程序化更新
        if len(context) > 10:
            repeated_chars = max([context.count(char) for char in set(context) if char.isprintable()])
            if repeated_chars > len(context) * 0.7:  # 70%以上是重复字符
                logger.debug(f"⚠️ 疑似程序化更新，跳过自动补全：{context[:20]}")
                return False
        
        # 检查是否在短时间内有多次触发（可能是循环）
        import time
        current_time = time.time()
        if hasattr(self, '_last_auto_trigger_time'):
            if current_time - self._last_auto_trigger_time < 0.5:  # 500ms内重复触发
                logger.debug("⚠️ 检测到快速重复触发，跳过自动补全")
                return False
        self._last_auto_trigger_time = current_time
        
        return True
            
    def _on_popup_suggestion_accepted(self, suggestion: CompletionSuggestion):
        """弹出式建议被接受"""
        # 插入建议到编辑器（保持与 IntelligentTextEditor._on_suggestion_accepted 一致）
        cursor = self._text_editor.textCursor()
        cursor.setPosition(suggestion.insert_position)

        if suggestion.replace_length > 0:
            cursor.setPosition(
                suggestion.insert_position + suggestion.replace_length,
                QTextCursor.MoveMode.KeepAnchor,
            )

        cursor.insertText(suggestion.text)
        self._text_editor.setTextCursor(cursor)
        self._popup_widget.hide()
        try:
            self._completion_state_machine.set_state(CompletionState.APPLIED)
        except Exception:
            pass

        logger.info(f"弹出式建议已接受: {suggestion.text}")
        
    def _on_popup_cancelled(self):
        """弹出式补全被取消"""
        self._popup_widget.hide()
        try:
            self._completion_state_machine.set_state(CompletionState.CANCELLED)
        except Exception:
            pass
        logger.debug("弹出式补全被取消")
        
    def _on_inline_suggestion_accepted(self, suggestion: str):
        """内联建议被接受"""
        try:
            self._completion_state_machine.set_state(CompletionState.APPLIED)
        except Exception:
            pass
        logger.info(f"内联建议已接受: {suggestion[:50]}...")
        
    def _on_inline_suggestion_rejected(self):
        """内联建议被拒绝"""
        logger.debug("内联建议被拒绝")
        
    def is_completing(self) -> bool:
        """是否正在补全"""
        return (self._is_completing or
                self._popup_widget.isVisible() or
                self._inline_manager.is_showing() or
                (self._ghost_completion and self._ghost_completion.is_showing()))

    def get_status_indicator(self):
        """获取状态指示器"""
        # FloatingStatusIndicator已被移除
        # 状态显示由ModernAIStatusIndicator和EmbeddedStatusIndicator负责
        return None
    
    def _validate_state_consistency(self) -> bool:
        """验证状态一致性 - 检查各个状态标记是否同步
        
        Returns:
            bool: 状态是否一致
        """
        try:
            # 检查核心状态
            is_completing = self._is_completing
            has_active_timer = hasattr(self, '_ai_timeout_timer') and self._ai_timeout_timer.isActive()
            request_completed = getattr(self, '_ai_request_completed', False)
            has_active_ghost = self._ghost_completion and self._ghost_completion.has_active_ghost_text() if self._ghost_completion else False
            
            # 状态一致性检查
            inconsistencies = []
            
            # 如果请求已完成，不应该还有活跃的超时定时器
            if request_completed and has_active_timer:
                inconsistencies.append("请求已完成但超时定时器仍活跃")
                
            # 如果没有正在补全，不应该有活跃的超时定时器
            if not is_completing and has_active_timer:
                inconsistencies.append("未在补全但超时定时器活跃")
                
            # 如果有活跃的Ghost Text，应该标记为正在补全
            if has_active_ghost and not is_completing:
                inconsistencies.append("有活跃Ghost Text但未标记为补全中")
            
            if inconsistencies:
                logger.warning(f"🚨 状态不一致检测到: {', '.join(inconsistencies)}")
                logger.debug(f"   状态详情: completing={is_completing}, timer={has_active_timer}, "
                           f"completed={request_completed}, ghost={has_active_ghost}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"状态一致性验证失败: {e}")
            return False
    
    def _force_state_sync(self):
        """强制状态同步 - 修复检测到的状态不一致问题"""
        try:
            logger.info("🔧 执行强制状态同步")
            
            # 检查是否有活跃的Ghost Text
            has_active_ghost = False
            if self._ghost_completion:
                try:
                    has_active_ghost = self._ghost_completion.has_active_ghost_text()
                except:
                    has_active_ghost = False
            
            # 检查是否有活跃的弹出补全
            has_popup = self._popup_widget.isVisible()
            
            # 检查是否有活跃的内联补全
            has_inline = self._inline_manager.is_showing()
            
            # 根据实际情况同步状态
            should_be_completing = has_active_ghost or has_popup or has_inline
            
            if should_be_completing != self._is_completing:
                logger.info(f"🔄 同步补全状态: {self._is_completing} -> {should_be_completing}")
                self._is_completing = should_be_completing
            
            # 如果没有任何活跃补全，确保清理所有相关状态
            if not should_be_completing:
                if hasattr(self, '_ai_timeout_timer') and self._ai_timeout_timer.isActive():
                    self._ai_timeout_timer.stop()
                    logger.debug("🛑 强制停止超时定时器")
                    
                self._ai_request_completed = False
                
                # 清理临时状态
                for attr in ['_last_ai_context', '_ai_request_time']:
                    if hasattr(self, attr):
                        delattr(self, attr)
                        
            logger.info("✅ 强制状态同步完成")
            
        except Exception as e:
            logger.error(f"强制状态同步失败: {e}")
    
    def get_timeout_statistics(self) -> Dict[str, Any]:
        """获取超时管理统计信息
        
        Returns:
            Dict: 超时统计信息
        """
        try:
            stats = self._timeout_manager.get_timeout_statistics()
            
            # 添加当前状态信息
            stats.update({
                'current_state': {
                    'is_completing': self._is_completing,
                    'has_active_timer': hasattr(self, '_ai_timeout_timer') and self._ai_timeout_timer.isActive(),
                    'request_completed': getattr(self, '_ai_request_completed', False),
                    'completion_mode': self._completion_mode
                },
                'state_consistent': self._validate_state_consistency()
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"获取超时统计信息失败: {e}")
            return {'error': str(e)}
    
    def reset_timeout_history(self):
        """重置超时历史记录 - 用于调试和维护"""
        try:
            self._timeout_manager.reset_history()
            logger.info("📊 超时历史记录已重置")
        except Exception as e:
            logger.error(f"重置超时历史记录失败: {e}")
    
    def emergency_reset(self):
        """紧急重置 - 清理所有状态，用于故障恢复"""
        try:
            logger.warning("🚨 执行紧急重置")
            
            # 停止所有定时器
            if hasattr(self, '_ai_timeout_timer'):
                self._ai_timeout_timer.stop()
            if hasattr(self, '_auto_completion_timer'):
                self._auto_completion_timer.stop()
            
            # 隐藏所有补全
            self.hide_all_completions()
            
            # 重置所有状态标记
            self._is_completing = False
            self._ai_request_completed = False
            self._last_completion_pos = -1
            
            # 清理临时状态
            for attr in ['_last_ai_context', '_ai_request_time', '_last_trigger_time', '_last_auto_trigger_time']:
                if hasattr(self, attr):
                    delattr(self, attr)
            
            # 通知状态管理器
            if hasattr(self._text_editor, '_ai_status_manager'):
                self._text_editor._ai_status_manager.hide()
            
            logger.info("✅ 紧急重置完成")
            
        except Exception as e:
            logger.error(f"紧急重置失败: {e}")
