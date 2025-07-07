"""
智能补全管理器
统一管理所有补全功能，实现智能的分层补全策略
"""

import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QTextCursor, QKeyEvent

from .completion_engine import CompletionEngine, CompletionSuggestion
from .completion_widget import CompletionWidget
from .inline_completion import InlineCompletionManager
from .ghost_text_completion import ModernGhostTextCompletion
from .completion_status_indicator import FloatingStatusIndicator

logger = logging.getLogger(__name__)


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
        self._ghost_completion = ModernGhostTextCompletion(text_editor)
        self._status_indicator = FloatingStatusIndicator(text_editor)
        
        # 补全状态
        self._is_completing = False
        self._last_completion_pos = -1
        self._completion_mode = 'manual_ai'  # manual_ai, disabled, auto_ai - 默认手动模式
        
        # 定时器
        self._auto_completion_timer = QTimer()
        self._auto_completion_timer.setSingleShot(True)
        self._auto_completion_timer.timeout.connect(self._trigger_auto_completion)
        
        self._init_connections()
        
        # 彻底禁用浮动状态指示器，防止黄色横杆出现
        self._status_indicator.hide()
        self._status_indicator.setVisible(False)
        if hasattr(self._status_indicator, '_force_hide'):
            self._status_indicator._force_hide()
        
        logger.info("SmartCompletionManager initialized with FloatingStatusIndicator disabled")
        
    def _init_connections(self):
        """初始化信号连接"""
        # 弹出式补全信号
        self._popup_widget.suggestionAccepted.connect(self._on_popup_suggestion_accepted)
        self._popup_widget.cancelled.connect(self._on_popup_cancelled)
        
        # 内联补全信号
        self._inline_manager._completion_widget.suggestionAccepted.connect(self._on_inline_suggestion_accepted)
        self._inline_manager._completion_widget.suggestionRejected.connect(self._on_inline_suggestion_rejected)

        # 状态指示器信号
        self._status_indicator.modeChangeRequested.connect(self.set_completion_mode)

        # 文本编辑器信号
        self._text_editor.textChanged.connect(self._on_text_changed)
        
    def set_completion_mode(self, mode: str):
        """设置补全模式

        Args:
            mode: 'manual_ai', 'disabled', 'auto_ai'
        """
        self._completion_mode = mode
        logger.info(f"补全模式设置为: {mode}")

        # 更新状态指示器（但保持隐藏）
        self._status_indicator.set_completion_mode(mode)

        # 彻底禁用浮动状态指示器，防止黄色横杆出现
        # 状态指示器功能已被嵌入式指示器替代
        if hasattr(self._status_indicator, '_force_hide'):
            self._status_indicator._force_hide()
        
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
            
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """处理按键事件
        
        Returns:
            bool: 如果事件被处理则返回True
        """
        if self._completion_mode == 'disabled':
            return False
            
        # 优先处理Ghost Text补全
        if self._ghost_completion.handle_key_press(event):
            return True

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
                return True
                
        # Tab键处理 - 根据模式不同行为
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            if self._completion_mode == 'manual_ai':
                # 手动AI补全模式：Tab键触发一次AI补全
                self.trigger_completion('ai')
                return True
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

        # 防止重复触发
        if self._is_completing and self._last_completion_pos == position:
            return

        self._is_completing = True
        self._last_completion_pos = position

        # 根据当前补全模式和触发方式选择策略
        if self._completion_mode == 'manual_ai':
            # 手动AI模式：只有手动触发（包括Tab键和Ctrl+Space）时才进行AI补全
            if trigger_type in ['manual', 'ai']:
                self._ai_complete(text, position)
            else:
                # 自动触发时不做任何补全
                self._is_completing = False
        elif self._completion_mode == 'auto_ai':
            # 自动AI模式：优先AI补全，兜底智能补全
            if trigger_type == 'manual':
                # 手动触发：直接AI补全
                self._ai_complete(text, position)
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
                self._ai_complete(text, position)
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
        
    def _ai_complete(self, text: str, position: int):
        """AI补全 - 使用Ghost Text补全"""
        # 显示请求状态 - 使用现代状态指示器
        if hasattr(self._text_editor, '_ai_status_manager'):
            self._text_editor._ai_status_manager.show_requesting("发送AI补全请求")
        
        # 更新旧状态指示器（保持兼容，但不显示）
        self._status_indicator.set_ai_status('thinking')
        if hasattr(self._status_indicator, '_force_hide'):
            self._status_indicator._force_hide()

        # 构建AI提示
        context = self._build_ai_context(text, position)

        # 发出AI补全请求
        self.aiCompletionRequested.emit(text, context)

        # AI补全是异步的，不在这里设置_is_completing = False
        
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
        
    def _build_ai_context(self, text: str, position: int) -> Dict[str, Any]:
        """构建AI补全上下文"""
        # 获取光标前的文本作为上下文
        before_cursor = text[:position]
        after_cursor = text[position:]
        
        # 限制上下文长度
        if len(before_cursor) > 500:
            before_cursor = before_cursor[-500:]
            
        if len(after_cursor) > 100:
            after_cursor = after_cursor[:100]
            
        return {
            'before_cursor': before_cursor,
            'after_cursor': after_cursor,
            'position': position,
            'mode': 'inline',
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
        """显示AI补全建议"""
        # 更新旧状态指示器（保持兼容，但不显示）
        self._status_indicator.set_ai_status('idle')
        if hasattr(self._status_indicator, '_force_hide'):
            self._status_indicator._force_hide()

        if suggestion and suggestion.strip():
            # 显示完成状态 - 使用现代状态指示器
            if hasattr(self._text_editor, '_ai_status_manager'):
                self._text_editor._ai_status_manager.show_completed("AI补全生成完成")
            
            # 优先使用Ghost Text补全
            self._ghost_completion.show_completion(suggestion.strip())
            logger.info(f"AI Ghost Text补全显示: {suggestion[:50]}...")
        else:
            # 显示错误状态 - 使用现代状态指示器
            if hasattr(self._text_editor, '_ai_status_manager'):
                self._text_editor._ai_status_manager.show_error("AI补全生成失败")
            
            # 如果没有建议，设置AI状态为错误（但不显示旧指示器）
            self._status_indicator.set_ai_status('error')
            if hasattr(self._status_indicator, '_force_hide'):
                self._status_indicator._force_hide()

        self._is_completing = False
        
    def hide_all_completions(self):
        """隐藏所有补全"""
        self._popup_widget.hide()
        self._inline_manager.hide_completion()
        self._ghost_completion.hide_completion()
        self._is_completing = False
        
    def _trigger_auto_completion(self):
        """自动触发补全"""
        if self._completion_mode == 'auto_ai':
            self.trigger_completion('auto')
            
    def _on_text_changed(self):
        """文本变化处理"""
        if self._completion_mode == 'disabled':
            return

        # 重置补全状态
        self._is_completing = False

        # 手动AI模式：用户修改文本后清除所有补全
        if self._completion_mode == 'manual_ai':
            self.hide_all_completions()
            return

        # 自动AI模式：检查是否需要自动补全
        if self._completion_mode == 'auto_ai':
            cursor = self._text_editor.textCursor()
            text = self._text_editor.toPlainText()
            position = cursor.position()

            # 检查是否在@标记后输入
            if position > 0 and text[position-1:position+1] in ['@', '@c', '@l', '@t']:
                # 延迟触发自动补全
                self._auto_completion_timer.start(300)
            
    def _on_popup_suggestion_accepted(self, suggestion: CompletionSuggestion):
        """弹出式建议被接受"""
        # 插入建议到编辑器
        cursor = self._text_editor.textCursor()

        # 如果有替换长度信息，先删除要替换的文本
        if suggestion.replace_length > 0:
            cursor.movePosition(QTextCursor.MoveOperation.Left,
                              QTextCursor.MoveMode.KeepAnchor,
                              suggestion.replace_length)
            cursor.removeSelectedText()

        cursor.insertText(suggestion.text)
        self._popup_widget.hide()

        logger.info(f"弹出式建议已接受: {suggestion.text}")
        
    def _on_popup_cancelled(self):
        """弹出式补全被取消"""
        self._popup_widget.hide()
        logger.debug("弹出式补全被取消")
        
    def _on_inline_suggestion_accepted(self, suggestion: str):
        """内联建议被接受"""
        logger.info(f"内联建议已接受: {suggestion[:50]}...")
        
    def _on_inline_suggestion_rejected(self):
        """内联建议被拒绝"""
        logger.debug("内联建议被拒绝")
        
    def is_completing(self) -> bool:
        """是否正在补全"""
        return (self._is_completing or
                self._popup_widget.isVisible() or
                self._inline_manager.is_showing() or
                self._ghost_completion.is_showing())

    def get_status_indicator(self):
        """获取状态指示器"""
        return self._status_indicator
