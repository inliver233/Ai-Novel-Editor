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




class MainWindowDialogsMixin:
    """MainWindow mixin."""
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
                
                # 批量更新配置（避免每次 set 都落盘）
                with self._config.batch_update():
                    for key, value in ai_config_updates.items():
                        self._config.set('ai', key, value)
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
                self, "RAG 未启用",
                "RAG 向量搜索服务未启用/未初始化，可能需要配置。\n" +
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
                self, "RAG 未启用",
                "RAG 向量搜索服务未启用/未初始化，需要先配置 RAG 服务。\n" +
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

