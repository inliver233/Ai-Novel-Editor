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




class MainWindowMenusMixin:
    """MainWindow mixin."""
    def _init_menu_bar(self):
        self._menu_bar = MenuBar(config=self._config, parent=self)
        self.setMenuBar(self._menu_bar)
        self._menu_bar.actionTriggered.connect(self._on_menu_action)
        
        # 初始状态下禁用项目相关操作
        self._menu_bar.get_action('save_project').setEnabled(False)
        self._menu_bar.get_action('save_project_as').setEnabled(False)
        self._menu_bar.get_action('close_project').setEnabled(False)
    def _init_tool_bar(self):
        self._toolbar_manager = ToolBarManager(self)
        main_toolbar = self._toolbar_manager.get_toolbar("main")
        if main_toolbar and hasattr(main_toolbar, 'actionTriggered'):
            main_toolbar.actionTriggered.connect(self._on_toolbar_action)
        
        # 连接AI工具栏信号
        ai_toolbar = self._toolbar_manager.get_toolbar("ai")
        if ai_toolbar and hasattr(ai_toolbar, 'aiActionTriggered'):
            ai_toolbar.aiActionTriggered.connect(self._on_ai_toolbar_action)
        
        # 默认显示AI工具栏
        if ai_toolbar:
            ai_toolbar.show()
    def _init_status_bar(self):
        self._status_bar = EnhancedStatusBar(self)
        self.setStatusBar(self._status_bar)
        if self._ai_manager:
            self._status_bar.aiConfigRequested.connect(lambda: self._ai_manager.show_config_dialog(self))
        if hasattr(self, "_task_manager") and self._task_manager:
            self._task_manager.taskFailed.connect(self._on_task_failed)
    @pyqtSlot(str, dict)
    def _on_menu_action(self, action_id: str, data: dict):
        logger.debug(f"Menu action: {action_id}")

        if action_id == "open_recent":
            project_path = data.get("project_path") or data.get("project")
            if project_path:
                self._open_recent_project(str(project_path))
            else:
                logger.warning("open_recent triggered without project_path")
            return

        if action_id == "clear_recent":
            try:
                self._config.clear_recent_projects()
                self._menu_bar.refresh_recent_projects_menu()
            except Exception:
                logger.exception("Failed to clear recent projects")
            return
        
        # 将所有action映射到一个地方处理
        actions = {
            # Project Controller Actions
            "new_project": self._project_controller.on_create_project,
            "open_project": self._project_controller.on_open_project,
            "save_project": self._project_controller.on_save_project,
            "save_project_as": self._project_controller.on_save_project_as,
            "close_project": self._project_controller.on_close_project,

            # Document Actions
            "save_document": self._on_save,
            "import_text": self._show_import_dialog,
            "import_project": lambda: self._show_import_dialog(project_mode=True),
            "export_text": self._show_export_dialog,
            "export_pdf": lambda: self._show_export_dialog(pdf_mode=True),
            "import_export_codex": self._show_import_export_codex_dialog,

            # Editor Actions
            "undo": lambda: self._editor_panel.get_current_editor().undo() if self._editor_panel.get_current_editor() else None,
            "redo": lambda: self._editor_panel.get_current_editor().redo() if self._editor_panel.get_current_editor() else None,
            "cut": lambda: self._editor_panel.get_current_editor().cut() if self._editor_panel.get_current_editor() else None,
            "copy": lambda: self._editor_panel.get_current_editor().copy() if self._editor_panel.get_current_editor() else None,
            "paste": lambda: self._editor_panel.get_current_editor().paste() if self._editor_panel.get_current_editor() else None,
            "select_all": lambda: self._editor_panel.get_current_editor().selectAll() if self._editor_panel.get_current_editor() else None,

            # Find/Replace
            "find": self._show_find_replace,
            "simple_find": self._show_simple_find,
            "replace": lambda: self._show_find_replace(replace_mode=True),

            # View Actions
            "fullscreen": self._toggle_fullscreen,
            "toggle_project_panel": self._toggle_left_panel,
            "toggle_outline_panel": self._toggle_outline_panel,
            "toggle_codex_panel": self._toggle_codex_panel,

            # Focus Mode Actions
            "focus_typewriter": self._toggle_typewriter_mode,
            "focus_mode": self._toggle_focus_mode,
            "focus_distraction_free": self._toggle_distraction_free_mode,

            # Theme Actions
            "light_theme": lambda: self._set_theme(ThemeType.LIGHT),
            "dark_theme": lambda: self._set_theme(ThemeType.DARK),

            # AI Actions
            "ai_complete": self._trigger_ai_completion,
            "ai_continue": self._trigger_ai_continue,
            "concept_detect": self._trigger_concept_detection,
            "completion_mode": self._cycle_completion_mode,
            "ai_control_panel": self._show_ai_control_panel,
            "ai_prompt_settings": self._show_ai_prompt_settings,
            "index_manager": self._show_index_manager,
            "batch_index": self._show_batch_index_dialog,

            # Dialogs
            "preferences": self._show_preferences,
            "project_settings": self._show_project_settings,
            "ai_config": self._show_ai_config_dialog,
            "word_count": self._show_word_count,
            "about": self._show_about,
            "auto_replace_settings": self._show_auto_replace_settings,
            "concept_manager": self._show_concept_manager,
            "codex_manager": self._show_codex_manager,
            "restore_project": self._restore_project_from_backup,
            
            # Toolbar Actions
            "toggle_ai_toolbar": self._toggle_ai_toolbar,
            "toggle_main_toolbar": self._toggle_main_toolbar,
            "toggle_format_toolbar": self._toggle_format_toolbar,
            
            # Application Exit
            "exit": self.close,
        }

        if action_id in actions:
            actions[action_id]()
        else:
            logger.warning(f"Unhandled menu action: {action_id}")

    def _open_recent_project(self, project_dir: str) -> None:
        """Open a project directory from Recent Projects."""
        parent_widget = self

        try:
            project_path = Path(project_dir)
        except Exception:
            QMessageBox.critical(parent_widget, "错误", f"无效项目路径:\n{project_dir}")
            return

        db_file = project_path / "project.db"
        if not db_file.exists():
            QMessageBox.critical(parent_widget, "错误", f"项目数据库 'project.db' 未找到于:\n{project_path}")
            return

        if self._project_manager.open_project(str(project_path)):
            project = self._project_manager.get_current_project()
            if project:
                QMessageBox.information(parent_widget, "成功", f"项目 '{project.name}' 打开成功！")
                self._project_controller.project_opened.emit(project.project_path)
                self._project_controller.project_structure_changed.emit()
        else:
            QMessageBox.critical(parent_widget, "错误", "项目打开失败！")
    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()
    def _toggle_left_panel(self):
        # 切换可见性
        new_visible = not self._left_panel.isVisible()
        self._left_panel.setVisible(new_visible)
        
        # 如果要显示面板，确保它有合理的宽度
        if new_visible:
            sizes = self._main_splitter.sizes()
            if sizes[0] == 0:
                # 从中间面板借一些宽度给左面板，使用更紧凑的尺寸
                total_width = sum(sizes)
                sizes[0] = 130  # 进一步缩小左面板宽度
                sizes[1] = max(400, sizes[1] - 130)  # 确保中间面板至少400像素
                self._main_splitter.setSizes(sizes)
        
        # 更新菜单状态
        if hasattr(self, '_menu_bar'):
            action = self._menu_bar.get_action('toggle_project_panel')
            if action:
                action.setChecked(self._left_panel.isVisible())
    def _toggle_outline_panel(self):
        """切换大纲面板显示"""
        # 右侧面板就是大纲面板，直接切换可见性
        self._toggle_right_panel()
        
        # 统一同步菜单状态
        self._sync_panel_menu_states()
    def _toggle_codex_panel(self):
        """切换Codex面板显示"""
        # 如果右侧面板不可见，先显示右侧面板
        if not self._right_panel.isVisible():
            self._toggle_right_panel()
        
        # 如果有Codex面板，切换到Codex标签页
        if hasattr(self._right_panel, 'widget') and self._codex_panel:
            # 获取标签容器
            tab_widget = self._right_panel
            if isinstance(tab_widget, QTabWidget):
                # 查找Codex标签页的索引
                for i in range(tab_widget.count()):
                    if tab_widget.tabText(i) == "Codex":
                        tab_widget.setCurrentIndex(i)
                        break
        
        # 统一同步菜单状态
        self._sync_panel_menu_states()
    def _toggle_right_panel(self):
        """切换右侧面板可见性"""
        # 切换可见性
        new_visible = not self._right_panel.isVisible()
        self._right_panel.setVisible(new_visible)
        
        # 如果要显示面板，确保它有合理的宽度
        if new_visible:
            sizes = self._main_splitter.sizes()
            if sizes[2] == 0:
                # 从中间面板借一些宽度给右面板，使用更紧凑的尺寸
                total_width = sum(sizes)
                sizes[2] = 160  # 更紧凑的右面板宽度
                sizes[1] = max(400, sizes[1] - 160)  # 确保中间面板至少400像素
                self._main_splitter.setSizes(sizes)
    def _toggle_ai_toolbar(self):
        """切换AI工具栏显示/隐藏"""
        ai_toolbar = self._toolbar_manager.get_toolbar("ai")
        if ai_toolbar:
            ai_toolbar.setVisible(not ai_toolbar.isVisible())
            logger.info(f"AI工具栏已{'显示' if ai_toolbar.isVisible() else '隐藏'}")
    def _toggle_main_toolbar(self):
        """切换主工具栏显示/隐藏"""
        main_toolbar = self._toolbar_manager.get_toolbar("main")
        if main_toolbar:
            main_toolbar.setVisible(not main_toolbar.isVisible())
            logger.info(f"主工具栏已{'显示' if main_toolbar.isVisible() else '隐藏'}")
    def _toggle_format_toolbar(self):
        """切换格式工具栏显示/隐藏"""
        format_toolbar = self._toolbar_manager.get_toolbar("format")
        if format_toolbar:
            format_toolbar.setVisible(not format_toolbar.isVisible())
            logger.info(f"格式工具栏已{'显示' if format_toolbar.isVisible() else '隐藏'}")
    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
        # 查找相关快捷键已在菜单栏定义，避免重复
        # QShortcut(QKeySequence("Ctrl+F"), self, self._show_simple_find)  # 简单查找
        # QShortcut(QKeySequence("Ctrl+Shift+H"), self, self._show_find_replace)  # 高级查找
        # QShortcut(QKeySequence("Ctrl+H"), self, lambda: self._show_find_replace(True))  # 替换
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)
        
        # 专注模式快捷键
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, self._toggle_typewriter_mode)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._toggle_focus_mode)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self, self._toggle_distraction_free_mode)
        QShortcut(QKeySequence("Escape"), self, self._exit_focus_mode)
        
        # AI功能快捷键
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._quick_cycle_context_mode)
        QShortcut(QKeySequence("Ctrl+Shift+M"), self, self._quick_cycle_completion_mode)
        QShortcut(QKeySequence("Ctrl+Alt+A"), self, self._trigger_ai_completion)
    def _sync_theme_menu_state(self, theme_type: ThemeType):
        """同步主题菜单状态"""
        if not hasattr(self, '_menu_bar'):
            return
            
        try:
            # 获取主题动作
            light_action = self._menu_bar.get_action('light_theme')
            dark_action = self._menu_bar.get_action('dark_theme')
            
            if light_action and dark_action:
                # 根据当前主题设置选中状态
                if theme_type == ThemeType.LIGHT:
                    light_action.setChecked(True)
                    dark_action.setChecked(False)
                    logger.debug("主题菜单已同步: 浅色主题选中")
                elif theme_type == ThemeType.DARK:
                    light_action.setChecked(False)
                    dark_action.setChecked(True)
                    logger.debug("主题菜单已同步: 深色主题选中")
            else:
                logger.warning("无法找到主题菜单动作")
                
        except Exception as e:
            logger.error(f"同步主题菜单状态失败: {e}")
    def _sync_panel_menu_states(self):
        """同步所有面板的菜单状态"""
        if not hasattr(self, '_menu_bar'):
            return
            
        # 同步项目面板状态
        if hasattr(self, '_left_panel'):
            action = self._menu_bar.get_action('toggle_project_panel')
            if action:
                action.setChecked(self._left_panel.isVisible())
        
        # 同步右侧面板状态（大纲面板）
        if hasattr(self, '_right_panel'):
            is_right_visible = self._right_panel.isVisible()
            
            # 大纲面板状态（右侧面板就是大纲面板）
            outline_action = self._menu_bar.get_action('toggle_outline_panel')
            if outline_action:
                outline_action.setChecked(is_right_visible)
                logger.debug(f"大纲面板菜单状态: 右侧可见={is_right_visible}, 菜单勾选={is_right_visible}")
        
        
        # 同步工具栏状态
        if hasattr(self, '_toolbar_manager'):
            # 主工具栏
            main_toolbar = self._toolbar_manager.get_toolbar("main")
            if main_toolbar:
                action = self._menu_bar.get_action('toggle_main_toolbar')
                if action:
                    action.setChecked(main_toolbar.isVisible())
            
            # AI工具栏
            ai_toolbar = self._toolbar_manager.get_toolbar("ai")
            if ai_toolbar:
                action = self._menu_bar.get_action('toggle_ai_toolbar')
                if action:
                    action.setChecked(ai_toolbar.isVisible())
            
            # 格式工具栏
            format_toolbar = self._toolbar_manager.get_toolbar("format")
            if format_toolbar:
                action = self._menu_bar.get_action('toggle_format_toolbar')
                if action:
                    action.setChecked(format_toolbar.isVisible())

