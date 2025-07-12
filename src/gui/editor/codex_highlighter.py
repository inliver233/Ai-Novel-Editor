"""
Codex引用高亮器
在编辑器中实时高亮显示Codex条目的引用
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import (
    QTextCharFormat, QTextDocument, QTextCursor,
    QColor, QFont, QTextBlockUserData
)
from PyQt6.QtWidgets import QTextEdit

logger = logging.getLogger(__name__)


class CodexReferenceData(QTextBlockUserData):
    """存储文本块中的Codex引用信息"""
    
    def __init__(self):
        super().__init__()
        self.references: List[Tuple[str, str, int, int]] = []  # (entry_id, text, start, end)


class CodexHighlighter(QObject):
    """Codex引用高亮器"""
    
    # 信号定义
    referencesDetected = pyqtSignal(list)  # 检测到引用时发出
    
    def __init__(self, text_edit: QTextEdit, codex_manager=None, 
                 reference_detector=None, parent=None):
        super().__init__(parent)
        
        self._text_edit = text_edit
        self._codex_manager = codex_manager
        self._reference_detector = reference_detector
        
        # 高亮格式配置
        self._formats = {
            'character': self._create_format(QColor(100, 150, 255), bold=True),     # 蓝色，角色
            'location': self._create_format(QColor(100, 200, 100), bold=True),      # 绿色，地点
            'object': self._create_format(QColor(255, 180, 100), bold=True),        # 橙色，物品
            'lore': self._create_format(QColor(200, 100, 200), bold=True),          # 紫色，传说
            'subplot': self._create_format(QColor(255, 150, 150), bold=True),       # 粉色，子情节
            'other': self._create_format(QColor(150, 150, 150), bold=True),         # 灰色，其他
        }
        
        # 悬停格式（带下划线）
        self._hover_formats = {}
        for entry_type, format in self._formats.items():
            hover_format = QTextCharFormat(format)
            hover_format.setFontUnderline(True)
            self._hover_formats[entry_type] = hover_format
        
        # 延迟高亮定时器
        self._highlight_timer = QTimer()
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.timeout.connect(self._do_highlight)
        
        # 缓存
        self._last_text = ""
        self._last_references: List[Tuple[str, str, int, int]] = []
        
        # 连接信号
        if self._text_edit:
            self._text_edit.textChanged.connect(self._on_text_changed)
            self._text_edit.cursorPositionChanged.connect(self._on_cursor_changed)
        
        logger.info("Codex highlighter initialized")
    
    def _create_format(self, color: QColor, bold: bool = False, 
                      underline: bool = False) -> QTextCharFormat:
        """创建文本格式"""
        format = QTextCharFormat()
        format.setForeground(color)
        
        if bold:
            format.setFontWeight(QFont.Weight.Bold)
        
        if underline:
            format.setFontUnderline(True)
        
        # 添加工具提示属性
        format.setToolTip("Codex引用")
        
        return format
    
    def set_codex_manager(self, codex_manager):
        """设置Codex管理器"""
        self._codex_manager = codex_manager
        self._request_highlight()
    
    def set_reference_detector(self, reference_detector):
        """设置引用检测器"""
        self._reference_detector = reference_detector
        self._request_highlight()
    
    def _on_text_changed(self):
        """文本变化时触发"""
        # 使用定时器延迟高亮，避免频繁触发
        self._highlight_timer.stop()
        self._highlight_timer.start(300)  # 300ms延迟
    
    def _on_cursor_changed(self):
        """光标位置变化时触发"""
        # 可以在这里实现悬停效果
        pass
    
    def _request_highlight(self):
        """请求高亮更新"""
        self._highlight_timer.stop()
        self._highlight_timer.start(100)
    
    def _do_highlight(self):
        """执行高亮"""
        if not self._text_edit or not self._reference_detector:
            return
        
        document = self._text_edit.document()
        if not document:
            return
        
        # 获取当前文本
        current_text = document.toPlainText()
        
        # 如果文本没有变化，跳过
        if current_text == self._last_text:
            return
        
        self._last_text = current_text
        
        try:
            # 检测引用
            references = self._reference_detector.detect_references(current_text)
            self._last_references = references
            
            # 清除现有高亮
            self._clear_highlights()
            
            # 应用新高亮
            self._apply_highlights(references)
            
            # 发送信号
            if references:
                self.referencesDetected.emit(references)
            
            logger.debug(f"Applied {len(references)} Codex highlights")
            
        except Exception as e:
            logger.error(f"Error highlighting Codex references: {e}")
    
    def _clear_highlights(self):
        """清除所有高亮"""
        # 不再清除所有格式，避免破坏语法高亮
        # 触发语法高亮器重新高亮整个文档
        if hasattr(self._text_edit, 'syntax_highlighter'):
            highlighter = self._text_edit.syntax_highlighter
            if highlighter:
                highlighter.rehighlight()
    
    def _apply_highlights(self, references: List):
        """应用高亮到检测到的引用"""
        if not self._codex_manager or not references:
            return
        
        document = self._text_edit.document()
        if not document:
            return
        
        cursor = QTextCursor(document)
        
        # 直接应用Codex高亮，不再调用rehighlight避免冲突
        # 使用mergeCharFormat保持现有格式
        for ref in references:
            entry = self._codex_manager.get_entry(ref.entry_id)
            if not entry:
                continue
            
            # 根据条目类型选择格式
            entry_type = entry.entry_type.value.lower()
            format = self._formats.get(entry_type, self._formats['other'])
            
            # 移动光标到引用位置
            cursor.setPosition(ref.start_position)
            cursor.setPosition(ref.end_position, QTextCursor.MoveMode.KeepAnchor)
            
            # 应用格式
            cursor.mergeCharFormat(format)
            
            # 存储引用数据到块用户数据
            block = cursor.block()
            block_data = block.userData()
            if not block_data:
                block_data = CodexReferenceData()
                block.setUserData(block_data)
            
            block_data.references.append((ref.entry_id, ref.matched_text, ref.start_position, ref.end_position))
    
    def _restore_original_formatting(self, cursor: QTextCursor):
        """恢复原始格式（如语法高亮）"""
        # 确保语法高亮器重新处理文档
        if hasattr(self._text_edit, 'syntax_highlighter'):
            highlighter = self._text_edit.syntax_highlighter
            if highlighter:
                # 重新高亮整个文档，确保语法高亮正确
                highlighter.rehighlight()
    
    def _restore_original_formatting_for_block(self, block):
        """恢复特定块的原始格式"""
        if hasattr(self._text_edit, 'syntax_highlighter'):
            highlighter = self._text_edit.syntax_highlighter
            if highlighter:
                # 重新高亮这个特定的块
                highlighter.rehighlightBlock(block)
    
    def get_reference_at_cursor(self) -> Optional[Tuple[str, str]]:
        """获取光标位置的引用信息"""
        cursor = self._text_edit.textCursor()
        position = cursor.position()
        
        # 查找包含该位置的引用
        for ref in self._last_references:
            if ref.start_position <= position <= ref.end_position:
                entry = self._codex_manager.get_entry(ref.entry_id) if self._codex_manager else None
                if entry:
                    return (ref.entry_id, entry.title)
        
        return None
    
    def highlight_reference(self, entry_id: str):
        """高亮特定条目的所有引用"""
        if not self._text_edit or not self._codex_manager:
            return
        
        cursor = QTextCursor(self._text_edit.document())
        
        # 查找并高亮该条目的所有引用
        for ref in self._last_references:
            if ref.entry_id == entry_id:
                cursor.setPosition(ref.start_position)
                cursor.setPosition(ref.end_position, QTextCursor.MoveMode.KeepAnchor)
                
                # 使用特殊的高亮格式
                special_format = QTextCharFormat()
                special_format.setBackground(QColor(255, 255, 100, 100))  # 淡黄色背景
                cursor.mergeCharFormat(special_format)
    
    def clear_special_highlights(self):
        """清除特殊高亮（保留普通Codex高亮）"""
        # 重新应用普通高亮
        self._do_highlight()
    
    def set_highlight_enabled(self, enabled: bool):
        """启用/禁用高亮"""
        if enabled:
            self._request_highlight()
        else:
            self._clear_highlights()
            self._last_text = ""
    
    def refresh(self):
        """刷新高亮"""
        self._last_text = ""  # 强制刷新
        self._request_highlight()