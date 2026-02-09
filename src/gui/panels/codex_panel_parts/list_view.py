import logging
from typing import List, TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from gui.themes.ui_tokens import FONT, RADIUS, SPACING

if TYPE_CHECKING:
    from core.codex_manager import CodexEntry

logger = logging.getLogger(__name__)


class CodexListView(QWidget):
    """列表视图（QListWidget），并提供空状态展示。"""

    entrySelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._empty_state = QLabel("暂无条目")
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setVisible(False)
        self._empty_state.setStyleSheet(
            f"""
            QLabel {{
                padding: {SPACING.lg}px;
                border-radius: {RADIUS.md}px;
                border: 1px dashed #BDC3C7;
                color: #7F8C8D;
                font-size: {FONT.md}px;
            }}
            """
        )
        layout.addWidget(self._empty_state)

        self._list_widget = QListWidget()
        self._list_widget.itemClicked.connect(self._on_item_clicked)
        self._list_widget.setStyleSheet(
            f"""
            QListWidget {{
                border: 1px solid #BDC3C7;
                border-radius: {RADIUS.sm}px;
                font-size: {FONT.md}px;
            }}
            QListWidget::item {{
                padding: {SPACING.xs}px {SPACING.sm}px;
                margin: {SPACING.xs}px;
                border-radius: {RADIUS.sm}px;
            }}
            QListWidget::item:selected {{
                background-color: #3498DB;
                color: white;
            }}
            """
        )
        layout.addWidget(self._list_widget)

    def set_entries(self, entries: List["CodexEntry"]):
        self._list_widget.clear()

        if not entries:
            self._empty_state.setVisible(True)
            self._list_widget.setVisible(False)
            return

        self._empty_state.setVisible(False)
        self._list_widget.setVisible(True)

        for entry in entries:
            item_text = f"[{entry.entry_type.value}] {entry.title}"
            if getattr(entry, "is_global", False):
                item_text += " 🌐"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            self._list_widget.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if entry_id:
            self.entrySelected.emit(entry_id)
