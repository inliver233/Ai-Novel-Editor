"""
导入对话框
提供文件导入功能的用户界面
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QCheckBox,
    QGroupBox, QFileDialog, QMessageBox, QProgressBar,
    QLabel, QDialogButtonBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread

from core.import_manager import ImportManager, ImportFormat, ImportOptions

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.project import ProjectManager

logger = logging.getLogger(__name__)


class ImportWorker(QThread):
    """导入工作线程"""
    
    def __init__(self, import_manager: ImportManager, options: ImportOptions):
        super().__init__()
        self.import_manager = import_manager
        self.options = options
        self.success = False
        
    def run(self):
        """执行导入"""
        self.success = self.import_manager.import_content(self.options)


class ImportDialog(QDialog):
    """导入对话框"""
    
    def __init__(self, project_manager: 'ProjectManager', parent=None):
        super().__init__(parent)
        
        self._project_manager = project_manager
        self._import_manager = ImportManager(project_manager)
        self._import_worker = None
        
        self._init_ui()
        self._setup_connections()
        self._update_format_options()
        
        self.setWindowTitle("导入文件")
        self.resize(500, 450)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 文件选择
        file_group = QGroupBox("选择文件")
        file_layout = QHBoxLayout(file_group)
        
        self._file_path_edit = QLineEdit()
        self._file_path_edit.setPlaceholderText("选择要导入的文件...")
        file_layout.addWidget(self._file_path_edit)
        
        self._browse_btn = QPushButton("浏览...")
        file_layout.addWidget(self._browse_btn)
        
        layout.addWidget(file_group)
        
        # 导入格式
        format_group = QGroupBox("导入格式")
        format_layout = QFormLayout(format_group)
        
        self._format_combo = QComboBox()
        self._format_combo.addItems([
            "纯文本 (.txt)",
            "Markdown (.md)",
            "Word文档 (.docx)"
        ])
        format_layout.addRow("文件格式:", self._format_combo)
        
        layout.addWidget(format_group)
        
        # 导入选项
        options_group = QGroupBox("导入选项")
        options_layout = QVBoxLayout(options_group)
        
        self._split_chapters_check = QCheckBox("自动识别并分割章节")
        self._split_chapters_check.setChecked(True)
        options_layout.addWidget(self._split_chapters_check)
        
        self._create_project_check = QCheckBox("创建新项目")
        self._create_project_check.setChecked(False)
        options_layout.addWidget(self._create_project_check)
        
        # 章节识别模式
        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel("章节模式:"))
        self._chapter_pattern_edit = QLineEdit()
        self._chapter_pattern_edit.setText(r"^第[一二三四五六七八九十\d]+章")
        self._chapter_pattern_edit.setToolTip("正则表达式，用于识别章节标题")
        pattern_layout.addWidget(self._chapter_pattern_edit)
        options_layout.addLayout(pattern_layout)
        
        layout.addWidget(options_group)
        
        # 预览区
        preview_group = QGroupBox("文件预览")
        preview_layout = QVBoxLayout(preview_group)
        
        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumHeight(100)
        self._preview_text.setPlaceholderText("选择文件后将显示预览...")
        preview_layout.addWidget(self._preview_text)
        
        layout.addWidget(preview_group)
        
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
        self._import_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._import_btn.setText("导入")
        self._cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        self._cancel_btn.setText("取消")
        
        layout.addWidget(button_box)
        
        # 连接按钮信号
        button_box.accepted.connect(self._on_import)
        button_box.rejected.connect(self.reject)
    
    def _setup_connections(self):
        """设置信号连接"""
        self._browse_btn.clicked.connect(self._browse_file)
        self._format_combo.currentIndexChanged.connect(self._update_format_options)
        self._split_chapters_check.toggled.connect(self._on_split_chapters_toggled)
        
        # 连接导入管理器信号
        self._import_manager.importStarted.connect(self._on_import_started)
        self._import_manager.importProgress.connect(self._on_import_progress)
        self._import_manager.importCompleted.connect(self._on_import_completed)
        self._import_manager.importError.connect(self._on_import_error)
    
    def _update_format_options(self):
        """更新格式相关选项"""
        # 可以根据格式调整选项
        pass
    
    def _on_split_chapters_toggled(self, checked: bool):
        """章节分割选项切换"""
        self._chapter_pattern_edit.setEnabled(checked)
    
    def _browse_file(self):
        """浏览文件"""
        format_index = self._format_combo.currentIndex()
        
        # 根据格式设置文件过滤器
        filters = {
            0: "文本文件 (*.txt)",
            1: "Markdown文件 (*.md *.markdown)",
            2: "Word文档 (*.docx)"
        }
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要导入的文件",
            str(Path.home()),
            filters.get(format_index, "所有文件 (*.*)")
        )
        
        if file_path:
            self._file_path_edit.setText(file_path)
            self._preview_file(file_path)
    
    def _preview_file(self, file_path: str):
        """预览文件内容"""
        try:
            path = Path(file_path)
            if not path.exists():
                return
            
            # 读取前1000个字符作为预览
            with open(path, 'r', encoding='utf-8') as f:
                preview = f.read(1000)
                if len(preview) == 1000:
                    preview += "\n..."
                
                self._preview_text.setPlainText(preview)
                
        except Exception as e:
            self._preview_text.setPlainText(f"无法预览文件: {e}")
    
    def _on_import(self):
        """执行导入"""
        # 验证输入
        if not self._file_path_edit.text():
            QMessageBox.warning(self, "警告", "请选择要导入的文件")
            return
        
        file_path = Path(self._file_path_edit.text())
        if not file_path.exists():
            QMessageBox.warning(self, "警告", "文件不存在")
            return
        
        # 创建导入选项
        format_map = {
            0: ImportFormat.TEXT,
            1: ImportFormat.MARKDOWN,
            2: ImportFormat.DOCX
        }
        
        options = ImportOptions(
            format=format_map[self._format_combo.currentIndex()],
            input_path=file_path,
            split_chapters=self._split_chapters_check.isChecked(),
            chapter_pattern=self._chapter_pattern_edit.text(),
            create_project=self._create_project_check.isChecked(),
            project_name=file_path.stem if self._create_project_check.isChecked() else None
        )
        
        # 禁用控件
        self._set_ui_enabled(False)
        
        # 创建并启动工作线程
        self._import_worker = ImportWorker(self._import_manager, options)
        self._import_worker.finished.connect(self._on_worker_finished)
        self._import_worker.start()
    
    def _set_ui_enabled(self, enabled: bool):
        """设置UI启用状态"""
        self._file_path_edit.setEnabled(enabled)
        self._browse_btn.setEnabled(enabled)
        self._format_combo.setEnabled(enabled)
        self._split_chapters_check.setEnabled(enabled)
        self._create_project_check.setEnabled(enabled)
        self._chapter_pattern_edit.setEnabled(enabled and self._split_chapters_check.isChecked())
        self._import_btn.setEnabled(enabled)
        
        # 显示/隐藏进度条和状态
        self._progress_bar.setVisible(not enabled)
        self._status_label.setVisible(not enabled)
    
    @pyqtSlot(str)
    def _on_import_started(self, message: str):
        """导入开始"""
        self._status_label.setText(message)
        self._progress_bar.setValue(0)
        logger.info(f"导入开始: {message}")
    
    @pyqtSlot(int, int)
    def _on_import_progress(self, current: int, total: int):
        """导入进度更新"""
        if total > 0:
            progress = int(current * 100 / total)
            self._progress_bar.setValue(progress)
            self._status_label.setText(f"正在导入... ({current}/{total})")
    
    @pyqtSlot(int)
    def _on_import_completed(self, count: int):
        """导入完成"""
        self._progress_bar.setValue(100)
        self._status_label.setText(f"导入完成！共导入 {count} 个文档")
        logger.info(f"导入完成: {count} 个文档")
        
        QMessageBox.information(
            self,
            "导入完成",
            f"成功导入 {count} 个文档到项目中。"
        )
    
    @pyqtSlot(str)
    def _on_import_error(self, error: str):
        """导入错误"""
        self._status_label.setText(f"导入失败: {error}")
        logger.error(f"导入失败: {error}")
        QMessageBox.critical(self, "导入失败", error)
    
    def _on_worker_finished(self):
        """工作线程完成"""
        self._set_ui_enabled(True)
        
        if self._import_worker and self._import_worker.success:
            self.accept()
        
        self._import_worker = None