"""
Codex知识库管理面板
基于NovelCrafter的Codex设计，提供直观的知识库管理界面
"""

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QMenu, QMessageBox, QSplitter,
    QGroupBox, QToolButton, QFrame, QComboBox, QTextEdit, QCheckBox,
    QTabWidget, QListWidget, QListWidgetItem, QScrollArea, QGridLayout,
    QDialog, QButtonGroup, QRadioButton, QSlider, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QAction, QIcon, QFont

if TYPE_CHECKING:
    from core.config import Config
    from core.shared import Shared
    from core.codex_manager import CodexManager, CodexEntry
    from core.reference_detector import ReferenceDetector

from core.codex_manager import CodexEntryType
from .modern_codex_card import ModernCodexCard

logger = logging.getLogger(__name__)


class CodexEntryWidget(QWidget):
    """单个Codex条目的卡片组件"""
    
    entrySelected = pyqtSignal(str)  # 条目选中信号
    entryEdit = pyqtSignal(str)      # 条目编辑信号
    entryDelete = pyqtSignal(str)    # 条目删除信号
    
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        
        # 标题行
        title_layout = QHBoxLayout()
        
        # 标题标签
        title_label = QLabel(self.entry.title)
        title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #2C3E50;
            }
        """)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 类型标签
        type_label = QLabel(self.entry.entry_type.value)
        type_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self._get_type_color()};
                color: white;
                padding: 2px 6px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        title_layout.addWidget(type_label)
        
        layout.addLayout(title_layout)
        
        # 描述（如果有）
        if self.entry.description:
            desc_label = QLabel(self.entry.description[:100] + "..." if len(self.entry.description) > 100 else self.entry.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #7F8C8D;
                    font-size: 11px;
                    padding: 2px 0px;
                }
            """)
            layout.addWidget(desc_label)
        
        # 标记行
        markers_layout = QHBoxLayout()
        
        # 全局标记
        if self.entry.is_global:
            global_label = QLabel("🌐 全局")
            global_label.setStyleSheet("""
                QLabel {
                    color: #E74C3C;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
            markers_layout.addWidget(global_label)
        
        # 别名数量
        if self.entry.aliases:
            alias_label = QLabel(f"📝 {len(self.entry.aliases)}个别名")
            alias_label.setStyleSheet("""
                QLabel {
                    color: #3498DB;
                    font-size: 10px;
                }
            """)
            markers_layout.addWidget(alias_label)
        
        markers_layout.addStretch()
        layout.addLayout(markers_layout)
        
        # 设置卡片样式
        self._apply_theme_styles()
        
        # 设置固定高度
        self.setFixedHeight(80)
        
        # 添加点击事件
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 连接主题变更信号
        self._connect_theme_signals()

    def _get_type_color(self) -> str:
        """根据类型获取颜色"""
        color_map = {
            CodexEntryType.CHARACTER: "#E74C3C",   # 红色
            CodexEntryType.LOCATION: "#2ECC71",    # 绿色
            CodexEntryType.OBJECT: "#F39C12",      # 橙色
            CodexEntryType.LORE: "#9B59B6",        # 紫色
            CodexEntryType.SUBPLOT: "#34495E",     # 深蓝灰
            CodexEntryType.OTHER: "#95A5A6",       # 灰色
        }
        return color_map.get(self.entry.entry_type, "#95A5A6")

    def _apply_theme_styles(self):
        """应用主题样式"""
        is_dark_theme = self._is_dark_theme()

        if is_dark_theme:
            # 深色主题样式
            self.setStyleSheet("""
                CodexEntryWidget {
                    background-color: #2D3748;
                    border: 1px solid #4A5568;
                    border-radius: 8px;
                    margin: 2px;
                    color: #E2E8F0;
                }
                CodexEntryWidget:hover {
                    border-color: #63B3ED;
                    background-color: #364153;
                }
            """)
        else:
            # 浅色主题样式
            self.setStyleSheet("""
                CodexEntryWidget {
                    background-color: #FFFFFF;
                    border: 1px solid #BDC3C7;
                    border-radius: 8px;
                    margin: 2px;
                    color: #2C3E50;
                }
                CodexEntryWidget:hover {
                    border-color: #3498DB;
                    background-color: #F8F9FA;
                }
            """)

    def _is_dark_theme(self) -> bool:
        """检查当前是否为深色主题"""
        try:
            # 尝试从主窗口获取主题管理器
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # 查找主窗口
                for widget in app.topLevelWidgets():
                    if hasattr(widget, '_theme_manager'):
                        theme_manager = widget._theme_manager
                        if theme_manager:
                            from gui.themes.theme_manager import ThemeType
                            current_theme = theme_manager.get_current_theme()
                            return current_theme == ThemeType.DARK

            # 备用方案：检查样式表
            if app:
                app_stylesheet = app.styleSheet()
                return "#1a1a1a" in app_stylesheet or "background-color: #1a1a1a" in app_stylesheet

            return True  # 默认深色主题
        except Exception:
            return True  # 出错时默认深色主题

    def _connect_theme_signals(self):
        """连接主题变更信号"""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # 查找主窗口的主题管理器
                for widget in app.topLevelWidgets():
                    if hasattr(widget, '_theme_manager'):
                        theme_manager = widget._theme_manager
                        if theme_manager:
                            # 连接主题变更信号
                            theme_manager.themeChanged.connect(self._on_theme_changed)
                            break
        except Exception:
            pass  # 如果连接失败，组件仍然可以工作

    def _on_theme_changed(self, theme_name: str):
        """响应主题变更"""
        self._apply_theme_styles()

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.entrySelected.emit(self.entry.id)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)
        
        edit_action = menu.addAction("编辑")
        edit_action.triggered.connect(lambda: self.entryEdit.emit(self.entry.id))
        
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(lambda: self.entryDelete.emit(self.entry.id))
        
        menu.exec(position)


class CodexPanel(QWidget):
    """Codex知识库管理面板"""
    
    # 信号定义
    entrySelected = pyqtSignal(str)      # 条目选择信号
    entryCreated = pyqtSignal(str)       # 条目创建信号
    entryUpdated = pyqtSignal(str)       # 条目更新信号
    entryDeleted = pyqtSignal(str)       # 条目删除信号
    referencesRequested = pyqtSignal(str) # 引用查看信号
    
    def __init__(self, config: 'Config', shared: 'Shared', codex_manager: 'CodexManager', 
                 reference_detector: 'ReferenceDetector', parent=None):
        super().__init__(parent)
        
        self._config = config
        self._shared = shared
        self._codex_manager = codex_manager
        self._reference_detector = reference_detector
        
        self._current_filter = None  # 当前过滤类型
        self._search_text = ""       # 搜索文本
        
        self._init_ui()
        self._init_signals()
        self._apply_panel_theme()
        self._connect_theme_signals()
        self._refresh_entries()

        logger.info("Codex panel initialized")

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        # 标题栏
        title_frame = self._create_title_frame()
        layout.addWidget(title_frame)
        
        # 控制栏
        control_frame = self._create_control_frame()
        layout.addWidget(control_frame)
        
        # 主要内容区
        content_widget = self._create_content_area()
        layout.addWidget(content_widget)
        
        # 底部统计栏
        stats_frame = self._create_stats_frame()
        layout.addWidget(stats_frame)

    def _create_title_frame(self) -> QFrame:
        """创建标题栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)
        
        # 标题
        title_label = QLabel("📚 Codex知识库")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                padding: 2px;
            }
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 新建按钮
        self._new_btn = QPushButton("新建")
        self._new_btn.setFixedSize(50, 24)
        self._new_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        layout.addWidget(self._new_btn)
        
        return frame

    def _create_control_frame(self) -> QFrame:
        """创建增强的控制栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # 搜索栏（增强版）
        search_group = QGroupBox("🔍 智能搜索")
        self._search_group = search_group  # 保存引用以便主题更新
        self._apply_search_group_theme()  # 应用主题样式
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(4)
        
        # 主搜索框
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索标题、描述、别名...")
        self._apply_search_input_theme()  # 应用主题样式
        search_row.addWidget(self._search_input)
        
        # 清除搜索按钮
        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(30, 30)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
        """)
        clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(clear_btn)
        
        search_layout.addLayout(search_row)
        
        # 搜索选项
        search_options = QHBoxLayout()
        
        # 搜索范围选择
        search_scope_group = QButtonGroup(self)
        
        self._search_all_radio = QRadioButton("全部")
        self._search_all_radio.setChecked(True)
        search_scope_group.addButton(self._search_all_radio)
        search_options.addWidget(self._search_all_radio)
        
        self._search_title_radio = QRadioButton("仅标题")
        search_scope_group.addButton(self._search_title_radio)
        search_options.addWidget(self._search_title_radio)
        
        self._search_desc_radio = QRadioButton("仅描述")
        search_scope_group.addButton(self._search_desc_radio)
        search_options.addWidget(self._search_desc_radio)
        
        self._search_alias_radio = QRadioButton("仅别名")
        search_scope_group.addButton(self._search_alias_radio)
        search_options.addWidget(self._search_alias_radio)
        
        # 样式化单选按钮
        self._radio_buttons = [self._search_all_radio, self._search_title_radio,
                              self._search_desc_radio, self._search_alias_radio]
        self._apply_radio_theme()  # 应用主题样式
        
        search_options.addStretch()
        search_layout.addLayout(search_options)
        layout.addWidget(search_group)
        
        # 过滤栏（增强版）
        filter_group = QGroupBox("🎛️ 高级过滤")
        filter_group.setStyleSheet("""
            QGroupBox {
                font-size: 11px;
                font-weight: bold;
                color: #2C3E50;
                border: 1px solid #BDC3C7;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(6)
        
        # 第一行：类型和状态过滤
        filter_row1 = QHBoxLayout()
        
        # 类型过滤
        filter_row1.addWidget(QLabel("类型:"))
        self._type_filter = QComboBox()
        self._type_filter.addItem("全部类型", None)
        for entry_type in CodexEntryType:
            self._type_filter.addItem(f"{entry_type.value}", entry_type)
        self._type_filter.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #BDC3C7;
                border-radius: 4px;
                font-size: 10px;
                min-width: 80px;
            }
        """)
        filter_row1.addWidget(self._type_filter)
        
        filter_row1.addSpacing(10)
        
        # 状态过滤复选框
        self._global_only_check = QCheckBox("🌐 仅全局")
        self._has_aliases_check = QCheckBox("📝 有别名")
        self._has_relations_check = QCheckBox("🔗 有关系")
        self._has_progression_check = QCheckBox("📈 有进展")
        
        checkbox_style = """
            QCheckBox {
                font-size: 10px;
                color: #34495E;
                spacing: 4px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #BDC3C7;
            }
            QCheckBox::indicator:checked {
                background-color: #3498DB;
                border-color: #3498DB;
            }
        """
        
        for checkbox in [self._global_only_check, self._has_aliases_check,
                        self._has_relations_check, self._has_progression_check]:
            checkbox.setStyleSheet(checkbox_style)
            filter_row1.addWidget(checkbox)
        
        filter_row1.addStretch()
        filter_layout.addLayout(filter_row1)
        
        # 第二行：关系和进展数量过滤
        filter_row2 = QHBoxLayout()
        
        # 别名数量过滤
        filter_row2.addWidget(QLabel("别名数:"))
        self._alias_count_min = QSpinBox()
        self._alias_count_min.setRange(0, 99)
        self._alias_count_min.setStyleSheet("font-size: 10px; max-width: 50px;")
        filter_row2.addWidget(self._alias_count_min)
        filter_row2.addWidget(QLabel("-"))
        self._alias_count_max = QSpinBox()
        self._alias_count_max.setRange(0, 99)
        self._alias_count_max.setValue(99)
        self._alias_count_max.setStyleSheet("font-size: 10px; max-width: 50px;")
        filter_row2.addWidget(self._alias_count_max)
        
        filter_row2.addSpacing(10)
        
        # 关系数量过滤
        filter_row2.addWidget(QLabel("关系数:"))
        self._relation_count_min = QSpinBox()
        self._relation_count_min.setRange(0, 99)
        self._relation_count_min.setStyleSheet("font-size: 10px; max-width: 50px;")
        filter_row2.addWidget(self._relation_count_min)
        filter_row2.addWidget(QLabel("-"))
        self._relation_count_max = QSpinBox()
        self._relation_count_max.setRange(0, 99)
        self._relation_count_max.setValue(99)
        self._relation_count_max.setStyleSheet("font-size: 10px; max-width: 50px;")
        filter_row2.addWidget(self._relation_count_max)
        
        filter_row2.addSpacing(10)
        
        # 重置过滤器按钮
        reset_btn = QPushButton("重置")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #95A5A6;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7F8C8D;
            }
        """)
        reset_btn.clicked.connect(self._reset_filters)
        filter_row2.addWidget(reset_btn)
        
        filter_row2.addStretch()
        filter_layout.addLayout(filter_row2)
        
        layout.addWidget(filter_group)
        
        # 排序选项
        sort_group = QGroupBox("📊 排序方式")
        sort_group.setStyleSheet("""
            QGroupBox {
                font-size: 11px;
                font-weight: bold;
                color: #2C3E50;
                border: 1px solid #BDC3C7;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        sort_layout = QHBoxLayout(sort_group)
        
        self._sort_combo = QComboBox()
        self._sort_combo.addItems([
            "按标题 (A-Z)",
            "按标题 (Z-A)",
            "按创建时间 (新-旧)",
            "按创建时间 (旧-新)",
            "按更新时间 (新-旧)",
            "按更新时间 (旧-新)",
            "按别名数量 (多-少)",
            "按关系数量 (多-少)",
            "按进展数量 (多-少)"
        ])
        self._sort_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #BDC3C7;
                border-radius: 4px;
                font-size: 10px;
                min-width: 120px;
            }
        """)
        sort_layout.addWidget(self._sort_combo)
        sort_layout.addStretch()
        
        layout.addWidget(sort_group)
        
        return frame

    def _create_content_area(self) -> QWidget:
        """创建内容区域"""
        # 使用Tab组织不同视图
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #BDC3C7;
                border-radius: 4px;
            }
            QTabBar::tab {
                padding: 4px 12px;
                margin-right: 2px;
                font-size: 10px;
            }
            QTabBar::tab:selected {
                background-color: #3498DB;
                color: white;
            }
        """)
        
        # 卡片视图
        self._card_view = self._create_card_view()
        tab_widget.addTab(self._card_view, "卡片视图")
        
        # 列表视图
        self._list_view = self._create_list_view()
        tab_widget.addTab(self._list_view, "列表视图")
        
        # 统计视图
        self._stats_view = self._create_statistics_view()
        tab_widget.addTab(self._stats_view, "统计")
        
        return tab_widget

    def _create_card_view(self) -> QWidget:
        """创建卡片视图"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 内容容器
        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._card_layout.setSpacing(4)
        
        scroll_area.setWidget(self._card_container)
        return scroll_area

    def _create_list_view(self) -> QWidget:
        """创建列表视图"""
        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #BDC3C7;
                border-radius: 4px;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #ECF0F1;
            }
            QListWidget::item:selected {
                background-color: #3498DB;
                color: white;
            }
        """)
        return self._list_widget

    def _create_statistics_view(self) -> QWidget:
        """创建统计视图"""
        # 使用标签页组织不同的统计视图
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #BDC3C7;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                padding: 2px 8px;
                font-size: 11px;
            }
        """)
        
        # 基础统计
        basic_stats = self._create_basic_stats()
        tab_widget.addTab(basic_stats, "概览")
        
        # 引用统计
        try:
            from .codex_reference_stats import CodexReferenceStatsWidget
            self._reference_stats = CodexReferenceStatsWidget(self._codex_manager)
            # 连接信号
            self._reference_stats.entrySelected.connect(self._on_stats_entry_selected)
            self._reference_stats.locationClicked.connect(self._on_stats_location_clicked)
            tab_widget.addTab(self._reference_stats, "引用统计")
        except ImportError:
            logger.warning("引用统计组件不可用")
            self._reference_stats = None
            
        # 增强的引用统计
        try:
            from .enhanced_reference_stats import EnhancedReferenceStatsWidget
            self._enhanced_stats = EnhancedReferenceStatsWidget(self._codex_manager)
            self._enhanced_stats.entry_selected.connect(self._on_stats_entry_selected)
            tab_widget.addTab(self._enhanced_stats, "高级统计")
        except ImportError:
            logger.warning("增强统计组件不可用")
            self._enhanced_stats = None
            
        # 关系图可视化
        try:
            from .relationship_graph import RelationshipGraphWidget
            self._relationship_graph = RelationshipGraphWidget(self._codex_manager)
            self._relationship_graph.entry_selected.connect(self._on_stats_entry_selected)
            tab_widget.addTab(self._relationship_graph, "关系网络")
        except ImportError:
            logger.warning("关系图组件不可用")
            self._relationship_graph = None
        
        return tab_widget
    
    def _create_basic_stats(self) -> QWidget:
        """创建基础统计视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 统计标签
        self._stats_labels = {}
        
        stats_info = [
            ("total", "总条目数"),
            ("characters", "角色"),
            ("locations", "地点"),
            ("objects", "物品"),
            ("lore", "传说"),
            ("global_entries", "全局条目"),
            ("tracked_entries", "追踪条目"),
            ("total_references", "总引用数")
        ]
        
        for key, label in stats_info:
            stat_layout = QHBoxLayout()
            stat_layout.addWidget(QLabel(f"{label}:"))
            
            value_label = QLabel("0")
            value_label.setStyleSheet("font-weight: bold; color: #2C3E50;")
            stat_layout.addWidget(value_label)
            stat_layout.addStretch()
            
            self._stats_labels[key] = value_label
            layout.addLayout(stat_layout)
        
        layout.addStretch()
        return widget

    def _create_stats_frame(self) -> QFrame:
        """创建底部统计栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setMaximumHeight(30)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)
        
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("font-size: 10px; color: #7F8C8D;")
        layout.addWidget(self._status_label)
        
        layout.addStretch()
        
        self._count_label = QLabel("0 个条目")
        self._count_label.setStyleSheet("font-size: 10px; color: #7F8C8D;")
        layout.addWidget(self._count_label)
        
        return frame

    def _init_signals(self):
        """初始化信号连接"""
        # 按钮信号
        self._new_btn.clicked.connect(self._create_new_entry)
        
        # 搜索信号
        self._search_input.textChanged.connect(self._on_search_changed)
        
        # 搜索范围信号
        self._search_all_radio.toggled.connect(self._on_filter_changed)
        self._search_title_radio.toggled.connect(self._on_filter_changed)
        self._search_desc_radio.toggled.connect(self._on_filter_changed)
        self._search_alias_radio.toggled.connect(self._on_filter_changed)
        
        # 过滤信号
        self._type_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._global_only_check.toggled.connect(self._on_filter_changed)
        self._has_aliases_check.toggled.connect(self._on_filter_changed)
        self._has_relations_check.toggled.connect(self._on_filter_changed)
        self._has_progression_check.toggled.connect(self._on_filter_changed)
        
        # 数量过滤信号
        self._alias_count_min.valueChanged.connect(self._on_filter_changed)
        self._alias_count_max.valueChanged.connect(self._on_filter_changed)
        self._relation_count_min.valueChanged.connect(self._on_filter_changed)
        self._relation_count_max.valueChanged.connect(self._on_filter_changed)
        
        # 排序信号
        self._sort_combo.currentIndexChanged.connect(self._on_filter_changed)
        
        # Codex管理器信号
        if self._codex_manager:
            self._codex_manager.entryAdded.connect(self._refresh_entries)
            self._codex_manager.entryUpdated.connect(self._refresh_entries)
            self._codex_manager.entryDeleted.connect(self._refresh_entries)
        
        # 设置快捷键
        self._setup_shortcuts()

    def _create_new_entry(self):
        """创建新条目"""
        try:
            from ..dialogs.codex_entry_dialog import CodexEntryDialog
            dialog = CodexEntryDialog(self._codex_manager, parent=self)
            dialog.entryUpdated.connect(self._on_entry_dialog_updated)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._status_label.setText("新条目已创建")
                self._refresh_entries()  # 刷新显示

        except ImportError as e:
            logger.warning(f"无法导入条目编辑对话框: {e}")
            # 回退到简单创建
            from datetime import datetime

            entry_id = self._codex_manager.add_entry(
                title=f"测试角色_{datetime.now().strftime('%H%M%S')}",
                entry_type=CodexEntryType.CHARACTER,
                description="这是一个用于测试UI显示的角色条目。包含了基本的描述信息，用来验证卡片是否能正确显示。",
                is_global=False
            )

            self._status_label.setText("新条目已创建")
            self._refresh_entries()  # 刷新显示
            logger.info(f"Created new entry: {entry_id}")

        except Exception as e:
            logger.error(f"创建条目失败: {e}")
            self._status_label.setText(f"创建失败: {str(e)}")

    def _on_search_changed(self, text: str):
        """搜索文本变化"""
        self._search_text = text
        self._apply_filters()

    def _on_filter_changed(self):
        """过滤条件变化"""
        self._current_filter = self._type_filter.currentData()
        self._apply_filters()
    
    def _clear_search(self):
        """清除搜索"""
        self._search_input.clear()
    
    def _reset_filters(self):
        """重置所有过滤器"""
        # 重置搜索
        self._search_input.clear()
        self._search_all_radio.setChecked(True)
        
        # 重置过滤器
        self._type_filter.setCurrentIndex(0)
        self._global_only_check.setChecked(False)
        self._has_aliases_check.setChecked(False)
        self._has_relations_check.setChecked(False)
        self._has_progression_check.setChecked(False)
        
        # 重置数量过滤
        self._alias_count_min.setValue(0)
        self._alias_count_max.setValue(99)
        self._relation_count_min.setValue(0)
        self._relation_count_max.setValue(99)
        
        # 重置排序
        self._sort_combo.setCurrentIndex(0)

    def _apply_filters(self):
        """应用过滤条件"""
        # 延迟刷新以避免频繁更新
        if not hasattr(self, '_filter_timer'):
            self._filter_timer = QTimer()
            self._filter_timer.setSingleShot(True)
            self._filter_timer.timeout.connect(self._refresh_entries)
        
        self._filter_timer.stop()
        self._filter_timer.start(300)  # 300ms延迟

    def _refresh_entries(self):
        """刷新条目显示"""
        if not self._codex_manager:
            return
        
        # 获取所有条目
        all_entries = self._codex_manager.get_all_entries()
        
        # 应用过滤
        filtered_entries = self._filter_entries(all_entries)
        
        # 更新卡片视图
        self._update_card_view(filtered_entries)
        
        # 更新列表视图
        self._update_list_view(filtered_entries)
        
        # 更新统计
        self._update_statistics()
        
        # 更新状态栏
        self._count_label.setText(f"{len(filtered_entries)} 个条目")

    def _filter_entries(self, entries: List) -> List:
        """增强的过滤条目"""
        filtered = entries
        
        # 类型过滤
        if self._current_filter is not None:
            filtered = [e for e in filtered if e.entry_type == self._current_filter]
        
        # 状态过滤
        if self._global_only_check.isChecked():
            filtered = [e for e in filtered if e.is_global]
        
        if self._has_aliases_check.isChecked():
            filtered = [e for e in filtered if e.aliases]
        
        if self._has_relations_check.isChecked():
            filtered = [e for e in filtered if e.relationships]
        
        if self._has_progression_check.isChecked():
            filtered = [e for e in filtered if e.progression]
        
        # 数量过滤
        alias_min = self._alias_count_min.value()
        alias_max = self._alias_count_max.value()
        filtered = [e for e in filtered if alias_min <= len(e.aliases) <= alias_max]
        
        relation_min = self._relation_count_min.value()
        relation_max = self._relation_count_max.value()
        filtered = [e for e in filtered if relation_min <= len(e.relationships) <= relation_max]
        
        # 搜索过滤（支持不同搜索范围）
        if self._search_text:
            search_lower = self._search_text.lower()
            search_filtered = []
            
            for entry in filtered:
                match = False
                
                if self._search_all_radio.isChecked():
                    # 搜索所有字段
                    if (search_lower in entry.title.lower() or 
                        search_lower in entry.description.lower() or
                        any(search_lower in alias.lower() for alias in entry.aliases)):
                        match = True
                elif self._search_title_radio.isChecked():
                    # 仅搜索标题
                    if search_lower in entry.title.lower():
                        match = True
                elif self._search_desc_radio.isChecked():
                    # 仅搜索描述
                    if search_lower in entry.description.lower():
                        match = True
                elif self._search_alias_radio.isChecked():
                    # 仅搜索别名
                    if any(search_lower in alias.lower() for alias in entry.aliases):
                        match = True
                
                if match:
                    search_filtered.append(entry)
            
            filtered = search_filtered
        
        # 排序
        sort_index = self._sort_combo.currentIndex()
        if sort_index == 0:  # 按标题 (A-Z)
            filtered.sort(key=lambda e: e.title.lower())
        elif sort_index == 1:  # 按标题 (Z-A)
            filtered.sort(key=lambda e: e.title.lower(), reverse=True)
        elif sort_index == 2:  # 按创建时间 (新-旧)
            filtered.sort(key=lambda e: e.created_at, reverse=True)
        elif sort_index == 3:  # 按创建时间 (旧-新)
            filtered.sort(key=lambda e: e.created_at)
        elif sort_index == 4:  # 按更新时间 (新-旧)
            filtered.sort(key=lambda e: e.updated_at, reverse=True)
        elif sort_index == 5:  # 按更新时间 (旧-新)
            filtered.sort(key=lambda e: e.updated_at)
        elif sort_index == 6:  # 按别名数量 (多-少)
            filtered.sort(key=lambda e: len(e.aliases), reverse=True)
        elif sort_index == 7:  # 按关系数量 (多-少)
            filtered.sort(key=lambda e: len(e.relationships), reverse=True)
        elif sort_index == 8:  # 按进展数量 (多-少)
            filtered.sort(key=lambda e: len(e.progression), reverse=True)
        
        return filtered

    def _update_card_view(self, entries: List):
        """更新现代化卡片视图 - 优化版本，支持增量更新和卡片复用"""
        logger.debug(f"更新卡片视图，条目数量: {len(entries)}")
        
        # 获取当前需要显示的条目ID集合
        new_entry_ids = {entry.id for entry in entries}
        
        # 获取当前已显示的卡片映射
        current_cards = self._get_current_card_mapping()
        current_entry_ids = set(current_cards.keys())
        
        # 计算需要的操作
        entries_to_add = new_entry_ids - current_entry_ids
        entries_to_remove = current_entry_ids - new_entry_ids
        entries_to_keep = current_entry_ids & new_entry_ids
        
        logger.debug(f"卡片更新统计: 添加{len(entries_to_add)}, 删除{len(entries_to_remove)}, 保留{len(entries_to_keep)}")
        
        # 禁用布局更新以提高性能
        self._card_container.setUpdatesEnabled(False)
        self._card_layout.setEnabled(False)
        
        try:
            # 移除不需要的卡片
            cards_removed = 0
            for entry_id in entries_to_remove:
                card = current_cards[entry_id]
                self._remove_card_from_layout(card)
                cards_removed += 1
            
            # 更新保留的卡片（检查是否需要刷新）
            cards_updated = 0
            for entry_id in entries_to_keep:
                card = current_cards[entry_id]
                entry = next((e for e in entries if e.id == entry_id), None)
                if entry and self._card_needs_update(card, entry):
                    self._update_existing_card(card, entry)
                    cards_updated += 1
            
            # 添加新卡片
            cards_added = 0
            entries_map = {entry.id: entry for entry in entries}
            
            for entry_id in entries_to_add:
                entry = entries_map.get(entry_id)
                if entry:
                    card = self._create_card(entry)
                    if card:
                        self._add_card_to_layout(card)
                        cards_added += 1
            
            # 确保卡片顺序与条目顺序一致
            if entries_to_add or entries_to_remove:
                self._reorder_cards_to_match_entries(entries)
            
        finally:
            # 重新启用布局更新
            self._card_container.setUpdatesEnabled(True)
            self._card_layout.setEnabled(True)
            self._card_container.update()
        
        logger.info(f"卡片视图增量更新完成: 添加{cards_added}, 删除{cards_removed}, 更新{cards_updated}")

    def _get_current_card_mapping(self) -> Dict[str, QWidget]:
        """获取当前卡片的ID映射"""
        card_mapping = {}
        
        for i in range(self._card_layout.count()):
            widget = self._card_layout.itemAt(i).widget()
            if widget and hasattr(widget, '_entry') and hasattr(widget._entry, 'id'):
                card_mapping[widget._entry.id] = widget
        
        return card_mapping

    def _card_needs_update(self, card: QWidget, entry) -> bool:
        """检查卡片是否需要更新"""
        if not hasattr(card, '_entry'):
            return True
        
        old_entry = card._entry
        
        # 检查关键字段是否发生变化
        if (old_entry.title != entry.title or
            old_entry.description != entry.description or
            old_entry.entry_type != entry.entry_type or
            old_entry.aliases != entry.aliases or
            old_entry.updated_at != entry.updated_at):
            return True
        
        return False

    def _update_existing_card(self, card: QWidget, entry):
        """更新现有卡片的内容"""
        try:
            # 如果卡片支持更新方法，调用它
            if hasattr(card, 'update_entry'):
                card.update_entry(entry)
            else:
                # 否则替换卡片
                old_card_index = self._get_card_index(card)
                self._remove_card_from_layout(card)
                new_card = self._create_card(entry)
                if new_card:
                    self._insert_card_at_index(new_card, old_card_index)
            
            logger.debug(f"更新卡片: {entry.title}")
            
        except Exception as e:
            logger.error(f"更新卡片失败 {entry.title}: {e}")

    def _create_card(self, entry) -> Optional[QWidget]:
        """创建新卡片"""
        try:
            from .modern_codex_card import ModernCodexCard
            
            logger.debug(f"创建卡片: {entry.title} ({entry.entry_type.value})")
            card = ModernCodexCard(entry, self._codex_manager)

            # 连接基本信号
            card.entrySelected.connect(self.entrySelected.emit)
            card.entryEdit.connect(self._edit_entry)
            card.entryDelete.connect(self._delete_entry)

            # 连接新的管理信号
            card.aliasesEdit.connect(self._edit_aliases)
            card.relationshipsEdit.connect(self._edit_relationships)
            card.progressionEdit.connect(self._edit_progression)

            logger.debug(f"卡片创建成功: {entry.title}")
            return card

        except Exception as e:
            logger.error(f"创建卡片失败 {entry.title}: {e}")
            # 创建简单的错误卡片
            error_card = QLabel(f"❌ 卡片加载失败: {entry.title}\n错误: {str(e)}")
            error_card.setStyleSheet("""
                QLabel {
                    background-color: #FFE6E6;
                    border: 1px solid #FF9999;
                    border-radius: 8px;
                    padding: 10px;
                    color: #CC0000;
                    font-size: 11px;
                }
            """)
            error_card.setWordWrap(True)
            error_card.setMinimumHeight(80)
            return error_card

    def _remove_card_from_layout(self, card: QWidget):
        """从布局中移除卡片"""
        self._card_layout.removeWidget(card)
        card.setParent(None)

    def _add_card_to_layout(self, card: QWidget):
        """将卡片添加到布局"""
        self._card_layout.addWidget(card)

    def _get_card_index(self, card: QWidget) -> int:
        """获取卡片在布局中的索引"""
        for i in range(self._card_layout.count()):
            if self._card_layout.itemAt(i).widget() == card:
                return i
        return -1

    def _insert_card_at_index(self, card: QWidget, index: int):
        """在指定索引位置插入卡片"""
        if index >= 0 and index < self._card_layout.count():
            self._card_layout.insertWidget(index, card)
        else:
            self._card_layout.addWidget(card)

    def _reorder_cards_to_match_entries(self, entries: List):
        """重新排序卡片以匹配条目顺序"""
        # 获取当前所有卡片
        current_cards = []
        for i in range(self._card_layout.count()):
            widget = self._card_layout.itemAt(i).widget()
            if widget:
                current_cards.append(widget)
        
        # 创建卡片ID到卡片的映射
        card_by_id = {}
        for card in current_cards:
            if hasattr(card, '_entry') and hasattr(card._entry, 'id'):
                card_by_id[card._entry.id] = card
        
        # 按照条目顺序重新排列卡片
        # 先移除所有卡片
        for card in current_cards:
            self._card_layout.removeWidget(card)
        
        # 按新顺序添加卡片
        for entry in entries:
            card = card_by_id.get(entry.id)
            if card:
                self._card_layout.addWidget(card)

    def _update_list_view(self, entries: List):
        """更新列表视图"""
        self._list_widget.clear()
        
        for entry in entries:
            item_text = f"[{entry.entry_type.value}] {entry.title}"
            if entry.is_global:
                item_text += " 🌐"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            self._list_widget.addItem(item)

    def _apply_panel_theme(self):
        """应用面板主题样式"""
        is_dark_theme = self._is_panel_dark_theme()

        if is_dark_theme:
            # 深色主题样式
            self.setStyleSheet("""
                CodexPanel {
                    background-color: #1a1a1a;
                    color: #e8e8e8;
                }
                QScrollArea {
                    background-color: #1a1a1a;
                    border: 1px solid #383838;
                    border-radius: 6px;
                }
                QScrollArea > QWidget > QWidget {
                    background-color: #1a1a1a;
                }
                QTabWidget::pane {
                    border: 1px solid #383838;
                    border-radius: 4px;
                    background-color: #1a1a1a;
                }
                QTabBar::tab {
                    background-color: #2D3748;
                    color: #e8e8e8;
                    padding: 4px 12px;
                    margin-right: 2px;
                    font-size: 10px;
                    border-radius: 4px 4px 0 0;
                }
                QTabBar::tab:selected {
                    background-color: #3498DB;
                    color: white;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #404040;
                }
            """)
        else:
            # 浅色主题样式
            self.setStyleSheet("""
                CodexPanel {
                    background-color: #f8f5e4;
                    color: #1a1611;
                }
                QScrollArea {
                    background-color: #f8f5e4;
                    border: 1px solid #c7b99c;
                    border-radius: 6px;
                }
                QScrollArea > QWidget > QWidget {
                    background-color: #f8f5e4;
                }
                QTabWidget::pane {
                    border: 1px solid #c7b99c;
                    border-radius: 4px;
                    background-color: #f8f5e4;
                }
                QTabBar::tab {
                    background-color: #f0e9d2;
                    color: #1a1611;
                    padding: 4px 12px;
                    margin-right: 2px;
                    font-size: 10px;
                    border-radius: 4px 4px 0 0;
                }
                QTabBar::tab:selected {
                    background-color: #8b4513;
                    color: #f8f5e4;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #e6dcc6;
                }
            """)

    def _is_panel_dark_theme(self) -> bool:
        """检查当前是否为深色主题"""
        try:
            # 尝试从主窗口获取主题管理器
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # 查找主窗口
                for widget in app.topLevelWidgets():
                    if hasattr(widget, '_theme_manager'):
                        theme_manager = widget._theme_manager
                        if theme_manager:
                            from gui.themes.theme_manager import ThemeType
                            current_theme = theme_manager.get_current_theme()
                            return current_theme == ThemeType.DARK

            # 备用方案：检查样式表
            if app:
                app_stylesheet = app.styleSheet()
                return "#1a1a1a" in app_stylesheet or "background-color: #1a1a1a" in app_stylesheet

            return True  # 默认深色主题
        except Exception:
            return True  # 出错时默认深色主题

    def _connect_theme_signals(self):
        """连接主题变更信号"""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # 查找主窗口的主题管理器
                for widget in app.topLevelWidgets():
                    if hasattr(widget, '_theme_manager'):
                        theme_manager = widget._theme_manager
                        if theme_manager:
                            # 连接主题变更信号
                            theme_manager.themeChanged.connect(self._on_panel_theme_changed)
                            break
        except Exception:
            pass  # 如果连接失败，组件仍然可以工作

    def _on_panel_theme_changed(self, theme_name: str):
        """响应主题变更"""
        self._apply_panel_theme()
        # 应用搜索相关组件的主题
        if hasattr(self, '_search_group'):
            self._apply_search_group_theme()
        if hasattr(self, '_search_input'):
            self._apply_search_input_theme()
        if hasattr(self, '_radio_buttons'):
            self._apply_radio_theme()
        # 刷新所有卡片以应用新主题
        self._refresh_entries()

    def _apply_search_group_theme(self):
        """应用搜索组的主题样式"""
        is_dark_theme = self._is_panel_dark_theme()

        if is_dark_theme:
            self._search_group.setStyleSheet("""
                QGroupBox {
                    font-size: 11px;
                    font-weight: bold;
                    color: #e8e8e8;
                    border: 1px solid #4A5568;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 4px;
                    background-color: #2D3748;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px 0 4px;
                    color: #e8e8e8;
                }
            """)
        else:
            self._search_group.setStyleSheet("""
                QGroupBox {
                    font-size: 11px;
                    font-weight: bold;
                    color: #2C3E50;
                    border: 1px solid #BDC3C7;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 4px;
                    background-color: #FFFFFF;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px 0 4px;
                    color: #2C3E50;
                }
            """)

    def _apply_search_input_theme(self):
        """应用搜索输入框的主题样式"""
        is_dark_theme = self._is_panel_dark_theme()

        if is_dark_theme:
            self._search_input.setStyleSheet("""
                QLineEdit {
                    padding: 6px 12px;
                    border: 2px solid #4A5568;
                    border-radius: 8px;
                    font-size: 12px;
                    background-color: #2a2a2a;
                    color: #e8e8e8;
                }
                QLineEdit:focus {
                    border-color: #63B3ED;
                    background-color: #353535;
                }
                QLineEdit:hover {
                    border-color: #505050;
                }
            """)
        else:
            self._search_input.setStyleSheet("""
                QLineEdit {
                    padding: 6px 12px;
                    border: 2px solid #ECF0F1;
                    border-radius: 8px;
                    font-size: 12px;
                    background-color: #FAFAFA;
                    color: #2C3E50;
                }
                QLineEdit:focus {
                    border-color: #3498DB;
                    background-color: white;
                }
            """)

    def _apply_radio_theme(self):
        """应用单选按钮的主题样式"""
        is_dark_theme = self._is_panel_dark_theme()

        if is_dark_theme:
            radio_style = """
                QRadioButton {
                    font-size: 10px;
                    color: #A0AEC0;
                    spacing: 4px;
                }
                QRadioButton::indicator {
                    width: 12px;
                    height: 12px;
                }
                QRadioButton::indicator:checked {
                    background-color: #63B3ED;
                    border: 2px solid #2D3748;
                    border-radius: 6px;
                }
                QRadioButton::indicator:unchecked {
                    background-color: #4A5568;
                    border: 2px solid #2D3748;
                    border-radius: 6px;
                }
            """
        else:
            radio_style = """
                QRadioButton {
                    font-size: 10px;
                    color: #7F8C8D;
                    spacing: 4px;
                }
                QRadioButton::indicator {
                    width: 12px;
                    height: 12px;
                }
                QRadioButton::indicator:checked {
                    background-color: #3498DB;
                    border: 2px solid white;
                    border-radius: 6px;
                }
            """

        for radio in self._radio_buttons:
            radio.setStyleSheet(radio_style)

    def _update_statistics(self):
        """更新统计信息"""
        if not self._codex_manager:
            return
        
        stats = self._codex_manager.get_statistics()
        
        # 更新统计标签
        self._stats_labels["total"].setText(str(stats["total_entries"]))
        self._stats_labels["global_entries"].setText(str(stats["global_entries"]))
        self._stats_labels["tracked_entries"].setText(str(stats["tracked_entries"]))
        
        # 更新类型统计
        type_mapping = {
            "characters": "CHARACTER",
            "locations": "LOCATION", 
            "objects": "OBJECT",
            "lore": "LORE"
        }
        
        for ui_key, type_key in type_mapping.items():
            if ui_key in self._stats_labels:
                count = stats["type_counts"].get(type_key, 0)
                self._stats_labels[ui_key].setText(str(count))
        
        # 更新总引用数
        if "total_references" in self._stats_labels:
            self._stats_labels["total_references"].setText(str(stats.get("total_references", 0)))
        
        # 刷新引用统计组件
        if hasattr(self, '_reference_stats') and self._reference_stats:
            self._reference_stats.refresh()
            
        # 刷新增强统计组件
        if hasattr(self, '_enhanced_stats') and self._enhanced_stats:
            self._enhanced_stats.refresh_statistics()
            
        # 刷新关系图组件
        if hasattr(self, '_relationship_graph') and self._relationship_graph:
            self._relationship_graph.refresh_graph()

    def _edit_entry(self, entry_id: str):
        """编辑条目"""
        try:
            from ..dialogs.codex_entry_dialog import CodexEntryDialog
            dialog = CodexEntryDialog(self._codex_manager, entry_id, parent=self)
            dialog.entryUpdated.connect(self._on_entry_dialog_updated)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._status_label.setText(f"条目已更新: {entry_id}")
                
        except ImportError as e:
            logger.warning(f"无法导入条目编辑对话框: {e}")
            self._status_label.setText(f"编辑条目: {entry_id}")
            logger.info(f"Edit entry requested: {entry_id}")

    def _delete_entry(self, entry_id: str):
        """删除条目"""
        reply = QMessageBox.question(
            self, "确认删除", 
            "确定要删除这个条目吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self._codex_manager.delete_entry(entry_id):
                self._status_label.setText("条目已删除")
                logger.info(f"Entry deleted: {entry_id}")

    @pyqtSlot(str)
    def refresh_for_document(self, document_id: str):
        """为特定文档刷新引用信息"""
        self._status_label.setText(f"更新文档引用: {document_id}")
        # TODO: 高亮该文档中被引用的条目
    
    @pyqtSlot(str)
    def _on_stats_entry_selected(self, entry_id: str):
        """统计视图中选择条目"""
        # 在主视图中也选中该条目
        # TODO: 实现在卡片/列表视图中高亮对应条目
        self.entrySelected.emit(entry_id)
        self._status_label.setText(f"选中条目: {entry_id}")
    
    @pyqtSlot(str, int)
    def _on_stats_location_clicked(self, document_id: str, position: int):
        """统计视图中点击位置"""
        # 通知主窗口跳转到指定文档和位置
        self._status_label.setText(f"跳转到: {document_id} 位置 {position}")
        # TODO: 实现跳转功能
    
    @pyqtSlot(str)
    def _on_entry_dialog_updated(self, entry_id: str):
        """条目对话框更新处理"""
        # 刷新显示
        self._refresh_entries()
        # 发送信号
        self.entryUpdated.emit(entry_id)
    
    def _edit_aliases(self, entry_id: str):
        """编辑条目别名"""
        try:
            from ..dialogs.alias_management_dialog import AliasManagementDialog
            dialog = AliasManagementDialog(self._codex_manager, entry_id, parent=self)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._status_label.setText(f"别名已更新: {entry_id}")
                self._refresh_entries()
                
        except ImportError as e:
            logger.warning(f"无法导入别名管理对话框: {e}")
            # 简单的占位符实现
            entry = self._codex_manager.get_entry(entry_id)
            if entry:
                self._status_label.setText(f"编辑 {entry.title} 的别名功能待实现")
                logger.info(f"Edit aliases requested for: {entry.title}")
    
    def _edit_relationships(self, entry_id: str):
        """编辑条目关系"""
        try:
            from ..dialogs.relationship_management_dialog import RelationshipManagementDialog
            dialog = RelationshipManagementDialog(self._codex_manager, entry_id, parent=self)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._status_label.setText(f"关系已更新: {entry_id}")
                self._refresh_entries()
                
        except ImportError as e:
            logger.warning(f"无法导入关系管理对话框: {e}")
            # 简单的占位符实现
            entry = self._codex_manager.get_entry(entry_id)
            if entry:
                self._status_label.setText(f"编辑 {entry.title} 的关系功能待实现")
                logger.info(f"Edit relationships requested for: {entry.title}")
    
    def _edit_progression(self, entry_id: str):
        """编辑条目进展"""
        try:
            from ..dialogs.progression_management_dialog import ProgressionManagementDialog
            dialog = ProgressionManagementDialog(self._codex_manager, entry_id, parent=self)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._status_label.setText(f"进展已更新: {entry_id}")
                self._refresh_entries()
                
        except ImportError as e:
            logger.warning(f"无法导入进展管理对话框: {e}")
            # 简单的占位符实现
            entry = self._codex_manager.get_entry(entry_id)
            if entry:
                self._status_label.setText(f"编辑 {entry.title} 的进展功能待实现")
                logger.info(f"Edit progression requested for: {entry.title}")
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        from PyQt6.QtGui import QShortcut, QKeySequence
        
        # Ctrl+N: 新建条目
        new_shortcut = QShortcut(QKeySequence.StandardKey.New, self)
        new_shortcut.activated.connect(self._create_new_entry)
        
        # Ctrl+F: 聚焦搜索框
        search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        search_shortcut.activated.connect(self._focus_search)
        
        # Ctrl+R: 刷新列表
        refresh_shortcut = QShortcut(QKeySequence.StandardKey.Refresh, self)
        refresh_shortcut.activated.connect(self._refresh_entries)
        
        # Escape: 清空搜索
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self._clear_search)
        
        # Delete: 删除选中条目
        delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self)
        delete_shortcut.activated.connect(self._delete_selected_entry)
    
    def _focus_search(self):
        """聚焦搜索框"""
        self._search_input.setFocus()
        self._search_input.selectAll()
    
    def _clear_search(self):
        """清空搜索"""
        self._search_input.clear()
    
    def _delete_selected_entry(self):
        """删除选中的条目"""
        # 这里可以添加删除逻辑，需要先确定当前选中的条目
        self._status_label.setText("请选择要删除的条目")
        logger.info("Delete shortcut activated")