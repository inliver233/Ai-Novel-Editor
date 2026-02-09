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


class CompletionEventType(Enum):
    """用户可观测的 completion 事件（纯逻辑，无 Qt 依赖）。"""

    TAB = "tab"
    SHIFT_TAB = "shift_tab"
    ESC = "esc"
    TEXT_CHANGED = "text_changed"
    CURSOR_MOVED = "cursor_moved"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"


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

    def reset(self) -> None:
        self._state = CompletionState.IDLE
        self._suggestion = ""
        self._error = ""

    def set_suggestion_ready(self, suggestion: str) -> None:
        self._suggestion = suggestion
        self._error = ""
        self._state = CompletionState.SUGGESTION_READY

    def start_streaming(self) -> None:
        self._error = ""
        self._state = CompletionState.STREAMING

    def handle_event(self, event: CompletionEventType) -> CompletionSnapshot:
        """处理事件并更新状态。

        说明：这是一个最小可用的纯状态机实现，优先覆盖 Epic 7.1 的状态/事件枚举，
        以及取消/应用路径，供 GUI 协调器后续接入。
        """
        if self._state == CompletionState.IDLE:
            if event in (CompletionEventType.TAB, CompletionEventType.SHIFT_TAB):
                self._error = ""
                self._state = CompletionState.REQUESTING
            return self.snapshot()

        if self._state in (CompletionState.REQUESTING, CompletionState.STREAMING):
            if event in (
                CompletionEventType.ESC,
                CompletionEventType.TEXT_CHANGED,
                CompletionEventType.CURSOR_MOVED,
                CompletionEventType.TIMEOUT,
                CompletionEventType.NETWORK_ERROR,
            ):
                if event == CompletionEventType.TIMEOUT:
                    self._error = "timeout"
                elif event == CompletionEventType.NETWORK_ERROR:
                    self._error = "network_error"
                else:
                    self._error = ""
                self._suggestion = ""
                self._state = CompletionState.CANCELLED
            return self.snapshot()

        if self._state == CompletionState.SUGGESTION_READY:
            if event in (CompletionEventType.TAB, CompletionEventType.SHIFT_TAB):
                self._state = CompletionState.APPLIED
            elif event in (
                CompletionEventType.ESC,
                CompletionEventType.TEXT_CHANGED,
                CompletionEventType.CURSOR_MOVED,
                CompletionEventType.TIMEOUT,
                CompletionEventType.NETWORK_ERROR,
            ):
                self._suggestion = ""
                self._error = ""
                self._state = CompletionState.CANCELLED
            return self.snapshot()

        # Terminal states: keep state until caller resets/consumes it.
        return self.snapshot()
