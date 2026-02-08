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


from gui.main_window_parts.ui import MainWindowUIMixin
from gui.main_window_parts.menus import MainWindowMenusMixin
from gui.main_window_parts.dialogs import MainWindowDialogsMixin
from gui.main_window_parts.integrations import MainWindowIntegrationsMixin
from gui.main_window_parts.state import MainWindowStateMixin

logger = logging.getLogger(__name__)


class MainWindow(
    MainWindowUIMixin,
    MainWindowMenusMixin,
    MainWindowDialogsMixin,
    MainWindowIntegrationsMixin,
    MainWindowStateMixin,
    QMainWindow,
):
    """主窗口类"""

    def __init__(self, config: Config, shared: Shared, project_manager: ProjectManager,
                 codex_manager=None, reference_detector=None, prompt_function_registry=None):
        super().__init__()

        self._config = config
        self._shared = shared
        self._project_manager = project_manager
        
        # Codex系统组件（可选）
        self._codex_manager = codex_manager
        self._reference_detector = reference_detector
        self._prompt_function_registry = prompt_function_registry
        self._project_controller = ProjectController(
            project_manager=self._project_manager,
            config=self._config,
            parent=self
        )

        # 初始化简化的AI管理器
        self._ai_manager = None
        self._ai_control_panel = None
        
        try:
            logger.info("初始化增强AI管理器...")
            from gui.ai.enhanced_ai_manager import EnhancedAIManager
            
            # 创建增强的AI管理器
            self._ai_manager = EnhancedAIManager(self._config, self._shared, self)
            logger.info("增强AI管理器已初始化")
            
            # 初始化AI控制面板（如果可用）
            try:
                from gui.ai.ai_completion_control import AICompletionControlPanel
                self._ai_control_panel = AICompletionControlPanel(self)
                logger.info("AI控制面板已初始化")
            except ImportError:
                logger.info("AI控制面板不可用，跳过初始化")
                self._ai_control_panel = None
            
            # 注册AI管理器到共享对象
            self._shared.ai_manager = self._ai_manager
            logger.info("AI管理器已注册到共享对象")
            
            # 注册其他组件到共享对象（如果可用）
            if self._codex_manager:
                self._shared.codex_manager = self._codex_manager
                logger.info("Codex管理器已注册到共享对象")
            if self._reference_detector:
                self._shared.reference_detector = self._reference_detector
                logger.info("引用检测器已注册到共享对象")
            if self._prompt_function_registry:
                self._shared.prompt_function_registry = self._prompt_function_registry
                logger.info("提示词函数注册表已注册到共享对象")
                
        except Exception as e:
            logger.error(f"AI管理器初始化失败: {e}")
            self._ai_manager = None
            self._ai_control_panel = None

        # TaskManager/IndexScheduler 初始化（统一取消/去重/节流/错误上报）
        self._task_manager = TaskManager(self)
        self._index_scheduler = IndexScheduler(self._task_manager, self)
        self._shared.task_manager = self._task_manager
        self._shared.index_scheduler = self._index_scheduler
        self._index_scheduler.bind_shared(self._shared)
        self._index_scheduler.bind_project_manager(self._project_manager)
        if self._ai_manager:
            try:
                self._ai_manager.set_task_manager(self._task_manager)
                self._index_scheduler.bind_ai_manager(self._ai_manager)
            except Exception as e:
                logger.warning(f"TaskManager绑定AI管理器失败: {e}")

        self._theme_manager = ThemeManager(self)
        self._find_replace_dialog = None
        self._word_count_dialog = None
        self._shortcuts_dialog = None
        self._outline_panel = None  # 大纲面板实例

        self._statistics_update_timer = QTimer()
        self._statistics_update_timer.setSingleShot(True)
        self._statistics_update_timer.timeout.connect(self._update_statistics_delayed)
        self._pending_text = ""

        self._init_ui()
        self._init_layout()
        
        # 在编辑器面板创建后集成Codex和AI系统
        self._integrate_codex_with_ai()
        
        self._init_focus_mode()
        self._init_menu_bar()
        self._init_tool_bar()
        self._init_status_bar()
        self._init_signals()
        self._setup_ai_control_panel()
        self._restore_window_state()
        self._apply_theme()
        
        # 同步菜单状态以反映面板的实际可见性
        # 使用QTimer延迟执行，确保所有初始化完成后再同步
        QTimer.singleShot(100, self._sync_panel_menu_states)
        QTimer.singleShot(110, lambda: self._sync_theme_menu_state(self._theme_manager.get_current_theme()))

        logger.info("Main window initialized")
