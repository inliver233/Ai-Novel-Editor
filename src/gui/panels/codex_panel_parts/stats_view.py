import logging
from typing import Dict, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from core.codex_manager import CodexManager

logger = logging.getLogger(__name__)


class CodexStatsView(QTabWidget):
    """统计视图子组件（概览/引用/高级统计/关系）。"""

    entrySelected = pyqtSignal(str)
    locationClicked = pyqtSignal(str, int)

    def __init__(self, codex_manager: "CodexManager", parent=None):
        super().__init__(parent)
        self._codex_manager = codex_manager
        self._stats_labels: Dict[str, QLabel] = {}
        self._reference_stats = None
        self._enhanced_stats = None
        self._relationship_graph = None

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(
            """
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
            """
        )

        basic_stats = self._create_basic_stats()
        self.addTab(basic_stats, "概览")

        self._init_optional_tabs()

    def _init_optional_tabs(self):
        try:
            from ..codex_reference_stats import CodexReferenceStatsWidget

            self._reference_stats = CodexReferenceStatsWidget(self._codex_manager)
            self._reference_stats.entrySelected.connect(self.entrySelected.emit)
            self._reference_stats.locationClicked.connect(self.locationClicked.emit)
            self.addTab(self._reference_stats, "引用统计")
        except ImportError:
            logger.warning("引用统计组件不可用")
            self._reference_stats = None

        try:
            from ..enhanced_reference_stats import EnhancedReferenceStatsWidget

            self._enhanced_stats = EnhancedReferenceStatsWidget(self._codex_manager)
            self._enhanced_stats.entry_selected.connect(self.entrySelected.emit)
            self.addTab(self._enhanced_stats, "高级统计")
        except ImportError:
            logger.warning("增强统计组件不可用")
            self._enhanced_stats = None

        try:
            from ..relationship_graph import RelationshipGraphWidget

            self._relationship_graph = RelationshipGraphWidget(self._codex_manager)
            self._relationship_graph.entry_selected.connect(self.entrySelected.emit)
            self.addTab(self._relationship_graph, "关系网络")
        except ImportError:
            logger.warning("关系图组件不可用")
            self._relationship_graph = None

    def _create_basic_stats(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        stats_info = [
            ("total", "总条目数"),
            ("characters", "角色"),
            ("locations", "地点"),
            ("objects", "物品"),
            ("lore", "传说"),
            ("global_entries", "全局条目"),
            ("tracked_entries", "追踪条目"),
            ("total_references", "总引用数"),
        ]

        for key, label in stats_info:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label}:"))

            value_label = QLabel("0")
            value_label.setStyleSheet("font-weight: bold; color: #2C3E50;")
            row.addWidget(value_label)
            row.addStretch()

            self._stats_labels[key] = value_label
            layout.addLayout(row)

        layout.addStretch()
        return widget

    def refresh_statistics(self):
        if not self._codex_manager:
            return

        stats = self._codex_manager.get_statistics()

        self._stats_labels["total"].setText(str(stats["total_entries"]))
        self._stats_labels["global_entries"].setText(str(stats["global_entries"]))
        self._stats_labels["tracked_entries"].setText(str(stats["tracked_entries"]))

        type_mapping = {
            "characters": "CHARACTER",
            "locations": "LOCATION",
            "objects": "OBJECT",
            "lore": "LORE",
        }
        for ui_key, type_key in type_mapping.items():
            if ui_key in self._stats_labels:
                self._stats_labels[ui_key].setText(str(stats["type_counts"].get(type_key, 0)))

        if "total_references" in self._stats_labels:
            self._stats_labels["total_references"].setText(str(stats.get("total_references", 0)))

        if self._reference_stats:
            self._reference_stats.refresh()
        if self._enhanced_stats:
            self._enhanced_stats.refresh_statistics()
        if self._relationship_graph:
            self._relationship_graph.refresh_graph()

