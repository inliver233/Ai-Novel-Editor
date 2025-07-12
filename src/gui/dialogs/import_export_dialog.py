"""
导入导出对话框
提供用户友好的导入导出界面
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QMovie
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                           QWidget, QLabel, QPushButton, QComboBox, QCheckBox,
                           QProgressBar, QTextEdit, QGroupBox, QGridLayout,
                           QFileDialog, QMessageBox, QSplitter, QFrame,
                           QListWidget, QListWidgetItem, QSpacerItem, QSizePolicy)

from core.import_export_engine import (ImportExportEngine, ExportFormat, 
                                       ImportMode, ImportResult, ExportResult)

logger = logging.getLogger(__name__)


class ImportExportWorker(QThread):
    """导入导出工作线程"""
    
    progressChanged = pyqtSignal(int, str)  # 进度, 状态消息
    resultReady = pyqtSignal(object)  # 结果对象
    errorOccurred = pyqtSignal(str)  # 错误消息
    
    def __init__(self, operation_type: str, engine: ImportExportEngine, **kwargs):
        super().__init__()
        self.operation_type = operation_type
        self.engine = engine
        self.kwargs = kwargs
        self.is_cancelled = False
    
    def run(self):
        """执行操作"""
        try:
            if self.operation_type == "export":
                result = self.engine.export_codex_data(**self.kwargs)
            elif self.operation_type == "import":
                result = self.engine.import_codex_data(**self.kwargs)
            elif self.operation_type == "backup":
                result = self.engine.create_backup(**self.kwargs)
            elif self.operation_type == "restore":
                result = self.engine.restore_backup(**self.kwargs)
            else:
                raise ValueError(f"Unknown operation: {self.operation_type}")
            
            if not self.is_cancelled:
                self.resultReady.emit(result)
                
        except Exception as e:
            if not self.is_cancelled:
                self.errorOccurred.emit(str(e))
    
    def cancel(self):
        """取消操作"""
        self.is_cancelled = True
        self.engine.progress_reporter.cancel()


class ImportTab(QWidget):
    """导入标签页"""
    
    def __init__(self, engine: ImportExportEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.worker = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 文件选择组
        file_group = QGroupBox("选择导入文件")
        file_layout = QGridLayout(file_group)
        
        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setStyleSheet("QLabel { background: #f0f0f0; padding: 8px; border-radius: 4px; }")
        
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self._browse_file)
        
        file_layout.addWidget(QLabel("文件路径:"), 0, 0)
        file_layout.addWidget(self.file_path_label, 0, 1)
        file_layout.addWidget(self.browse_button, 0, 2)
        
        layout.addWidget(file_group)
        
        # 导入选项组
        options_group = QGroupBox("导入选项")
        options_layout = QGridLayout(options_group)
        
        # 导入模式
        options_layout.addWidget(QLabel("导入模式:"), 0, 0)
        self.import_mode_combo = QComboBox()
        for mode in ImportMode:
            self.import_mode_combo.addItem(mode.name, mode)
        options_layout.addWidget(self.import_mode_combo, 0, 1)
        
        # 自动修复
        self.auto_fix_check = QCheckBox("自动修复数据错误")
        self.auto_fix_check.setChecked(True)
        options_layout.addWidget(self.auto_fix_check, 1, 0, 1, 2)
        
        # 备份现有数据
        self.backup_check = QCheckBox("导入前备份现有数据")
        self.backup_check.setChecked(True)
        options_layout.addWidget(self.backup_check, 2, 0, 1, 2)
        
        layout.addWidget(options_group)
        
        # 预览区域
        preview_group = QGroupBox("文件预览")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        # 进度区域
        progress_group = QGroupBox("导入进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(progress_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.import_button = QPushButton("开始导入")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._start_import)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_import)
        
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.engine.progress_reporter.progress.connect(self.progress_bar.setValue)
        self.engine.progress_reporter.status.connect(self.progress_label.setText)
    
    def _browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择导入文件", "",
            "所有支持格式 (*.json *.csv *.backup *.zip);;JSON文件 (*.json);;CSV文件 (*.csv);;备份文件 (*.backup *.zip)"
        )
        
        if file_path:
            self.file_path_label.setText(file_path)
            self.import_button.setEnabled(True)
            self._preview_file(file_path)
    
    def _preview_file(self, file_path: str):
        """预览文件"""
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            preview_text = f"文件名: {file_name}\n"
            preview_text += f"文件大小: {file_size / 1024:.1f} KB\n"
            preview_text += f"文件类型: {Path(file_path).suffix}\n\n"
            
            # 如果是文本文件，显示前几行
            if file_path.lower().endswith(('.json', '.csv')):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:10]
                        preview_text += "文件预览:\n" + "".join(lines)
                        if len(lines) == 10:
                            preview_text += "\n... (文件内容更多)"
                except:
                    preview_text += "无法预览文件内容"
            
            self.preview_text.setPlainText(preview_text)
            
        except Exception as e:
            self.preview_text.setPlainText(f"预览错误: {e}")
    
    def _start_import(self):
        """开始导入"""
        file_path = self.file_path_label.text()
        if file_path == "未选择文件":
            return
        
        # 获取选项
        import_mode = self.import_mode_combo.currentData()
        auto_fix = self.auto_fix_check.isChecked()
        
        # 如果需要备份
        if self.backup_check.isChecked():
            self._create_backup_before_import()
        
        # 启动工作线程
        self.worker = ImportExportWorker(
            "import", self.engine,
            file_path=file_path,
            import_mode=import_mode,
            auto_fix=auto_fix
        )
        
        self.worker.resultReady.connect(self._on_import_finished)
        self.worker.errorOccurred.connect(self._on_import_error)
        
        self.worker.start()
        
        # 更新UI状态
        self.import_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_label.setText("开始导入...")
    
    def _create_backup_before_import(self):
        """导入前创建备份"""
        try:
            from datetime import datetime
            backup_path = f"backup_before_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup"
            self.engine.create_backup(backup_path)
            logger.info(f"Backup created before import: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to create backup before import: {e}")
    
    def _cancel_import(self):
        """取消导入"""
        if self.worker:
            self.worker.cancel()
            self.worker.wait()
        
        self._reset_ui()
    
    def _on_import_finished(self, result: ImportResult):
        """导入完成"""
        self._reset_ui()
        
        if result.success:
            message = f"导入成功！\n\n"
            message += f"导入条目数: {result.imported_count}\n"
            if result.skipped_count > 0:
                message += f"跳过条目数: {result.skipped_count}\n"
            if result.conflicts_resolved > 0:
                message += f"解决冲突数: {result.conflicts_resolved}\n"
            
            if result.validation_result and result.validation_result.fixed_issues:
                message += f"\n自动修复问题:\n"
                for issue in result.validation_result.fixed_issues[:5]:
                    message += f"• {issue}\n"
            
            QMessageBox.information(self, "导入成功", message)
        else:
            error_message = "导入失败:\n\n" + "\n".join(result.errors)
            QMessageBox.warning(self, "导入失败", error_message)
    
    def _on_import_error(self, error_message: str):
        """导入错误"""
        self._reset_ui()
        QMessageBox.critical(self, "导入错误", f"导入过程中发生错误:\n\n{error_message}")
    
    def _reset_ui(self):
        """重置UI状态"""
        self.import_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")


class ExportTab(QWidget):
    """导出标签页"""
    
    def __init__(self, engine: ImportExportEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.worker = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 导出选项组
        options_group = QGroupBox("导出选项")
        options_layout = QGridLayout(options_group)
        
        # 导出格式
        options_layout.addWidget(QLabel("导出格式:"), 0, 0)
        self.format_combo = QComboBox()
        for fmt in self.engine.get_supported_formats():
            self.format_combo.addItem(fmt.value.upper(), fmt)
        options_layout.addWidget(self.format_combo, 0, 1)
        
        # 文件路径
        options_layout.addWidget(QLabel("保存到:"), 1, 0)
        self.file_path_label = QLabel("未选择路径")
        self.file_path_label.setStyleSheet("QLabel { background: #f0f0f0; padding: 8px; border-radius: 4px; }")
        
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self._browse_save_path)
        
        options_layout.addWidget(self.file_path_label, 1, 1)
        options_layout.addWidget(self.browse_button, 1, 2)
        
        layout.addWidget(options_group)
        
        # 高级选项组
        advanced_group = QGroupBox("高级选项")
        advanced_layout = QVBoxLayout(advanced_group)
        
        # 包含元数据
        self.include_metadata_check = QCheckBox("包含详细元数据")
        self.include_metadata_check.setChecked(True)
        advanced_layout.addWidget(self.include_metadata_check)
        
        # 压缩输出
        self.compress_check = QCheckBox("压缩输出文件")
        self.compress_check.setChecked(False)
        advanced_layout.addWidget(self.compress_check)
        
        layout.addWidget(advanced_group)
        
        # 数据预览组
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        
        # 统计信息
        self.stats_label = QLabel()
        self._update_stats()
        preview_layout.addWidget(self.stats_label)
        
        # 条目列表
        self.entry_list = QListWidget()
        self.entry_list.setMaximumHeight(120)
        self._update_entry_list()
        preview_layout.addWidget(self.entry_list)
        
        layout.addWidget(preview_group)
        
        # 进度区域
        progress_group = QGroupBox("导出进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(progress_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.export_button = QPushButton("开始导出")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._start_export)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_export)
        
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.engine.progress_reporter.progress.connect(self.progress_bar.setValue)
        self.engine.progress_reporter.status.connect(self.progress_label.setText)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
    
    def _update_stats(self):
        """更新统计信息"""
        if self.engine.codex_manager:
            entries = self.engine.codex_manager.get_all_entries()
            total_count = len(entries)
            
            # 按类型统计
            type_counts = {}
            for entry in entries:
                entry_type = entry.entry_type.value
                type_counts[entry_type] = type_counts.get(entry_type, 0) + 1
            
            stats_text = f"总条目数: {total_count}\n"
            for entry_type, count in type_counts.items():
                stats_text += f"{entry_type}: {count} "
            
            self.stats_label.setText(stats_text)
        else:
            self.stats_label.setText("无数据可导出")
    
    def _update_entry_list(self):
        """更新条目列表"""
        self.entry_list.clear()
        
        if self.engine.codex_manager:
            entries = self.engine.codex_manager.get_all_entries()
            for entry in entries[:10]:  # 只显示前10个
                item_text = f"{entry.title} ({entry.entry_type.value})"
                self.entry_list.addItem(item_text)
            
            if len(entries) > 10:
                self.entry_list.addItem(f"... 还有 {len(entries) - 10} 个条目")
    
    def _browse_save_path(self):
        """浏览保存路径"""
        export_format = self.format_combo.currentData()
        if not export_format:
            return
        
        # 根据格式确定文件扩展名
        extension = export_format.value
        filter_text = f"{extension.upper()} 文件 (*.{extension})"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择保存位置", f"codex_export.{extension}", filter_text
        )
        
        if file_path:
            self.file_path_label.setText(file_path)
            self.export_button.setEnabled(True)
    
    def _on_format_changed(self):
        """格式改变"""
        # 重置文件路径
        self.file_path_label.setText("未选择路径")
        self.export_button.setEnabled(False)
    
    def _start_export(self):
        """开始导出"""
        file_path = self.file_path_label.text()
        if file_path == "未选择路径":
            return
        
        export_format = self.format_combo.currentData()
        if not export_format:
            return
        
        # 获取选项
        include_metadata = self.include_metadata_check.isChecked()
        compress = self.compress_check.isChecked()
        
        # 启动工作线程
        self.worker = ImportExportWorker(
            "export", self.engine,
            file_path=file_path,
            export_format=export_format,
            include_metadata=include_metadata,
            compress=compress
        )
        
        self.worker.resultReady.connect(self._on_export_finished)
        self.worker.errorOccurred.connect(self._on_export_error)
        
        self.worker.start()
        
        # 更新UI状态
        self.export_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_label.setText("开始导出...")
    
    def _cancel_export(self):
        """取消导出"""
        if self.worker:
            self.worker.cancel()
            self.worker.wait()
        
        self._reset_ui()
    
    def _on_export_finished(self, result: ExportResult):
        """导出完成"""
        self._reset_ui()
        
        if result.success:
            message = f"导出成功！\n\n"
            message += f"导出条目数: {result.exported_count}\n"
            message += f"文件大小: {result.file_size_mb:.2f} MB\n"
            message += f"保存位置: {result.file_path}"
            
            QMessageBox.information(self, "导出成功", message)
        else:
            error_message = "导出失败:\n\n" + "\n".join(result.errors)
            QMessageBox.warning(self, "导出失败", error_message)
    
    def _on_export_error(self, error_message: str):
        """导出错误"""
        self._reset_ui()
        QMessageBox.critical(self, "导出错误", f"导出过程中发生错误:\n\n{error_message}")
    
    def _reset_ui(self):
        """重置UI状态"""
        self.export_button.setEnabled(self.file_path_label.text() != "未选择路径")
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")


class BackupTab(QWidget):
    """备份标签页"""
    
    def __init__(self, engine: ImportExportEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.worker = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建备份组
        backup_group = QGroupBox("创建备份")
        backup_layout = QVBoxLayout(backup_group)
        
        backup_desc = QLabel("创建包含所有Codex数据、配置和数据库的完整备份")
        backup_desc.setWordWrap(True)
        backup_layout.addWidget(backup_desc)
        
        backup_button_layout = QHBoxLayout()
        backup_button_layout.addStretch()
        
        self.create_backup_button = QPushButton("创建备份")
        self.create_backup_button.clicked.connect(self._create_backup)
        backup_button_layout.addWidget(self.create_backup_button)
        
        backup_layout.addLayout(backup_button_layout)
        layout.addWidget(backup_group)
        
        # 恢复备份组
        restore_group = QGroupBox("恢复备份")
        restore_layout = QGridLayout(restore_group)
        
        restore_desc = QLabel("从备份文件恢复所有数据（将覆盖当前数据）")
        restore_desc.setWordWrap(True)
        restore_layout.addWidget(restore_desc, 0, 0, 1, 3)
        
        restore_layout.addWidget(QLabel("备份文件:"), 1, 0)
        self.backup_file_label = QLabel("未选择文件")
        self.backup_file_label.setStyleSheet("QLabel { background: #f0f0f0; padding: 8px; border-radius: 4px; }")
        
        self.browse_backup_button = QPushButton("浏览...")
        self.browse_backup_button.clicked.connect(self._browse_backup_file)
        
        restore_layout.addWidget(self.backup_file_label, 1, 1)
        restore_layout.addWidget(self.browse_backup_button, 1, 2)
        
        # 恢复选项
        self.restore_database_check = QCheckBox("恢复数据库文件")
        self.restore_database_check.setChecked(True)
        restore_layout.addWidget(self.restore_database_check, 2, 0, 1, 3)
        
        restore_button_layout = QHBoxLayout()
        restore_button_layout.addStretch()
        
        self.restore_backup_button = QPushButton("恢复备份")
        self.restore_backup_button.setEnabled(False)
        self.restore_backup_button.clicked.connect(self._restore_backup)
        restore_button_layout.addWidget(self.restore_backup_button)
        
        restore_layout.addLayout(restore_button_layout, 3, 0, 1, 3)
        layout.addWidget(restore_group)
        
        # 进度区域
        progress_group = QGroupBox("操作进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(progress_group)
        
        # 添加弹簧
        layout.addStretch()
    
    def _connect_signals(self):
        """连接信号"""
        self.engine.progress_reporter.progress.connect(self.progress_bar.setValue)
        self.engine.progress_reporter.status.connect(self.progress_label.setText)
    
    def _create_backup(self):
        """创建备份"""
        from datetime import datetime
        
        default_name = f"codex_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择备份保存位置", default_name,
            "备份文件 (*.backup);;ZIP文件 (*.zip)"
        )
        
        if file_path:
            # 启动备份线程
            self.worker = ImportExportWorker(
                "backup", self.engine,
                backup_path=file_path,
                # 这里可以添加其他备份选项
            )
            
            self.worker.resultReady.connect(self._on_backup_finished)
            self.worker.errorOccurred.connect(self._on_backup_error)
            
            self.worker.start()
            
            self.create_backup_button.setEnabled(False)
            self.progress_label.setText("创建备份中...")
    
    def _browse_backup_file(self):
        """浏览备份文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择备份文件", "",
            "备份文件 (*.backup *.zip);;所有文件 (*)"
        )
        
        if file_path:
            self.backup_file_label.setText(file_path)
            self.restore_backup_button.setEnabled(True)
    
    def _restore_backup(self):
        """恢复备份"""
        file_path = self.backup_file_label.text()
        if file_path == "未选择文件":
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认恢复",
            "恢复备份将覆盖所有当前数据。\n是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 启动恢复线程
        self.worker = ImportExportWorker(
            "restore", self.engine,
            backup_path=file_path,
            restore_database=self.restore_database_check.isChecked()
        )
        
        self.worker.resultReady.connect(self._on_restore_finished)
        self.worker.errorOccurred.connect(self._on_restore_error)
        
        self.worker.start()
        
        self.restore_backup_button.setEnabled(False)
        self.progress_label.setText("恢复备份中...")
    
    def _on_backup_finished(self, result: ExportResult):
        """备份完成"""
        self.create_backup_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")
        
        if result.success:
            message = f"备份创建成功！\n\n"
            message += f"备份条目数: {result.exported_count}\n"
            message += f"文件大小: {result.file_size_mb:.2f} MB\n"
            message += f"保存位置: {result.file_path}"
            
            QMessageBox.information(self, "备份成功", message)
        else:
            error_message = "备份失败:\n\n" + "\n".join(result.errors)
            QMessageBox.warning(self, "备份失败", error_message)
    
    def _on_backup_error(self, error_message: str):
        """备份错误"""
        self.create_backup_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")
        QMessageBox.critical(self, "备份错误", f"备份过程中发生错误:\n\n{error_message}")
    
    def _on_restore_finished(self, result: ImportResult):
        """恢复完成"""
        self.restore_backup_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")
        
        if result.success:
            message = f"备份恢复成功！\n\n"
            message += f"恢复条目数: {result.imported_count}\n"
            message += "请重启应用程序以确保所有更改生效。"
            
            QMessageBox.information(self, "恢复成功", message)
        else:
            error_message = "恢复失败:\n\n" + "\n".join(result.errors)
            QMessageBox.warning(self, "恢复失败", error_message)
    
    def _on_restore_error(self, error_message: str):
        """恢复错误"""
        self.restore_backup_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")
        QMessageBox.critical(self, "恢复错误", f"恢复过程中发生错误:\n\n{error_message}")


class ImportExportDialog(QDialog):
    """导入导出主对话框"""
    
    def __init__(self, codex_manager, parent=None):
        super().__init__(parent)
        self.codex_manager = codex_manager
        
        # 创建导入导出引擎
        self.engine = ImportExportEngine(codex_manager)
        
        self._setup_ui()
        self._setup_window()
        
        logger.info("Import/Export dialog initialized")
    
    def _setup_window(self):
        """设置窗口"""
        self.setWindowTitle("数据导入导出")
        self.setModal(True)
        self.resize(800, 600)
        
        # 现代化样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #e9ecef;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background: #f8f9fa;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #007bff, stop:1 #0056b3);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0087ff, stop:1 #0062c9);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0056b3, stop:1 #004085);
            }
            QPushButton:disabled {
                background: #6c757d;
                color: #adb5bd;
            }
            QProgressBar {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                text-align: center;
                background: #e9ecef;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28a745, stop:1 #1e7e34);
                border-radius: 3px;
            }
        """)
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 导出标签页
        self.export_tab = ExportTab(self.engine)
        self.tab_widget.addTab(self.export_tab, "导出数据")
        
        # 导入标签页  
        self.import_tab = ImportTab(self.engine)
        self.tab_widget.addTab(self.import_tab, "导入数据")
        
        # 备份标签页
        self.backup_tab = BackupTab(self.engine)
        self.tab_widget.addTab(self.backup_tab, "备份恢复")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
    
    def closeEvent(self, event):
        """关闭事件"""
        # 检查是否有正在运行的操作
        active_workers = []
        
        if hasattr(self.export_tab, 'worker') and self.export_tab.worker and self.export_tab.worker.isRunning():
            active_workers.append("导出")
        if hasattr(self.import_tab, 'worker') and self.import_tab.worker and self.import_tab.worker.isRunning():
            active_workers.append("导入")
        if hasattr(self.backup_tab, 'worker') and self.backup_tab.worker and self.backup_tab.worker.isRunning():
            active_workers.append("备份")
        
        if active_workers:
            reply = QMessageBox.question(
                self, "确认关闭",
                f"以下操作正在进行中：{', '.join(active_workers)}\n强制关闭可能导致数据丢失。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 取消所有活动操作
                for tab in [self.export_tab, self.import_tab, self.backup_tab]:
                    if hasattr(tab, 'worker') and tab.worker and tab.worker.isRunning():
                        tab.worker.cancel()
                        tab.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()