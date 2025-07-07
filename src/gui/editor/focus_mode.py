"""
专注写作模式管理器
提供打字机模式、专注模式、无干扰模式等功能
"""

import logging
from typing import Dict, Any
from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QMainWindow
from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtGui import QTextCursor

logger = logging.getLogger(__name__)


class TypewriterScrollManager(QObject):
    """打字机模式 - 保持光标在屏幕中央"""
    
    def __init__(self, editor: QPlainTextEdit):
        super().__init__()
        self.editor = editor
        self.enabled = False
        self.center_position = 0.5  # 光标位置百分比（0.5为中央）
        self.smooth_scroll = True
        self.animation_duration = 200  # 毫秒
        
        # 延迟处理，避免频繁滚动
        self.scroll_timer = QTimer()
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self._do_center_cursor)
        
    def enable_typewriter_mode(self):
        """启用打字机模式"""
        if self.enabled:
            return
            
        self.enabled = True
        logger.info("打字机模式已启用")
        
        # 连接光标位置变化信号
        self.editor.cursorPositionChanged.connect(self._on_cursor_changed)
        
        # 立即居中一次
        self._center_cursor()
    
    def disable_typewriter_mode(self):
        """禁用打字机模式"""
        if not self.enabled:
            return
            
        self.enabled = False
        logger.info("打字机模式已禁用")
        
        # 断开信号连接
        try:
            self.editor.cursorPositionChanged.disconnect(self._on_cursor_changed)
        except TypeError:
            pass  # 信号可能已经断开
        
        # 停止滚动定时器
        self.scroll_timer.stop()
    
    def _on_cursor_changed(self):
        """光标位置变化时延迟处理"""
        if not self.enabled:
            return
        
        # 延迟50ms处理，避免频繁滚动
        self.scroll_timer.start(50)
    
    def _do_center_cursor(self):
        """实际执行光标居中"""
        if not self.enabled:
            return
        
        self._center_cursor()
    
    def _center_cursor(self):
        """将光标滚动到屏幕中央"""
        if not self.enabled:
            return
        
        try:
            cursor = self.editor.textCursor()
            cursor_rect = self.editor.cursorRect(cursor)
            viewport_height = self.editor.viewport().height()
            
            # 计算目标Y位置（屏幕中央）
            target_y = viewport_height * self.center_position
            
            # 计算需要滚动的距离
            scroll_offset = cursor_rect.y() - target_y
            
            # 获取滚动条
            scrollbar = self.editor.verticalScrollBar()
            current_value = scrollbar.value()
            target_value = current_value + int(scroll_offset)
            
            # 确保目标值在有效范围内
            target_value = max(scrollbar.minimum(), min(scrollbar.maximum(), target_value))
            
            if self.smooth_scroll:
                self._animate_scroll(scrollbar, target_value)
            else:
                scrollbar.setValue(target_value)
                
        except Exception as e:
            logger.warning(f"打字机模式光标居中失败: {e}")
    
    def _animate_scroll(self, scrollbar, target_value):
        """平滑滚动动画"""
        if not hasattr(self, '_scroll_animation'):
            self._scroll_animation = QPropertyAnimation(scrollbar, b"value")
            self._scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self._scroll_animation.stop()
        self._scroll_animation.setStartValue(scrollbar.value())
        self._scroll_animation.setEndValue(target_value)
        self._scroll_animation.setDuration(self.animation_duration)
        self._scroll_animation.start()


class FocusMode(QObject):
    """专注写作模式管理器"""
    
    # 模式定义
    MODES = {
        'normal': '普通模式',
        'focus': '专注模式',
        'typewriter': '打字机模式', 
        'distraction_free': '无干扰模式',
        'zen': '禅意模式'
    }
    
    # 信号
    modeChanged = pyqtSignal(str, str)  # 模式ID，模式名称
    
    def __init__(self, main_window: QMainWindow, editor: QPlainTextEdit):
        super().__init__()
        self.main_window = main_window
        self.editor = editor
        self.current_mode = 'normal'
        
        # 打字机模式管理器
        self.typewriter_manager = TypewriterScrollManager(editor)
        
        # 保存原始状态
        self.original_state = {}
        
        logger.info("专注模式管理器已初始化")
        
    def get_current_mode(self) -> str:
        """获取当前模式"""
        return self.current_mode
    
    def get_available_modes(self) -> Dict[str, str]:
        """获取可用模式列表"""
        return self.MODES.copy()
    
    def set_mode(self, mode: str):
        """切换专注模式"""
        if mode not in self.MODES:
            logger.warning(f"未知的专注模式: {mode}")
            return False
        
        if mode == self.current_mode:
            logger.debug(f"已经是{self.MODES[mode]}模式")
            return True
        
        old_mode = self.current_mode
        
        try:
            # 先退出当前模式
            if old_mode != 'normal':
                self._exit_mode(old_mode)
            
            # 进入新模式
            self._enter_mode(mode)
            
            self.current_mode = mode
            logger.info(f"专注模式已切换: {self.MODES[old_mode]} -> {self.MODES[mode]}")
            
            # 发出模式变化信号
            self.modeChanged.emit(mode, self.MODES[mode])
            
            return True
            
        except Exception as e:
            logger.error(f"切换专注模式失败: {e}")
            # 尝试恢复到普通模式
            self._enter_mode('normal')
            self.current_mode = 'normal'
            return False
    
    def toggle_typewriter_mode(self):
        """切换打字机模式"""
        if self.current_mode == 'typewriter':
            self.set_mode('normal')
        else:
            self.set_mode('typewriter')
    
    def toggle_focus_mode(self):
        """切换专注模式"""
        if self.current_mode == 'focus':
            self.set_mode('normal')
        else:
            self.set_mode('focus')
    
    def toggle_distraction_free_mode(self):
        """切换无干扰模式"""
        if self.current_mode == 'distraction_free':
            self.set_mode('normal')
        else:
            self.set_mode('distraction_free')
    
    def _enter_mode(self, mode: str):
        """进入指定模式"""
        if mode == 'normal':
            self._enter_normal_mode()
        elif mode == 'typewriter':
            self._enter_typewriter_mode()
        elif mode == 'focus':
            self._enter_focus_mode()
        elif mode == 'distraction_free':
            self._enter_distraction_free_mode()
        elif mode == 'zen':
            self._enter_zen_mode()
    
    def _exit_mode(self, mode: str):
        """退出指定模式"""
        if mode == 'typewriter':
            self.typewriter_manager.disable_typewriter_mode()
        elif mode in ['focus', 'distraction_free', 'zen']:
            self._restore_ui_state()
    
    def _enter_normal_mode(self):
        """普通模式：恢复所有UI元素"""
        self._restore_ui_state()
        self.typewriter_manager.disable_typewriter_mode()
    
    def _enter_typewriter_mode(self):
        """打字机模式：光标居中 + 隐藏侧边栏"""
        self._save_ui_state()
        self.typewriter_manager.enable_typewriter_mode()
        self._hide_side_panels()
    
    def _enter_focus_mode(self):
        """专注模式：隐藏工具栏 + 增大编辑区"""
        self._save_ui_state()
        self._hide_toolbars()
        self._hide_side_panels()
    
    def _enter_distraction_free_mode(self):
        """无干扰模式：全屏 + 隐藏所有UI元素"""
        self._save_ui_state()
        self.main_window.showFullScreen()
        self._hide_all_ui_elements()
    
    def _enter_zen_mode(self):
        """禅意模式：打字机 + 无干扰 + 特殊主题"""
        self._save_ui_state()
        self.typewriter_manager.enable_typewriter_mode()
        self.main_window.showFullScreen()
        self._hide_all_ui_elements()
        # TODO: 应用禅意主题
    
    def _save_ui_state(self):
        """保存当前UI状态"""
        if not self.original_state:  # 只在第一次进入专注模式时保存
            try:
                # 保存窗口状态
                self.original_state['window_state'] = self.main_window.windowState()
                self.original_state['is_fullscreen'] = self.main_window.isFullScreen()
                
                # 保存面板可见性
                if hasattr(self.main_window, '_left_panel'):
                    self.original_state['left_panel_visible'] = self.main_window._left_panel.isVisible()
                if hasattr(self.main_window, '_right_panel'):
                    self.original_state['right_panel_visible'] = self.main_window._right_panel.isVisible()
                
                # 保存工具栏可见性
                if hasattr(self.main_window, 'menuBar'):
                    self.original_state['menu_bar_visible'] = self.main_window.menuBar().isVisible()
                if hasattr(self.main_window, 'statusBar'):
                    self.original_state['status_bar_visible'] = self.main_window.statusBar().isVisible()
                
                logger.debug("UI状态已保存")
                
            except Exception as e:
                logger.warning(f"保存UI状态失败: {e}")
    
    def _restore_ui_state(self):
        """恢复原始UI状态"""
        if not self.original_state:
            return
        
        try:
            # 恢复窗口状态
            if self.original_state.get('is_fullscreen', False):
                self.main_window.showFullScreen()
            else:
                self.main_window.showNormal()
            
            # 恢复面板可见性
            if hasattr(self.main_window, '_left_panel'):
                visible = self.original_state.get('left_panel_visible', True)
                self.main_window._left_panel.setVisible(visible)
                # 如果面板应该可见，确保有合理的宽度
                if visible and hasattr(self.main_window, '_main_splitter'):
                    sizes = self.main_window._main_splitter.sizes()
                    if sizes[0] == 0:
                        sizes[0] = 200
                        sizes[1] = max(400, sizes[1] - 200)
                        self.main_window._main_splitter.setSizes(sizes)
            
            if hasattr(self.main_window, '_right_panel'):
                visible = self.original_state.get('right_panel_visible', True)
                self.main_window._right_panel.setVisible(visible)
                # 如果面板应该可见，确保有合理的宽度
                if visible and hasattr(self.main_window, '_main_splitter'):
                    sizes = self.main_window._main_splitter.sizes()
                    if sizes[2] == 0:
                        sizes[2] = 200
                        sizes[1] = max(400, sizes[1] - 200)
                        self.main_window._main_splitter.setSizes(sizes)
            
            # 恢复工具栏可见性
            if hasattr(self.main_window, 'menuBar'):
                visible = self.original_state.get('menu_bar_visible', True)
                self.main_window.menuBar().setVisible(visible)
            
            if hasattr(self.main_window, 'statusBar'):
                visible = self.original_state.get('status_bar_visible', True)
                self.main_window.statusBar().setVisible(visible)
            
            logger.debug("UI状态已恢复")
            
            # 清空状态记录
            self.original_state.clear()
            
            # 同步菜单状态
            if hasattr(self.main_window, '_sync_panel_menu_states'):
                self.main_window._sync_panel_menu_states()
            
        except Exception as e:
            logger.warning(f"恢复UI状态失败: {e}")
    
    def _hide_side_panels(self):
        """隐藏侧边栏"""
        try:
            if hasattr(self.main_window, '_left_panel'):
                self.main_window._left_panel.setVisible(False)
            if hasattr(self.main_window, '_right_panel'):
                self.main_window._right_panel.setVisible(False)
        except Exception as e:
            logger.warning(f"隐藏侧边栏失败: {e}")
    
    def _hide_toolbars(self):
        """隐藏工具栏"""
        try:
            if hasattr(self.main_window, 'menuBar'):
                self.main_window.menuBar().setVisible(False)
        except Exception as e:
            logger.warning(f"隐藏工具栏失败: {e}")
    
    def _hide_all_ui_elements(self):
        """隐藏所有UI元素"""
        self._hide_side_panels()
        self._hide_toolbars()
        try:
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().setVisible(False)
        except Exception as e:
            logger.warning(f"隐藏状态栏失败: {e}")