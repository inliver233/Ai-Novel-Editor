import os
import sys


# Keep import style consistent with other tests in this repo.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from domain.completion_state_machine import CompletionState, CompletionStateMachine


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

