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
    QMessageBox, QApplication, QFileDialog, QDialog,
    QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QKeySequence, QCloseEvent, QShortcut
from core.config import Config
from core.shared import Shared
from core.project import ProjectManager, DocumentType
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
    FindReplaceDialog, WordCountDialog, ShortcutsDialog,
    AutoReplaceDialog, ImportDialog, ExportDialog
)
from gui.dialogs.import_export_dialog import ImportExportDialog
from gui.dialogs.simple_find_dialog import SimpleFindDialog
from gui.dialogs.enhanced_find_dialog import EnhancedFindDialog


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
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
        
        # 连接Codex相关信号
        self._connect_codex_signals()

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

    def _connect_codex_signals(self):
        """连接Codex相关信号"""
        if not self._codex_panel:
            return
            
        try:
            # 连接文档变更信号到引用检测
            if hasattr(self._shared, 'documentChanged'):
                self._shared.documentChanged.connect(self._on_document_changed_for_codex)
            
            # 连接编辑器文档修改信号到引用检测
            if hasattr(self._editor_panel, 'documentModified'):
                self._editor_panel.documentModified.connect(self._on_document_modified_for_codex)
            
            # 连接Codex面板的信号
            if hasattr(self._codex_panel, 'entrySelected'):
                self._codex_panel.entrySelected.connect(self._on_codex_entry_selected)
            if hasattr(self._codex_panel, 'entryCreated'):
                self._codex_panel.entryCreated.connect(self._on_codex_entry_created)
            if hasattr(self._codex_panel, 'entryUpdated'):
                self._codex_panel.entryUpdated.connect(self._on_codex_entry_updated)
                
            logger.info("Codex信号连接已建立")
        except Exception as e:
            logger.error(f"连接Codex信号失败: {e}")

    @pyqtSlot(str)
    def _on_codex_entry_selected(self, entry_id: str):
        """处理Codex条目选择事件"""
        if self._codex_manager:
            entry = self._codex_manager.get_entry(entry_id)
            if entry:
                self._status_bar.show_message(f"选中Codex条目: {entry.title}", 2000)
                logger.info(f"Codex entry selected: {entry.title} ({entry_id})")

    @pyqtSlot(str)
    def _on_codex_entry_created(self, entry_id: str):
        """处理Codex条目创建事件"""
        if self._codex_manager:
            entry = self._codex_manager.get_entry(entry_id)
            if entry:
                self._status_bar.show_message(f"创建Codex条目: {entry.title}", 2000)
                logger.info(f"Codex entry created: {entry.title} ({entry_id})")

    @pyqtSlot(str)
    def _on_codex_entry_updated(self, entry_id: str):
        """处理Codex条目更新事件"""
        if self._codex_manager:
            entry = self._codex_manager.get_entry(entry_id)
            if entry:
                self._status_bar.show_message(f"更新Codex条目: {entry.title}", 2000)
                logger.info(f"Codex entry updated: {entry.title} ({entry_id})")

    @pyqtSlot(str)
    def _on_document_changed_for_codex(self, document_id: str):
        """文档变更时触发Codex引用检测"""
        if not (self._reference_detector and self._codex_panel):
            return
            
        try:
            # 获取当前文档内容
            current_editor = self._editor_panel.get_current_editor() if self._editor_panel else None
            if current_editor and current_editor.get_current_document_id() == document_id:
                content = current_editor.toPlainText()
                
                # 触发引用检测
                if hasattr(self._reference_detector, 'detect_references'):
                    references = self._reference_detector.detect_references(content)
                    
                    # 通知Codex面板刷新
                    if hasattr(self._codex_panel, 'refresh_for_document'):
                        self._codex_panel.refresh_for_document(document_id)
                    
                    logger.debug(f"检测到文档 {document_id} 中的 {len(references)} 个引用")
                        
        except Exception as e:
            logger.error(f"文档引用检测失败: {e}")

    @pyqtSlot(str, bool)
    def _on_document_modified_for_codex(self, document_id: str, is_modified: bool):
        """文档修改时触发Codex引用检测（仅在修改时）"""
        if not is_modified or not (self._reference_detector and self._codex_panel):
            return
            
        # 延迟触发检测，避免频繁调用
        if not hasattr(self, '_codex_detection_timer'):
            from PyQt6.QtCore import QTimer
            self._codex_detection_timer = QTimer()
            self._codex_detection_timer.setSingleShot(True)
            self._codex_detection_timer.timeout.connect(self._do_codex_detection)
        
        # 存储文档ID以供延迟执行
        self._pending_codex_document_id = document_id
        self._codex_detection_timer.stop()
        self._codex_detection_timer.start(2000)  # 2秒延迟
    
    def _do_codex_detection(self):
        """执行Codex引用检测"""
        if not hasattr(self, '_pending_codex_document_id'):
            return
            
        document_id = self._pending_codex_document_id
        try:
            self._on_document_changed_for_codex(document_id)
        except Exception as e:
            logger.error(f"Codex引用检测失败: {e}")

    def _integrate_codex_with_ai(self):
        """集成Codex系统与AI系统的提示词功能"""
        if not (self._ai_manager and self._codex_manager and self._prompt_function_registry):
            logger.info("Codex与AI系统集成跳过：组件不完整")
            return
            
        try:
            # 检查AI管理器是否支持Codex集成
            if hasattr(self._ai_manager, 'integrate_codex_system'):
                self._ai_manager.integrate_codex_system(
                    codex_manager=self._codex_manager,
                    reference_detector=self._reference_detector,
                    prompt_function_registry=self._prompt_function_registry
                )
                logger.info("Codex系统已成功集成到AI管理器")
            elif hasattr(self._ai_manager, 'prompt_manager'):
                # 如果是增强型AI管理器，注册Codex相关的提示词函数
                prompt_manager = self._ai_manager.prompt_manager
                if hasattr(prompt_manager, 'register_context_provider'):
                    # 注册Codex作为上下文提供者
                    prompt_manager.register_context_provider('codex', self._codex_manager)
                    logger.info("Codex已注册为AI提示词上下文提供者")
                    
                # 注册提示词函数
                if hasattr(prompt_manager, 'register_function_registry'):
                    prompt_manager.register_function_registry(self._prompt_function_registry)
                    logger.info("Codex提示词函数注册表已注册")
            else:
                logger.info("AI管理器不支持Codex集成，使用基础功能")
            
            # 设置编辑器的Codex组件（用于实时高亮）
            if self._editor_panel and hasattr(self._editor_panel, 'set_codex_components'):
                self._editor_panel.set_codex_components(self._codex_manager, self._reference_detector)
                logger.info("Codex组件已设置到编辑器面板（用于引用高亮）")
                
        except Exception as e:
            logger.error(f"Codex与AI系统集成失败: {e}")
            # 不阻止应用启动，仅记录错误

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
            
            # 同步主题菜单状态
            self._sync_theme_menu_state(theme_type)
            
            logger.info(f"Applied {theme_name} theme")
        except (KeyError, Exception) as e:
            logger.error(f"Failed to apply theme: {e}")
            self._theme_manager.set_theme(ThemeType.DARK)
            # 即使失败也要同步菜单状态
            self._sync_theme_menu_state(ThemeType.DARK)


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
            
            # 延迟自动更新RAG索引（避免阻塞保存操作）
            if self._ai_manager and hasattr(self._ai_manager, 'index_document'):
                try:
                    # 使用定时器延迟索引，避免阻塞UI
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(1000, lambda: self._delayed_index_document(document_id, content))
                    logger.debug(f"Document indexing scheduled: {document_id}")
                except Exception as e:
                    logger.error(f"Failed to schedule document indexing: {e}")
                    # 不影响保存操作，只记录错误
        else:
            QMessageBox.critical(self, "错误", "文档保存失败")
    
    def _delayed_index_document(self, document_id: str, content: str):
        """延迟执行文档索引（完全异步，避免UI阻塞）"""
        try:
            if self._ai_manager and hasattr(self._ai_manager, 'index_document'):
                # 使用线程池避免阻塞主线程
                from PyQt6.QtCore import QThreadPool, QRunnable, QObject, pyqtSignal
                
                class IndexWorker(QRunnable):
                    def __init__(self, ai_manager, document_id, content):
                        super().__init__()
                        self.ai_manager = ai_manager
                        self.document_id = document_id
                        self.content = content
                    
                    def run(self):
                        try:
                            # 优先使用同步版本（为PyQt线程优化）
                            if hasattr(self.ai_manager, 'index_document_sync'):
                                success = self.ai_manager.index_document_sync(self.document_id, self.content)
                                if success:
                                    logger.info(f"Document indexed for RAG (async): {self.document_id}")
                                else:
                                    logger.warning(f"Document indexing failed (async): {self.document_id}")
                            else:
                                # 回退到普通版本
                                self.ai_manager.index_document(self.document_id, self.content)
                                logger.info(f"Document indexed for RAG (async fallback): {self.document_id}")
                        except Exception as e:
                            logger.error(f"Failed to index document in background: {e}")
                
                # 在后台线程中执行索引
                worker = IndexWorker(self._ai_manager, document_id, content)
                QThreadPool.globalInstance().start(worker)
                logger.debug(f"Document indexing started in background thread: {document_id}")
                
        except Exception as e:
            logger.error(f"Failed to start background indexing: {e}")
            # 如果线程池失败，回退到简单的延迟执行
            if self._ai_manager and hasattr(self._ai_manager, 'index_document'):
                try:
                    self._ai_manager.index_document(document_id, content)
                    logger.info(f"Document indexed for RAG (fallback): {document_id}")
                except Exception as fallback_error:
                    logger.error(f"Fallback indexing also failed: {fallback_error}")

    @pyqtSlot(str, str)
    def _on_document_saved_auto_index(self, document_id: str, content: str):
        """文档保存后自动索引处理（从项目管理器触发）"""
        logger.debug(f"收到文档保存信号，准备异步索引: {document_id}")
        
        # 使用延迟异步索引，避免阻塞UI
        try:
            from PyQt6.QtCore import QTimer
            # 延迟2秒，让保存操作完全完成
            QTimer.singleShot(2000, lambda: self._delayed_index_document(document_id, content))
            logger.debug(f"Auto indexing scheduled for document: {document_id}")
        except Exception as e:
            logger.error(f"Failed to schedule auto indexing: {e}")
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
        
        # 不需要更新菜单状态，因为这是内部方法

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
        
        # 同步主题菜单状态
        self._sync_theme_menu_state(theme_type)
        
        logger.info(f"Theme changed to: {theme_type.value}")

    def _show_preferences(self):
        dialog = SettingsDialog(self, {})
        dialog.exec()

    def _show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_concept_manager(self):
        """显示概念管理器"""
        # 概念管理功能暂时通过右侧面板中的大纲面板来处理
        # 切换到大纲面板显示
        self._toggle_outline_panel()
        if self._status_bar:
            self._status_bar.show_message("概念管理功能集成在大纲面板中", 3000)

    def _show_codex_manager(self):
        """显示Codex知识库管理器"""
        if self._codex_panel:
            # 如果有Codex面板，切换到Codex面板
            self._toggle_codex_panel()
            if self._status_bar:
                self._status_bar.show_message("已切换到Codex知识库面板", 3000)
        else:
            # 如果没有Codex面板，显示消息
            if self._status_bar:
                self._status_bar.show_message("Codex知识库系统未启用", 3000)
            logger.warning("Codex管理器不可用 - Codex系统未初始化")

    def _show_ai_prompt_settings(self):
        """显示AI写作提示词设置对话框"""
        try:
            from gui.ai.simplified_prompt_dialog import SimplifiedPromptDialog
            
            # 创建并显示简化的对话框
            dialog = SimplifiedPromptDialog(self)
            # 不连接settingsChanged信号，避免重复保存
            
            result = dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                # 获取并应用设置
                settings = dialog.get_current_settings()
                self._on_ai_prompt_config_saved(settings)
                logger.info("AI写作提示词设置已保存")
            
        except ImportError as e:
            logger.error(f"导入简化提示词对话框失败: {e}")
            QMessageBox.critical(self, "错误", "无法加载AI写作提示词设置界面。")
        except Exception as e:
            logger.error(f"显示AI写作提示词设置失败: {e}")
            QMessageBox.critical(self, "错误", f"显示AI写作提示词设置时发生错误：{str(e)}")
    
    def _on_ai_prompt_config_saved(self, config: dict):
        """处理AI写作提示词配置保存"""
        try:
            # 提取设置数据
            selected_tags = config.get('selected_tags', [])
            advanced_settings = config.get('advanced_settings', {})
            
            # 应用配置到AI管理器
            if self._ai_manager:
                # 应用上下文模式
                if hasattr(self._ai_manager, 'set_context_mode'):
                    context_mode = advanced_settings.get('mode', 'balanced')
                    self._ai_manager.set_context_mode(context_mode)
                
                # 应用风格标签
                if hasattr(self._ai_manager, 'set_style_tags'):
                    self._ai_manager.set_style_tags(selected_tags)
                
                # 应用其他设置
                if hasattr(self._ai_manager, 'update_completion_settings'):
                    completion_settings = {
                        'temperature': advanced_settings.get('creativity', 0.5),
                        'max_length': advanced_settings.get('word_count', 300),
                        'auto_trigger': advanced_settings.get('auto_trigger', True),
                        'trigger_delay': advanced_settings.get('trigger_delay', 1000)
                    }
                    self._ai_manager.update_completion_settings(completion_settings)
                
                logger.info("AI写作配置已应用到AI管理器")
            
            # 批量保存配置到配置文件，避免多次保存
            if self._config:
                # 准备配置更新
                ai_config_updates = {
                    'context_mode': advanced_settings.get('mode', 'balanced'),
                    'style_tags': selected_tags,
                    'temperature': advanced_settings.get('creativity', 0.5),
                    'completion_length': advanced_settings.get('word_count', 300),
                    'auto_suggestions': advanced_settings.get('auto_trigger', True),
                    'completion_delay': advanced_settings.get('trigger_delay', 1000),
                    'rag_enabled': advanced_settings.get('rag_enabled', True),
                    'entity_detection': advanced_settings.get('entity_detection', True)
                }
                
                # 批量更新配置
                for key, value in ai_config_updates.items():
                    self._config.set('ai', key, value)
                
                # 一次性保存
                self._config.save()
                logger.info("AI写作提示词配置已保存到配置文件")
                
        except Exception as e:
            logger.error(f"应用AI写作提示词配置失败: {e}")
            QMessageBox.warning(self, "警告", f"保存配置时发生错误：{str(e)}")

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
            # 显示AI配置对话框
            if hasattr(self._ai_manager, 'show_config_dialog'):
                self._ai_manager.show_config_dialog(self)
            else:
                # fallback: 直接使用统一配置对话框
                from gui.ai.unified_ai_config_dialog import UnifiedAIConfigDialog
                dialog = UnifiedAIConfigDialog(self, self._config)
                if dialog.exec():
                    self._try_reinit_ai_manager()
                
        except Exception as e:
            logger.error(f"显示AI配置对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开AI配置对话框: {str(e)}")
    
    def _try_reinit_ai_manager(self):
        """尝试重新初始化AI管理器"""
        try:
            logger.info("开始重新初始化简化AI管理器")
            
            # 清理现有的AI管理器
            if self._ai_manager:
                try:
                    if hasattr(self._ai_manager, 'cleanup'):
                        self._ai_manager.cleanup()
                except Exception as e:
                    logger.warning(f"清理现有AI管理器失败: {e}")
            
            self._ai_manager = None
            self._ai_control_panel = None
            
            # 重新初始化增强AI管理器
            from gui.ai.enhanced_ai_manager import EnhancedAIManager
            self._ai_manager = EnhancedAIManager(self._config, self._shared, self)
            logger.info("增强AI管理器重新初始化成功")
            
            # 重新初始化控制面板
            if self._ai_manager:
                try:
                    from gui.ai.ai_completion_control import AICompletionControlPanel
                    self._ai_control_panel = AICompletionControlPanel(self)
                    self._shared.ai_manager = self._ai_manager
                    
                    # 重新注册Codex组件到共享对象（如果可用）
                    if self._codex_manager:
                        self._shared.codex_manager = self._codex_manager
                    if self._reference_detector:
                        self._shared.reference_detector = self._reference_detector
                    if self._prompt_function_registry:
                        self._shared.prompt_function_registry = self._prompt_function_registry
                    
                    logger.info("AI控制面板和共享对象重新初始化成功")
                except Exception as panel_error:
                    logger.warning(f"AI控制面板重新初始化失败: {panel_error}")
            
            return self._ai_manager is not None
                    
        except Exception as e:
            import traceback
            logger.error(f"重新初始化AI管理器失败: {e}")
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            self._ai_manager = None
            self._ai_control_panel = None
            return False
    
    # 复杂的模板选择器已被简化的AI写作设置替代
    # 用户现在可以通过AI菜单访问简化的标签化界面

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
    
    def _show_import_export_codex_dialog(self):
        """显示Codex数据导入导出对话框"""
        if not self._codex_manager:
            QMessageBox.warning(self, "警告", "Codex管理器未初始化")
            return
        
        try:
            dialog = ImportExportDialog(self._codex_manager, self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Failed to show import/export dialog: {e}")
            QMessageBox.critical(
                self, "错误", 
                f"无法打开导入导出对话框：\n{str(e)}\n\n请检查是否安装了所有必要的依赖包。"
            )
    
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
    @pyqtSlot(str, int, str)
    def _on_completion_requested(self, text: str, position: int, document_id: str):
        """处理来自编辑器的补全请求，转发给AI管理器"""
        if self._ai_manager:
            logger.debug(f"转发补全请求到AI管理器: text_length={len(text)}, position={position}, doc_id={document_id}")
            self._ai_manager.request_completion('manual')
        else:
            logger.warning("AI管理器不可用，无法处理补全请求")
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
            
        # 刷新Codex面板
        if hasattr(self, '_codex_panel') and self._codex_panel:
            try:
                if hasattr(self._codex_panel, '_refresh_entries'):
                    self._codex_panel._refresh_entries()
                logger.debug("Codex面板已刷新")
            except Exception as e:
                logger.error(f"刷新Codex面板失败: {e}")

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
            # 模板选择器已被简化的AI写作设置替代
            self._show_ai_writing_settings()
        elif action_id == "index_manager":
            self._show_index_manager()
        elif action_id == "batch_index":
            self._show_batch_index_dialog()
        elif action_id == "codex_manager":
            self._show_codex_manager()
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
    
    # _show_prompt_manager 已被统一的 _show_ai_prompt_settings 替代
    
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
            QMessageBox.critical(self, "错误", "无法加载AI配置对话框")
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
                # 使用简化的AI配置对话框
                self._ai_manager.show_config_dialog(parent=self)
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
                # 使用简化的AI配置对话框
                self._ai_manager.show_config_dialog(parent=self)
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
