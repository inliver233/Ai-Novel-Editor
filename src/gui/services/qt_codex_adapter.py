"""
QtCodexAdapter

CodexManager is intentionally Qt-free (domain-friendly). When the GUI needs Qt signals,
use this adapter to forward CodexManager domain events into `pyqtSignal`s.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from core.codex_manager import CodexManager

logger = logging.getLogger(__name__)


class QtCodexAdapter(QObject):
    entryAdded = pyqtSignal(str)
    entryUpdated = pyqtSignal(str)
    entryDeleted = pyqtSignal(str)
    referencesUpdated = pyqtSignal(str, int)

    def __init__(self, codex_manager: CodexManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._codex_manager = codex_manager
        self._unsubscribers: List[Callable[[], None]] = []
        self._bind()

    def _bind(self) -> None:
        self._unsubscribers.append(self._codex_manager.on_entry_added(self.entryAdded.emit))
        self._unsubscribers.append(self._codex_manager.on_entry_updated(self.entryUpdated.emit))
        self._unsubscribers.append(self._codex_manager.on_entry_deleted(self.entryDeleted.emit))
        self._unsubscribers.append(self._codex_manager.on_references_updated(self.referencesUpdated.emit))

    def close(self) -> None:
        for unsubscribe in self._unsubscribers:
            try:
                unsubscribe()
            except Exception:
                logger.exception("Failed to unsubscribe CodexManager listener")
        self._unsubscribers.clear()

