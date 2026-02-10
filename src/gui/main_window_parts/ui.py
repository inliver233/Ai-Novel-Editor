from __future__ import annotations

"""
主窗口实现
基于novelWriter的GuiMain设计，实现三栏布局的主界面
"""

import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter,
    QMessageBox, QApplication, QDialog, QFileDialog,
    QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QKeySequence, QCloseEvent, QShortcut
from core.config import Config
from core.shared import Shared
from core.project import ProjectManager
from gui.panels.project_panel import ProjectPanel
from gui.panels.outline_panel import OutlinePanel
from gui.panels.codex_panel import CodexPanel
from gui.editor.editor_panel import EditorPanel
from gui.editor.focus_mode import FocusMode
from gui.menus import MenuBar, ToolBarManager
from gui.status import EnhancedStatusBar
from gui.themes import ThemeManager, ThemeType
from gui.controllers.project_controller import ProjectController
from gui.dialogs import (
    SettingsDialog, AboutDialog, ProjectSettingsDialog,
    WordCountDialog, ShortcutsDialog,
    AutoReplaceDialog, ImportDialog, ExportDialog
)
from gui.dialogs.import_export_dialog import ImportExportDialog
from gui.dialogs.simple_find_dialog import SimpleFindDialog
from gui.dialogs.enhanced_find_dialog import EnhancedFindDialog
from gui.services.task_manager import TaskManager
from gui.services.index_scheduler import IndexScheduler


logger = logging.getLogger(__name__)




class MainWindowUIMixin:
    """MainWindow mixin."""
    def _setup_ai_control_panel(self):
        if not self._ai_manager or not self._ai_control_panel:
            return
        self._ai_control_panel.completionEnabledChanged.connect(self._ai_manager.set_completion_enabled)
        self._ai_control_panel.autoTriggerEnabledChanged.connect(self._ai_manager.set_auto_trigger_enabled)
        self._ai_control_panel.punctuationAssistChanged.connect(self._ai_manager.set_punctuation_assist_enabled)
        self._ai_control_panel.triggerDelayChanged.connect(self._ai_manager.set_trigger_delay)
        self._ai_control_panel.completionModeChanged.connect(self._ai_manager.set_completion_mode)
        logger.info("AI控制面板已设置")
    def _calculate_word_count(self, text: str) -> int:
        if not text:
            return 0
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        numbers = len(re.findall(r'\b\d+\b', text))
        return chinese_chars + english_words + numbers
    def _init_ui(self):
        self.setWindowTitle("AI Novel Editor")
        self.setMinimumSize(800, 600)
        
        # 设置应用程序图标
        self._set_window_icon()
        
        self._setup_shortcuts()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self._main_layout = QHBoxLayout(central_widget)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
    def _set_window_icon(self):
        """设置窗口图标"""
        try:
            # 优先使用ico格式，fallback到png格式
            icon_dir = Path(__file__).parent.parent.parent / "icon"
            ico_path = icon_dir / "图标.ico"
            png_path = icon_dir / "图标.png"
            
            from PyQt6.QtGui import QIcon
            
            if ico_path.exists():
                icon = QIcon(str(ico_path))
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    logger.info(f"成功加载ICO图标: {ico_path}")
                    return
            
            if png_path.exists():
                icon = QIcon(str(png_path))
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    logger.info(f"成功加载PNG图标: {png_path}")
                    return
                    
            logger.warning("未找到可用的应用程序图标")
            
        except Exception as e:
            logger.error(f"设置窗口图标失败: {e}")
    def _init_layout(self):
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_layout.addWidget(self._main_splitter)
        self._left_panel = self._create_left_panel()
        self._main_splitter.addWidget(self._left_panel)
        self._center_panel = self._create_center_panel()
        self._main_splitter.addWidget(self._center_panel)
        self._right_panel = self._create_right_panel()
        self._main_splitter.addWidget(self._right_panel)
        self._main_splitter.setCollapsible(0, True)
        self._main_splitter.setCollapsible(1, False)
        self._main_splitter.setCollapsible(2, True)
        
        # 恢复布局状态（包括面板可见性）
        self._restore_layout_state()
        
        # 确保右侧面板默认隐藏（在布局恢复之后强制设置）
        if not hasattr(self, '_layout_restored_right_panel'):
            self._right_panel.setVisible(False)
        self._main_splitter.splitterMoved.connect(self._save_layout_state)
    def _create_left_panel(self) -> QWidget:
        panel = ProjectPanel(self._config, self._shared, self._project_manager, self)
        panel.documentSelected.connect(self._on_document_selected)
        return panel
    def _create_center_panel(self) -> QWidget:
        # 直接创建并返回编辑器面板
        self._editor_panel = EditorPanel(self._config, self._shared, self)
        try:
            self._editor_panel.set_project_manager(self._project_manager)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to bind ProjectManager to EditorPanel: %s", exc)
        self._editor_panel.documentModified.connect(self._on_document_modified)
        self._editor_panel.documentSaved.connect(self._on_document_saved)
        if self._ai_manager:
            current_editor = self._editor_panel.get_current_editor()
            if current_editor:
                self._ai_manager.set_editor(current_editor)
                logger.info("AI管理器已设置当前编辑器")
        return self._editor_panel
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板 - 大纲面板，如果Codex可用则创建标签容器"""
        logger.info(f"开始创建右侧面板...")
        logger.info(f"Codex系统可用性检查: codex_manager={self._codex_manager is not None}, reference_detector={self._reference_detector is not None}")
        
        # 检查是否有Codex系统
        if (self._codex_manager is not None and self._reference_detector is not None):
            logger.info("检测到Codex系统可用，创建标签容器...")
            # 有Codex系统时创建标签容器
            from PyQt6.QtWidgets import QTabWidget
            tab_widget = QTabWidget()
            tab_widget.setTabPosition(QTabWidget.TabPosition.South)
            
            # 创建大纲面板
            logger.info("创建大纲面板...")
            self._outline_panel = OutlinePanel(self._config, self._shared, self._project_manager, self)
            self._outline_panel.documentSelected.connect(self._on_document_selected)
            tab_widget.addTab(self._outline_panel, "大纲")
            logger.info("大纲面板创建完成")
            
            # 创建Codex面板
            logger.info("开始创建Codex面板...")
            try:
                from gui.panels.codex_panel import CodexPanel
                logger.info("CodexPanel类导入成功")
                self._codex_panel = CodexPanel(
                    self._config, 
                    self._shared, 
                    self._codex_manager, 
                    self._reference_detector, 
                    self
                )
                logger.info("CodexPanel实例创建成功")
                
                # 连接Codex面板信号
                self._codex_panel.entrySelected.connect(self._on_codex_entry_selected)
                self._codex_panel.entryCreated.connect(self._on_codex_entry_created)
                self._codex_panel.entryUpdated.connect(self._on_codex_entry_updated)
                logger.info("Codex面板信号连接完成")
                
                tab_widget.addTab(self._codex_panel, "📚 Codex")
                logger.info("Codex面板标签页添加成功")
                logger.info("Codex面板已添加到右侧标签容器")
                return tab_widget
                
            except Exception as e:
                logger.error(f"创建Codex面板失败: {e}")
                logger.error(f"异常详细信息: {str(e)}")
                import traceback
                logger.error(f"错误堆栈:\n{traceback.format_exc()}")
                # 如果Codex面板创建失败，仍然返回带大纲面板的标签容器
                self._codex_panel = None
                logger.info("Codex面板创建失败，返回仅包含大纲面板的标签容器")
                return tab_widget
        else:
            # 没有Codex系统时，直接返回大纲面板（保持原有行为）
            self._outline_panel = OutlinePanel(self._config, self._shared, self._project_manager, self)
            self._outline_panel.documentSelected.connect(self._on_document_selected)
            self._codex_panel = None
            logger.info("仅创建大纲面板（Codex系统不可用）")
            return self._outline_panel
    def _init_focus_mode(self):
        """初始化专注模式管理器"""
        try:
            # 获取当前编辑器
            current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
            if current_editor:
                self._focus_mode = FocusMode(self, current_editor)
                # 连接模式变化信号到状态栏显示
                self._focus_mode.modeChanged.connect(self._on_focus_mode_changed)
                logger.info("专注模式管理器已初始化")
            else:
                self._focus_mode = None
                logger.warning("无法获取编辑器，专注模式初始化失败")
        except Exception as e:
            logger.error(f"专注模式初始化失败: {e}")
            self._focus_mode = None
    @pyqtSlot(str, str)
    def _on_focus_mode_changed(self, mode_id: str, mode_name: str):
        """专注模式变化时更新状态栏和菜单状态"""
        if hasattr(self, '_status_bar'):
            self._status_bar.show_message(f"专注模式: {mode_name}", 3000)
        
        # 更新菜单项的选中状态
        if hasattr(self, '_menu_bar'):
            # 清除所有专注模式菜单的选中状态
            focus_actions = {
                'focus_typewriter': 'typewriter',
                'focus_mode': 'focus', 
                'focus_distraction_free': 'distraction_free'
            }
            
            for action_id, mode in focus_actions.items():
                action = self._menu_bar.get_action(action_id)
                if action:
                    # 仅选中当前激活的模式
                    action.setChecked(mode == mode_id)
    def _apply_theme(self):
        try:
            ui_config = self._config.get_section("ui") or {}
            theme_name = ui_config.get("theme", "dark")
            theme_type = ThemeType[theme_name.upper()]
            self._theme_manager.set_theme(theme_type)
            
            # 同步主题菜单状态
            self._sync_theme_menu_state(theme_type)
            
            logger.info(f"Applied {theme_name} theme")
        except (KeyError, Exception) as e:
            logger.error(f"Failed to apply theme: {e}")
            self._theme_manager.set_theme(ThemeType.DARK)
            # 即使失败也要同步菜单状态
            self._sync_theme_menu_state(ThemeType.DARK)
    def update_ai_status_display(self, status: str, status_type: str = "success"):
        """更新AI状态显示"""
        ai_toolbar = self._toolbar_manager.get_toolbar("ai")
        if ai_toolbar and hasattr(ai_toolbar, 'update_ai_status'):
            # 映射状态类型到颜色
            color_map = {
                "success": "#155724",
                "warning": "#856404", 
                "error": "#721c24",
                "info": "#0c5460"
            }
            color = color_map.get(status_type, "#155724")
            ai_toolbar.update_ai_status(status, color)
    def _set_theme(self, theme_type: ThemeType):
        self._theme_manager.set_theme(theme_type)
        ui_config = self._config.get_section("ui")
        ui_config["theme"] = theme_type.value
        self._config.set_section("ui", ui_config)
        
        # 同步主题菜单状态
        self._sync_theme_menu_state(theme_type)
        
        logger.info(f"Theme changed to: {theme_type.value}")
    def _update_ai_manager_editor(self):
        """更新AI管理器的编辑器引用（增强版本）"""
        if self._ai_manager and hasattr(self, '_editor_panel'):
            current_editor = self._editor_panel.get_current_editor()
            if current_editor:
                # 设置编辑器引用
                self._ai_manager.set_editor(current_editor)
                
                # 验证连接是否成功
                if hasattr(self._ai_manager, 'diagnose_ai_completion_issues'):
                    diagnosis = self._ai_manager.diagnose_ai_completion_issues()
                    if diagnosis['issues']:
                        logger.warning(f"AI completion issues detected: {diagnosis['issues']}")
                    else:
                        logger.info("AI manager editor reference updated successfully")
                else:
                    logger.debug("AI管理器编辑器引用已更新")
            else:
                logger.warning("No current editor available for AI manager")
        else:
            if not self._ai_manager:
                logger.warning("AI manager not available for editor update")
            if not hasattr(self, '_editor_panel'):
                logger.warning("Editor panel not available for AI manager update")
    def _update_focus_mode_editor(self):
        """更新专注模式的编辑器引用"""
        if self._focus_mode and hasattr(self, '_editor_panel'):
            current_editor = self._editor_panel.get_current_editor()
            if current_editor:
                # 更新专注模式管理器的编辑器引用
                self._focus_mode.editor = current_editor
                # 更新打字机模式的编辑器引用
                self._focus_mode.typewriter_manager.editor = current_editor
                logger.debug("专注模式编辑器引用已更新")
    def _toggle_typewriter_mode(self):
        """切换打字机模式"""
        if not self._focus_mode:
            logger.warning("专注模式管理器未初始化")
            return
        self._focus_mode.toggle_typewriter_mode()
    def _toggle_focus_mode(self):
        """切换专注模式"""
        if not self._focus_mode:
            logger.warning("专注模式管理器未初始化")
            return
        self._focus_mode.toggle_focus_mode()
    def _toggle_distraction_free_mode(self):
        """切换无干扰模式"""
        if not self._focus_mode:
            logger.warning("专注模式管理器未初始化")
            return
        self._focus_mode.toggle_distraction_free_mode()
    def _exit_focus_mode(self):
        """退出专注模式（Esc键）"""
        # 🔧 修复：优先处理Ghost Text的Esc键事件
        try:
            if hasattr(self, '_editor_panel') and self._editor_panel:
                text_editor = self._editor_panel.get_current_editor()
                if text_editor and hasattr(text_editor, '_ghost_completion') and text_editor._ghost_completion:
                    if text_editor._ghost_completion.has_active_ghost_text():
                        # 如果有活跃的Ghost Text，优先处理
                        logger.debug("🔄 全局Esc快捷键：检测到活跃Ghost Text，优先处理")
                        text_editor._ghost_completion.reject_ghost_text()
                        return
                    else:
                        logger.debug("🔄 全局Esc快捷键：没有活跃Ghost Text，继续处理专注模式")
                else:
                    logger.debug("🔄 全局Esc快捷键：Ghost Text系统不可用")
        except Exception as e:
            logger.error(f"🔄 全局Esc快捷键：处理Ghost Text时发生异常: {e}")
            # 异常时继续处理专注模式
        
        if not self._focus_mode:
            return
        # 只在非普通模式时才退出到普通模式
        if self._focus_mode.get_current_mode() != 'normal':
            self._focus_mode.set_mode('normal')

