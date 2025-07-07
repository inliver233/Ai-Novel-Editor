"""
导出对话框
提供项目导出功能的用户界面
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QCheckBox,
    QGroupBox, QFileDialog, QMessageBox, QProgressBar,
    QLabel, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread

from core.export_manager import ExportManager, ExportFormat, ExportOptions

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.project import ProjectManager

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    """导出工作线程"""
    
    def __init__(self, export_manager: ExportManager, options: ExportOptions):
        super().__init__()
        self.export_manager = export_manager
        self.options = options
        self.success = False
        
    def run(self):
        """执行导出"""
        self.success = self.export_manager.export_project(self.options)


class ExportDialog(QDialog):
    """导出对话框"""
    
    def __init__(self, project_manager: 'ProjectManager', parent=None):
        super().__init__(parent)
        
        self._project_manager = project_manager
        self._export_manager = ExportManager(project_manager)
        self._export_worker = None
        
        self._init_ui()
        self._setup_connections()
        self._update_format_options()
        
        self.setWindowTitle("导出项目")
        self.resize(500, 400)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 导出格式选择
        format_group = QGroupBox("导出格式")
        format_layout = QFormLayout(format_group)
        
        self._format_combo = QComboBox()
        self._format_combo.addItems([
            "纯文本 (.txt)",
            "Markdown (.md)",
            "Word文档 (.docx)",
            "PDF文档 (.pdf)",
            "HTML网页 (.html)"
        ])
        format_layout.addRow("文件格式:", self._format_combo)
        
        layout.addWidget(format_group)
        
        # 导出选项
        options_group = QGroupBox("导出选项")
        options_layout = QVBoxLayout(options_group)
        
        self._include_metadata_check = QCheckBox("包含标题和作者信息")
        self._include_metadata_check.setChecked(True)
        options_layout.addWidget(self._include_metadata_check)
        
        self._preserve_formatting_check = QCheckBox("保留格式")
        self._preserve_formatting_check.setChecked(True)
        options_layout.addWidget(self._preserve_formatting_check)
        
        layout.addWidget(options_group)
        
        # 文件路径选择
        path_group = QGroupBox("输出路径")
        path_layout = QHBoxLayout(path_group)
        
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("选择导出文件路径...")
        path_layout.addWidget(self._path_edit)
        
        self._browse_btn = QPushButton("浏览...")
        path_layout.addWidget(self._browse_btn)
        
        layout.addWidget(path_group)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # 状态标签
        self._status_label = QLabel("")
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        self._export_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._export_btn.setText("导出")
        self._cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        self._cancel_btn.setText("取消")
        
        layout.addWidget(button_box)
        
        # 连接按钮信号
        button_box.accepted.connect(self._on_export)
        button_box.rejected.connect(self.reject)
    
    def _setup_connections(self):
        """设置信号连接"""
        self._format_combo.currentIndexChanged.connect(self._update_format_options)
        self._browse_btn.clicked.connect(self._browse_output_path)
        
        # 连接导出管理器信号
        self._export_manager.exportStarted.connect(self._on_export_started)
        self._export_manager.exportProgress.connect(self._on_export_progress)
        self._export_manager.exportCompleted.connect(self._on_export_completed)
        self._export_manager.exportError.connect(self._on_export_error)
    
    def _update_format_options(self):
        """更新格式相关选项"""
        format_index = self._format_combo.currentIndex()
        
        # 某些格式不支持格式保留
        if format_index == 0:  # 纯文本
            self._preserve_formatting_check.setEnabled(False)
            self._preserve_formatting_check.setChecked(False)
        else:
            self._preserve_formatting_check.setEnabled(True)
            self._preserve_formatting_check.setChecked(True)
    
    def _browse_output_path(self):
        """浏览输出路径"""
        format_index = self._format_combo.currentIndex()
        
        # 根据格式设置文件过滤器
        filters = [
            "文本文件 (*.txt)",
            "Markdown文件 (*.md)",
            "Word文档 (*.docx)",
            "PDF文档 (*.pdf)",
            "HTML文件 (*.html)"
        ]
        
        extensions = [".txt", ".md", ".docx", ".pdf", ".html"]
        
        # 获取项目名称作为默认文件名
        project = self._project_manager.get_current_project()
        default_name = project.name if project else "导出文档"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择导出路径",
            str(Path.home() / f"{default_name}{extensions[format_index]}"),
            filters[format_index]
        )
        
        if file_path:
            self._path_edit.setText(file_path)
    
    def _on_export(self):
        """执行导出"""
        # 验证输入
        if not self._path_edit.text():
            QMessageBox.warning(self, "警告", "请选择输出路径")
            return
        
        # 获取当前项目
        project = self._project_manager.get_current_project()
        if not project:
            QMessageBox.warning(self, "警告", "没有打开的项目")
            return
        
        # 创建导出选项
        format_map = {
            0: ExportFormat.TEXT,
            1: ExportFormat.MARKDOWN,
            2: ExportFormat.DOCX,
            3: ExportFormat.PDF,
            4: ExportFormat.HTML
        }
        
        options = ExportOptions(
            format=format_map[self._format_combo.currentIndex()],
            output_path=Path(self._path_edit.text()),
            include_metadata=self._include_metadata_check.isChecked(),
            preserve_formatting=self._preserve_formatting_check.isChecked(),
            title=project.name,
            author=project.author
        )
        
        # 禁用控件
        self._set_ui_enabled(False)
        
        # 创建并启动工作线程
        self._export_worker = ExportWorker(self._export_manager, options)
        self._export_worker.finished.connect(self._on_worker_finished)
        self._export_worker.start()
    
    def _set_ui_enabled(self, enabled: bool):
        """设置UI启用状态"""
        self._format_combo.setEnabled(enabled)
        self._path_edit.setEnabled(enabled)
        self._browse_btn.setEnabled(enabled)
        self._include_metadata_check.setEnabled(enabled)
        self._preserve_formatting_check.setEnabled(enabled)
        self._export_btn.setEnabled(enabled)
        
        # 显示/隐藏进度条和状态
        self._progress_bar.setVisible(not enabled)
        self._status_label.setVisible(not enabled)
    
    @pyqtSlot(str)
    def _on_export_started(self, message: str):
        """导出开始"""
        self._status_label.setText(message)
        self._progress_bar.setValue(0)
        logger.info(f"导出开始: {message}")
    
    @pyqtSlot(int, int)
    def _on_export_progress(self, current: int, total: int):
        """导出进度更新"""
        if total > 0:
            progress = int(current * 100 / total)
            self._progress_bar.setValue(progress)
            self._status_label.setText(f"正在导出... ({current}/{total})")
    
    @pyqtSlot(str)
    def _on_export_completed(self, output_path: str):
        """导出完成"""
        self._progress_bar.setValue(100)
        self._status_label.setText("导出完成！")
        logger.info(f"导出完成: {output_path}")
        
        # 询问是否打开文件
        reply = QMessageBox.question(
            self,
            "导出完成",
            f"文件已导出到:\n{output_path}\n\n是否打开文件？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            import os
            import platform
            
            try:
                if platform.system() == 'Windows':
                    os.startfile(output_path)
                elif platform.system() == 'Darwin':  # macOS
                    os.system(f'open "{output_path}"')
                else:  # Linux
                    os.system(f'xdg-open "{output_path}"')
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法打开文件: {e}")
        
        # 导出成功后关闭对话框
        self.accept()
    
    @pyqtSlot(str)
    def _on_export_error(self, error: str):
        """导出错误"""
        self._status_label.setText(f"导出失败: {error}")
        logger.error(f"导出失败: {error}")
        QMessageBox.critical(self, "导出失败", error)
    
    def _on_worker_finished(self):
        """工作线程完成"""
        self._set_ui_enabled(True)
        
        if self._export_worker:
            if self._export_worker.success:
                # 如果成功，对话框保持打开状态，但状态已更新
                logger.info("导出成功完成")
            else:
                # 如果失败，显示错误信息但不关闭对话框
                logger.warning("导出过程中出现错误")
        
        self._export_worker = None