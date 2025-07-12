"""
现代化的Codex条目卡片组件
基于NovelCrafter的现代UI设计，支持别名、关系、进展的完整展示
"""

from typing import Optional, TYPE_CHECKING
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QPushButton, QToolButton, QMenu, QGraphicsDropShadowEffect,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QAction, QIcon, QPainter, QColor, QBrush, QPen, QFont, QPixmap

if TYPE_CHECKING:
    from core.codex_manager import CodexEntry, CodexManager

import logging

logger = logging.getLogger(__name__)


class QFlowLayout(QHBoxLayout):
    """流式布局 - 用于显示标签"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(4)
        
    def addWidget(self, widget):
        """添加组件"""
        super().addWidget(widget)
        widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class ModernTagWidget(QLabel):
    """现代化标签组件"""
    
    def __init__(self, text: str, tag_type: str = "default", parent=None):
        super().__init__(text, parent)
        self.tag_type = tag_type
        self._setup_style()
    
    def _setup_style(self):
        """设置样式"""
        colors = {
            "type": "#3498DB",      # 蓝色 - 类型标签
            "alias": "#E67E22",     # 橙色 - 别名标签
            "relation": "#9B59B6",  # 紫色 - 关系标签
            "progress": "#27AE60",  # 绿色 - 进展标签
            "global": "#E74C3C",    # 红色 - 全局标签
            "default": "#95A5A6"    # 灰色 - 默认
        }
        
        color = colors.get(self.tag_type, colors["default"])
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
                margin: 1px;
            }}
        """)
        
        self.setFixedHeight(20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class ModernCodexCard(QFrame):
    """现代化Codex条目卡片"""
    
    # 信号定义
    entrySelected = pyqtSignal(str)      # 条目选中
    entryEdit = pyqtSignal(str)          # 条目编辑
    entryDelete = pyqtSignal(str)        # 条目删除
    aliasesEdit = pyqtSignal(str)        # 别名编辑
    relationshipsEdit = pyqtSignal(str)  # 关系编辑
    progressionEdit = pyqtSignal(str)    # 进展编辑
    
    def __init__(self, entry: 'CodexEntry', codex_manager: 'CodexManager', parent=None):
        super().__init__(parent)
        self.entry = entry
        self.codex_manager = codex_manager
        self._expanded = False
        self._init_ui()
        self._setup_animations()
        self._update_content()
    
    def _init_ui(self):
        """初始化UI"""
        # 设置卡片基本样式
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self._apply_theme_styles()  # 应用主题样式

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 10, 12, 10)
        self.main_layout.setSpacing(8)

        # 创建头部（标题行）
        self._create_header()

        # 创建内容区
        self._create_content()

        # 创建操作按钮区（初始隐藏）
        self._create_actions()

        # 设置初始大小 - 增加高度确保内容可见
        self.setMinimumHeight(120)  # 最小高度
        self.setFixedHeight(120)    # 收起状态的高度
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 连接主题变更信号
        self._connect_theme_signals()
    
    def _create_header(self):
        """创建头部"""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧：标题和基本信息
        left_layout = QVBoxLayout()
        left_layout.setSpacing(2)
        
        # 标题行
        title_layout = QHBoxLayout()
        
        # 条目标题
        self.title_label = QLabel(self.entry.title)
        self._apply_title_style()
        title_layout.addWidget(self.title_label)
        
        # 类型标签
        self.type_tag = ModernTagWidget(self.entry.entry_type.value, "type")
        title_layout.addWidget(self.type_tag)
        
        title_layout.addStretch()
        left_layout.addLayout(title_layout)
        
        # 描述（截断显示）
        if self.entry.description:
            self.desc_label = QLabel(self._truncate_text(self.entry.description, 80))
            self._apply_desc_style()
            self.desc_label.setWordWrap(True)
            left_layout.addWidget(self.desc_label)
        
        header_layout.addLayout(left_layout, 1)
        
        # 右侧：状态指示器和展开按钮
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 状态指示器
        status_layout = QHBoxLayout()
        status_layout.setSpacing(2)
        
        # 全局标记
        if self.entry.is_global:
            global_tag = ModernTagWidget("🌐", "global")
            status_layout.addWidget(global_tag)
        
        # 别名数量
        if self.entry.aliases:
            alias_tag = ModernTagWidget(f"{len(self.entry.aliases)}个别名", "alias")
            status_layout.addWidget(alias_tag)
        
        status_layout.addStretch()
        right_layout.addLayout(status_layout)
        
        # 展开/收起按钮
        self.expand_btn = QToolButton()
        self.expand_btn.setText("▼")
        self.expand_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-size: 12px;
                color: #3498DB;
                padding: 2px;
            }
            QToolButton:hover {
                background-color: #ECF0F1;
                border-radius: 4px;
            }
        """)
        self.expand_btn.clicked.connect(self._toggle_expand)
        right_layout.addWidget(self.expand_btn)
        
        header_layout.addLayout(right_layout)
        self.main_layout.addLayout(header_layout)
    
    def _create_content(self):
        """创建可展开的内容区"""
        # 内容容器（初始隐藏）
        self.content_frame = QFrame()
        self.content_frame.setVisible(False)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 5, 0, 0)
        self.content_layout.setSpacing(8)
        
        # 完整描述
        if self.entry.description and len(self.entry.description) > 80:
            full_desc = QLabel(self.entry.description)
            full_desc.setStyleSheet("""
                QLabel {
                    color: #34495E;
                    font-size: 11px;
                    background-color: #F8F9FA;
                    padding: 8px;
                    border-radius: 6px;
                    border-left: 3px solid #3498DB;
                }
            """)
            full_desc.setWordWrap(True)
            self.content_layout.addWidget(full_desc)
        
        # 别名区域
        self._create_aliases_section()
        
        # 关系区域
        self._create_relationships_section()
        
        # 进展区域
        self._create_progression_section()
        
        self.main_layout.addWidget(self.content_frame)
    
    def _create_aliases_section(self):
        """创建别名区域"""
        if not self.entry.aliases:
            return
        
        aliases_frame = QFrame()
        aliases_layout = QVBoxLayout(aliases_frame)
        aliases_layout.setContentsMargins(0, 0, 0, 0)
        aliases_layout.setSpacing(4)
        
        # 别名标题
        aliases_title = QLabel("📝 别名")
        aliases_title.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: bold;
                color: #E67E22;
                margin-bottom: 2px;
            }
        """)
        aliases_layout.addWidget(aliases_title)
        
        # 别名标签流式布局
        aliases_container = QWidget()
        aliases_flow = QFlowLayout(aliases_container)
        
        for alias in self.entry.aliases:
            alias_tag = ModernTagWidget(alias, "alias")
            aliases_flow.addWidget(alias_tag)
        
        aliases_layout.addWidget(aliases_container)
        self.content_layout.addWidget(aliases_frame)
    
    def _create_relationships_section(self):
        """创建关系区域"""
        if not self.entry.relationships:
            return
        
        relations_frame = QFrame()
        relations_layout = QVBoxLayout(relations_frame)
        relations_layout.setContentsMargins(0, 0, 0, 0)
        relations_layout.setSpacing(4)
        
        # 关系标题
        relations_title = QLabel("🔗 关系")
        relations_title.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: bold;
                color: #9B59B6;
                margin-bottom: 2px;
            }
        """)
        relations_layout.addWidget(relations_title)
        
        # 关系列表（最多显示前3个）
        display_relations = self.entry.relationships[:3]
        for rel in display_relations:
            target_id = rel.get('target_id')
            if target_id in self.codex_manager._entries:
                target_entry = self.codex_manager._entries[target_id]
                rel_type = rel.get('relationship_type', '')
                
                rel_text = f"{rel_type} → {target_entry.title}"
                rel_label = QLabel(rel_text)
                rel_label.setStyleSheet("""
                    QLabel {
                        font-size: 10px;
                        color: #7F8C8D;
                        padding: 2px 4px;
                        background-color: #F8F9FA;
                        border-radius: 3px;
                        margin: 1px 0;
                    }
                """)
                relations_layout.addWidget(rel_label)
        
        # 如果关系超过3个，显示更多提示
        if len(self.entry.relationships) > 3:
            more_label = QLabel(f"...还有{len(self.entry.relationships) - 3}个关系")
            more_label.setStyleSheet("""
                QLabel {
                    font-size: 9px;
                    color: #BDC3C7;
                    font-style: italic;
                }
            """)
            relations_layout.addWidget(more_label)
        
        self.content_layout.addWidget(relations_frame)
    
    def _create_progression_section(self):
        """创建进展区域"""
        if not self.entry.progression:
            return
        
        progress_frame = QFrame()
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)
        
        # 进展标题
        progress_title = QLabel(f"📈 发展历程 ({len(self.entry.progression)}个事件)")
        progress_title.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: bold;
                color: #27AE60;
                margin-bottom: 2px;
            }
        """)
        progress_layout.addWidget(progress_title)
        
        # 最近的进展事件（按时间排序，显示最新的2个）
        recent_events = sorted(
            self.entry.progression, 
            key=lambda x: x.get('timestamp', ''), 
            reverse=True
        )[:2]
        
        for event in recent_events:
            event_type = event.get('event_type', '')
            description = event.get('description', '')
            event_text = f"[{event_type}] {description}"
            
            event_label = QLabel(self._truncate_text(event_text, 60))
            event_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: #7F8C8D;
                    padding: 2px 4px;
                    background-color: #F8F9FA;
                    border-radius: 3px;
                    margin: 1px 0;
                }
            """)
            progress_layout.addWidget(event_label)
        
        self.content_layout.addWidget(progress_frame)
    
    def _create_actions(self):
        """创建操作按钮区"""
        actions_frame = QFrame()
        actions_frame.setVisible(False)
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 5, 0, 0)
        actions_layout.setSpacing(8)
        
        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        edit_btn.clicked.connect(lambda: self.entryEdit.emit(self.entry.id))
        actions_layout.addWidget(edit_btn)
        
        # 别名管理按钮
        aliases_btn = QPushButton("别名")
        aliases_btn.setStyleSheet("""
            QPushButton {
                background-color: #E67E22;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D35400;
            }
        """)
        aliases_btn.clicked.connect(lambda: self.aliasesEdit.emit(self.entry.id))
        actions_layout.addWidget(aliases_btn)
        
        # 关系管理按钮
        relations_btn = QPushButton("关系")
        relations_btn.setStyleSheet("""
            QPushButton {
                background-color: #9B59B6;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8E44AD;
            }
        """)
        relations_btn.clicked.connect(lambda: self.relationshipsEdit.emit(self.entry.id))
        actions_layout.addWidget(relations_btn)
        
        # 进展管理按钮
        progress_btn = QPushButton("进展")
        progress_btn.setStyleSheet("""
            QPushButton {
                background-color: #27AE60;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        progress_btn.clicked.connect(lambda: self.progressionEdit.emit(self.entry.id))
        actions_layout.addWidget(progress_btn)
        
        actions_layout.addStretch()
        
        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
        """)
        delete_btn.clicked.connect(lambda: self.entryDelete.emit(self.entry.id))
        actions_layout.addWidget(delete_btn)
        
        self.actions_frame = actions_frame
        self.main_layout.addWidget(actions_frame)
    
    def _setup_animations(self):
        """设置动画效果"""
        self.expand_animation = QPropertyAnimation(self, b"maximumHeight")
        self.expand_animation.setDuration(300)
        self.expand_animation.setEasingCurve(QEasingCurve.Type.InOutQuart)
    
    def _toggle_expand(self):
        """切换展开/收起状态"""
        self._expanded = not self._expanded
        
        if self._expanded:
            # 展开
            self.content_frame.setVisible(True)
            self.actions_frame.setVisible(True)
            self.expand_btn.setText("▲")
            
            # 计算展开后的高度
            self.adjustSize()
            target_height = self.sizeHint().height()
            
            self.expand_animation.setStartValue(90)
            self.expand_animation.setEndValue(target_height)
        else:
            # 收起
            self.expand_btn.setText("▼")
            
            self.expand_animation.setStartValue(self.height())
            self.expand_animation.setEndValue(90)
            self.expand_animation.finished.connect(self._on_collapse_finished)
        
        self.expand_animation.start()
    
    def _on_collapse_finished(self):
        """收起动画完成后隐藏内容"""
        if not self._expanded:
            self.content_frame.setVisible(False)
            self.actions_frame.setVisible(False)
        self.expand_animation.finished.disconnect()

    def _apply_theme_styles(self):
        """应用主题样式"""
        # 检查当前主题
        is_dark_theme = self._is_dark_theme()

        if is_dark_theme:
            # 深色主题样式
            self.setStyleSheet("""
                ModernCodexCard {
                    background-color: #2D3748;
                    border: 1px solid #4A5568;
                    border-radius: 12px;
                    margin: 4px;
                    color: #E2E8F0;
                }
                ModernCodexCard:hover {
                    border-color: #63B3ED;
                    background-color: #364153;
                }
            """)
        else:
            # 浅色主题样式
            self.setStyleSheet("""
                ModernCodexCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E0E0E0;
                    border-radius: 12px;
                    margin: 4px;
                    color: #2D3748;
                }
                ModernCodexCard:hover {
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
        if hasattr(self, 'title_label'):
            self._apply_title_style()
        if hasattr(self, 'desc_label'):
            self._apply_desc_style()

    def _apply_title_style(self):
        """应用标题样式"""
        is_dark_theme = self._is_dark_theme()

        if is_dark_theme:
            self.title_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: #E2E8F0;
                }
            """)
        else:
            self.title_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: #2C3E50;
                }
            """)

    def _apply_desc_style(self):
        """应用描述样式"""
        is_dark_theme = self._is_dark_theme()

        if is_dark_theme:
            self.desc_label.setStyleSheet("""
                QLabel {
                    color: #A0AEC0;
                    font-size: 11px;
                    line-height: 1.3;
                }
            """)
        else:
            self.desc_label.setStyleSheet("""
                QLabel {
                    color: #7F8C8D;
                    font-size: 11px;
                    line-height: 1.3;
                }
            """)

    def _update_content(self):
        """更新卡片内容"""
        # 这个方法可以在条目数据更新时调用，重新构建UI
        pass
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """截断文本"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
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
        
        edit_action = menu.addAction("编辑条目")
        edit_action.triggered.connect(lambda: self.entryEdit.emit(self.entry.id))
        
        menu.addSeparator()
        
        aliases_action = menu.addAction("管理别名")
        aliases_action.triggered.connect(lambda: self.aliasesEdit.emit(self.entry.id))
        
        relations_action = menu.addAction("管理关系")
        relations_action.triggered.connect(lambda: self.relationshipsEdit.emit(self.entry.id))
        
        progress_action = menu.addAction("管理进展")
        progress_action.triggered.connect(lambda: self.progressionEdit.emit(self.entry.id))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("删除条目")
        delete_action.triggered.connect(lambda: self.entryDelete.emit(self.entry.id))
        
        menu.exec(position)