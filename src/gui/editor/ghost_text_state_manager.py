from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal


class GhostTextState(Enum):
    IDLE = "idle"
    GENERATING = "generating"
    VISIBLE = "visible"


@dataclass
class GhostTextSnapshot:
    state: GhostTextState
    completion: str


class GhostTextStateManager(QObject):
    state_changed = pyqtSignal(object)
    completion_updated = pyqtSignal(str)
    text_accepted = pyqtSignal(str)
    text_to_clear = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = GhostTextState.IDLE
        self._completion = ""

    @property
    def state(self) -> GhostTextState:
        return self._state

    @property
    def completion(self) -> str:
        return self._completion

    def snapshot(self) -> GhostTextSnapshot:
        return GhostTextSnapshot(state=self._state, completion=self._completion)

    def is_active(self) -> bool:
        return self._state != GhostTextState.IDLE

    def set_state(self, state: GhostTextState) -> None:
        if self._state == state:
            return
        self._state = state
        self.state_changed.emit(state)

    def request_completion(self) -> bool:
        if self._state != GhostTextState.IDLE:
            return False
        self.set_state(GhostTextState.GENERATING)
        return True

    def show(self, completion: str) -> bool:
        if self._state != GhostTextState.GENERATING:
            return False
        self._completion = completion
        self.set_state(GhostTextState.VISIBLE)
        self.completion_updated.emit(completion)
        return True

    def mark_visible(self, completion: str) -> None:
        """Force state to VISIBLE with given completion text.

        Used as a recovery path when the caller cannot guarantee the exact
        previous state (e.g., legacy flows calling show without request).
        """
        self._completion = completion
        self.set_state(GhostTextState.VISIBLE)
        self.completion_updated.emit(completion)

    def accept(self) -> bool:
        if self._state != GhostTextState.VISIBLE:
            return False
        accepted_text = self._completion
        self._completion = ""
        self.set_state(GhostTextState.IDLE)
        self.text_accepted.emit(accepted_text)
        self.completion_updated.emit("")
        return True

    def accept_with_text(self, accepted_text: str) -> None:
        """Accept with explicit text, regardless of stored completion."""
        self._completion = ""
        self.set_state(GhostTextState.IDLE)
        self.text_accepted.emit(accepted_text)
        self.completion_updated.emit("")

    def reject(self) -> bool:
        if self._state == GhostTextState.IDLE:
            return False
        self._completion = ""
        self.set_state(GhostTextState.IDLE)
        self.text_to_clear.emit()
        return True

    def force_idle(self) -> None:
        """Force state to IDLE without caring about previous state."""
        self._completion = ""
        self.set_state(GhostTextState.IDLE)
