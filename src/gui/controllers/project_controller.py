# src/gui/controllers/project_controller.py

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from pathlib import Path
import logging

from core.project import ProjectManager
from core.config import Config

logger = logging.getLogger(__name__)

class ProjectController(QObject):
    """
    处理所有与项目相关的业务逻辑，如创建、打开、保存等。
    """
    # 信号，用于通知UI更新
    # 信号，用于通知UI更新
    project_opened = pyqtSignal(str)  # 传递项目路径
    project_closed = pyqtSignal()
    status_message_changed = pyqtSignal(str)
    # 信号，当需要刷新项目树或概念时发出
    project_structure_changed = pyqtSignal()

    def __init__(self, project_manager: ProjectManager, config: Config, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config = config

    @pyqtSlot()
    def on_create_project(self):
        """处理创建新项目的逻辑"""
        parent_widget = self.parent() if self.parent() else None
        name, ok = QInputDialog.getText(parent_widget, "新建项目", "请输入项目名称:")
        if not ok or not name.strip():
            return
        
        project_dir = QFileDialog.getExistingDirectory(parent_widget, "选择项目保存位置")
        if not project_dir:
            return

        project_path = Path(project_dir) / name.strip()
        if self.project_manager.create_project(name=name.strip(), path=str(project_path)):
            self.status_message_changed.emit(f"项目 '{name}' 创建成功！")
            QMessageBox.information(parent_widget, "成功", f"项目 '{name}' 创建成功！")
            self.project_structure_changed.emit()
        else:
            self.status_message_changed.emit("项目创建失败！")
            QMessageBox.critical(parent_widget, "错误", "项目创建失败！")

    @pyqtSlot()
    def on_open_project(self):
        """处理打开项目的逻辑"""
        parent_widget = self.parent() if self.parent() else None
        project_dir = QFileDialog.getExistingDirectory(parent_widget, "打开项目目录")
        if not project_dir:
            return

        db_file = Path(project_dir) / "project.db"
        if not db_file.exists():
            QMessageBox.critical(parent_widget, "错误", f"项目数据库 'project.db' 未找到于:\n{project_dir}")
            return

        if self.project_manager.open_project(project_dir):
            project = self.project_manager.get_current_project()
            if project:
                self.status_message_changed.emit(f"项目 '{project.name}' 打开成功！")
                QMessageBox.information(parent_widget, "成功", f"项目 '{project.name}' 打开成功！")
                self.project_opened.emit(project.project_path)
                self.project_structure_changed.emit()
        else:
            self.status_message_changed.emit("项目打开失败！")
            QMessageBox.critical(parent_widget, "错误", "项目打开失败！")

    @pyqtSlot()
    def on_save_project(self):
        """处理保存项目的逻辑"""
        # 注意：当前主窗口的保存逻辑是保存单个文件，而非整个项目。
        # 此处暂时留空，因为项目级的保存应该是自动的或通过特定机制触发。
        # 我们将在后续任务中明确项目保存策略。
        logger.warning("on_save_project is not fully implemented yet. Project save is handled differently.")
        self.status_message_changed.emit("项目保存功能正在设计中。")
        # 实际的文档保存逻辑应该由 EditorController 处理。

    @pyqtSlot()
    def on_save_project_as(self):
        """处理项目另存为的逻辑"""
        logger.warning("on_save_project_as is not implemented yet.")
        self.status_message_changed.emit("项目另存为功能尚未实现。")

    @pyqtSlot()
    def on_close_project(self):
        """处理关闭项目的逻辑"""
        if self.project_manager.close_project():
            self.status_message_changed.emit("项目已关闭。")
            self.project_closed.emit()
            return True
        else:
            parent_widget = self.parent() if self.parent() else None
            reply = QMessageBox.question(parent_widget, "确认", "保存项目失败，确定要关闭吗？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.project_closed.emit()
                return True
        return False