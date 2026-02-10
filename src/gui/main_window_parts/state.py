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




class MainWindowStateMixin:
    """MainWindow mixin."""
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
    def _restore_project_from_backup(self):
        """从备份目录恢复当前项目数据库。"""
        project = self._project_manager.get_current_project()
        if not project or not project.project_path:
            QMessageBox.warning(self, "恢复失败", "请先打开一个项目再执行恢复。")
            return

        project_path = Path(project.project_path)
        backup_root = project_path / "backups"
        initial_dir = str(backup_root) if backup_root.exists() else str(project_path)

        backup_dir = QFileDialog.getExistingDirectory(self, "选择备份目录", initial_dir)
        if not backup_dir:
            return

        try:
            from core.backup_service import restore_backup_set, BackupServiceError
            restore_backup_set(project_path, Path(backup_dir))
        except BackupServiceError as exc:
            logger.error("Restore backup failed: %s", exc)
            QMessageBox.critical(self, "恢复失败", f"恢复备份失败：\n{exc}")
            return
        except Exception as exc:
            logger.exception("Unexpected restore failure")
            QMessageBox.critical(self, "恢复失败", f"恢复备份时发生异常：\n{exc}")
            return

        if self._project_manager.open_project(str(project_path)):
            self._project_controller.project_opened.emit(str(project_path))
            self._project_controller.project_structure_changed.emit()

        QMessageBox.information(self, "恢复完成", "备份恢复完成，项目已重新载入。")
    def closeEvent(self, event: QCloseEvent):
        logger.info("主窗口关闭事件触发")
        
        # 保存窗口和布局状态
        self._save_window_state()
        self._save_layout_state()

        # Flush editor buffers (project docs + scratch recovery) before closing the project DB.
        try:
            editor_panel = getattr(self, "_editor_panel", None)
            if editor_panel and hasattr(editor_panel, "flush_all_editors"):
                editor_panel.flush_all_editors()
        except Exception:
            logger.exception("Failed to flush editors before close; continuing")
        
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

