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
from ..services.qt_codex_adapter import QtCodexAdapter
from ..themes.ui_tokens import FONT, RADIUS, SPACING
from .codex_panel_parts import (
    CodexCardView,
    CodexFiltersWidget,
    CodexListView,
    CodexStatsView,
)

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
        self._qt_codex_adapter = QtCodexAdapter(codex_manager, parent=self) if codex_manager else None
        self._reference_detector = reference_detector
        
        self._init_ui()
        self._init_signals()
        self._apply_panel_theme()
        self._connect_theme_signals()
        self._refresh_entries()

        logger.info("Codex panel initialized")

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.sm, SPACING.sm, SPACING.sm, SPACING.sm)
        layout.setSpacing(SPACING.xs)
        
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
        layout.setContentsMargins(SPACING.xs, SPACING.xs, SPACING.xs, SPACING.xs)
        
        # 标题
        title_label = QLabel("📚 Codex知识库")
        title_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: {FONT.lg}px;
                font-weight: bold;
                padding: {SPACING.xs}px;
            }}
            """
        )
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 新建按钮
        self._new_btn = QPushButton("新建")
        self._new_btn.setFixedSize(50, 24)
        self._new_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #3498DB;
                color: white;
                border: none;
                border-radius: {RADIUS.sm}px;
                font-size: {FONT.sm}px;
                font-weight: bold;
                padding: {SPACING.xs}px {SPACING.sm}px;
            }}
            QPushButton:hover {{
                background-color: #2980B9;
            }}
            """
        )
        layout.addWidget(self._new_btn)
        
        return frame

    def _create_control_frame(self) -> QWidget:
        """创建控制栏（搜索/过滤/排序）"""
        self._filters = CodexFiltersWidget(parent=self)
        self._filters.apply_theme(self._is_panel_dark_theme())
        return self._filters

    def _create_content_area(self) -> QWidget:
        """创建内容区域"""
        # 使用Tab组织不同视图
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: 1px solid #BDC3C7;
                border-radius: {RADIUS.sm}px;
            }}
            QTabBar::tab {{
                padding: {SPACING.xs}px {SPACING.md}px;
                margin-right: 2px;
                font-size: {FONT.sm}px;
            }}
            QTabBar::tab:selected {{
                background-color: #3498DB;
                color: white;
            }}
            """
        )
        
        # 卡片视图
        self._card_view = CodexCardView(self._codex_manager, parent=self)
        tab_widget.addTab(self._card_view, "卡片视图")
        
        # 列表视图
        self._list_view = CodexListView(parent=self)
        tab_widget.addTab(self._list_view, "列表视图")
        
        # 统计视图
        self._stats_view = CodexStatsView(self._codex_manager, parent=self)
        tab_widget.addTab(self._stats_view, "统计")
        
        return tab_widget

    def _create_stats_frame(self) -> QFrame:
        """创建底部统计栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setMaximumHeight(30)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(SPACING.xs, SPACING.xs, SPACING.xs, SPACING.xs)
        
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet(f"font-size: {FONT.sm}px; color: #7F8C8D;")
        layout.addWidget(self._status_label)
        
        layout.addStretch()
        
        self._count_label = QLabel("0 个条目")
        self._count_label.setStyleSheet(f"font-size: {FONT.sm}px; color: #7F8C8D;")
        layout.addWidget(self._count_label)
        
        return frame

    def _init_signals(self):
        """初始化信号连接"""
        self._new_btn.clicked.connect(self._create_new_entry)

        # 搜索/过滤控件（内置 debounce）
        self._filters.filtersChanged.connect(self._refresh_entries)

        # 卡片视图信号
        self._card_view.entrySelected.connect(self.entrySelected.emit)
        self._card_view.entryEdit.connect(self._edit_entry)
        self._card_view.entryDelete.connect(self._delete_entry)
        self._card_view.aliasesEdit.connect(self._edit_aliases)
        self._card_view.relationshipsEdit.connect(self._edit_relationships)
        self._card_view.progressionEdit.connect(self._edit_progression)

        # 列表视图信号
        self._list_view.entrySelected.connect(self.entrySelected.emit)

        # 统计视图信号
        self._stats_view.entrySelected.connect(self._on_stats_entry_selected)
        self._stats_view.locationClicked.connect(self._on_stats_location_clicked)
        
        # Codex domain events -> Qt signals
        if self._qt_codex_adapter:
            self._qt_codex_adapter.entryAdded.connect(self._refresh_entries)
            self._qt_codex_adapter.entryUpdated.connect(self._refresh_entries)
            self._qt_codex_adapter.entryDeleted.connect(self._refresh_entries)
        
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

    def _reset_filters(self):
        """重置所有过滤器"""
        self._filters.reset_all()

    def _refresh_entries(self):
        """刷新条目显示"""
        if not self._codex_manager:
            return
        
        # 获取所有条目
        all_entries = self._codex_manager.get_all_entries()
        
        # 应用过滤
        filtered_entries = self._filter_entries(all_entries)
        
        # 更新视图（子组件）
        self._card_view.set_entries(filtered_entries)
        self._list_view.set_entries(filtered_entries)
        self._stats_view.refresh_statistics()
        
        # 更新状态栏
        self._count_label.setText(f"{len(filtered_entries)} 个条目")

    def _filter_entries(self, entries: List) -> List:
        """应用搜索/过滤/排序（由 CodexFiltersWidget 提供状态）。"""
        state = self._filters.get_state()
        filtered = entries

        # 类型过滤
        if state.entry_type is not None:
            filtered = [e for e in filtered if e.entry_type == state.entry_type]

        # 状态过滤
        if state.global_only:
            filtered = [e for e in filtered if getattr(e, "is_global", False)]

        if state.has_aliases:
            filtered = [e for e in filtered if getattr(e, "aliases", None)]

        if state.has_relations:
            filtered = [e for e in filtered if getattr(e, "relationships", None)]

        if state.has_progression:
            filtered = [e for e in filtered if getattr(e, "progression", None)]

        # 数量过滤
        alias_min = state.alias_min
        alias_max = state.alias_max
        filtered = [
            e
            for e in filtered
            if alias_min <= len(getattr(e, "aliases", []) or []) <= alias_max
        ]

        relation_min = state.relation_min
        relation_max = state.relation_max
        filtered = [
            e
            for e in filtered
            if relation_min
            <= len(getattr(e, "relationships", []) or [])
            <= relation_max
        ]

        # 搜索过滤（支持不同搜索范围）
        if state.search_text:
            search_lower = state.search_text.lower()
            search_filtered = []

            for entry in filtered:
                title = (getattr(entry, "title", "") or "").lower()
                desc = (getattr(entry, "description", "") or "").lower()
                aliases = getattr(entry, "aliases", []) or []

                if state.search_scope == "title":
                    match = search_lower in title
                elif state.search_scope == "desc":
                    match = search_lower in desc
                elif state.search_scope == "alias":
                    match = any(search_lower in (a or "").lower() for a in aliases)
                else:
                    match = (
                        search_lower in title
                        or search_lower in desc
                        or any(search_lower in (a or "").lower() for a in aliases)
                    )

                if match:
                    search_filtered.append(entry)

            filtered = search_filtered

        # 排序
        sort_index = state.sort_index
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
            filtered.sort(key=lambda e: len(getattr(e, "aliases", []) or []), reverse=True)
        elif sort_index == 7:  # 按关系数量 (多-少)
            filtered.sort(
                key=lambda e: len(getattr(e, "relationships", []) or []), reverse=True
            )
        elif sort_index == 8:  # 按进展数量 (多-少)
            filtered.sort(
                key=lambda e: len(getattr(e, "progression", []) or []), reverse=True
            )

        return filtered

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
        # 应用控制栏主题
        if hasattr(self, "_filters"):
            self._filters.apply_theme(self._is_panel_dark_theme())
        # 刷新所有卡片以应用新主题
        self._refresh_entries()

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
        self._filters.focus_search()
    
    def _clear_search(self):
        """清空搜索"""
        self._filters.clear_search()
    
    def _delete_selected_entry(self):
        """删除选中的条目"""
        # 这里可以添加删除逻辑，需要先确定当前选中的条目
        self._status_label.setText("请选择要删除的条目")
        logger.info("Delete shortcut activated")
