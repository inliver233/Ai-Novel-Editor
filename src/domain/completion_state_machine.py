from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompletionState(Enum):
    """Completion 状态机状态（纯逻辑，无 Qt 依赖）。"""

    IDLE = "idle"
    REQUESTING = "requesting"
    STREAMING = "streaming"
    SUGGESTION_READY = "suggestion_ready"
    APPLIED = "applied"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CompletionSnapshot:
    state: CompletionState
    suggestion: str = ""
    error: str = ""


class CompletionStateMachine:
    """纯状态机容器（用于后续事件驱动的 transition）。"""

    def __init__(self) -> None:
        self._state = CompletionState.IDLE
        self._suggestion = ""
        self._error = ""

    @property
    def state(self) -> CompletionState:
        return self._state

    @property
    def suggestion(self) -> str:
        return self._suggestion

    @property
    def error(self) -> str:
        return self._error

    def snapshot(self) -> CompletionSnapshot:
        return CompletionSnapshot(
            state=self._state,
            suggestion=self._suggestion,
            error=self._error,
        )

    def set_state(self, state: CompletionState) -> None:
        self._state = state

