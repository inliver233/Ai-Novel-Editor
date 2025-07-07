from __future__ import annotations

"""
主窗口实现
基于novelWriter的GuiMain设计，实现三栏布局的主界面
"""

import logging
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QMenuBar, QToolBar, QStatusBar,
    QMessageBox, QApplication, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QKeySequence, QCloseEvent, QShortcut
from core.config import Config
from core.shared import Shared
from core.project import ProjectManager, DocumentType
from core.concepts import ConceptManager
from gui.panels.project_panel import ProjectPanel
from gui.panels.concept_panel import ConceptPanel
from gui.panels.outline_panel import OutlinePanel
from gui.editor.editor_panel import EditorPanel
from gui.editor.focus_mode import FocusMode
from gui.viewer.document_viewer import DocumentViewer
from gui.menus import MenuBar, ToolBarManager
from gui.ai import AIManager
from gui.status import EnhancedStatusBar
from gui.themes import ThemeManager, ThemeType
from gui.controllers.project_controller import ProjectController
from gui.dialogs import (
    SettingsDialog, AboutDialog, ProjectSettingsDialog,
    FindReplaceDialog, WordCountDialog, ShortcutsDialog,
    AutoReplaceDialog, ImportDialog, ExportDialog
)
from gui.dialogs.simple_find_dialog import SimpleFindDialog
from gui.dialogs.enhanced_find_dialog import EnhancedFindDialog


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self, config: Config, shared: Shared, concept_manager: ConceptManager, project_manager: ProjectManager):
        super().__init__()

        self._config = config
        self._shared = shared
        self._concept_manager = concept_manager
        self._project_manager = project_manager
        self._project_controller = ProjectController(
            project_manager=self._project_manager,
            config=self._config,
            concept_manager=self._concept_manager,
            parent=self
        )

        # 初始化AI管理器
        self._ai_manager = None
        self._ai_control_panel = None
        
        try:
            # 优先尝试使用增强型AI管理器（支持提示词工程系统）
            try:
                logger.info("开始初始化增强型AI管理器...")
                
                # 测试核心模块导入
                try:
                    from core.prompt_engineering import EnhancedPromptManager
                    from core.builtin_templates import register_builtin_loader
                    from core.context_variables import IntelligentContextAnalyzer
                    logger.info("核心提示词模块导入成功")
                except ImportError as import_error:
                    logger.error(f"核心提示词模块导入失败: {import_error}")
                    raise import_error
                
                # 导入增强型AI管理器
                from gui.ai.enhanced_ai_manager import EnhancedAIManager
                logger.info("EnhancedAIManager类导入成功")
                
                # 获取RAG服务和向量存储（如果可用）
                rag_service = getattr(self._shared, 'rag_service', None)
                vector_store = getattr(self._shared, 'vector_store', None)
                logger.info(f"RAG服务: {'可用' if rag_service else '不可用'}, 向量存储: {'可用' if vector_store else '不可用'}")
                
                # 创建增强型AI管理器，传递所有必要参数
                self._ai_manager = EnhancedAIManager(
                    config=self._config,
                    shared=self._shared,
                    concept_manager=self._concept_manager,
                    rag_service=rag_service,
                    vector_store=vector_store,
                    parent=self
                )
                
                # 验证提示词系统是否正确初始化
                if hasattr(self._ai_manager, 'prompt_manager') and self._ai_manager.prompt_manager:
                    logger.info("增强型AI管理器已初始化，提示词系统正常")
                else:
                    logger.warning("增强型AI管理器初始化成功，但提示词系统未正确初始化")
                
                # 验证关键方法是否存在
                if hasattr(self._ai_manager, 'open_template_manager'):
                    logger.info("提示词管理方法验证成功")
                else:
                    logger.error("提示词管理方法不存在")
                
            except Exception as enhanced_error:
                import traceback
                logger.error(f"增强型AI管理器初始化失败，完整错误信息: {enhanced_error}")
                logger.error(f"错误堆栈: {traceback.format_exc()}")
                logger.warning("回退到基础AI管理器")
                # 回退到基础AI管理器
                from gui.ai.ai_manager import AIManager
                self._ai_manager = AIManager(self._config, self)
                logger.info("基础AI管理器已初始化")
            
            # 初始化AI控制面板（在AI管理器初始化成功后）
            if self._ai_manager:
                try:
                    from gui.ai.ai_completion_control import AICompletionControlPanel
                    self._ai_control_panel = AICompletionControlPanel(self)
                    logger.info("AI控制面板已初始化")
                except Exception as panel_error:
                    logger.warning(f"AI控制面板初始化失败: {panel_error}")
                    self._ai_control_panel = None
                
                # 注册AI管理器到共享对象，以便项目管理器可以访问
                self._shared.ai_manager = self._ai_manager
                logger.info("AI管理器已注册到共享对象")
            
        except Exception as e:
            logger.error(f"AI管理器初始化完全失败: {e}")
            self._ai_manager = None
            self._ai_control_panel = None

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

        logger.info("Main window initialized")

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
        center_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._editor_panel = EditorPanel(self._config, self._shared, self._concept_manager, self)
        center_splitter.addWidget(self._editor_panel)
        self._document_viewer = DocumentViewer(self._config, self._shared, self._project_manager, self._theme_manager, self)
        center_splitter.addWidget(self._document_viewer)
        self._document_viewer.setVisible(False)
        center_splitter.setSizes([600, 200])
        center_splitter.setCollapsible(0, False)
        center_splitter.setCollapsible(1, True)
        self._editor_panel.documentModified.connect(self._on_document_modified)
        self._editor_panel.documentSaved.connect(self._on_document_saved)
        self._editor_panel.conceptsDetected.connect(self._on_concepts_detected)
        if self._ai_manager:
            current_editor = self._editor_panel.get_current_editor()
            if current_editor:
                self._ai_manager.set_editor(current_editor)
                logger.info("AI管理器已设置当前编辑器")
        self._document_viewer.documentChanged.connect(self._on_viewer_document_changed)
        self._document_viewer.linkClicked.connect(self._on_viewer_link_clicked)
        return center_splitter

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板容器，支持概念面板和大纲面板切换"""
        from PyQt6.QtWidgets import QStackedWidget
        
        # 创建堆叠控件来容纳多个面板
        self._right_stack = QStackedWidget()
        
        # 创建概念面板
        self._concept_panel = ConceptPanel(self._config, self._shared, self._concept_manager, self)
        self._concept_panel.conceptSelected.connect(self._on_concept_selected)
        self._right_stack.addWidget(self._concept_panel)
        
        # 创建大纲面板
        self._outline_panel = OutlinePanel(self._config, self._shared, self._project_manager, self)
        self._outline_panel.documentSelected.connect(self._on_document_selected)
        self._right_stack.addWidget(self._outline_panel)
        
        # 设置默认显示概念面板（但整个右侧面板默认隐藏）
        # 这样当用户首次打开面板时，显示的是概念面板
        self._right_stack.setCurrentWidget(self._concept_panel)
        
        return self._right_stack

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

    def _init_menu_bar(self):
        self._menu_bar = MenuBar(self)
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

    def _init_signals(self):
        self._shared.projectChanged.connect(self._on_project_changed)
        self._shared.themeChanged.connect(self._on_theme_changed)
        self._theme_manager.themeChanged.connect(self._on_theme_manager_changed)
        
        # 连接ProjectController的信号
        self._connect_controller_signals()
        
        # 连接共享对象的文档保存信号到自动索引
        if self._shared and hasattr(self._shared, 'documentSaved'):
            self._shared.documentSaved.connect(self._on_document_saved_auto_index)

        if hasattr(self._editor_panel, 'documentSaved'):
            self._editor_panel.documentSaved.connect(self._on_document_saved)
        if hasattr(self._editor_panel, 'completionRequested'):
            self._editor_panel.completionRequested.connect(self._on_completion_requested)
        if hasattr(self._editor_panel, 'documentModified'):
            self._editor_panel.documentModified.connect(self._on_document_modified)
        if hasattr(self._editor_panel, 'textStatisticsChanged'):
            self._editor_panel.textStatisticsChanged.connect(self._on_text_statistics_changed)
        if hasattr(self._editor_panel, 'cursorPositionChanged'):
            self._editor_panel.cursorPositionChanged.connect(self._on_cursor_position_changed)
            
        # 连接AI管理器信号到编辑器
        self._connect_ai_manager_signals()

    def _connect_ai_manager_signals(self):
        """连接AI管理器信号到编辑器智能补全管理器"""
        if not self._ai_manager:
            logger.warning("AI管理器不可用，跳过信号连接")
            return
            
        try:
            # 获取当前编辑器
            current_editor = self._editor_panel.get_current_editor()
            if not current_editor:
                logger.warning("当前编辑器不可用，跳过AI信号连接")
                return
                
            # 获取智能补全管理器
            smart_completion = getattr(current_editor, '_smart_completion', None)
            if not smart_completion:
                logger.warning("智能补全管理器不可用，跳过AI信号连接")
                return
                
            # 连接AI管理器的completionReceived信号到智能补全管理器的show_ai_completion方法
            if hasattr(self._ai_manager, 'completionReceived') and hasattr(smart_completion, 'show_ai_completion'):
                self._ai_manager.completionReceived.connect(self._on_ai_completion_received)
                logger.info("AI管理器completionReceived信号已连接到主窗口处理器")
            else:
                logger.warning("AI管理器或智能补全管理器缺少必要的信号/方法")
                
        except Exception as e:
            logger.error(f"连接AI管理器信号失败: {e}")
            
    def _on_ai_completion_received(self, response: str, metadata: dict):
        """处理AI补全响应，转发给当前编辑器的智能补全管理器"""
        try:
            current_editor = self._editor_panel.get_current_editor()
            if not current_editor:
                logger.warning("当前编辑器不可用，无法显示AI补全")
                return
                
            smart_completion = getattr(current_editor, '_smart_completion', None)
            if not smart_completion:
                logger.warning("智能补全管理器不可用，无法显示AI补全")
                return
                
            if hasattr(smart_completion, 'show_ai_completion'):
                smart_completion.show_ai_completion(response)
                logger.debug(f"AI补全响应已转发给智能补全管理器: {response[:50]}...")
            else:
                logger.warning("智能补全管理器缺少show_ai_completion方法")
                
        except Exception as e:
            logger.error(f"处理AI补全响应失败: {e}")

    def _restore_window_state(self):
        try:
            ui_config = self._config.get_section("ui")
            screen = QApplication.primaryScreen()
            screen_geometry = screen.availableGeometry() if screen else self.rect()
            max_width, max_height = screen_geometry.width(), screen_geometry.height()
            width = max(800, min(ui_config.get("window_width", 1200), max_width))
            height = max(600, min(ui_config.get("window_height", 800), max_height))
            self.resize(width, height)
            if ui_config.get("window_maximized", False):
                self.showMaximized()
            else:
                if screen:
                    x = (screen_geometry.width() - width) // 2 + screen_geometry.left()
                    y = (screen_geometry.height() - height) // 2 + screen_geometry.top()
                    self.move(x, y)
            # 面板可见性在_restore_layout_state()中统一处理
            logger.debug(f"Window state restored: {width}x{height}")
        except Exception as e:
            logger.error(f"Failed to restore window state: {e}")
            self.resize(1200, 800)

    def _save_window_state(self):
        ui_config = self._config.get_section("ui")
        if not self.isMaximized():
            ui_config["window_width"] = self.width()
            ui_config["window_height"] = self.height()
        ui_config["window_maximized"] = self.isMaximized()
        ui_config["show_left_panel"] = self._left_panel.isVisible()
        ui_config["show_right_panel"] = self._right_panel.isVisible()
        self._config.set_section("ui", ui_config)

    def _apply_theme(self):
        try:
            ui_config = self._config.get_section("ui") or {}
            theme_name = ui_config.get("theme", "dark")
            theme_type = ThemeType[theme_name.upper()]
            self._theme_manager.set_theme(theme_type)
            logger.info(f"Applied {theme_name} theme")
        except (KeyError, Exception) as e:
            logger.error(f"Failed to apply theme: {e}")
            self._theme_manager.set_theme(ThemeType.DARK)


    @pyqtSlot()
    def _on_save(self):
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor:
            QMessageBox.warning(self, "警告", "没有打开的文档可以保存")
            return
        document_id = current_editor.get_current_document_id()
        if not document_id:
            QMessageBox.warning(self, "警告", "无法确定当前文档")
            return
        content = current_editor.toPlainText()
        if self._project_manager.update_document(document_id, content=content):
            self._status_bar.set_document_status("已保存", "#1a7f37")
            self._status_bar.show_message("文档保存成功", 2000)
            current_editor.document().setModified(False)
            if hasattr(self._editor_panel, 'documentModified'):
                self._editor_panel.documentModified.emit(document_id, False)
            logger.info(f"Document saved: {document_id}")
            
            # 自动更新RAG索引（如果启用）
            if self._ai_manager and hasattr(self._ai_manager, 'index_document'):
                try:
                    self._ai_manager.index_document(document_id, content)
                    logger.info(f"Document indexed for RAG: {document_id}")
                except Exception as e:
                    logger.error(f"Failed to index document: {e}")
                    # 不影响保存操作，只记录错误
        else:
            QMessageBox.critical(self, "错误", "文档保存失败")

    @pyqtSlot(str, str)
    def _on_document_saved_auto_index(self, document_id: str, content: str):
        """文档保存后自动索引处理（从项目管理器触发）"""
        logger.debug(f"收到文档保存信号，准备自动索引: {document_id}")
        
        # 自动更新RAG索引
        if self._ai_manager and hasattr(self._ai_manager, 'index_document'):
            try:
                self._ai_manager.index_document(document_id, content)
                logger.info(f"文档自动索引完成: {document_id}")
            except Exception as e:
                logger.error(f"文档自动索引失败: {e}")
                # 不影响其他操作，只记录错误

    @pyqtSlot(str)
    def _on_document_selected(self, document_id: str):
        logger.info(f"Document selected: {document_id}")
        document = self._project_manager.get_document(document_id)
        if document:
            if hasattr(self, '_editor_panel'):
                if not self._editor_panel.switch_to_document(document_id):
                    self._editor_panel.create_new_document(document_id, document.name, document.content)
                self._update_ai_manager_editor()
                # 更新专注模式的编辑器引用
                self._update_focus_mode_editor()
            if hasattr(self, '_document_viewer'):
                self._document_viewer.load_document(document_id)
            word_count = self._calculate_word_count(document.content)
            self.statusBar().showMessage(f"已打开文档: {document.name} ({word_count} 字)")
        else:
            self.statusBar().showMessage(f"无法加载文档: {document_id}")

    @pyqtSlot(str, bool)
    def _on_document_modified(self, document_id: str, is_modified: bool):
        if is_modified:
            self._status_bar.set_document_status("未保存", "#d1242f")
        else:
            self._status_bar.set_document_status("已保存", "#1a7f37")

    @pyqtSlot(str)
    def _on_document_saved(self, document_id: str):
        logger.info(f"Document saved: {document_id}")
        self._status_bar.show_message(f"文档已保存: {document_id}", 2000)
        self._status_bar.set_document_status("已保存", "#1a7f37")

    @pyqtSlot(str)
    def _on_document_requested(self, document_id: str):
        """从搜索结果请求打开文档"""
        logger.info(f"Document requested from search: {document_id}")
        # 复用现有的文档选择逻辑
        self._on_document_selected(document_id)

    @pyqtSlot(str, dict)
    def _on_menu_action(self, action_id: str, data: dict):
        logger.debug(f"Menu action: {action_id}")
        
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
            "toggle_concept_panel": self._toggle_concept_panel,
            "toggle_outline_panel": self._toggle_outline_panel,
            "toggle_preview_panel": self._toggle_preview_panel,

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
            "prompt_manager": self._show_prompt_manager,
            "index_manager": self._show_index_manager,
            "batch_index": self._show_batch_index_dialog,

            # Dialogs
            "preferences": self._show_preferences,
            "project_settings": self._show_project_settings,
            "ai_config": self._show_ai_config_dialog,
            "word_count": self._show_word_count,
            "about": self._show_about,
            "auto_replace_settings": self._show_auto_replace_settings,
            
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

    def _toggle_concept_panel(self):
        """切换概念面板显示"""
        # 检查当前状态
        is_right_panel_visible = self._right_panel.isVisible()
        is_concept_panel_current = (hasattr(self, '_right_stack') and hasattr(self, '_concept_panel') and 
                                   self._right_stack.currentWidget() == self._concept_panel)
        
        # 如果概念面板正在显示，则隐藏右侧面板
        if is_right_panel_visible and is_concept_panel_current:
            self._right_panel.setVisible(False)
        else:
            # 否则显示概念面板
            if not is_right_panel_visible:
                self._toggle_right_panel()
            
            # 切换到概念面板
            if hasattr(self, '_right_stack') and hasattr(self, '_concept_panel'):
                self._right_stack.setCurrentWidget(self._concept_panel)
        
        # 统一同步菜单状态
        self._sync_panel_menu_states()
    
    def _toggle_outline_panel(self):
        """切换大纲面板显示"""
        # 检查当前状态
        is_right_panel_visible = self._right_panel.isVisible()
        is_outline_panel_current = (hasattr(self, '_right_stack') and hasattr(self, '_outline_panel') and 
                                   self._right_stack.currentWidget() == self._outline_panel)
        
        # 如果大纲面板正在显示，则隐藏右侧面板
        if is_right_panel_visible and is_outline_panel_current:
            self._right_panel.setVisible(False)
        else:
            # 否则显示大纲面板
            if not is_right_panel_visible:
                self._toggle_right_panel()
            
            # 切换到大纲面板
            if hasattr(self, '_right_stack') and hasattr(self, '_outline_panel'):
                self._right_stack.setCurrentWidget(self._outline_panel)
        
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
        
        # 不需要更新菜单状态，因为这是内部方法

    def _toggle_preview_panel(self):
        if hasattr(self, '_document_viewer'):
            self._document_viewer.setVisible(not self._document_viewer.isVisible())
            # 更新菜单状态
            if hasattr(self, '_menu_bar'):
                action = self._menu_bar.get_action('toggle_preview_panel')
                if action:
                    action.setChecked(self._document_viewer.isVisible())
    
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
        logger.info(f"Theme changed to: {theme_type.value}")

    def _show_preferences(self):
        dialog = SettingsDialog(self, {})
        dialog.exec()

    def _show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_ai_config_dialog(self):
        """显示AI配置对话框"""
        if not self._ai_manager:
            # 尝试重新初始化AI管理器
            reply = QMessageBox.question(
                self, "AI管理器未初始化", 
                "AI管理器未正确初始化。是否尝试重新初始化？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._try_reinit_ai_manager()
                if not self._ai_manager:
                    QMessageBox.critical(self, "初始化失败", "AI管理器重新初始化失败。")
                    return
            else:
                return
            
        try:
            # 检查AI管理器是否有配置对话框方法
            if hasattr(self._ai_manager, 'show_config_dialog'):
                # 先检查AI状态（如果方法存在）
                if hasattr(self._ai_manager, 'get_ai_status'):
                    ai_status = self._ai_manager.get_ai_status()
                    if not ai_status.get('ai_client_available', True):
                        logger.warning("AI客户端不可用，尝试恢复")
                        if hasattr(self._ai_manager, 'force_reinit_ai'):
                            recovery_success = self._ai_manager.force_reinit_ai()
                            if not recovery_success:
                                reply = QMessageBox.question(
                                    self, "AI服务不可用", 
                                    "AI客户端初始化失败，可能是配置问题。\n是否仍要打开配置对话框进行设置？",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                )
                                if reply == QMessageBox.StandardButton.No:
                                    return
                
                # 显示配置对话框
                self._ai_manager.show_config_dialog(self)
            else:
                # 回退：使用基础配置对话框
                self._show_basic_ai_config()
                
        except Exception as e:
            logger.error(f"显示AI配置对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开AI配置对话框: {str(e)}")
    
    def _try_reinit_ai_manager(self):
        """尝试重新初始化AI管理器"""
        try:
            logger.info("开始重新初始化AI管理器")
            
            # 清理现有的AI管理器
            if self._ai_manager:
                try:
                    if hasattr(self._ai_manager, 'cleanup'):
                        self._ai_manager.cleanup()
                except Exception as e:
                    logger.warning(f"清理现有AI管理器失败: {e}")
            
            self._ai_manager = None
            self._ai_control_panel = None
            
            # 强制重新初始化 - 优先尝试增强型
            try:
                logger.info("尝试重新初始化增强型AI管理器...")
                
                # 重新测试核心模块导入
                from core.prompt_engineering import EnhancedPromptManager
                from core.builtin_templates import register_builtin_loader
                from core.context_variables import IntelligentContextAnalyzer
                logger.info("核心提示词模块重新导入成功")
                
                # 重新导入增强型AI管理器
                from gui.ai.enhanced_ai_manager import EnhancedAIManager
                logger.info("EnhancedAIManager类重新导入成功")
                
                rag_service = getattr(self._shared, 'rag_service', None)
                vector_store = getattr(self._shared, 'vector_store', None)
                
                self._ai_manager = EnhancedAIManager(
                    config=self._config,
                    shared=self._shared,
                    concept_manager=self._concept_manager,
                    rag_service=rag_service,
                    vector_store=vector_store,
                    parent=self
                )
                
                # 验证增强型功能
                if (hasattr(self._ai_manager, 'prompt_manager') and 
                    self._ai_manager.prompt_manager and
                    hasattr(self._ai_manager, 'open_template_manager')):
                    logger.info("增强型AI管理器重新初始化成功，提示词系统正常")
                else:
                    logger.warning("增强型AI管理器重新初始化成功，但提示词系统有问题")
                    if hasattr(self._ai_manager, 'prompt_manager'):
                        logger.warning(f"prompt_manager状态: {self._ai_manager.prompt_manager}")
                
            except Exception as enhanced_error:
                import traceback
                logger.error(f"增强型AI管理器重新初始化失败: {enhanced_error}")
                logger.error(f"错误堆栈: {traceback.format_exc()}")
                logger.warning("回退到基础AI管理器")
                
                # 回退到基础AI管理器
                from gui.ai.ai_manager import AIManager
                self._ai_manager = AIManager(self._config, self)
                logger.info("基础AI管理器重新初始化成功")
            
            # 重新初始化控制面板
            if self._ai_manager:
                try:
                    from gui.ai.ai_completion_control import AICompletionControlPanel
                    self._ai_control_panel = AICompletionControlPanel(self)
                    self._shared.ai_manager = self._ai_manager
                    logger.info("AI控制面板和共享对象重新初始化成功")
                except Exception as panel_error:
                    logger.warning(f"AI控制面板重新初始化失败: {panel_error}")
            
            return self._ai_manager is not None
                    
        except Exception as e:
            import traceback
            logger.error(f"重新初始化AI管理器完全失败: {e}")
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            self._ai_manager = None
            self._ai_control_panel = None
            return False
    
    def _show_basic_ai_config(self):
        """显示基础AI配置对话框（回退方案）"""
        try:
            from gui.ai.unified_ai_config_dialog import UnifiedAIConfigDialog
            dialog = UnifiedAIConfigDialog(self, self._config)
            if dialog.exec():
                # 配置保存后尝试重新初始化
                self._try_reinit_ai_manager()
        except Exception as e:
            logger.error(f"显示基础AI配置对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开配置对话框: {str(e)}")

    def _show_template_selector_dialog(self):
        """显示提示词模板选择对话框"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
            
        try:
            # 检查是否有增强AI管理器和模板系统
            if hasattr(self._ai_manager, 'get_available_templates') and hasattr(self._ai_manager, 'get_current_template_info'):
                self._show_enhanced_template_selector()
            else:
                QMessageBox.information(self, "提示", "当前AI管理器不支持模板选择功能")
                
        except Exception as e:
            logger.error(f"显示模板选择对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开模板选择对话框: {str(e)}")
    
    def _show_enhanced_template_selector(self):
        """显示增强版模板选择对话框"""
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QTextEdit
            
            # 创建对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("选择提示词模板")
            dialog.setMinimumSize(700, 550)  # 增加最小尺寸
            dialog.resize(750, 600)  # 设置更大的默认尺寸
            
            # 应用深色主题样式
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #1a1a1a;
                    color: #e8e8e8;
                }
                QLabel {
                    color: #e8e8e8;
                    background-color: transparent;
                }
                QListWidget {
                    background-color: #2a2a2a;
                    border: 1px solid #404040;
                    border-radius: 6px;
                    color: #e8e8e8;
                    selection-background-color: #8b5cf6;
                    selection-color: #ffffff;
                    alternate-background-color: #333333;
                    padding: 4px;
                }
                QListWidget::item {
                    padding: 8px 12px;
                    border-bottom: 1px solid #404040;
                    min-height: 24px;
                    max-height: 40px;
                }
                QListWidget::item:selected {
                    background-color: #8b5cf6;
                    color: #ffffff;
                }
                QListWidget::item:hover {
                    background-color: #4a4a4a;
                }
                QTextEdit {
                    background-color: #2a2a2a;
                    border: 1px solid #404040;
                    border-radius: 6px;
                    color: #e8e8e8;
                    padding: 8px;
                    font-size: 12px;
                }
                QPushButton {
                    background-color: #8b5cf6;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #7c3aed;
                }
                QPushButton:pressed {
                    background-color: #6d28d9;
                }
                QPushButton:disabled {
                    background-color: #4a4a4a;
                    color: #888888;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(16)
            layout.setContentsMargins(20, 20, 20, 20)
            
            # 当前模板信息
            current_info = self._ai_manager.get_current_template_info()
            if current_info:
                current_label = QLabel(f"当前模板: {current_info['name']} ({current_info['category']})")
                current_label.setStyleSheet("""
                    QLabel {
                        font-weight: bold; 
                        padding: 10px 16px; 
                        background-color: rgba(139, 92, 246, 0.15);
                        border: 1px solid rgba(139, 92, 246, 0.3);
                        border-radius: 6px;
                        color: #e8e8e8;
                        margin-bottom: 8px;
                    }
                """)
                layout.addWidget(current_label)
            
            # 模板列表区域
            list_label = QLabel("可用模板:")
            list_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 12px; margin-bottom: 6px;")
            layout.addWidget(list_label)
            
            template_list = QListWidget()
            template_list.setAlternatingRowColors(True)
            template_list.setMinimumHeight(250)  # 增加列表高度
            template_list.setMaximumHeight(300)  # 限制最大高度，为描述区域留空间
            template_list.setSpacing(2)  # 设置项目间距
            template_list.setUniformItemSizes(True)  # 统一项目大小
            available_templates = self._ai_manager.get_available_templates()
            
            for template_id in available_templates:
                # 获取模板详细信息（如果可能）
                try:
                    if hasattr(self._ai_manager, 'prompt_manager') and self._ai_manager.prompt_manager:
                        template = self._ai_manager.prompt_manager.get_template(template_id)
                        if template:
                            item_text = f"{template.name} - {template.category}"
                            item = QListWidgetItem(item_text)
                            item.setData(Qt.ItemDataRole.UserRole, template_id)
                            # 设置固定高度避免重叠
                            from PyQt6.QtCore import QSize
                            item.setSizeHint(QSize(-1, 32))  # 固定高度32像素
                            template_list.addItem(item)
                            
                            # 如果是当前模板，设置选中
                            if current_info and template_id == current_info['id']:
                                template_list.setCurrentItem(item)
                except Exception as e:
                    logger.warning(f"获取模板信息失败: {template_id}, {e}")
                    # 回退到简单显示
                    item = QListWidgetItem(template_id)
                    item.setData(Qt.ItemDataRole.UserRole, template_id)
                    from PyQt6.QtCore import QSize
                    item.setSizeHint(QSize(-1, 32))  # 固定高度32像素
                    template_list.addItem(item)
            
            layout.addWidget(template_list)
            
            # 模板描述区域
            desc_label = QLabel("模板描述:")
            desc_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 12px; margin-bottom: 6px;")
            layout.addWidget(desc_label)
            
            description_area = QTextEdit()
            description_area.setFixedHeight(100)  # 固定高度，防止布局冲突
            description_area.setReadOnly(True)
            description_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            layout.addWidget(description_area)
            
            # 更新描述的函数
            def update_description():
                current_item = template_list.currentItem()
                if current_item:
                    template_id = current_item.data(Qt.ItemDataRole.UserRole)
                    try:
                        if hasattr(self._ai_manager, 'prompt_manager') and self._ai_manager.prompt_manager:
                            template = self._ai_manager.prompt_manager.get_template(template_id)
                            if template:
                                desc = f"名称: {template.name}\n"
                                desc += f"分类: {template.category}\n"
                                desc += f"描述: {template.description}\n"
                                desc += f"类型: {'内置' if template.is_builtin else '自定义'}"
                                description_area.setPlainText(desc)
                            else:
                                description_area.setPlainText(f"模板ID: {template_id}")
                        else:
                            description_area.setPlainText(f"模板ID: {template_id}")
                    except Exception as e:
                        description_area.setPlainText(f"无法获取模板信息: {str(e)}")
                else:
                    description_area.clear()
            
            template_list.currentItemChanged.connect(lambda: update_description())
            
            # 初始化描述
            if template_list.currentItem():
                update_description()
            
            # 按钮区域
            button_layout = QHBoxLayout()
            button_layout.setSpacing(12)
            button_layout.setContentsMargins(0, 20, 0, 0)  # 顶部留更多空间
            
            # 管理按钮（左侧）
            manage_btn = QPushButton("管理模板")
            manage_btn.setMinimumWidth(100)
            manage_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a5568;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: bold;
                    min-width: 100px;
                }
                QPushButton:hover {
                    background-color: #2d3748;
                }
                QPushButton:pressed {
                    background-color: #1a202c;
                }
            """)
            
            # 主要按钮（右侧）
            select_btn = QPushButton("选择模板")
            select_btn.setMinimumWidth(100)
            
            cancel_btn = QPushButton("取消")
            cancel_btn.setMinimumWidth(80)
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e53e3e;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #c53030;
                }
                QPushButton:pressed {
                    background-color: #9c1c1c;
                }
            """)
            
            def on_select():
                current_item = template_list.currentItem()
                if current_item:
                    template_id = current_item.data(Qt.ItemDataRole.UserRole)
                    success = self._ai_manager.set_current_template(template_id)
                    if success:
                        dialog.accept()
                        # 更新工具栏显示（如果需要）
                        if hasattr(self, '_toolbar_manager'):
                            try:
                                ai_toolbar = self._toolbar_manager.get_toolbar('ai_toolbar')
                                if hasattr(ai_toolbar, 'update_template_display'):
                                    ai_toolbar.update_template_display(template_id)
                            except:
                                pass
                        
                        QMessageBox.information(self, "成功", f"已切换到模板: {current_item.text()}")
                    else:
                        QMessageBox.warning(self, "错误", "设置模板失败")
                else:
                    QMessageBox.warning(self, "警告", "请先选择一个模板")
            
            def on_manage():
                try:
                    if hasattr(self._ai_manager, 'open_template_manager'):
                        self._ai_manager.open_template_manager(self)
                        dialog.close()
                    else:
                        QMessageBox.information(self, "提示", "当前版本不支持模板管理功能")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"打开模板管理器失败: {str(e)}")
            
            select_btn.clicked.connect(on_select)
            cancel_btn.clicked.connect(dialog.reject)
            manage_btn.clicked.connect(on_manage)
            
            button_layout.addWidget(manage_btn)
            button_layout.addStretch()
            button_layout.addWidget(select_btn)
            button_layout.addWidget(cancel_btn)
            
            # 添加按钮布局到主布局
            layout.addLayout(button_layout)
            
            # 显示对话框
            dialog.exec()
            
        except Exception as e:
            logger.error(f"创建增强版模板选择对话框失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"创建模板选择对话框失败: {str(e)}")

    def _show_project_settings(self):
        dialog = ProjectSettingsDialog(self, {})
        dialog.exec()

    def _show_word_count(self):
        """显示字数统计对话框"""
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor:
            QMessageBox.warning(self, "警告", "没有打开的文档")
            return
        
        if not self._word_count_dialog:
            self._word_count_dialog = WordCountDialog(self, current_editor)
        else:
            # 更新编辑器引用
            self._word_count_dialog._text_editor = current_editor
            self._word_count_dialog._setup_connections()
        
        self._word_count_dialog.show_and_focus()
    
    def _show_simple_find(self):
        """显示简单查找对话框（类似记事本）"""
        current_text_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_text_editor:
            QMessageBox.warning(self, "警告", "没有打开的文档")
            return
            
        # 使用简单查找对话框
        if not hasattr(self, '_simple_find_dialog') or not self._simple_find_dialog:
            self._simple_find_dialog = SimpleFindDialog(self, current_text_editor)
        else:
            self._simple_find_dialog._text_editor = current_text_editor
            
        # 如果有选中文本，设置为搜索内容
        if current_text_editor.textCursor().hasSelection():
            self._simple_find_dialog.set_search_text(current_text_editor.textCursor().selectedText())
            
        self._simple_find_dialog.show_and_focus()

    def _show_import_dialog(self, project_mode: bool = False):
        """显示导入对话框"""
        if not self._project_manager.has_project() and not project_mode:
            QMessageBox.warning(self, "警告", "请先打开或创建一个项目")
            return
        
        dialog = ImportDialog(self._project_manager, self)
        if dialog.exec():
            # 刷新项目树
            if hasattr(self, '_left_panel'):
                self._left_panel._load_project_tree()
            # 刷新大纲
            if hasattr(self, '_outline_panel'):
                self._outline_panel._load_outline()
    
    def _show_export_dialog(self, pdf_mode: bool = False):
        """显示导出对话框"""
        if not self._project_manager.has_project():
            QMessageBox.warning(self, "警告", "没有打开的项目")
            return
        
        dialog = ExportDialog(self._project_manager, self)
        
        # 如果是PDF模式，默认选择PDF格式
        if pdf_mode and hasattr(dialog, '_format_combo'):
            dialog._format_combo.setCurrentIndex(3)  # PDF是第4个选项
        
        dialog.exec()
    
    def _show_auto_replace_settings(self):
        """显示自动替换设置对话框"""
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor:
            QMessageBox.warning(self, "警告", "没有打开的文档")
            return
        
        # 使用编辑器的自动替换管理器
        if hasattr(current_editor, '_auto_replace_manager'):
            dialog = AutoReplaceDialog(current_editor._auto_replace_manager, self)
            dialog.exec()
        else:
            QMessageBox.warning(self, "警告", "自动替换功能不可用")
    
    def _show_find_replace(self, replace_mode: bool = False):
        current_text_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not self._find_replace_dialog:
            # 使用增强搜索对话框替代简单搜索对话框
            self._find_replace_dialog = EnhancedFindDialog(
                self, 
                current_text_editor, 
                self._project_manager
            )
            # 连接文档跳转信号
            self._find_replace_dialog.documentRequested.connect(self._on_document_requested)
        else:
            self._find_replace_dialog._text_editor = current_text_editor
        if current_text_editor and current_text_editor.textCursor().hasSelection():
            self._find_replace_dialog.set_search_text(current_text_editor.textCursor().selectedText())
        # EnhancedFindDialog不使用标签页，所以移除替换模式的处理
        # if replace_mode:
        #     self._find_replace_dialog._tabs.setCurrentIndex(1)
        self._find_replace_dialog.show_and_focus()

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
    
    def closeEvent(self, event: QCloseEvent):
        logger.info("主窗口关闭事件触发")
        
        # 保存窗口和布局状态
        self._save_window_state()
        self._save_layout_state()
        
        # 关闭项目
        if not self._project_controller.on_close_project():
            event.ignore()
            return
        
        # 清理AI管理器资源（防止线程崩溃）
        if self._ai_manager:
            try:
                logger.info("清理AI管理器资源")
                self._ai_manager.cleanup()
            except Exception as e:
                logger.error(f"清理AI管理器时出错: {e}")
        
        # 清理其他资源
        try:
            # 确保所有面板都正确关闭
            if hasattr(self, '_left_panel'):
                self._left_panel.deleteLater()
            if hasattr(self, '_right_panel'):
                self._right_panel.deleteLater()
            if hasattr(self, '_editor_panel'):
                self._editor_panel.deleteLater()
        except Exception as e:
            logger.warning(f"清理UI组件时出错: {e}")
        
        event.accept()
        logger.info("主窗口关闭完成")

    def _save_layout_state(self):
        try:
            self._config.set('layout', 'splitter_sizes', self._main_splitter.sizes())
            self._config.set('layout', 'left_panel_visible', self._left_panel.isVisible())
            self._config.set('layout', 'right_panel_visible', self._right_panel.isVisible())
            self._config.save()
            logger.debug("Layout state saved")
        except Exception as e:
            logger.error(f"Failed to save layout state: {e}")

    def _restore_layout_state(self):
        try:
            splitter_sizes = self._config.get('layout', 'splitter_sizes')
            if splitter_sizes and len(splitter_sizes) == 3:
                # 确保左右面板至少有最小宽度，但使用更紧凑的默认值
                if splitter_sizes[0] < 100:  # 左面板最小100像素
                    splitter_sizes[0] = 130  # 进一步缩小左面板默认宽度
                if splitter_sizes[2] < 120:  # 右面板最小120像素
                    splitter_sizes[2] = 160
                self._main_splitter.setSizes(splitter_sizes)
            else:
                # 使用更紧凑的默认布局：左面板130px，右面板160px
                self._main_splitter.setSizes([130, 910, 160])
            
            # 恢复面板可见性
            left_visible = self._config.get('layout', 'left_panel_visible', True)
            right_visible = self._config.get('layout', 'right_panel_visible', False)  # 默认隐藏右侧面板
            
            self._left_panel.setVisible(left_visible)
            self._right_panel.setVisible(right_visible)
            
            # 如果面板应该可见但宽度为0，强制设置一个默认宽度
            sizes = self._main_splitter.sizes()
            if left_visible and sizes[0] == 0:
                sizes[0] = 130  # 进一步缩小的默认宽度
                self._main_splitter.setSizes(sizes)
            if right_visible and sizes[2] == 0:
                sizes[2] = 160  # 更紧凑的默认宽度
                self._main_splitter.setSizes(sizes)
                
            logger.debug(f"Layout state restored: sizes={self._main_splitter.sizes()}")
        except Exception as e:
            logger.error(f"Failed to restore layout state: {e}")
            # 恢复失败时使用默认布局，更紧凑
            self._main_splitter.setSizes([130, 910, 160])

    # 专注模式相关方法
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
        if not self._focus_mode:
            return
        # 只在非普通模式时才退出到普通模式
        if self._focus_mode.get_current_mode() != 'normal':
            self._focus_mode.set_mode('normal')

    # Dummy slots for signals that might not be connected yet
    @pyqtSlot(str, str)
    def _on_concept_selected(self, concept_type: str, concept_name: str): pass
    @pyqtSlot(str)
    def _on_viewer_document_changed(self, document_id: str): pass
    @pyqtSlot(str)
    def _on_viewer_link_clicked(self, link: str): pass
    @pyqtSlot(str, int, str)
    def _on_completion_requested(self, text: str, position: int, document_id: str):
        """处理来自编辑器的补全请求，转发给AI管理器"""
        if self._ai_manager:
            logger.debug(f"转发补全请求到AI管理器: text_length={len(text)}, position={position}, doc_id={document_id}")
            self._ai_manager.request_completion('manual')
        else:
            logger.warning("AI管理器不可用，无法处理补全请求")
    @pyqtSlot(str, list)
    def _on_concepts_detected(self, document_id: str, concepts: list): pass
    @pyqtSlot(str)
    def _on_project_changed(self, project_path: str): pass

    @pyqtSlot(str)
    def _on_theme_changed(self, theme: str):
        """主题变更时，重新应用主题"""
        self._apply_theme()

    def _connect_controller_signals(self):
        """集中连接所有与ProjectController相关的信号和槽"""
        controller = self._project_controller
        menu_bar = self._menu_bar

        # 菜单动作已经通过 _on_menu_action 统一处理并分发给控制器，
        # 此处不再需要直接连接菜单的triggered信号。

        # 监听来自控制器的信号
        controller.project_opened.connect(self._on_project_opened)
        controller.project_closed.connect(self._on_project_closed)
        controller.project_structure_changed.connect(self._on_project_structure_changed)
        controller.status_message_changed.connect(self.statusBar().showMessage)

    @pyqtSlot(str)
    def _on_project_opened(self, project_path: str):
        """项目成功打开后的处理"""
        self.setWindowTitle(f"AI Novel Editor - {project_path}")
        self._menu_bar.get_action('save_project').setEnabled(True)
        self._menu_bar.get_action('save_project_as').setEnabled(True)
        self._menu_bar.get_action('close_project').setEnabled(True)
        self._on_project_structure_changed()
        
        # 确保AI管理器在项目打开后仍可用
        if self._ai_manager:
            ai_status = self._ai_manager.get_ai_status()
            if not ai_status['ai_client_available']:
                logger.warning("项目打开后AI客户端不可用，尝试恢复")
                self._ai_manager.force_reinit_ai()
        
        logger.info(f"Project opened at: {project_path}")

    @pyqtSlot()
    def _on_project_closed(self):
        """项目关闭后的处理"""
        self.setWindowTitle("AI Novel Editor")
        self._menu_bar.get_action('save_project').setEnabled(False)
        self._menu_bar.get_action('save_project_as').setEnabled(False)
        self._menu_bar.get_action('close_project').setEnabled(False)
        # 可能还需要清理项目面板等
        self._on_project_structure_changed()
        
        # 确保AI管理器在项目关闭后仍可用
        if self._ai_manager:
            ai_status = self._ai_manager.get_ai_status()
            if not ai_status['ai_client_available']:
                logger.warning("项目关闭后AI客户端不可用，尝试恢复")
                self._ai_manager.force_reinit_ai()
        
        logger.info("Project closed.")

    @pyqtSlot()
    def _on_project_structure_changed(self):
        """当项目结构（如新建或打开项目）发生变化时，刷新UI"""
        if hasattr(self, '_left_panel'):
            self._left_panel._load_project_tree()
        
        # 刷新概念面板和大纲面板
        if hasattr(self, '_concept_panel'):
            self._concept_panel.refresh_concepts()
        if hasattr(self, '_outline_panel'):
            self._outline_panel._load_outline()

    @pyqtSlot(str)
    def _on_theme_manager_changed(self, theme: str): pass
    @pyqtSlot(str)
    def _on_text_statistics_changed(self, text: str): pass
    @pyqtSlot(int, int)
    def _on_cursor_position_changed(self, line: int, column: int): pass
    def _update_statistics_delayed(self): pass
    @pyqtSlot(str, dict)
    def _on_toolbar_action(self, action_id: str, data: dict):
        """处理来自工具栏的动作，直接复用菜单栏的动作分发逻辑"""
        logger.debug(f"Toolbar action received, forwarding to menu action handler: {action_id}")
        self._on_menu_action(action_id, data)
    
    def _on_ai_toolbar_action(self, action_id: str, data: dict):
        """处理AI工具栏动作"""
        logger.debug(f"AI toolbar action: {action_id}, data: {data}")
        
        if action_id == "completion_mode_changed":
            self._on_completion_mode_changed(data.get("mode"))
        elif action_id == "context_mode_changed":
            self._on_context_mode_changed(data.get("mode"))
        elif action_id == "complete":
            self._trigger_ai_completion()
        elif action_id == "continue":
            self._trigger_ai_continue()
        elif action_id == "enhance":
            self._trigger_ai_enhance()
        elif action_id == "ai_config":
            self._show_ai_config_dialog()
        elif action_id == "template_selector":
            self._show_template_selector_dialog()
        elif action_id == "index_manager":
            self._show_index_manager()
        elif action_id == "batch_index":
            self._show_batch_index_dialog()
        else:
            logger.warning(f"Unknown AI toolbar action: {action_id}")
    
    def _on_completion_mode_changed(self, mode_text: str):
        """处理补全模式变化"""
        if not self._ai_manager:
            return
        
        # 映射显示名称到内部标识（支持精简版本和完整版本）
        mode_mapping = {
            # 精简版本（来自AI工具栏）
            "自动": "auto_ai",
            "手动": "manual_ai", 
            "禁用": "disabled",
            # 完整版本（兼容性）
            "自动AI补全": "auto_ai",
            "手动AI补全": "manual_ai",
            "禁用补全": "disabled"
        }
        
        mode = mode_mapping.get(mode_text, "auto_ai")
        self._ai_manager.set_completion_mode(mode)
        logger.info(f"补全模式已切换为: {mode_text} ({mode})")
        
        # 同步工具栏显示（如果需要）
        self._sync_completion_mode_to_toolbar(mode_text)
        
        # 更新状态栏
        if hasattr(self, '_status_bar'):
            self._status_bar.show_message(f"补全模式: {mode_text}", 2000)
    
    def _on_context_mode_changed(self, mode_text: str):
        """处理上下文模式变化"""
        if not self._ai_manager:
            return
        
        # 映射显示名称到内部标识（支持精简版本和完整版本）
        context_mapping = {
            # 精简版本（来自AI工具栏）
            "快速": "fast",
            "平衡": "balanced",
            "全局": "full",
            # 完整版本（兼容性）
            "快速模式 (<2K tokens)": "fast",
            "平衡模式 (2-8K tokens)": "balanced",
            "全局模式 (200K+ tokens)": "full"
        }
        
        context_mode = context_mapping.get(mode_text, "balanced")
        self._ai_manager.set_context_mode(context_mode)
        logger.info(f"上下文模式已切换为: {mode_text} ({context_mode})")
        
        # 同步工具栏显示（如果需要）
        self._sync_context_mode_to_toolbar(mode_text)
        
        # 更新状态栏
        if hasattr(self, '_status_bar'):
            self._status_bar.show_message(f"上下文模式: {mode_text}", 2000)
    
    def _sync_completion_mode_to_toolbar(self, mode_text: str):
        """同步补全模式到工具栏显示"""
        if not hasattr(self, '_toolbar_manager'):
            return
            
        ai_toolbar = self._toolbar_manager.get_toolbar("ai")
        if ai_toolbar and hasattr(ai_toolbar, 'set_completion_mode'):
            # 确保工具栏显示的是精简版本
            if mode_text not in ["自动", "手动", "禁用"]:
                # 如果输入的是完整版本，转换为精简版本
                mode_map = {
                    "自动AI补全": "自动",
                    "手动AI补全": "手动", 
                    "禁用补全": "禁用"
                }
                mode_text = mode_map.get(mode_text, mode_text)
            
            ai_toolbar._mode_combo.setCurrentText(mode_text)
            logger.debug(f"工具栏补全模式已同步为: {mode_text}")
    
    def _sync_context_mode_to_toolbar(self, mode_text: str):
        """同步上下文模式到工具栏显示"""
        if not hasattr(self, '_toolbar_manager'):
            return
            
        ai_toolbar = self._toolbar_manager.get_toolbar("ai")
        if ai_toolbar and hasattr(ai_toolbar, 'set_context_mode'):
            # 确保工具栏显示的是精简版本
            if mode_text not in ["快速", "平衡", "全局"]:
                # 如果输入的是完整版本，转换为精简版本
                mode_map = {
                    "快速模式 (<2K tokens)": "快速",
                    "平衡模式 (2-8K tokens)": "平衡",
                    "全局模式 (200K+ tokens)": "全局"
                }
                mode_text = mode_map.get(mode_text, mode_text)
            
            ai_toolbar._context_combo.setCurrentText(mode_text)
            logger.debug(f"工具栏上下文模式已同步为: {mode_text}")
    
    # AI相关方法实现
    def _trigger_ai_completion(self):
        """触发AI补全"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
        
        # 检查AI状态
        ai_status = self._ai_manager.get_ai_status()
        if not ai_status['ai_client_available']:
            QMessageBox.warning(self, "AI服务不可用", 
                              "AI客户端未初始化，请检查AI配置。\n" +
                              "您可以通过菜单 工具 → AI配置 进行设置。")
            return
        
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor:
            QMessageBox.warning(self, "警告", "没有当前编辑器")
            return
            
        self._ai_manager.request_completion('manual')
        logger.info("手动触发AI补全")
    
    def _trigger_ai_continue(self):
        """触发AI续写"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
        
        # 检查AI状态
        ai_status = self._ai_manager.get_ai_status()
        if not ai_status['ai_client_available']:
            QMessageBox.warning(self, "AI服务不可用", 
                              "AI客户端未初始化，请检查AI配置。\n" +
                              "您可以通过菜单 工具 → AI配置 进行设置。")
            return
            
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor:
            QMessageBox.warning(self, "警告", "没有当前编辑器")
            return
            
        # 获取当前文本作为提示
        text = current_editor.toPlainText()
        if text.strip():
            self._ai_manager.start_stream_response(text)
            logger.info("开始AI续写")
        else:
            QMessageBox.information(self, "提示", "请先输入一些内容作为续写的开始")
    
    def _trigger_ai_enhance(self):
        """触发AI润色"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
        
        # 检查AI状态
        ai_status = self._ai_manager.get_ai_status()
        if not ai_status['ai_client_available']:
            QMessageBox.warning(self, "AI服务不可用", 
                              "AI客户端未初始化，请检查AI配置。\n" +
                              "您可以通过菜单 工具 → AI配置 进行设置。")
            return
            
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor:
            QMessageBox.warning(self, "警告", "没有当前编辑器")
            return
        
        # 获取选中的文本或当前段落
        cursor = current_editor.textCursor()
        selected_text = cursor.selectedText()
        
        if not selected_text:
            # 如果没有选中文本，选择当前段落
            cursor.movePosition(cursor.MoveOperation.StartOfBlock, cursor.MoveMode.MoveAnchor)
            cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
            selected_text = cursor.selectedText()
        
        if selected_text.strip():
            # 构建润色提示词
            enhance_prompt = f"请对以下文本进行润色，保持原意的同时提升表达质量：\n\n{selected_text}"
            self._ai_manager.start_stream_response(enhance_prompt)
            logger.info("开始AI润色")
        else:
            QMessageBox.information(self, "提示", "请选择要润色的文本，或将光标置于要润色的段落")
    
    
    def _trigger_concept_detection(self):
        """触发概念检测"""
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor:
            QMessageBox.warning(self, "警告", "没有当前编辑器")
            return
            
        # 触发概念检测
        text = current_editor.toPlainText()
        if text.strip():
            detected_concepts = current_editor.get_detected_concepts()
            concept_count = len(detected_concepts)
            QMessageBox.information(
                self, "概念检测", 
                f"在当前文本中检测到 {concept_count} 个概念"
            )
            logger.info(f"概念检测完成：发现{concept_count}个概念")
        else:
            QMessageBox.information(self, "提示", "当前编辑器中没有文本内容")
    
    def _cycle_completion_mode(self):
        """循环切换补全模式"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
        
        # 检查AI状态
        ai_status = self._ai_manager.get_ai_status()
        if not ai_status['ai_client_available']:
            QMessageBox.warning(self, "AI服务不可用", 
                              "AI客户端未初始化，请检查AI配置。\n" +
                              "您可以通过菜单 工具 → AI配置 进行设置。")
            return
            
        current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
        if not current_editor or not hasattr(current_editor, '_smart_completion'):
            QMessageBox.warning(self, "警告", "智能补全管理器未就绪")
            return
            
        # 获取当前模式
        current_mode = getattr(current_editor._smart_completion, '_completion_mode', 'auto_ai')
        
        # 循环切换模式
        modes = ['auto_ai', 'manual_ai', 'disabled']
        mode_names = {
            'auto_ai': '全自动AI补全',
            'manual_ai': '手动AI补全', 
            'disabled': '禁用AI补全'
        }
        
        current_index = modes.index(current_mode) if current_mode in modes else 0
        next_mode = modes[(current_index + 1) % len(modes)]
        
        # 应用新模式
        current_editor._smart_completion.set_completion_mode(next_mode)
        self._ai_manager.set_completion_mode(next_mode)
        
        # 更新控制面板
        if self._ai_control_panel:
            mode_display_names = {
                'auto_ai': '自动AI补全',
                'manual_ai': '手动AI补全',
                'disabled': '禁用补全'
            }
            display_name = mode_display_names.get(next_mode, next_mode)
            index = self._ai_control_panel.completion_mode.findText(display_name)
            if index >= 0:
                self._ai_control_panel.completion_mode.setCurrentIndex(index)
        
        # 显示提示信息
        mode_name = mode_names.get(next_mode, next_mode)
        self.statusBar().showMessage(f"补全模式已切换为: {mode_name}", 3000)
        logger.info(f"补全模式切换为: {next_mode}")
    
    def _show_prompt_manager(self):
        """显示提示词管理对话框"""
        if not self._ai_manager:
            # 尝试重新初始化AI管理器
            reply = QMessageBox.question(
                self, "AI管理器未初始化", 
                "AI管理器未正确初始化。是否尝试重新初始化？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._try_reinit_ai_manager()
                if not self._ai_manager:
                    QMessageBox.critical(self, "初始化失败", "AI管理器重新初始化失败。")
                    return
            else:
                return
        
        # 详细检查AI管理器类型和功能
        ai_manager_type = type(self._ai_manager).__name__
        logger.info(f"当前AI管理器类型: {ai_manager_type}")
        
        # 检查是否为增强型AI管理器
        is_enhanced = 'Enhanced' in ai_manager_type or hasattr(self._ai_manager, 'prompt_manager')
        logger.info(f"是否为增强型AI管理器: {is_enhanced}")
        
        # 检查是否有提示词管理方法
        has_template_manager = hasattr(self._ai_manager, 'open_template_manager')
        logger.info(f"是否有open_template_manager方法: {has_template_manager}")
        
        if has_template_manager:
            try:
                # 进一步检查提示词系统状态
                if hasattr(self._ai_manager, 'prompt_manager'):
                    if self._ai_manager.prompt_manager is None:
                        reply = QMessageBox.question(
                            self, "提示词系统未初始化", 
                            "提示词系统未正确初始化。这可能是由于缺少依赖或配置问题。\n\n"
                            "是否要重新初始化AI系统？",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.Yes:
                            self._try_reinit_ai_manager()
                            if not (self._ai_manager and hasattr(self._ai_manager, 'prompt_manager') and self._ai_manager.prompt_manager):
                                QMessageBox.critical(self, "初始化失败", 
                                                   "提示词系统重新初始化失败。\n请检查日志文件获取详细错误信息。")
                                return
                        else:
                            return
                
                # 打开提示词管理对话框
                logger.info("正在打开提示词管理对话框...")
                self._ai_manager.open_template_manager(self)
                logger.info("提示词管理对话框已打开")
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"打开提示词管理对话框失败: {e}")
                logger.error(f"错误堆栈: {error_details}")
                
                QMessageBox.critical(self, "错误", 
                                   f"无法打开提示词管理对话框:\n\n{str(e)}\n\n"
                                   f"AI管理器类型: {ai_manager_type}\n"
                                   f"请检查日志文件获取详细信息。")
        else:
            # 提供更详细的诊断信息
            diagnostic_info = []
            diagnostic_info.append(f"AI管理器类型: {ai_manager_type}")
            diagnostic_info.append(f"是否为增强型: {is_enhanced}")
            
            if hasattr(self._ai_manager, '__dict__'):
                available_methods = [method for method in dir(self._ai_manager) if not method.startswith('_')]
                diagnostic_info.append(f"可用方法: {', '.join(available_methods[:10])}...")
            
            # 尝试重新初始化为增强型管理器
            reply = QMessageBox.question(
                self, "提示词管理功能不可用", 
                f"当前AI管理器不支持提示词管理功能。\n\n"
                f"诊断信息:\n" + "\n".join(diagnostic_info) + "\n\n"
                f"是否要尝试重新初始化为增强型AI管理器？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._try_reinit_ai_manager()
                # 递归调用自己，重新检查
                if self._ai_manager:
                    self._show_prompt_manager()
            else:
                QMessageBox.information(self, "功能说明", 
                                      "提示词管理功能需要增强型AI管理器支持。\n"
                                      "如果问题持续存在，请检查以下内容:\n\n"
                                      "1. 确保所有提示词工程模块已正确安装\n"
                                      "2. 检查应用程序日志获取详细错误信息\n"
                                      "3. 重启应用程序尝试重新初始化")
    
    def _show_ai_control_panel(self):
        """显示AI补全设置（跳转到配置中心的补全设置页面）"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
        
        # 检查AI状态
        ai_status = self._ai_manager.get_ai_status()
        if not ai_status['ai_client_available']:
            reply = QMessageBox.question(
                self, "AI服务不可用", 
                "AI客户端未初始化，可能是配置问题。\n是否要打开配置对话框进行设置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._show_ai_config_dialog()
            return
            
        # 显示统一配置对话框并切换到补全设置页面
        try:
            from .ai.unified_ai_config_dialog import UnifiedAIConfigDialog
            
            # 创建配置对话框
            config_dialog = UnifiedAIConfigDialog(self, self._config)
            
            # 连接补全设置信号到AI管理器
            completion_widget = config_dialog.get_completion_widget()
            if completion_widget:
                completion_widget.completionEnabledChanged.connect(self._ai_manager.set_completion_enabled)
                completion_widget.autoTriggerEnabledChanged.connect(self._ai_manager.set_auto_trigger_enabled)
                completion_widget.punctuationAssistChanged.connect(self._ai_manager.set_punctuation_assist_enabled)
                completion_widget.triggerDelayChanged.connect(self._ai_manager.set_trigger_delay)
                completion_widget.completionModeChanged.connect(self._ai_manager.set_completion_mode)
            
            # 连接配置保存信号
            config_dialog.configSaved.connect(self._ai_manager._on_unified_config_saved)
            
            # 切换到补全设置页面（第二个标签）
            config_dialog._tabs.setCurrentIndex(1)
            
            # 显示对话框
            config_dialog.exec()
            
        except ImportError as e:
            logger.error(f"导入统一配置对话框失败: {e}")
            # 回退到直接显示AI配置对话框
            self._show_ai_config_dialog()
        except Exception as e:
            logger.error(f"显示AI补全设置失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开AI补全设置: {str(e)}")
    
    def _show_index_manager(self):
        """显示索引管理对话框"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
        
        # 检查AI状态（RAG功能需要）
        ai_status = self._ai_manager.get_ai_status()
        if not ai_status['rag_service_available']:
            reply = QMessageBox.question(
                self, "RAG服务不可用", 
                "RAG向量搜索服务未初始化，可能需要配置。\n" +
                "是否要打开RAG配置对话框进行设置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # 打开统一配置对话框的RAG页面
                try:
                    from .ai.unified_ai_config_dialog import UnifiedAIConfigDialog
                    config_dialog = UnifiedAIConfigDialog(self, self._config)
                    config_dialog._tabs.setCurrentIndex(2)  # RAG配置页面
                    config_dialog.configSaved.connect(self._ai_manager._on_unified_config_saved)
                    config_dialog.exec()
                except Exception as e:
                    logger.error(f"打开RAG配置失败: {e}")
                    QMessageBox.critical(self, "错误", f"无法打开RAG配置: {str(e)}")
            return
        
        try:
            self._ai_manager.show_index_manager(
                parent=self, 
                project_manager=self._project_manager
            )
        except Exception as e:
            logger.error(f"显示索引管理对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开索引管理对话框: {str(e)}")
    
    def _show_batch_index_dialog(self):
        """显示批量索引对话框"""
        if not self._ai_manager:
            QMessageBox.warning(self, "警告", "AI管理器未初始化")
            return
        
        # 检查是否有打开的项目
        if not self._project_manager.get_current_project():
            QMessageBox.warning(self, "警告", "请先打开一个项目")
            return
        
        # 检查AI状态（RAG功能需要）
        ai_status = self._ai_manager.get_ai_status()
        if not ai_status['rag_service_available']:
            reply = QMessageBox.question(
                self, "RAG服务不可用", 
                "RAG向量搜索服务未初始化，需要先配置RAG服务。\n" +
                "是否要打开RAG配置对话框进行设置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # 打开统一配置对话框的RAG页面
                try:
                    from .ai.unified_ai_config_dialog import UnifiedAIConfigDialog
                    config_dialog = UnifiedAIConfigDialog(self, self._config)
                    config_dialog._tabs.setCurrentIndex(2)  # RAG配置页面
                    config_dialog.configSaved.connect(self._ai_manager._on_unified_config_saved)
                    config_dialog.exec()
                except Exception as e:
                    logger.error(f"打开RAG配置失败: {e}")
                    QMessageBox.critical(self, "错误", f"无法打开RAG配置: {str(e)}")
            return
        
        try:
            self._ai_manager.show_batch_index_dialog(
                parent=self, 
                project_manager=self._project_manager
            )
        except Exception as e:
            logger.error(f"显示批量索引对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开批量索引对话框: {str(e)}")

    def _quick_cycle_context_mode(self):
        """快速循环切换上下文模式（快捷键）"""
        ai_toolbar = self._toolbar_manager.get_toolbar("ai")
        if ai_toolbar and hasattr(ai_toolbar, '_cycle_context_mode'):
            ai_toolbar._cycle_context_mode()
            # 显示当前模式
            current_mode = ai_toolbar.get_context_mode()
            if hasattr(self, '_status_bar'):
                self._status_bar.show_message(f"上下文模式: {current_mode}", 2000)
    
    def _quick_cycle_completion_mode(self):
        """快速循环切换补全模式（快捷键）"""
        ai_toolbar = self._toolbar_manager.get_toolbar("ai")
        if ai_toolbar and hasattr(ai_toolbar, '_cycle_completion_mode'):
            ai_toolbar._cycle_completion_mode()
            # 显示当前模式
            current_mode = ai_toolbar.get_completion_mode()
            if hasattr(self, '_status_bar'):
                self._status_bar.show_message(f"补全模式: {current_mode}", 2000)
    
    def _sync_panel_menu_states(self):
        """同步所有面板的菜单状态"""
        if not hasattr(self, '_menu_bar'):
            return
            
        # 同步项目面板状态
        if hasattr(self, '_left_panel'):
            action = self._menu_bar.get_action('toggle_project_panel')
            if action:
                action.setChecked(self._left_panel.isVisible())
        
        # 同步右侧面板状态（概念面板和大纲面板）
        if hasattr(self, '_right_panel') and hasattr(self, '_right_stack'):
            is_right_visible = self._right_panel.isVisible()
            
            # 概念面板状态
            concept_action = self._menu_bar.get_action('toggle_concept_panel')
            if concept_action:
                is_concept_current = (hasattr(self, '_concept_panel') and 
                                    self._right_stack.currentWidget() == self._concept_panel)
                should_check = is_right_visible and is_concept_current
                concept_action.setChecked(should_check)
                logger.debug(f"概念面板菜单状态: 右侧可见={is_right_visible}, 概念当前={is_concept_current}, 菜单勾选={should_check}")
            
            # 大纲面板状态  
            outline_action = self._menu_bar.get_action('toggle_outline_panel')
            if outline_action:
                is_outline_current = (hasattr(self, '_outline_panel') and 
                                    self._right_stack.currentWidget() == self._outline_panel)
                should_check = is_right_visible and is_outline_current
                outline_action.setChecked(should_check)
                logger.debug(f"大纲面板菜单状态: 右侧可见={is_right_visible}, 大纲当前={is_outline_current}, 菜单勾选={should_check}")
        
        # 同步预览面板状态
        if hasattr(self, '_document_viewer'):
            action = self._menu_bar.get_action('toggle_preview_panel')
            if action:
                action.setChecked(self._document_viewer.isVisible())
        
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
