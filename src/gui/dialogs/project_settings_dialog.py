"""
项目设置对话框
管理项目的基本信息、结构设置、导出配置等
"""

import logging
from typing import Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout,
    QLineEdit, QTextEdit, QSpinBox, QCheckBox, QComboBox, QPushButton,
    QLabel, QGroupBox, QFileDialog, QDateEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class ProjectInfoWidget(QGroupBox):
    """项目信息组件"""
    
    def __init__(self, parent=None):
        super().__init__("项目信息", parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 项目名称
        self._project_name = QLineEdit()
        self._project_name.setPlaceholderText("输入项目名称")
        layout.addRow("项目名称:", self._project_name)
        
        # 作者信息
        self._author_name = QLineEdit()
        self._author_name.setPlaceholderText("作者姓名")
        layout.addRow("作者:", self._author_name)
        
        # 项目描述
        self._description = QTextEdit()
        self._description.setPlaceholderText("项目简介和描述...")
        self._description.setMaximumHeight(100)
        layout.addRow("描述:", self._description)
        
        # 类型和风格
        self._genre = QComboBox()
        self._genre.addItems([
            "现代都市", "古代言情", "玄幻修仙", "科幻未来", 
            "悬疑推理", "历史军事", "游戏竞技", "其他"
        ])
        layout.addRow("类型:", self._genre)
        
        # 目标字数
        self._target_words = QSpinBox()
        self._target_words.setRange(1000, 10000000)
        self._target_words.setValue(100000)
        self._target_words.setSuffix(" 字")
        layout.addRow("目标字数:", self._target_words)
        
        # 创建日期
        self._created_date = QDateEdit()
        self._created_date.setDate(QDate.currentDate())
        self._created_date.setCalendarPopup(True)
        layout.addRow("创建日期:", self._created_date)
        
        # 项目状态
        self._status = QComboBox()
        self._status.addItems(["构思中", "写作中", "修改中", "已完成", "已发布"])
        layout.addRow("状态:", self._status)
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "name": self._project_name.text(),
            "author": self._author_name.text(),
            "description": self._description.toPlainText(),
            "genre": self._genre.currentText(),
            "target_words": self._target_words.value(),
            "created_date": self._created_date.date().toString("yyyy-MM-dd"),
            "status": self._status.currentText()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        self._project_name.setText(settings.get("name", ""))
        self._author_name.setText(settings.get("author", ""))
        self._description.setPlainText(settings.get("description", ""))
        self._genre.setCurrentText(settings.get("genre", "现代都市"))
        self._target_words.setValue(settings.get("target_words", 100000))
        
        created_date = settings.get("created_date", "")
        if created_date:
            self._created_date.setDate(QDate.fromString(created_date, "yyyy-MM-dd"))
        
        self._status.setCurrentText(settings.get("status", "构思中"))


class ProjectStructureWidget(QGroupBox):
    """项目结构组件"""
    
    def __init__(self, parent=None):
        super().__init__("项目结构", parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 章节命名规则
        self._chapter_naming = QComboBox()
        self._chapter_naming.addItems([
            "第{number}章 {title}",
            "Chapter {number}: {title}",
            "{number}. {title}",
            "自定义格式"
        ])
        layout.addRow("章节命名:", self._chapter_naming)
        
        # 自定义命名格式
        self._custom_naming = QLineEdit()
        self._custom_naming.setPlaceholderText("例如: 第{number}章 {title}")
        self._custom_naming.setEnabled(False)
        layout.addRow("自定义格式:", self._custom_naming)
        
        # 连接信号
        self._chapter_naming.currentTextChanged.connect(self._on_naming_changed)
        
        # 自动编号设置
        self._auto_numbering = QCheckBox("自动章节编号")
        self._auto_numbering.setChecked(True)
        layout.addRow(self._auto_numbering)
        
        # 起始编号
        self._start_number = QSpinBox()
        self._start_number.setRange(0, 1000)
        self._start_number.setValue(1)
        layout.addRow("起始编号:", self._start_number)
        
        # 默认章节长度
        self._default_chapter_length = QSpinBox()
        self._default_chapter_length.setRange(500, 50000)
        self._default_chapter_length.setValue(3000)
        self._default_chapter_length.setSuffix(" 字")
        layout.addRow("默认章节长度:", self._default_chapter_length)
        
        # 场景分隔符
        self._scene_separator = QLineEdit()
        self._scene_separator.setText("***")
        layout.addRow("场景分隔符:", self._scene_separator)
    
    def _on_naming_changed(self, text: str):
        """命名格式变化处理"""
        self._custom_naming.setEnabled(text == "自定义格式")
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "chapter_naming": self._chapter_naming.currentText(),
            "custom_naming": self._custom_naming.text(),
            "auto_numbering": self._auto_numbering.isChecked(),
            "start_number": self._start_number.value(),
            "default_chapter_length": self._default_chapter_length.value(),
            "scene_separator": self._scene_separator.text()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        self._chapter_naming.setCurrentText(settings.get("chapter_naming", "第{number}章 {title}"))
        self._custom_naming.setText(settings.get("custom_naming", ""))
        self._auto_numbering.setChecked(settings.get("auto_numbering", True))
        self._start_number.setValue(settings.get("start_number", 1))
        self._default_chapter_length.setValue(settings.get("default_chapter_length", 3000))
        self._scene_separator.setText(settings.get("scene_separator", "***"))


class ExportSettingsWidget(QGroupBox):
    """导出设置组件"""
    
    def __init__(self, parent=None):
        super().__init__("导出设置", parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 默认导出格式
        self._export_format = QComboBox()
        self._export_format.addItems(["TXT", "DOCX", "PDF", "HTML", "EPUB"])
        layout.addRow("默认格式:", self._export_format)
        
        # 导出路径
        export_path_layout = QHBoxLayout()
        self._export_path = QLineEdit()
        self._export_path.setPlaceholderText("选择导出目录")
        export_path_layout.addWidget(self._export_path)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_export_path)
        export_path_layout.addWidget(browse_btn)
        
        layout.addRow("导出路径:", export_path_layout)
        
        # 导出选项
        self._include_metadata = QCheckBox("包含元数据")
        self._include_metadata.setChecked(True)
        layout.addRow(self._include_metadata)
        
        self._include_toc = QCheckBox("生成目录")
        self._include_toc.setChecked(True)
        layout.addRow(self._include_toc)
        
        self._split_chapters = QCheckBox("按章节分割文件")
        layout.addRow(self._split_chapters)
        
        # 字体设置
        self._export_font = QComboBox()
        self._export_font.addItems(["宋体", "微软雅黑", "Times New Roman", "Arial"])
        layout.addRow("导出字体:", self._export_font)
        
        self._export_font_size = QSpinBox()
        self._export_font_size.setRange(8, 72)
        self._export_font_size.setValue(12)
        self._export_font_size.setSuffix("pt")
        layout.addRow("字体大小:", self._export_font_size)
    
    def _browse_export_path(self):
        """浏览导出路径"""
        path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if path:
            self._export_path.setText(path)
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "format": self._export_format.currentText(),
            "path": self._export_path.text(),
            "include_metadata": self._include_metadata.isChecked(),
            "include_toc": self._include_toc.isChecked(),
            "split_chapters": self._split_chapters.isChecked(),
            "font": self._export_font.currentText(),
            "font_size": self._export_font_size.value()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """设置配置"""
        self._export_format.setCurrentText(settings.get("format", "TXT"))
        self._export_path.setText(settings.get("path", ""))
        self._include_metadata.setChecked(settings.get("include_metadata", True))
        self._include_toc.setChecked(settings.get("include_toc", True))
        self._split_chapters.setChecked(settings.get("split_chapters", False))
        self._export_font.setCurrentText(settings.get("font", "宋体"))
        self._export_font_size.setValue(settings.get("font_size", 12))


class ProjectSettingsDialog(QDialog):
    """项目设置对话框"""
    
    # 信号定义
    settingsChanged = pyqtSignal(dict)  # 设置变更信号
    
    def __init__(self, parent=None, settings: Dict[str, Any] = None):
        super().__init__(parent)
        
        self._settings = settings or {}
        
        self._init_ui()
        self._load_settings()
        
        # 设置对话框属性
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        self.setWindowTitle("项目设置")
        
        logger.debug("Project settings dialog initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标签页
        self._tabs = QTabWidget()
        
        # 项目信息
        self._info_widget = ProjectInfoWidget()
        self._tabs.addTab(self._info_widget, "项目信息")
        
        # 项目结构
        self._structure_widget = ProjectStructureWidget()
        self._tabs.addTab(self._structure_widget, "项目结构")
        
        # 导出设置
        self._export_widget = ExportSettingsWidget()
        self._tabs.addTab(self._export_widget, "导出设置")
        
        layout.addWidget(self._tabs)
        
        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
    
    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)
        layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._save_settings)
        ok_btn.setDefault(True)
        layout.addWidget(ok_btn)
        
        return layout
    
    def _load_settings(self):
        """加载设置"""
        if not self._settings:
            return
        
        # 加载各个组件的设置
        info_settings = self._settings.get("info", {})
        self._info_widget.set_settings(info_settings)
        
        structure_settings = self._settings.get("structure", {})
        self._structure_widget.set_settings(structure_settings)
        
        export_settings = self._settings.get("export", {})
        self._export_widget.set_settings(export_settings)
    
    def _save_settings(self):
        """保存设置"""
        settings = {
            "info": self._info_widget.get_settings(),
            "structure": self._structure_widget.get_settings(),
            "export": self._export_widget.get_settings()
        }
        
        self.settingsChanged.emit(settings)
        self.accept()
        
        logger.info("Project settings saved")
    
    def get_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        return {
            "info": self._info_widget.get_settings(),
            "structure": self._structure_widget.get_settings(),
            "export": self._export_widget.get_settings()
        }
