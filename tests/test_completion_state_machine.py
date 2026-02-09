import os
import sys


# Keep import style consistent with other tests in this repo.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from domain.completion_state_machine import CompletionState, CompletionStateMachine
from domain.completion_state_machine import CompletionEventType


def test_completion_states_are_defined():
    assert {s.value for s in CompletionState} == {
        "idle",
        "requesting",
        "streaming",
        "suggestion_ready",
        "applied",
        "cancelled",
    }


def test_state_machine_starts_idle():
    sm = CompletionStateMachine()
    assert sm.state == CompletionState.IDLE


def test_tab_from_idle_enters_requesting():
    sm = CompletionStateMachine()
    sm.handle_event(CompletionEventType.TAB)
    assert sm.state == CompletionState.REQUESTING


def test_esc_from_requesting_cancels():
    sm = CompletionStateMachine()
    sm.handle_event(CompletionEventType.TAB)
    sm.handle_event(CompletionEventType.ESC)
    assert sm.state == CompletionState.CANCELLED


def test_timeout_records_error_and_cancels():
    sm = CompletionStateMachine()
    sm.handle_event(CompletionEventType.TAB)
    snap = sm.handle_event(CompletionEventType.TIMEOUT)
    assert snap.state == CompletionState.CANCELLED
    assert snap.error == "timeout"


def test_suggestion_ready_tab_applies():
    sm = CompletionStateMachine()
    sm.set_suggestion_ready("hello")
    sm.handle_event(CompletionEventType.TAB)
    assert sm.state == CompletionState.APPLIED
