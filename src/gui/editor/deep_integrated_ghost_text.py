"""
深度集成QTextDocument的Ghost Text系统
实现完美的预览效果，与实际插入效果完全一致
"""

import logging
import time
from typing import Optional, Dict, Set, List, Tuple
from PyQt6.QtWidgets import QTextEdit, QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QObject, pyqtSignal
from PyQt6.QtGui import (
    QTextDocument, QTextCursor, QTextBlock, QTextBlockUserData,
    QTextCharFormat, QTextLayout, QColor, QPainter, QFont,
    QFontMetrics, QKeyEvent, QPaintEvent
)

logger = logging.getLogger(__name__)


class GhostTextUserData(QTextBlockUserData):
    """存储Ghost Text相关数据的用户数据类"""
    
    def __init__(self):
        super().__init__()
        self.ghost_text = ""
        self.ghost_position = 0  # 在块中的相对位置
        self.is_active = False
        self.timestamp = time.time()  # 用于过期检查
        self.original_format = None  # 保存原始格式用于恢复


class PreciseLayoutCalculator:
    """精确布局计算器 - 基于QTextLayout的原生布局引擎"""
    
    def __init__(self, document: QTextDocument):
        self.document = document
        
    def calculate_ghost_position(self, block: QTextBlock, position_in_block: int) -> QRectF:
        """使用Qt原生布局引擎计算精确的Ghost Text位置"""
        if not block.isValid():
            return QRectF()
            
        layout = block.layout()
        if not layout:
            return QRectF()
            
        # 验证位置在块范围内
        if position_in_block < 0 or position_in_block > block.length():
            return QRectF()
            
        # 获取光标在当前行的位置
        line = layout.lineForTextPosition(position_in_block)
        if not line.isValid():
            return QRectF()
            
        try:
            # 计算精确的x坐标 - 安全处理可能的tuple返回值
            cursor_x_raw = line.cursorToX(position_in_block)
            cursor_x = float(cursor_x_raw[0]) if isinstance(cursor_x_raw, (tuple, list)) else float(cursor_x_raw)
            
            # 获取块在文档中的位置
            doc_layout = self.document.documentLayout()
            if not doc_layout:
                return QRectF()
            
            # 确保布局是最新的
            # 这会强制Qt更新文档布局
            doc_layout.documentSize()
                
            block_rect = doc_layout.blockBoundingRect(block)
            
            # 如果块还没有布局信息，尝试使用替代方法
            if block_rect.isNull() or (block_rect.y() == 0 and block.blockNumber() > 0):
                # 尝试通过迭代前面的块来计算位置
                estimated_y = 0.0
                current_block = self.document.firstBlock()
                while current_block.isValid() and current_block.blockNumber() < block.blockNumber():
                    current_rect = doc_layout.blockBoundingRect(current_block)
                    if not current_rect.isNull():
                        estimated_y = current_rect.y() + current_rect.height()
                    current_block = current_block.next()
                
                if estimated_y > 0:
                    logger.debug(f"Using estimated y position for block #{block.blockNumber()}: {estimated_y}")
                    # 创建一个估算的矩形
                    block_rect = QRectF(block_rect.x(), estimated_y, block_rect.width(), block_rect.height())
            
            # 安全获取line的位置和尺寸信息
            line_y = float(line.y())
            line_height = float(line.height())
            block_y = float(block_rect.y())
            
            # 添加调试日志
            logger.debug(f"Block #{block.blockNumber()}: block_rect={block_rect}, block_y={block_y}, line_y={line_y}, line_height={line_height}")
            
            # 检查block的有效性和布局状态
            if block_y == 0 and block.blockNumber() > 0:
                logger.warning(f"Block #{block.blockNumber()} has y=0, this might be a layout issue. Block text: '{block.text()[:50]}...'")
            
            # 计算最终坐标，确保值有效 - 使用显式的float参数
            ghost_rect = QRectF(
                max(0.0, cursor_x),
                max(0.0, block_y + line_y),
                1.0,  # 最小宽度确保isValid()通过，实际宽度在渲染时重新计算
                max(1.0, line_height)  # 确保最小高度
            )
            
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning(f"计算Ghost Text位置时出错: {e}")
            return QRectF()
        
        return ghost_rect
        
    def calculate_text_width(self, text: str, font: QFont) -> float:
        """计算文本宽度，考虑中英文混合"""
        font_metrics = QFontMetrics(font)
        return font_metrics.horizontalAdvance(text)
        
    def get_line_available_width(self, block: QTextBlock, position_in_block: int, 
                                text_edit_width: int) -> float:
        """获取当前行的可用宽度"""
        layout = block.layout()
        if not layout:
            return float(text_edit_width)
            
        line = layout.lineForTextPosition(position_in_block)
        if not line.isValid():
            return float(text_edit_width)
        
        try:
            # 安全获取cursor_x，处理可能的tuple返回值
            cursor_x_raw = line.cursorToX(position_in_block)
            cursor_x = float(cursor_x_raw[0]) if isinstance(cursor_x_raw, (tuple, list)) else float(cursor_x_raw)
            
            available = float(text_edit_width) - cursor_x
            return max(0.0, available)  # 确保不返回负数
            
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning(f"计算行可用宽度时出错: {e}")
            return float(text_edit_width)


class SmartRenderingEngine:
    """智能渲染引擎 - 非破坏性临时格式化"""
    
    def __init__(self, text_editor):
        self.text_editor = text_editor
        self.document = text_editor.document()
        self._ghost_format = self._create_ghost_format()
        
    def _create_ghost_format(self) -> QTextCharFormat:
        """创建Ghost Text专用格式"""
        ghost_format = QTextCharFormat()
        # 根据主题设置适当的颜色
        if hasattr(self.text_editor, 'palette'):
            base_color = self.text_editor.palette().text().color()
            if base_color.lightness() > 128:  # 浅色主题
                ghost_color = QColor(100, 100, 100, 200)  # 深灰色，更不透明
            else:  # 深色主题
                ghost_color = QColor(160, 160, 160, 220)  # 亮灰色，更不透明
        else:
            ghost_color = QColor(128, 128, 128, 200)  # 默认颜色
        ghost_format.setForeground(ghost_color)
        # 修复PyQt6 API兼容性 - 设置自定义属性标记Ghost Text
        try:
            # PyQt6中使用QTextFormat.UserProperty而不是QTextCharFormat.Property.UserProperty
            from PyQt6.QtGui import QTextFormat
            ghost_format.setProperty(QTextFormat.UserProperty + 1, "ghost_text")
        except (AttributeError, ImportError):
            try:
                # 备用方案1: 使用硬编码的UserProperty值
                ghost_format.setProperty(0x100000 + 1, "ghost_text")
            except Exception:
                # 备用方案2: 跳过属性设置，不影响核心功能
                logger.warning("无法设置Ghost Text自定义属性，但不影响功能")
        return ghost_format
        
    def render_ghost_text_at_position(self, painter: QPainter, text: str, 
                                    position: QRectF, font: QFont):
        """在指定位置渲染Ghost Text"""
        if not text or not position.isValid():
            return
            
        # 创建临时布局
        temp_layout = QTextLayout(text, font)
        temp_layout.beginLayout()
        
        try:
            line = temp_layout.createLine()
            if line.isValid():
                line.setPosition(QPointF(0, 0))  # 设置相对位置
                
                temp_layout.endLayout()
                
                # 设置绘制颜色 - 根据主题调整，使用半透明效果
                if hasattr(self.text_editor, 'palette'):
                    base_color = self.text_editor.palette().text().color()
                    if base_color.lightness() > 128:  # 浅色主题
                        ghost_color = QColor(80, 80, 80, 150)  # 更深的颜色，半透明
                    else:  # 深色主题
                        ghost_color = QColor(180, 180, 180, 150)  # 更亮的颜色，半透明
                else:
                    ghost_color = QColor(128, 128, 128, 150)  # 默认半透明
                painter.setPen(ghost_color)
                
                # 渲染文本到指定位置 - 确保位置参数类型正确
                top_left = position.topLeft()
                if isinstance(top_left, QPointF):
                    temp_layout.draw(painter, top_left)
                else:
                    # 安全回退：创建新的QPointF
                    safe_position = QPointF(float(position.x()), float(position.y()))
                    temp_layout.draw(painter, safe_position)
            else:
                temp_layout.endLayout()
        except Exception as e:
            # 确保布局被正确结束
            temp_layout.endLayout()
            logger.error(f"Ghost text rendering failed: {e}")
        
    def render_ghost_text_simple(self, painter: QPainter, text: str, 
                                position: QRectF, font: QFont):
        """简化的 Ghost Text 渲染方法 - 使用 drawText 直接渲染"""
        if not text:
            logger.debug("Ghost text渲染跳过: 文本为空")
            return
        if not position.isValid():
            logger.warning(f"Ghost text渲染跳过: position无效 - x={position.x()}, y={position.y()}, w={position.width()}, h={position.height()}")
            return
            
        try:
            # 保存画笔状态
            painter.save()
            
            # 设置字体
            painter.setFont(font)
            
            # 设置绘制颜色 - 根据主题调整
            if hasattr(self.text_editor, 'palette'):
                base_color = self.text_editor.palette().text().color()
                if base_color.lightness() > 128:  # 浅色主题
                    ghost_color = QColor(80, 80, 80, 180)  # 深灰色，适度透明
                else:  # 深色主题
                    ghost_color = QColor(180, 180, 180, 180)  # 亮灰色，适度透明
            else:
                ghost_color = QColor(128, 128, 128, 180)  # 默认灰色
            painter.setPen(ghost_color)
            
            # 计算绘制位置
            draw_x = position.x()
            if position.y() == 0:
                # 使用字体高度作为备用位置
                font_metrics = painter.fontMetrics()
                draw_y = font_metrics.height() * 0.85
            else:
                draw_y = position.y() + position.height() * 0.85
            
            # 绘制Ghost Text
            painter.drawText(QPointF(draw_x, draw_y), text)
            logger.debug(f"✅ Ghost text已绘制: '{text[:20]}...' at ({draw_x:.1f}, {draw_y:.1f})")
            
            # 恢复画笔状态
            painter.restore()
            
        except Exception as e:
            logger.error(f"Ghost text渲染失败: {e}")
            if painter:
                painter.restore()
        
    def wrap_text_to_width(self, text: str, available_width: float, 
                          font: QFont) -> List[str]:
        """智能文本换行，复用编辑器的换行逻辑"""
        if not text or available_width <= 0:
            return []
            
        try:
            font_metrics = QFontMetrics(font)
            lines = []
            remaining_text = text
            max_lines = 10  # 防止无限循环
            line_count = 0
            
            while remaining_text and line_count < max_lines:
                # 计算当前行能容纳的字符数
                line_text = ""
                for i, char in enumerate(remaining_text):
                    test_text = line_text + char
                    try:
                        text_width = font_metrics.horizontalAdvance(test_text)
                    except Exception:
                        # 如果字体度量失败，使用估算值
                        text_width = len(test_text) * 10
                        
                    if text_width > available_width:
                        break
                    line_text = test_text
                    
                if not line_text and remaining_text:
                    # 如果连一个字符都放不下，至少放一个
                    line_text = remaining_text[0]
                    
                lines.append(line_text)
                remaining_text = remaining_text[len(line_text):]
                line_count += 1
                
            return lines
        except Exception as e:
            logger.error(f"Text wrapping failed: {e}")
            return [text[:50] + "..." if len(text) > 50 else text]  # 兜底方案


class SmartUpdateManager:
    """智能更新管理器 - 优化性能"""
    
    def __init__(self, parent=None):
        self._update_timer = QTimer(parent)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._perform_update)
        self._pending_updates = set()
        self._update_callback = None
        
    def schedule_update(self, block_number: int, callback=None):
        """调度更新特定块"""
        self._pending_updates.add(block_number)
        if callback:
            self._update_callback = callback
        self._update_timer.start(16)  # 60fps更新频率
        
    def _perform_update(self):
        """执行批量更新"""
        if self._pending_updates and self._update_callback:
            self._update_callback(self._pending_updates.copy())
        self._pending_updates.clear()


class GhostTextEventHandler:
    """Ghost Text事件处理器"""
    
    def __init__(self, ghost_text_manager):
        self.manager = ghost_text_manager
        
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """处理按键事件
        
        Returns:
            bool: True if event was handled, False otherwise
        """
        if not self.manager.has_active_ghost_text():
            return False
            
        # Tab键：接受Ghost Text
        if event.key() == Qt.Key.Key_Tab:
            return self.manager.accept_ghost_text()
            
        # ESC键：拒绝Ghost Text  
        elif event.key() == Qt.Key.Key_Escape:
            return self.manager.reject_ghost_text()
            
        # 字符输入：清理Ghost Text
        elif event.text() and event.text().isprintable():
            self.manager.clear_ghost_text()
            return False
            
        return False


class DeepIntegratedGhostText(QObject):
    """深度集成QTextDocument的Ghost Text管理器
    
    核心特性：
    - 基于QTextBlockUserData的非破坏性存储
    - 使用Qt原生布局引擎的精确位置计算
    - 智能渲染确保预览与实际效果一致
    """
    
    # 信号
    ghost_text_changed = pyqtSignal(str)
    ghost_text_accepted = pyqtSignal(str)
    ghost_text_rejected = pyqtSignal()
    
    # 兼容性信号 - 用于替换 ModernGhostTextCompletion
    completionAccepted = pyqtSignal(str)
    completionRejected = pyqtSignal()
    
    def __init__(self, text_editor):
        super().__init__(text_editor)
        
        self.text_editor = text_editor
        self.document = text_editor.document()
        
        # 核心组件
        self.layout_calculator = PreciseLayoutCalculator(self.document)
        self.rendering_engine = SmartRenderingEngine(text_editor)
        self.update_manager = SmartUpdateManager(self)  # 传递parent避免内存泄漏
        self.event_handler = GhostTextEventHandler(self)
        
        # 状态管理
        self._ghost_blocks: Set[int] = set()  # 包含Ghost Text的块号
        self._active_ghost_data: Dict[int, GhostTextUserData] = {}
        self._current_ghost_position = -1
        self._current_ghost_text = ""
        
        # 精简日志控制 - 避免重复日志刷屏
        self._last_render_state = None
        self._render_fail_count = 0
        self._last_success_log = 0
        
        # 连接更新回调
        self.update_manager._update_callback = self._perform_block_updates
        
        # 连接编辑器事件
        self._connect_editor_events()
        
    def _connect_editor_events(self):
        """连接编辑器事件"""
        # 监听文档变化
        self.document.contentsChanged.connect(self._on_document_changed)
        
        # 监听光标变化
        self.text_editor.cursorPositionChanged.connect(self._on_cursor_changed)
        
    def show_ghost_text(self, text: str, position: int) -> bool:
        """显示Ghost Text
        
        Args:
            text: Ghost Text内容
            position: 插入位置
            
        Returns:
            bool: 是否成功显示
        """
        if not text or position < 0:
            return False
            
        # 清理现有的Ghost Text
        self.clear_ghost_text()
        
        # 找到目标块
        cursor = QTextCursor(self.document)
        cursor.setPosition(position)
        target_block = cursor.block()
        
        if not target_block.isValid():
            return False
            
        # 创建或获取用户数据
        user_data = target_block.userData()
        if not user_data or not isinstance(user_data, GhostTextUserData):
            user_data = GhostTextUserData()
            target_block.setUserData(user_data)
            
        # 设置Ghost Text数据
        user_data.ghost_text = text
        user_data.ghost_position = position - target_block.position()
        user_data.is_active = True
        user_data.timestamp = time.time()
        
        # 更新内部状态
        block_number = target_block.blockNumber()
        self._ghost_blocks.add(block_number)
        self._active_ghost_data[block_number] = user_data
        self._current_ghost_position = position
        self._current_ghost_text = text
        
        # 调度更新
        self.update_manager.schedule_update(block_number)
        
        # 发射信号
        self.ghost_text_changed.emit(text)
        
        # 🔧 修复：使用更安全的重绘方式，避免触发textChanged循环
        # 只更新viewport，不强制处理事件
        self.text_editor.viewport().update()
        
        # 移除可能触发额外事件的操作
        # self.text_editor.update()  # 注释掉，避免触发编辑器的额外更新
        # QApplication.processEvents()  # 注释掉，避免立即处理可能导致循环的事件
        
        logger.info(f"👻 显示Ghost Text: '{text[:25]}...' (pos={position}, block={block_number})")
        return True
        
    def clear_ghost_text(self):
        """清理所有Ghost Text"""
        if not self._ghost_blocks:
            return
            
        # 清理所有Ghost Text块
        for block_number in self._ghost_blocks:
            block = self.document.findBlockByNumber(block_number)
            if block.isValid():
                user_data = block.userData()
                if user_data and isinstance(user_data, GhostTextUserData):
                    user_data.is_active = False
                    
        # 清理内部状态
        self._ghost_blocks.clear()
        self._active_ghost_data.clear()
        self._current_ghost_position = -1
        self._current_ghost_text = ""
        
        # 触发重绘
        self.text_editor.viewport().update()
        
        logger.debug("清理所有Ghost Text")
        
    def accept_ghost_text(self) -> bool:
        """接受当前的Ghost Text"""
        if not self.has_active_ghost_text():
            return False
            
        ghost_text = self._current_ghost_text
        position = self._current_ghost_position
        
        # 清理Ghost Text状态
        self.clear_ghost_text()
        
        # 插入实际文本
        try:
            cursor = self.text_editor.textCursor()
        except Exception:
            cursor = QTextCursor(self.document)

        cursor.setPosition(position)
        cursor.insertText(ghost_text)
        try:
            self.text_editor.setTextCursor(cursor)
        except Exception:
            pass
        
        # 发射信号
        self.ghost_text_accepted.emit(ghost_text)
        self.completionAccepted.emit(ghost_text)  # 兼容性信号
        
        logger.debug(f"接受Ghost Text: '{ghost_text}'")
        return True
        
    def reject_ghost_text(self) -> bool:
        """拒绝当前的Ghost Text"""
        if not self.has_active_ghost_text():
            return False
            
        self.clear_ghost_text()
        self.ghost_text_rejected.emit()
        self.completionRejected.emit()  # 兼容性信号
        
        logger.debug("拒绝Ghost Text")
        return True
        
    def has_active_ghost_text(self) -> bool:
        """检查是否有活跃的Ghost Text"""
        result = bool(self._ghost_blocks and self._current_ghost_text)
        if not result and (self._ghost_blocks or self._current_ghost_text):
            logger.debug(f"Ghost text check: blocks={self._ghost_blocks}, text='{self._current_ghost_text[:20] if self._current_ghost_text else 'None'}'")
        return result
        
    def render_ghost_text(self, painter: QPainter):
        """在paintEvent中渲染Ghost Text"""
        # 检查基本条件
        has_active = self.has_active_ghost_text()
        painter_valid = painter and painter.isActive()
        
        # 状态检查：只在状态变化时记录
        current_state = (has_active, painter_valid, len(self._ghost_blocks))
        if current_state != self._last_render_state:
            logger.debug(f"👁️ Ghost渲染状态: active={has_active}, painter_ok={painter_valid}, blocks={len(self._ghost_blocks)}")
            self._last_render_state = current_state
        
        if not has_active or not painter_valid:
            return
            
        try:
            # 渲染所有活跃的Ghost Text块
            rendered_count = 0
            for block_number in self._ghost_blocks:
                try:
                    block = self.document.findBlockByNumber(block_number)
                    if not block.isValid():
                        continue
                        
                    user_data = block.userData()
                    if not user_data or not isinstance(user_data, GhostTextUserData) or not user_data.is_active:
                        continue
                        
                    self._render_block_ghost_text(painter, block, user_data)
                    rendered_count += 1
                except Exception as e:
                    logger.error(f"Block {block_number} render failed: {e}")
                    continue
                    
            # 只在首次成功或失败时记录
            import time
            now = time.time()
            if rendered_count > 0:
                if now - self._last_success_log > 5:  # 5秒内最多记录一次成功
                    logger.info(f"✅ Ghost Text渲染: {rendered_count}个块")
                    self._last_success_log = now
                self._render_fail_count = 0
            elif self._render_fail_count == 0:
                logger.warning("⚠️ Ghost Text渲染失败: 无有效块")
                self._render_fail_count = 1
        except Exception as e:
            logger.error(f"Ghost text rendering failed: {e}")
            
    def _render_block_ghost_text(self, painter: QPainter, block: QTextBlock, 
                                user_data: GhostTextUserData):
        """渲染单个块的Ghost Text"""
        # 计算精确位置
        position_is_viewport = False
        position = self.layout_calculator.calculate_ghost_position(
            block, user_data.ghost_position
        )
        
        # 如果位置计算失败或y为0，使用 cursorRect 作为主要方法
        if position.isNull() or position.y() == 0:
            cursor = QTextCursor(self.document)
            cursor.setPosition(block.position() + user_data.ghost_position)
            cursor_rect = self.text_editor.cursorRect(cursor)
            if not cursor_rect.isNull():
                # 使用 cursorRect 的位置，更可靠
                position = QRectF(cursor_rect)
                position_is_viewport = True
                logger.debug(f"Using cursorRect for block {block.blockNumber()}: {position}")
            else:
                logger.warning(f"Both methods failed for block {block.blockNumber()}")
                return
        
        # 如果y坐标为0且不是第一个块，尝试使用备用方法
        if position.y() == 0 and block.blockNumber() > 0:
            # 使用QTextCursor获取更准确的位置
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + user_data.ghost_position)
            cursor_rect = self.text_editor.cursorRect(cursor)
            if not cursor_rect.isNull() and cursor_rect.y() > 0:
                position = QRectF(cursor_rect)
                position_is_viewport = True
                logger.debug(f"Using cursor rect as fallback for block {block.blockNumber()}: {position}")
        
        # 转换到viewport坐标 - 使用translated方法正确转换
        content_offset = self.text_editor.contentOffset()
        viewport_position = position if position_is_viewport else position.translated(content_offset)
        viewport_x = viewport_position.x()
        viewport_y = viewport_position.y()
        
        logger.debug(f"坐标转换: doc_pos=({position.x()}, {position.y()}), content_offset=({content_offset.x()}, {content_offset.y()}), viewport=({viewport_x}, {viewport_y})")
        
        # 检查是否需要换行
        available_width = max(0.0, float(self.text_editor.viewport().width()) - float(viewport_x) - 2.0)
        
        # 智能换行
        lines = self.rendering_engine.wrap_text_to_width(
            user_data.ghost_text, available_width, self.text_editor.font()
        )
        
        # 渲染每一行
        try:
            line_height = float(position.height())
            # 使用viewport坐标
            pos_x = float(viewport_x)
            pos_y = float(viewport_y)
            
            for i, line_text in enumerate(lines):
                # 计算文本实际宽度以确保QRectF有效
                font_metrics = self.text_editor.fontMetrics()
                text_width = font_metrics.horizontalAdvance(line_text)
                
                line_position = QRectF(
                    pos_x,
                    pos_y + i * line_height,
                    max(1.0, float(text_width)),  # 确保宽度至少为1
                    line_height
                )
                
                # 使用简化的渲染方法以提高可靠性
                self.rendering_engine.render_ghost_text_simple(
                    painter, line_text, line_position, self.text_editor.font()
                )
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning(f"渲染Ghost Text时出错: {e}")
            return
            
    def _perform_block_updates(self, _block_numbers: Set[int]):
        """执行块更新"""
        # 触发编辑器重绘相关区域
        self.text_editor.viewport().update()
        
    def _on_document_changed(self):
        """文档内容变化时的处理"""
        # 清理过期的Ghost Text
        self._cleanup_expired_ghost_text()
        
    def _on_cursor_changed(self):
        """光标位置变化时的处理"""
        # 如果光标移动到Ghost Text区域外，清理Ghost Text
        cursor = self.text_editor.textCursor()
        current_position = cursor.position()
        
        if self.has_active_ghost_text():
            # 检查光标是否仍在Ghost Text区域
            ghost_start = self._current_ghost_position
            ghost_end = ghost_start + len(self._current_ghost_text)
            
            if current_position < ghost_start or current_position > ghost_end:
                # 光标移动到Ghost Text区域外，清理
                self.clear_ghost_text()
                
    def _cleanup_expired_ghost_text(self):
        """清理过期的Ghost Text数据"""
        current_time = time.time()
        expired_blocks = []
        
        for block_number, user_data in self._active_ghost_data.items():
            if current_time - user_data.timestamp > 30:  # 30秒过期
                expired_blocks.append(block_number)
                
        for block_number in expired_blocks:
            if block_number in self._ghost_blocks:
                self._ghost_blocks.discard(block_number)
            if block_number in self._active_ghost_data:
                del self._active_ghost_data[block_number]
                
        if expired_blocks:
            logger.debug(f"清理过期Ghost Text块: {expired_blocks}")
    
    # ============ 兼容性API - 用于替换 ModernGhostTextCompletion ============
    
    def show_completion(self, suggestion: str) -> bool:
        """显示补全建议 - 兼容API
        
        Args:
            suggestion: 补全建议文本
            
        Returns:
            bool: 是否成功显示
        """
        if not suggestion or not suggestion.strip():
            return False
            
        cursor = self.text_editor.textCursor()
        cursor_pos = cursor.position()
        
        # 计算增量补全
        current_text = self.text_editor.toPlainText()
        completion = self._calculate_incremental_completion(current_text, cursor_pos, suggestion.strip())
        
        if not completion:
            return False
            
        return self.show_ghost_text(completion, cursor_pos)
    
    def hide_completion(self):
        """隐藏补全 - 兼容API"""
        self.clear_ghost_text()
    
    def is_showing(self) -> bool:
        """是否正在显示补全 - 兼容API"""
        return self.has_active_ghost_text()
    
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """处理按键事件 - 兼容API
        
        Args:
            event: 按键事件
            
        Returns:
            bool: 如果事件被处理则返回True
        """
        return self.event_handler.handle_key_press(event)
    
    def _calculate_incremental_completion(self, current_text: str, cursor_pos: int, suggestion: str) -> str:
        """计算增量补全 - 从 ModernGhostTextCompletion 迁移
        
        Args:
            current_text: 当前文本
            cursor_pos: 光标位置
            suggestion: AI建议的完整文本
            
        Returns:
            str: 增量补全文本（只包含需要插入的部分）
        """
        if cursor_pos > len(current_text):
            return ""
            
        # 获取光标前的文本
        text_before_cursor = current_text[:cursor_pos]
        
        # 寻找公共前缀
        common_prefix_len = 0
        for i, char in enumerate(text_before_cursor):
            if i < len(suggestion) and char == suggestion[i]:
                common_prefix_len = i + 1
            else:
                break
                
        # 如果建议文本从光标位置开始，返回完整建议
        if common_prefix_len == cursor_pos:
            return suggestion[cursor_pos:]
            
        # 否则返回建议中除去公共前缀的部分
        if common_prefix_len > 0:
            return suggestion[common_prefix_len:]
            
        return suggestion

def integrate_with_text_editor(text_editor) -> DeepIntegratedGhostText:
    """将深度集成Ghost Text系统集成到文本编辑器
    
    Args:
        text_editor: IntelligentTextEditor实例
        
    Returns:
        DeepIntegratedGhostText: 集成后的Ghost Text管理器
    """
    ghost_text_manager = DeepIntegratedGhostText(text_editor)
    
    # 不再替换paintEvent方法 - IntelligentTextEditor类自身的paintEvent会处理Ghost Text渲染
    # 这样避免了方法替换被类定义覆盖的问题
    logger.info(f"🔧 深度集成Ghost Text已激活（通过类paintEvent集成）")
    
    # 保存原始的keyPressEvent方法
    original_key_press_event = text_editor.keyPressEvent
    
    def enhanced_key_press_event(event: QKeyEvent):
        """增强的keyPressEvent，集成Ghost Text事件处理"""
        # 先让Ghost Text处理事件
        if ghost_text_manager.event_handler.handle_key_press(event):
            return  # 事件已被处理
            
        # 否则调用原始的事件处理
        original_key_press_event(event)
        
    # 替换keyPressEvent方法
    text_editor.keyPressEvent = enhanced_key_press_event
    
    logger.info("深度集成Ghost Text系统已集成到文本编辑器")
    
    # 确保返回的对象有效
    if ghost_text_manager is None:
        logger.error("ghost_text_manager is None before return!")
        raise ValueError("Failed to create DeepIntegratedGhostText instance")
    
    if not hasattr(ghost_text_manager, 'show_completion'):
        logger.error(f"ghost_text_manager missing show_completion method! Type: {type(ghost_text_manager)}")
        raise AttributeError("DeepIntegratedGhostText instance missing show_completion method")
    
    return ghost_text_manager
