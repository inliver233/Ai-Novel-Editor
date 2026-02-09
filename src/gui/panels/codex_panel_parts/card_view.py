import logging
from typing import Dict, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ..modern_codex_card import ModernCodexCard
from gui.themes.ui_tokens import FONT, RADIUS, SPACING

if TYPE_CHECKING:
    from core.codex_manager import CodexEntry, CodexManager

logger = logging.getLogger(__name__)


class CodexCardView(QScrollArea):
    """卡片视图（ModernCodexCard 列表），支持增量更新与复用。"""

    entrySelected = pyqtSignal(str)
    entryEdit = pyqtSignal(str)
    entryDelete = pyqtSignal(str)
    aliasesEdit = pyqtSignal(str)
    relationshipsEdit = pyqtSignal(str)
    progressionEdit = pyqtSignal(str)

    def __init__(self, codex_manager: "CodexManager", parent=None):
        super().__init__(parent)
        self._codex_manager = codex_manager

        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

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
        container_layout.addWidget(self._empty_state)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_layout.setSpacing(SPACING.xs)
        container_layout.addWidget(self._cards_container)

        self.setWidget(container)

    def set_entries(self, entries: List["CodexEntry"]):
        logger.debug(f"更新卡片视图，条目数量: {len(entries)}")

        self._set_empty_state_visible(len(entries) == 0)
        if not entries:
            self._clear_cards()
            return

        new_entry_ids = {entry.id for entry in entries}
        current_cards = self._get_current_card_mapping()
        current_entry_ids = set(current_cards.keys())

        entries_to_add = new_entry_ids - current_entry_ids
        entries_to_remove = current_entry_ids - new_entry_ids
        entries_to_keep = current_entry_ids & new_entry_ids

        logger.debug(
            f"卡片更新统计: 添加{len(entries_to_add)}, 删除{len(entries_to_remove)}, 保留{len(entries_to_keep)}"
        )

        self._cards_container.setUpdatesEnabled(False)
        self._cards_layout.setEnabled(False)

        try:
            cards_removed = 0
            for entry_id in entries_to_remove:
                card = current_cards[entry_id]
                self._remove_card(card)
                cards_removed += 1

            cards_updated = 0
            for entry_id in entries_to_keep:
                card = current_cards[entry_id]
                entry = next((e for e in entries if e.id == entry_id), None)
                if entry and self._card_needs_update(card, entry):
                    self._update_existing_card(card, entry)
                    cards_updated += 1

            cards_added = 0
            entries_map = {entry.id: entry for entry in entries}
            for entry_id in entries_to_add:
                entry = entries_map.get(entry_id)
                if entry:
                    card = self._create_card(entry)
                    if card:
                        self._cards_layout.addWidget(card)
                        cards_added += 1

            if entries_to_add or entries_to_remove:
                self._reorder_cards_to_match_entries(entries)

        finally:
            self._cards_container.setUpdatesEnabled(True)
            self._cards_layout.setEnabled(True)
            self._cards_container.update()

        logger.info(
            f"卡片视图增量更新完成: 添加{cards_added}, 删除{cards_removed}, 更新{cards_updated}"
        )

    def _set_empty_state_visible(self, visible: bool):
        self._empty_state.setVisible(visible)
        self._cards_container.setVisible(not visible)

    def _clear_cards(self):
        for i in reversed(range(self._cards_layout.count())):
            widget = self._cards_layout.itemAt(i).widget()
            if widget:
                self._cards_layout.removeWidget(widget)
                widget.setParent(None)

    def _get_entry_id_from_card(self, card: QWidget) -> Optional[str]:
        entry = getattr(card, "_entry", None) or getattr(card, "entry", None)
        if entry and hasattr(entry, "id"):
            return entry.id
        return None

    def _get_current_card_mapping(self) -> Dict[str, QWidget]:
        mapping: Dict[str, QWidget] = {}
        for i in range(self._cards_layout.count()):
            widget = self._cards_layout.itemAt(i).widget()
            if not widget:
                continue
            entry_id = self._get_entry_id_from_card(widget)
            if entry_id:
                mapping[entry_id] = widget
        return mapping

    def _card_needs_update(self, card: QWidget, entry: "CodexEntry") -> bool:
        old_entry = getattr(card, "_entry", None) or getattr(card, "entry", None)
        if not old_entry:
            return True

        if (
            old_entry.title != entry.title
            or old_entry.description != entry.description
            or old_entry.entry_type != entry.entry_type
            or old_entry.aliases != entry.aliases
            or old_entry.updated_at != entry.updated_at
        ):
            return True

        return False

    def _update_existing_card(self, card: QWidget, entry: "CodexEntry"):
        try:
            if hasattr(card, "update_entry"):
                card.update_entry(entry)
                card._entry = entry
                if hasattr(card, "entry"):
                    card.entry = entry
                return

            old_index = self._get_card_index(card)
            self._remove_card(card)
            new_card = self._create_card(entry)
            if new_card:
                self._insert_card_at_index(new_card, old_index)

            logger.debug(f"更新卡片: {entry.title}")
        except Exception as e:
            logger.error(f"更新卡片失败 {entry.title}: {e}")

    def _create_card(self, entry: "CodexEntry") -> QWidget:
        try:
            logger.debug(f"创建卡片: {entry.title} ({entry.entry_type.value})")
            card = ModernCodexCard(entry, self._codex_manager)

            card._entry = entry

            card.entrySelected.connect(self.entrySelected.emit)
            card.entryEdit.connect(self.entryEdit.emit)
            card.entryDelete.connect(self.entryDelete.emit)
            card.aliasesEdit.connect(self.aliasesEdit.emit)
            card.relationshipsEdit.connect(self.relationshipsEdit.emit)
            card.progressionEdit.connect(self.progressionEdit.emit)

            return card
        except Exception as e:
            logger.error(f"创建卡片失败 {entry.title}: {e}")
            error_card = QLabel(f"❌ 卡片加载失败: {entry.title}\n错误: {str(e)}")
            error_card._entry = entry
            error_card.setStyleSheet(
                f"""
                QLabel {{
                    background-color: #FFE6E6;
                    border: 1px solid #FF9999;
                    border-radius: {RADIUS.md}px;
                    padding: {SPACING.md}px;
                    color: #CC0000;
                    font-size: {FONT.md}px;
                }}
                """
            )
            error_card.setWordWrap(True)
            error_card.setMinimumHeight(80)
            return error_card

    def _remove_card(self, card: QWidget):
        self._cards_layout.removeWidget(card)
        card.setParent(None)

    def _get_card_index(self, card: QWidget) -> int:
        for i in range(self._cards_layout.count()):
            if self._cards_layout.itemAt(i).widget() == card:
                return i
        return -1

    def _insert_card_at_index(self, card: QWidget, index: int):
        if 0 <= index < self._cards_layout.count():
            self._cards_layout.insertWidget(index, card)
        else:
            self._cards_layout.addWidget(card)

    def _reorder_cards_to_match_entries(self, entries: List["CodexEntry"]):
        current_cards: List[QWidget] = []
        for i in range(self._cards_layout.count()):
            widget = self._cards_layout.itemAt(i).widget()
            if widget:
                current_cards.append(widget)

        card_by_id: Dict[str, QWidget] = {}
        for card in current_cards:
            entry_id = self._get_entry_id_from_card(card)
            if entry_id:
                card_by_id[entry_id] = card

        for card in current_cards:
            self._cards_layout.removeWidget(card)

        for entry in entries:
            card = card_by_id.get(entry.id)
            if card:
                self._cards_layout.addWidget(card)
