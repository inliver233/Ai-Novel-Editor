"""
工具栏系统
实现主工具栏和各种功能工具栏
"""

import logging
from typing import Dict, Any, List
from PyQt6.QtWidgets import QToolBar, QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton, QSpinBox
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QFont

logger = logging.getLogger(__name__)


class MainToolBar(QToolBar):
    """精简主工具栏 - 只包含核心高频功能"""
    
    # 信号定义
    actionTriggered = pyqtSignal(str, dict)  # 工具栏动作触发信号
    
    def __init__(self, parent=None):
        super().__init__("主工具栏", parent)
        
        self._actions = {}
        self._init_toolbar()
        
        # 设置工具栏属性
        self.setMovable(False)  # 固定位置
        self.setFloatable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)  # 图标+文字横排
        self.setIconSize(self.iconSize() * 0.8)  # 稍小的图标
        
        logger.debug("Main toolbar initialized")
    
    def _init_toolbar(self):
        """初始化精简工具栏"""
        # 核心文件操作
        self._add_core_file_actions()
        
        self.addSeparator()
        
        # 视图控制
        self._add_view_actions()
        
        # 弹性空间
        spacer = QWidget()
        from PyQt6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        self.addWidget(spacer)
    
    def _add_core_file_actions(self):
        """添加核心文件操作"""
        # 新建项目
        new_project_action = self._create_action(
            "new_project", "新建项目", "",
            "创建新的小说项目"
        )
        self.addAction(new_project_action)
        
        # 打开项目
        open_project_action = self._create_action(
            "open_project", "打开项目", "",
            "打开现有项目"
        )
        self.addAction(open_project_action)
        
        # 保存文档
        save_document_action = self._create_action(
            "save_document", "保存", "",
            "保存当前文档 (Ctrl+S)"
        )
        self.addAction(save_document_action)
    
    
    
    def _add_view_actions(self):
        """添加视图控制"""
        # 全屏模式
        fullscreen_action = self._create_action(
            "fullscreen", "全屏", "",
            "切换全屏模式 (F11)"
        )
        fullscreen_action.setCheckable(True)
        self.addAction(fullscreen_action)
    
    
    
    def update_ai_status(self, status: str, color: str = "#4a5568"):
        """更新AI状态（主工具栏不再有状态显示）"""
        # 主工具栏不再有状态显示，保留接口兼容性
        pass
    
    def _create_action(self, action_id: str, text: str, icon_text: str, tooltip: str) -> QAction:
        """创建工具栏动作"""
        # 纯文字显示，不使用图标
        action = QAction(text, self)
        
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        
        # 连接信号
        action.triggered.connect(lambda: self._on_action_triggered(action_id))
        
        # 保存引用
        self._actions[action_id] = action
        
        return action
    
    def _on_action_triggered(self, action_id: str):
        """工具栏动作触发处理"""
        self.actionTriggered.emit(action_id, {})
        logger.debug(f"Toolbar action triggered: {action_id}")
    
    def update_word_count(self, count: int):
        """更新字数统计"""
        # 已移除字数显示，保留接口兼容性
        pass
    
    
    def get_action(self, action_id: str) -> QAction:
        """获取工具栏动作"""
        return self._actions.get(action_id)
    
    def set_action_enabled(self, action_id: str, enabled: bool):
        """设置工具栏动作启用状态"""
        action = self._actions.get(action_id)
        if action:
            action.setEnabled(enabled)


class FormatToolBar(QToolBar):
    """格式工具栏"""
    
    # 信号定义
    formatChanged = pyqtSignal(str, dict)  # 格式变更信号
    
    def __init__(self, parent=None):
        super().__init__("格式工具栏", parent)
        
        self._init_toolbar()
        
        # 设置工具栏属性
        self.setMovable(True)
        self.setFloatable(False)
        
        logger.debug("Format toolbar initialized")
    
    def _init_toolbar(self):
        """初始化格式工具栏"""
        # 字体选择
        font_label = QLabel("字体:")
        self.addWidget(font_label)
        
        self._font_combo = QComboBox()
        self._font_combo.addItems([
            "微软雅黑", "宋体", "黑体", "楷体", "仿宋",
            "Consolas", "Arial", "Times New Roman"
        ])
        self._font_combo.setCurrentText("微软雅黑")
        self._font_combo.currentTextChanged.connect(
            lambda font: self.formatChanged.emit("font_family", {"family": font})
        )
        self.addWidget(self._font_combo)
        
        # 字体大小
        size_label = QLabel("大小:")
        self.addWidget(size_label)
        
        self._size_spin = QSpinBox()
        self._size_spin.setRange(8, 72)
        self._size_spin.setValue(12)
        self._size_spin.setSuffix("pt")
        self._size_spin.valueChanged.connect(
            lambda size: self.formatChanged.emit("font_size", {"size": size})
        )
        self.addWidget(self._size_spin)
        
        self.addSeparator()
        
        # 文本格式
        bold_action = QAction("粗体", self)
        bold_action.setCheckable(True)
        bold_action.setShortcut("Ctrl+B")
        bold_action.triggered.connect(
            lambda checked: self.formatChanged.emit("bold", {"enabled": checked})
        )
        self.addAction(bold_action)
        
        italic_action = QAction("斜体", self)
        italic_action.setCheckable(True)
        italic_action.setShortcut("Ctrl+I")
        italic_action.triggered.connect(
            lambda checked: self.formatChanged.emit("italic", {"enabled": checked})
        )
        self.addAction(italic_action)
        
        underline_action = QAction("下划线", self)
        underline_action.setCheckable(True)
        underline_action.setShortcut("Ctrl+U")
        underline_action.triggered.connect(
            lambda checked: self.formatChanged.emit("underline", {"enabled": checked})
        )
        self.addAction(underline_action)
    
    def set_font_family(self, family: str):
        """设置字体族"""
        self._font_combo.setCurrentText(family)
    
    def set_font_size(self, size: int):
        """设置字体大小"""
        self._size_spin.setValue(size)


class AIToolBar(QToolBar):
    """精简AI功能工具栏 - 智能的紧凑布局"""
    
    # 信号定义
    aiActionTriggered = pyqtSignal(str, dict)  # AI动作触发信号
    
    def __init__(self, parent=None):
        super().__init__("AI工具栏", parent)
        
        self._init_toolbar()
        
        # 设置工具栏属性
        self.setMovable(False)  # 固定位置
        self.setFloatable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)  # 紧凑横排样式
        self.setIconSize(self.iconSize() * 0.8)  # 稍小的图标
        
        # 默认显示，但可以隐藏
        self.setVisible(True)
        
        logger.debug("AI toolbar initialized")
    
    def _init_toolbar(self):
        """初始化精简AI工具栏"""
        # 智能模式选择（紧凑版）
        self._add_smart_mode_selectors()
        
        self.addSeparator()
        
        # API配置按钮
        self._add_api_config_button()
        
        # 弹性空间
        spacer = QWidget()
        from PyQt6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        self.addWidget(spacer)
        
        # AI状态显示（在AI工具栏最右边）
        self._add_ai_status()
    
    
    def _add_smart_mode_selectors(self):
        """添加智能模式选择器（紧凑版）"""
        # 创建模式选择器组
        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(4)
        
        # 补全模式选择（精简版）
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([
            "自动", "手动", "禁用"
        ])
        self._mode_combo.setCurrentIndex(1)  # 默认手动模式
        self._mode_combo.setMaximumWidth(80)
        self._mode_combo.setToolTip("补全模式：自动/手动/禁用")
        self._mode_combo.currentTextChanged.connect(
            lambda mode: self.aiActionTriggered.emit("completion_mode_changed", {"mode": mode})
        )
        mode_layout.addWidget(self._mode_combo)
        
        # 上下文模式选择（精简版）
        self._context_combo = QComboBox()
        self._context_combo.addItems([
            "快速", "平衡", "全局"
        ])
        self._context_combo.setCurrentIndex(1)  # 默认平衡模式
        self._context_combo.setMaximumWidth(80)
        self._context_combo.setToolTip("上下文模式：快速(<2K)/平衡(2-8K)/全局(200K+)")
        self._context_combo.currentTextChanged.connect(
            lambda mode: self.aiActionTriggered.emit("context_mode_changed", {"mode": mode})
        )
        mode_layout.addWidget(self._context_combo)
        
        self.addWidget(mode_widget)
    
    def _add_api_config_button(self):
        """添加API配置按钮"""
        config_btn = QPushButton("API配置")
        config_btn.setToolTip("打开AI配置中心")
        config_btn.setMaximumHeight(28)  # 与深色模式保持一致
        config_btn.clicked.connect(
            lambda: self.aiActionTriggered.emit("ai_config", {})
        )
        self.addWidget(config_btn)
        
        # 添加提示词模板选择按钮
        self._add_template_selector()
    
    def _add_template_selector(self):
        """添加提示词模板选择器"""
        template_btn = QPushButton("模板")
        template_btn.setToolTip("选择当前使用的提示词模板")
        template_btn.setMaximumHeight(28)  # 与深色模式保持一致
        template_btn.clicked.connect(
            lambda: self.aiActionTriggered.emit("template_selector", {})
        )
        self.addWidget(template_btn)
    
    def _add_ai_status(self):
        """添加AI状态显示（在AI工具栏最右边）"""
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("""
            QLabel {
                color: #4a5568;
                padding: 4px 8px;
                border: 1px solid #4a5568;
                border-radius: 4px;
                background-color: rgba(74, 85, 104, 0.1);
                font-size: 11px;
            }
        """)
        self.addWidget(self._status_label)
    
    
    def set_completion_mode(self, mode: str):
        """设置补全模式"""
        # 映射到精简显示
        mode_map = {
            "自动AI补全": "自动",
            "手动AI补全": "手动",
            "禁用补全": "禁用"
        }
        display_mode = mode_map.get(mode, mode)
        self._mode_combo.setCurrentText(display_mode)
    
    def set_context_mode(self, mode: str):
        """设置上下文模式"""
        # 映射到精简显示
        mode_map = {
            "快速模式 (<2K tokens)": "快速",
            "平衡模式 (2-8K tokens)": "平衡",
            "全局模式 (200K+ tokens)": "全局"
        }
        display_mode = mode_map.get(mode, mode)
        self._context_combo.setCurrentText(display_mode)
    
    def get_completion_mode(self) -> str:
        """获取当前补全模式"""
        # 映射回原始格式
        mode_map = {
            "自动": "自动AI补全",
            "手动": "手动AI补全",
            "禁用": "禁用补全"
        }
        display_mode = self._mode_combo.currentText()
        return mode_map.get(display_mode, display_mode)
    
    def get_context_mode(self) -> str:
        """获取当前上下文模式"""
        # 映射回原始格式
        mode_map = {
            "快速": "快速模式 (<2K tokens)",
            "平衡": "平衡模式 (2-8K tokens)",
            "全局": "全局模式 (200K+ tokens)"
        }
        display_mode = self._context_combo.currentText()
        return mode_map.get(display_mode, display_mode)
    
    def update_ai_status(self, status: str, color: str = "#155724"):
        """更新AI状态"""
        # 根据状态选择色彩和背景，使用更柔和的配色
        if "error" in status.lower() or "错误" in status:
            bg_color = "rgba(220, 53, 69, 0.1)"
            border_color = "#dc3545"
            text_color = "#dc3545"
        elif "thinking" in status.lower() or "思考" in status or "工作" in status:
            bg_color = "rgba(255, 193, 7, 0.1)"
            border_color = "#ffc107"
            text_color = "#ffc107"
            # 启动思考动画
            if not hasattr(self, '_thinking_timer'):
                self._thinking_timer = QTimer()
                self._thinking_timer.timeout.connect(self._animate_thinking_status)
            if not self._thinking_timer.isActive():
                self._thinking_dots = 0
                self._thinking_timer.start(500)  # 每500ms更新一次
        elif "working" in status.lower():
            bg_color = "rgba(255, 193, 7, 0.1)"
            border_color = "#ffc107"
            text_color = "#ffc107"
        else:
            bg_color = "rgba(52, 144, 220, 0.1)"
            border_color = "#3490dc"
            text_color = "#3490dc"
            # 停止思考动画
            if hasattr(self, '_thinking_timer') and self._thinking_timer.isActive():
                self._thinking_timer.stop()
        
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                padding: 4px 8px;
                border: 1px solid {border_color};
                border-radius: 4px;
                background-color: {bg_color};
                font-size: 11px;
            }}
        """)
    
    def _animate_thinking_status(self):
        """思考状态动画效果"""
        if not hasattr(self, '_thinking_dots'):
            self._thinking_dots = 0
        
        self._thinking_dots = (self._thinking_dots + 1) % 4
        dots = "." * self._thinking_dots
        base_text = "思考中"
        
        # 从当前文本中提取基础状态
        current_text = self._status_label.text()
        if "思考" in current_text:
            # 保持思考状态，只更新点数
            self._status_label.setText(f"{base_text}{dots}")
        elif "工作" in current_text:
            # 工作状态也加动画
            self._status_label.setText(f"工作中{dots}")
        else:
            # 如果状态已经改变，停止动画
            if hasattr(self, '_thinking_timer') and self._thinking_timer.isActive():
                self._thinking_timer.stop()
    
    def _cycle_context_mode(self):
        """循环切换上下文模式"""
        current_index = self._context_combo.currentIndex()
        next_index = (current_index + 1) % self._context_combo.count()
        self._context_combo.setCurrentIndex(next_index)
        
        # 发出模式切换信号
        mode_text = self.get_context_mode()  # 使用映射后的格式
        self.aiActionTriggered.emit("context_mode_changed", {"mode": mode_text})
    
    def _cycle_completion_mode(self):
        """循环切换补全模式"""
        current_index = self._mode_combo.currentIndex()
        next_index = (current_index + 1) % self._mode_combo.count()
        self._mode_combo.setCurrentIndex(next_index)
        
        # 发出模式切换信号
        mode_text = self.get_completion_mode()  # 使用映射后的格式
        self.aiActionTriggered.emit("completion_mode_changed", {"mode": mode_text})


class ToolBarManager:
    """工具栏管理器 - 支持智能显示/隐藏"""
    
    def __init__(self, main_window):
        self._main_window = main_window
        self._toolbars = {}
        
        self._init_toolbars()
        
        logger.info("Toolbar manager initialized")
    
    def _init_toolbars(self):
        """初始化所有工具栏"""
        # 主工具栏（精简版）
        main_toolbar = MainToolBar(self._main_window)
        self._main_window.addToolBar(Qt.ToolBarArea.TopToolBarArea, main_toolbar)
        self._toolbars["main"] = main_toolbar
        
        # AI工具栏（紧凑版，默认显示）
        ai_toolbar = AIToolBar(self._main_window)
        self._main_window.addToolBar(Qt.ToolBarArea.TopToolBarArea, ai_toolbar)
        self._toolbars["ai"] = ai_toolbar
        
        # 格式工具栏（默认隐藏）
        format_toolbar = FormatToolBar(self._main_window)
        self._main_window.addToolBar(Qt.ToolBarArea.TopToolBarArea, format_toolbar)
        format_toolbar.hide()  # 默认隐藏
        self._toolbars["format"] = format_toolbar
    
    def get_toolbar(self, name: str) -> QToolBar:
        """获取工具栏"""
        return self._toolbars.get(name)
    
    def show_toolbar(self, name: str):
        """显示工具栏"""
        toolbar = self._toolbars.get(name)
        if toolbar:
            toolbar.show()
    
    def hide_toolbar(self, name: str):
        """隐藏工具栏"""
        toolbar = self._toolbars.get(name)
        if toolbar:
            toolbar.hide()
    
    def toggle_toolbar(self, name: str):
        """切换工具栏显示状态"""
        toolbar = self._toolbars.get(name)
        if toolbar:
            if toolbar.isVisible():
                toolbar.hide()
            else:
                toolbar.show()
    
    def connect_signals(self, handler):
        """连接工具栏信号"""
        for name, toolbar in self._toolbars.items():
            if hasattr(toolbar, 'actionTriggered'):
                toolbar.actionTriggered.connect(handler)
            if hasattr(toolbar, 'formatChanged'):
                toolbar.formatChanged.connect(handler)
            if hasattr(toolbar, 'aiActionTriggered'):
                toolbar.aiActionTriggered.connect(handler)
