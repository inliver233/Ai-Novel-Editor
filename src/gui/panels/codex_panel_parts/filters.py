import logging
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.codex_manager import CodexEntryType
from gui.themes.ui_tokens import FONT, RADIUS, SPACING

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CodexFilterState:
    search_text: str
    search_scope: str  # all | title | desc | alias
    entry_type: Optional[CodexEntryType]
    global_only: bool
    has_aliases: bool
    has_relations: bool
    has_progression: bool
    alias_min: int
    alias_max: int
    relation_min: int
    relation_max: int
    sort_index: int


class CodexFiltersWidget(QWidget):
    """Codex 搜索/过滤/排序控制区（统一样式与行为）"""

    filtersChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._init_debounce()
        self._init_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.sm)

        # 搜索栏
        self.search_group = QGroupBox("🔍 智能搜索")
        search_layout = QVBoxLayout(self.search_group)
        search_layout.setSpacing(SPACING.xs)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标题、描述、别名...")
        search_row.addWidget(self.search_input)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(30, 30)
        self.clear_btn.clicked.connect(self.clear_search)
        search_row.addWidget(self.clear_btn)
        search_layout.addLayout(search_row)

        search_options = QHBoxLayout()
        search_scope_group = QButtonGroup(self)

        self.search_all_radio = QRadioButton("全部")
        self.search_all_radio.setChecked(True)
        search_scope_group.addButton(self.search_all_radio)
        search_options.addWidget(self.search_all_radio)

        self.search_title_radio = QRadioButton("仅标题")
        search_scope_group.addButton(self.search_title_radio)
        search_options.addWidget(self.search_title_radio)

        self.search_desc_radio = QRadioButton("仅描述")
        search_scope_group.addButton(self.search_desc_radio)
        search_options.addWidget(self.search_desc_radio)

        self.search_alias_radio = QRadioButton("仅别名")
        search_scope_group.addButton(self.search_alias_radio)
        search_options.addWidget(self.search_alias_radio)

        self._radio_buttons = [
            self.search_all_radio,
            self.search_title_radio,
            self.search_desc_radio,
            self.search_alias_radio,
        ]

        search_options.addStretch()
        search_layout.addLayout(search_options)
        layout.addWidget(self.search_group)

        # 过滤栏
        self.filter_group = QGroupBox("🎛️ 高级过滤")
        filter_layout = QVBoxLayout(self.filter_group)
        filter_layout.setSpacing(SPACING.sm)

        filter_row1 = QHBoxLayout()
        filter_row1.addWidget(QLabel("类型:"))

        self.type_filter = QComboBox()
        self.type_filter.addItem("全部类型", None)
        for entry_type in CodexEntryType:
            self.type_filter.addItem(f"{entry_type.value}", entry_type)
        filter_row1.addWidget(self.type_filter)

        filter_row1.addSpacing(SPACING.sm)

        self.global_only_check = QCheckBox("🌐 仅全局")
        self.has_aliases_check = QCheckBox("📝 有别名")
        self.has_relations_check = QCheckBox("🔗 有关系")
        self.has_progression_check = QCheckBox("📈 有进展")
        for checkbox in [
            self.global_only_check,
            self.has_aliases_check,
            self.has_relations_check,
            self.has_progression_check,
        ]:
            filter_row1.addWidget(checkbox)

        filter_row1.addStretch()
        filter_layout.addLayout(filter_row1)

        filter_row2 = QHBoxLayout()

        filter_row2.addWidget(QLabel("别名数:"))
        self.alias_count_min = QSpinBox()
        self.alias_count_min.setRange(0, 99)
        filter_row2.addWidget(self.alias_count_min)
        filter_row2.addWidget(QLabel("-"))
        self.alias_count_max = QSpinBox()
        self.alias_count_max.setRange(0, 99)
        self.alias_count_max.setValue(99)
        filter_row2.addWidget(self.alias_count_max)

        filter_row2.addSpacing(SPACING.sm)

        filter_row2.addWidget(QLabel("关系数:"))
        self.relation_count_min = QSpinBox()
        self.relation_count_min.setRange(0, 99)
        filter_row2.addWidget(self.relation_count_min)
        filter_row2.addWidget(QLabel("-"))
        self.relation_count_max = QSpinBox()
        self.relation_count_max.setRange(0, 99)
        self.relation_count_max.setValue(99)
        filter_row2.addWidget(self.relation_count_max)

        filter_row2.addSpacing(SPACING.sm)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self.reset_all)
        filter_row2.addWidget(self.reset_btn)

        filter_row2.addStretch()
        filter_layout.addLayout(filter_row2)

        layout.addWidget(self.filter_group)

        # 排序栏
        self.sort_group = QGroupBox("📊 排序方式")
        sort_layout = QHBoxLayout(self.sort_group)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "按标题 (A-Z)",
                "按标题 (Z-A)",
                "按创建时间 (新-旧)",
                "按创建时间 (旧-新)",
                "按更新时间 (新-旧)",
                "按更新时间 (旧-新)",
                "按别名数量 (多-少)",
                "按关系数量 (多-少)",
                "按进展数量 (多-少)",
            ]
        )
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addStretch()

        layout.addWidget(self.sort_group)

    def _init_debounce(self):
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self.filtersChanged.emit)

    def _init_signals(self):
        self.search_input.textChanged.connect(self._request_emit)

        for radio in self._radio_buttons:
            radio.toggled.connect(self._request_emit)

        self.type_filter.currentIndexChanged.connect(self._request_emit)

        for checkbox in [
            self.global_only_check,
            self.has_aliases_check,
            self.has_relations_check,
            self.has_progression_check,
        ]:
            checkbox.toggled.connect(self._request_emit)

        for spin in [
            self.alias_count_min,
            self.alias_count_max,
            self.relation_count_min,
            self.relation_count_max,
        ]:
            spin.valueChanged.connect(self._request_emit)

        self.sort_combo.currentIndexChanged.connect(self._request_emit)

    def _request_emit(self):
        self._debounce_timer.stop()
        self._debounce_timer.start()

    def get_state(self) -> CodexFilterState:
        if self.search_title_radio.isChecked():
            scope = "title"
        elif self.search_desc_radio.isChecked():
            scope = "desc"
        elif self.search_alias_radio.isChecked():
            scope = "alias"
        else:
            scope = "all"

        return CodexFilterState(
            search_text=self.search_input.text().strip(),
            search_scope=scope,
            entry_type=self.type_filter.currentData(),
            global_only=self.global_only_check.isChecked(),
            has_aliases=self.has_aliases_check.isChecked(),
            has_relations=self.has_relations_check.isChecked(),
            has_progression=self.has_progression_check.isChecked(),
            alias_min=self.alias_count_min.value(),
            alias_max=self.alias_count_max.value(),
            relation_min=self.relation_count_min.value(),
            relation_max=self.relation_count_max.value(),
            sort_index=self.sort_combo.currentIndex(),
        )

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def clear_search(self):
        self.search_input.clear()

    def reset_all(self):
        self.clear_search()
        self.search_all_radio.setChecked(True)

        self.type_filter.setCurrentIndex(0)
        for checkbox in [
            self.global_only_check,
            self.has_aliases_check,
            self.has_relations_check,
            self.has_progression_check,
        ]:
            checkbox.setChecked(False)

        self.alias_count_min.setValue(0)
        self.alias_count_max.setValue(99)
        self.relation_count_min.setValue(0)
        self.relation_count_max.setValue(99)

        self.sort_combo.setCurrentIndex(0)
        self._request_emit()

    def apply_theme(self, is_dark_theme: bool):
        """应用主题样式（由外部传入主题判断结果）"""
        self._apply_search_group_theme(is_dark_theme)
        self._apply_search_input_theme(is_dark_theme)
        self._apply_radio_theme(is_dark_theme)
        self._apply_filter_sort_theme(is_dark_theme)

    def _apply_search_group_theme(self, is_dark_theme: bool):
        if is_dark_theme:
            self.search_group.setStyleSheet(
                f"""
                QGroupBox {{
                    font-size: {FONT.md}px;
                    font-weight: bold;
                    color: #e8e8e8;
                    border: 1px solid #4A5568;
                    border-radius: {RADIUS.md}px;
                    margin-top: {SPACING.sm}px;
                    padding-top: {SPACING.xs}px;
                    background-color: #2D3748;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: {SPACING.sm}px;
                    padding: 0 {SPACING.xs}px 0 {SPACING.xs}px;
                    color: #e8e8e8;
                }}
                """
            )
        else:
            self.search_group.setStyleSheet(
                f"""
                QGroupBox {{
                    font-size: {FONT.md}px;
                    font-weight: bold;
                    color: #2C3E50;
                    border: 1px solid #BDC3C7;
                    border-radius: {RADIUS.md}px;
                    margin-top: {SPACING.sm}px;
                    padding-top: {SPACING.xs}px;
                    background-color: #FFFFFF;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: {SPACING.sm}px;
                    padding: 0 {SPACING.xs}px 0 {SPACING.xs}px;
                    color: #2C3E50;
                }}
                """
            )

    def _apply_search_input_theme(self, is_dark_theme: bool):
        if is_dark_theme:
            self.search_input.setStyleSheet(
                f"""
                QLineEdit {{
                    padding: {SPACING.sm}px {SPACING.md}px;
                    border: 2px solid #4A5568;
                    border-radius: {RADIUS.lg}px;
                    font-size: {FONT.lg}px;
                    background-color: #2a2a2a;
                    color: #e8e8e8;
                }}
                QLineEdit:focus {{
                    border-color: #63B3ED;
                    background-color: #353535;
                }}
                QLineEdit:hover {{
                    border-color: #505050;
                }}
                """
            )
        else:
            self.search_input.setStyleSheet(
                f"""
                QLineEdit {{
                    padding: {SPACING.sm}px {SPACING.md}px;
                    border: 2px solid #ECF0F1;
                    border-radius: {RADIUS.lg}px;
                    font-size: {FONT.lg}px;
                    background-color: #FAFAFA;
                    color: #2C3E50;
                }}
                QLineEdit:focus {{
                    border-color: #3498DB;
                    background-color: white;
                }}
                """
            )

    def _apply_radio_theme(self, is_dark_theme: bool):
        if is_dark_theme:
            radio_style = f"""
                QRadioButton {{
                    font-size: {FONT.sm}px;
                    color: #A0AEC0;
                    spacing: {SPACING.xs}px;
                }}
                QRadioButton::indicator {{
                    width: 12px;
                    height: 12px;
                }}
                QRadioButton::indicator:checked {{
                    background-color: #63B3ED;
                    border: 2px solid #2D3748;
                    border-radius: 6px;
                }}
                QRadioButton::indicator:unchecked {{
                    background-color: #4A5568;
                    border: 2px solid #2D3748;
                    border-radius: 6px;
                }}
            """
        else:
            radio_style = f"""
                QRadioButton {{
                    font-size: {FONT.sm}px;
                    color: #7F8C8D;
                    spacing: {SPACING.xs}px;
                }}
                QRadioButton::indicator {{
                    width: 12px;
                    height: 12px;
                }}
                QRadioButton::indicator:checked {{
                    background-color: #3498DB;
                    border: 2px solid white;
                    border-radius: 6px;
                }}
            """

        for radio in self._radio_buttons:
            radio.setStyleSheet(radio_style)

    def _apply_filter_sort_theme(self, is_dark_theme: bool):
        if is_dark_theme:
            group_style = f"""
                QGroupBox {{
                    font-size: {FONT.md}px;
                    font-weight: bold;
                    color: #e8e8e8;
                    border: 1px solid #4A5568;
                    border-radius: {RADIUS.md}px;
                    margin-top: {SPACING.sm}px;
                    padding-top: {SPACING.xs}px;
                    background-color: #2D3748;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: {SPACING.sm}px;
                    padding: 0 {SPACING.xs}px 0 {SPACING.xs}px;
                }}
            """
            combo_style = f"""
                QComboBox {{
                    padding: {SPACING.xs}px {SPACING.sm}px;
                    border: 1px solid #4A5568;
                    border-radius: {RADIUS.sm}px;
                    font-size: {FONT.sm}px;
                    min-width: 80px;
                    background-color: #2a2a2a;
                    color: #e8e8e8;
                }}
            """
            checkbox_style = f"""
                QCheckBox {{
                    font-size: {FONT.sm}px;
                    color: #A0AEC0;
                    spacing: {SPACING.xs}px;
                }}
                QCheckBox::indicator {{
                    width: 14px;
                    height: 14px;
                    border-radius: {RADIUS.sm}px;
                    border: 1px solid #4A5568;
                }}
                QCheckBox::indicator:checked {{
                    background-color: #63B3ED;
                    border-color: #63B3ED;
                }}
            """
            spin_style = f"font-size: {FONT.sm}px; max-width: 50px; color: #e8e8e8;"
            button_style = f"""
                QPushButton {{
                    background-color: #718096;
                    color: white;
                    border: none;
                    padding: {SPACING.xs}px {SPACING.sm}px;
                    border-radius: {RADIUS.sm}px;
                    font-size: {FONT.sm}px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #4A5568;
                }}
            """
        else:
            group_style = f"""
                QGroupBox {{
                    font-size: {FONT.md}px;
                    font-weight: bold;
                    color: #2C3E50;
                    border: 1px solid #BDC3C7;
                    border-radius: {RADIUS.md}px;
                    margin-top: {SPACING.sm}px;
                    padding-top: {SPACING.xs}px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: {SPACING.sm}px;
                    padding: 0 {SPACING.xs}px 0 {SPACING.xs}px;
                }}
            """
            combo_style = f"""
                QComboBox {{
                    padding: {SPACING.xs}px {SPACING.sm}px;
                    border: 1px solid #BDC3C7;
                    border-radius: {RADIUS.sm}px;
                    font-size: {FONT.sm}px;
                    min-width: 80px;
                }}
            """
            checkbox_style = f"""
                QCheckBox {{
                    font-size: {FONT.sm}px;
                    color: #34495E;
                    spacing: {SPACING.xs}px;
                }}
                QCheckBox::indicator {{
                    width: 14px;
                    height: 14px;
                    border-radius: {RADIUS.sm}px;
                    border: 1px solid #BDC3C7;
                }}
                QCheckBox::indicator:checked {{
                    background-color: #3498DB;
                    border-color: #3498DB;
                }}
            """
            spin_style = f"font-size: {FONT.sm}px; max-width: 50px;"
            button_style = f"""
                QPushButton {{
                    background-color: #95A5A6;
                    color: white;
                    border: none;
                    padding: {SPACING.xs}px {SPACING.sm}px;
                    border-radius: {RADIUS.sm}px;
                    font-size: {FONT.sm}px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #7F8C8D;
                }}
            """

        for group in [self.filter_group, self.sort_group]:
            group.setStyleSheet(group_style)

        self.type_filter.setStyleSheet(combo_style)
        self.sort_combo.setStyleSheet(
            combo_style.replace("min-width: 80px;", "min-width: 120px;")
        )

        for checkbox in [
            self.global_only_check,
            self.has_aliases_check,
            self.has_relations_check,
            self.has_progression_check,
        ]:
            checkbox.setStyleSheet(checkbox_style)

        for spin in [
            self.alias_count_min,
            self.alias_count_max,
            self.relation_count_min,
            self.relation_count_max,
        ]:
            spin.setStyleSheet(spin_style)

        self.reset_btn.setStyleSheet(button_style)
        self.clear_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #E74C3C;
                color: white;
                border: none;
                 border-radius: {RADIUS.pill}px;
                 font-size: {FONT.lg}px;
                 font-weight: bold;
             }}
             QPushButton:hover {{
                 background-color: #C0392B;
             }}
             """
         )
