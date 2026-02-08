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




class MainWindowIntegrationsMixin:
    """MainWindow mixin."""
    def _init_signals(self):
        self._shared.projectChanged.connect(self._on_project_changed)
        self._shared.themeChanged.connect(self._on_theme_changed)
        self._theme_manager.themeChanged.connect(self._on_theme_manager_changed)
        
        # 连接ProjectController的信号
        self._connect_controller_signals()
        
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
        if hasattr(self, "_index_scheduler") and self._index_scheduler and self._ai_manager:
            try:
                self._index_scheduler.schedule_document_index(document_id, content)
                logger.debug(f"Auto indexing scheduled via IndexScheduler: {document_id}")
            except Exception as e:
                logger.error(f"IndexScheduler自动索引失败: {e}")
    @pyqtSlot(str, str, dict)
    def _on_task_failed(self, key: str, error: str, details: dict):
        """任务失败统一入口（UI可见）"""
        logger.error(f"任务失败: {key} - {error}")
        if hasattr(self, "_status_bar"):
            self._status_bar.show_message(f"任务失败: {key} - {error}", 5000)
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
    def _on_theme_manager_changed(self, theme: str):
        pass
    @pyqtSlot(str)
    def _on_text_statistics_changed(self, text: str):
        pass
    @pyqtSlot(int, int)
    def _on_cursor_position_changed(self, line: int, column: int):
        pass
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

