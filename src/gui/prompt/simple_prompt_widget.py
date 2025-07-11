"""
简化的提示词界面组件 - 借鉴NovelCrafter的设计理念
实现渐进式UI：从简单标签到高级设置的分层设计
"""

import logging
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QPushButton, QLabel, QTextEdit, QSpinBox, QComboBox, 
    QGroupBox, QCheckBox, QScrollArea, QSplitter,
    QFrame, QSlider, QProgressBar, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QFont, QPalette, QIcon

from core.prompt_events import (
    get_event_bus, emit_tags_changed, emit_mode_changed,
    EventType, PromptEvent
)
from core.simple_prompt_service import (
    SimplePromptContext, PromptMode, CompletionType,
    create_simple_prompt_context
)

logger = logging.getLogger(__name__)


class TagButton(QPushButton):
    """自定义标签按钮"""
    
    def __init__(self, tag_name: str, tag_category: str = ""):
        super().__init__(tag_name)
        self.tag_name = tag_name
        self.tag_category = tag_category
        
        self.setCheckable(True)
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)
        
        # 设置样式
        self._setup_style()
    
    def _setup_style(self):
        """设置按钮样式"""
        style = """
        QPushButton {
            border: 2px solid #cccccc;
            border-radius: 6px;
            padding: 4px 12px;
            background-color: #f5f5f5;
            color: #333333;
            font-weight: bold;
        }
        QPushButton:checked {
            background-color: #007acc;
            color: white;
            border-color: #005a9e;
        }
        QPushButton:hover {
            border-color: #007acc;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        """
        self.setStyleSheet(style)


class TagPanel(QWidget):
    """标签选择面板"""
    
    tagsChanged = pyqtSignal(list)  # 标签变化信号
    
    def __init__(self, prompt_manager=None):
        super().__init__()
        self.prompt_manager = prompt_manager
        self.tag_buttons = {}
        self.selected_tags = []
        
        self.init_ui()
        self._load_available_tags()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel("写作风格标签")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 标签容器 - 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)
        
        self.tag_widget = QWidget()
        self.tag_layout = QVBoxLayout(self.tag_widget)
        
        scroll_area.setWidget(self.tag_widget)
        layout.addWidget(scroll_area)
        
        # 快速操作按钮
        quick_actions = QHBoxLayout()
        
        clear_btn = QPushButton("清除全部")
        clear_btn.clicked.connect(self.clear_all_tags)
        quick_actions.addWidget(clear_btn)
        
        quick_actions.addStretch()
        
        # 预设组合按钮
        preset_btn = QPushButton("常用组合")
        preset_btn.clicked.connect(self.show_presets)
        quick_actions.addWidget(preset_btn)
        
        layout.addLayout(quick_actions)
    
    def _load_available_tags(self):
        """加载可用标签"""
        if self.prompt_manager:
            try:
                tag_categories = self.prompt_manager.get_available_tags()
                self._create_tag_groups(tag_categories)
            except Exception as e:
                logger.error(f"加载标签失败: {e}")
                self._create_default_tags()
        else:
            self._create_default_tags()
    
    def _create_tag_groups(self, tag_categories: Dict[str, List[str]]):
        """创建分类标签组"""
        for category, tags in tag_categories.items():
            # 创建分类组
            group_box = QGroupBox(category)
            group_layout = QGridLayout()
            
            # 添加标签按钮
            row, col = 0, 0
            for tag in tags:
                btn = TagButton(tag, category)
                btn.clicked.connect(self._on_tag_clicked)
                
                self.tag_buttons[tag] = btn
                group_layout.addWidget(btn, row, col)
                
                col += 1
                if col >= 3:  # 每行3个按钮
                    col = 0
                    row += 1
            
            group_box.setLayout(group_layout)
            self.tag_layout.addWidget(group_box)
    
    def _create_default_tags(self):
        """创建默认标签（fallback）"""
        default_tags = {
            "风格": ["科幻", "武侠", "都市", "奇幻", "历史"],
            "情节": ["悬疑", "浪漫", "动作", "日常", "高潮"],
            "视角": ["第一人称", "第三人称", "全知视角"]
        }
        self._create_tag_groups(default_tags)
    
    def _on_tag_clicked(self):
        """处理标签点击"""
        sender = self.sender()
        if isinstance(sender, TagButton):
            tag_name = sender.tag_name
            
            if sender.isChecked():
                if tag_name not in self.selected_tags:
                    self.selected_tags.append(tag_name)
            else:
                if tag_name in self.selected_tags:
                    self.selected_tags.remove(tag_name)
            
            # 发出信号
            self.tagsChanged.emit(self.selected_tags.copy())
            
            # 发布事件到总线
            emit_tags_changed(self.selected_tags.copy())
            
            logger.debug(f"标签选择变化: {self.selected_tags}")
    
    def clear_all_tags(self):
        """清除所有选中的标签"""
        for btn in self.tag_buttons.values():
            btn.setChecked(False)
        
        self.selected_tags.clear()
        self.tagsChanged.emit([])
        emit_tags_changed([])
    
    def show_presets(self):
        """显示预设组合"""
        # TODO: 实现预设标签组合功能
        pass
    
    def get_selected_tags(self) -> List[str]:
        """获取选中的标签"""
        return self.selected_tags.copy()
    
    def set_selected_tags(self, tags: List[str]):
        """设置选中的标签"""
        self.clear_all_tags()
        
        for tag in tags:
            if tag in self.tag_buttons:
                self.tag_buttons[tag].setChecked(True)
                self.selected_tags.append(tag)
        
        self.tagsChanged.emit(self.selected_tags.copy())


class AdvancedSettingsPanel(QWidget):
    """高级设置面板 - 可折叠"""
    
    settingsChanged = pyqtSignal(dict)  # 设置变化信号
    
    def __init__(self):
        super().__init__()
        self.settings = {}
        self.init_ui()
        self.setVisible(False)  # 默认隐藏
    
    def init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 续写字数
        self.word_count_spin = QSpinBox()
        self.word_count_spin.setRange(50, 2000)
        self.word_count_spin.setValue(300)
        self.word_count_spin.setSuffix(" 字")
        self.word_count_spin.valueChanged.connect(self._on_settings_changed)
        layout.addRow("续写字数:", self.word_count_spin)
        
        # 上下文长度
        self.context_size_spin = QSpinBox()
        self.context_size_spin.setRange(100, 1000)
        self.context_size_spin.setValue(500)
        self.context_size_spin.setSuffix(" 字符")
        self.context_size_spin.valueChanged.connect(self._on_settings_changed)
        layout.addRow("上下文长度:", self.context_size_spin)
        
        # 提示词模式
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["快速模式", "平衡模式", "完整模式"])
        self.mode_combo.setCurrentIndex(1)  # 默认平衡模式
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout.addRow("生成模式:", self.mode_combo)
        
        # 补全类型
        self.completion_type_combo = QComboBox()
        self.completion_type_combo.addItems([
            "通用文本", "角色描写", "场景描写", "对话", 
            "动作描写", "情感描写", "情节推进", "环境描写", "转场"
        ])
        self.completion_type_combo.currentTextChanged.connect(self._on_settings_changed)
        layout.addRow("补全类型:", self.completion_type_combo)
        
        # RAG增强
        self.rag_enabled = QCheckBox("启用RAG上下文增强")
        self.rag_enabled.setChecked(True)
        self.rag_enabled.toggled.connect(self._on_settings_changed)
        layout.addRow(self.rag_enabled)
        
        # 实体检测
        self.entity_detection = QCheckBox("启用角色/地点自动检测")
        self.entity_detection.setChecked(True)
        self.entity_detection.toggled.connect(self._on_settings_changed)
        layout.addRow(self.entity_detection)
    
    def _on_settings_changed(self):
        """设置变化处理"""
        self.settings = self.get_settings()
        self.settingsChanged.emit(self.settings)
    
    def _on_mode_changed(self, mode_text: str):
        """模式变化处理"""
        mode_map = {
            "快速模式": "fast",
            "平衡模式": "balanced", 
            "完整模式": "full"
        }
        
        mode = mode_map.get(mode_text, "balanced")
        emit_mode_changed(mode)
        self._on_settings_changed()
    
    def get_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        mode_map = {
            "快速模式": PromptMode.FAST,
            "平衡模式": PromptMode.BALANCED,
            "完整模式": PromptMode.FULL
        }
        
        type_map = {
            "通用文本": CompletionType.TEXT,
            "角色描写": CompletionType.CHARACTER,
            "场景描写": CompletionType.LOCATION,
            "对话": CompletionType.DIALOGUE,
            "动作描写": CompletionType.ACTION,
            "情感描写": CompletionType.EMOTION,
            "情节推进": CompletionType.PLOT,
            "环境描写": CompletionType.DESCRIPTION,
            "转场": CompletionType.TRANSITION
        }
        
        return {
            'word_count': self.word_count_spin.value(),
            'context_size': self.context_size_spin.value(),
            'prompt_mode': mode_map.get(self.mode_combo.currentText(), PromptMode.BALANCED),
            'completion_type': type_map.get(self.completion_type_combo.currentText(), CompletionType.TEXT),
            'rag_enabled': self.rag_enabled.isChecked(),
            'entity_detection': self.entity_detection.isChecked()
        }


class PromptPreviewPanel(QWidget):
    """提示词预览面板"""
    
    promptEditRequested = pyqtSignal(str)  # 提示词编辑请求
    
    def __init__(self):
        super().__init__()
        self.current_prompt = ""
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 标题和操作按钮
        header_layout = QHBoxLayout()
        
        title_label = QLabel("提示词预览")
        title_font = QFont()
        title_font.setBold(True)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self._on_edit_requested)
        header_layout.addWidget(edit_btn)
        
        # 复制按钮
        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(self._on_copy_requested)
        header_layout.addWidget(copy_btn)
        
        layout.addLayout(header_layout)
        
        # 预览文本框
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setPlaceholderText("提示词将在此显示...")
        self.preview_text.setReadOnly(True)
        
        # 设置字体
        font = QFont("Consolas", 9)
        self.preview_text.setFont(font)
        
        layout.addWidget(self.preview_text)
        
        # 统计信息
        self.stats_label = QLabel("字符数: 0")
        self.stats_label.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(self.stats_label)
    
    def update_preview(self, prompt: str):
        """更新提示词预览"""
        self.current_prompt = prompt
        self.preview_text.setPlainText(prompt)
        
        # 更新统计信息
        char_count = len(prompt)
        line_count = prompt.count('\n') + 1
        self.stats_label.setText(f"字符数: {char_count} | 行数: {line_count}")
    
    def _on_edit_requested(self):
        """处理编辑请求"""
        self.promptEditRequested.emit(self.current_prompt)
    
    def _on_copy_requested(self):
        """复制提示词到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.current_prompt)
        
        # 临时显示复制成功提示
        original_text = self.stats_label.text()
        self.stats_label.setText("✓ 已复制到剪贴板")
        self.stats_label.setStyleSheet("color: #009900; font-size: 11px;")
        
        # 2秒后恢复原文本
        QTimer.singleShot(2000, lambda: (
            self.stats_label.setText(original_text),
            self.stats_label.setStyleSheet("color: #666666; font-size: 11px;")
        ))


class SimplePromptWidget(QWidget):
    """简化的提示词界面 - 主组件"""
    
    promptGenerated = pyqtSignal(str)       # 提示词生成信号
    promptRequested = pyqtSignal(dict)      # 提示词请求信号
    
    def __init__(self, prompt_container=None):
        super().__init__()
        self.container = prompt_container
        self.prompt_manager = None
        self.event_bus = None
        
        if prompt_container:
            self.prompt_manager = prompt_container.get_service('prompt_manager')
            self.event_bus = prompt_container.get_service('event_bus')
        
        self.current_context = None
        self.init_ui()
        self._connect_events()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # 1. 标签选择面板
        self.tag_panel = TagPanel(self.prompt_manager)
        layout.addWidget(self.tag_panel)
        
        # 2. 高级设置面板（可折叠）
        self.advanced_panel = AdvancedSettingsPanel()
        layout.addWidget(self.advanced_panel)
        
        # 高级设置切换按钮
        advanced_toggle = QPushButton("▼ 高级设置")
        advanced_toggle.setCheckable(True)
        advanced_toggle.toggled.connect(self._toggle_advanced_panel)
        layout.insertWidget(-1, advanced_toggle)
        
        # 3. 提示词预览面板
        self.preview_panel = PromptPreviewPanel()
        layout.addWidget(self.preview_panel)
        
        # 4. 生成按钮
        generate_btn = QPushButton("生成提示词")
        generate_btn.setMinimumHeight(40)
        generate_btn.clicked.connect(self.generate_prompt)
        
        # 设置主要按钮样式
        generate_btn.setStyleSheet("""
        QPushButton {
            background-color: #007acc;
            color: white;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #005a9e;
        }
        QPushButton:pressed {
            background-color: #004078;
        }
        """)
        
        layout.addWidget(generate_btn)
    
    def _connect_events(self):
        """连接事件信号"""
        # 内部信号连接
        self.tag_panel.tagsChanged.connect(self._on_tags_changed)
        self.advanced_panel.settingsChanged.connect(self._on_settings_changed)
        self.preview_panel.promptEditRequested.connect(self._on_edit_requested)
        
        # 事件总线连接
        if self.event_bus:
            self.event_bus.promptGenerated.connect(self._on_prompt_generated)
    
    def _toggle_advanced_panel(self, checked: bool):
        """切换高级设置面板"""
        self.advanced_panel.setVisible(checked)
        
        # 更新按钮文本
        sender = self.sender()
        if isinstance(sender, QPushButton):
            if checked:
                sender.setText("▲ 高级设置")
            else:
                sender.setText("▼ 高级设置")
    
    def _on_tags_changed(self, tags: List[str]):
        """标签变化处理"""
        logger.debug(f"UI标签变化: {tags}")
    
    def _on_settings_changed(self, settings: Dict[str, Any]):
        """设置变化处理"""
        logger.debug(f"高级设置变化: {settings}")
    
    def _on_prompt_generated(self, prompt: str, context: Any = None):
        """提示词生成完成处理"""
        self.preview_panel.update_preview(prompt)
        self.promptGenerated.emit(prompt)
    
    def _on_edit_requested(self, prompt: str):
        """处理提示词编辑请求"""
        # TODO: 打开提示词编辑对话框
        logger.info("提示词编辑请求")
    
    def generate_prompt(self):
        """生成提示词"""
        if not self.prompt_manager:
            logger.warning("提示词管理器不可用")
            return
        
        try:
            # 构建上下文
            context = self._build_context()
            
            # 生成提示词
            prompt = self.prompt_manager.generate_prompt(context)
            
            # 更新预览
            self.preview_panel.update_preview(prompt)
            
            # 发出信号
            self.promptGenerated.emit(prompt)
            
        except Exception as e:
            logger.error(f"提示词生成失败: {e}")
    
    def _build_context(self) -> SimplePromptContext:
        """构建提示词上下文"""
        # 获取标签
        selected_tags = self.tag_panel.get_selected_tags()
        
        # 获取高级设置
        settings = self.advanced_panel.get_settings()
        
        # 创建上下文
        context = SimplePromptContext(
            text="",  # 将由外部设置
            cursor_position=0,  # 将由外部设置
            selected_tags=selected_tags,
            prompt_mode=settings['prompt_mode'],
            completion_type=settings['completion_type'],
            word_count=settings['word_count'],
            context_size=settings['context_size']
        )
        
        return context
    
    def update_context(self, text: str, cursor_pos: int = 0):
        """更新文本上下文"""
        # 存储当前上下文以供后续使用
        context = self._build_context()
        context.text = text
        context.cursor_position = cursor_pos
        self.current_context = context
    
    def get_current_context(self) -> Optional[SimplePromptContext]:
        """获取当前上下文"""
        return self.current_context
    
    def set_selected_tags(self, tags: List[str]):
        """设置选中的标签"""
        self.tag_panel.set_selected_tags(tags)
    
    def get_selected_tags(self) -> List[str]:
        """获取选中的标签"""
        return self.tag_panel.get_selected_tags()


# 工厂函数
def create_simple_prompt_widget(prompt_container=None) -> SimplePromptWidget:
    """创建简化提示词界面的工厂函数"""
    return SimplePromptWidget(prompt_container)