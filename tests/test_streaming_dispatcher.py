from __future__ import annotations

from application.ai_completion_service import AIRequestDispatcher


class _DummyAIClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def complete_async(self, *, prompt: str, context: dict, max_tokens: int, temperature: float) -> None:  # noqa: ARG002
        self.calls.append(("complete_async", dict(context)))

    def complete_stream_async(self, *, prompt: str, context: dict, max_tokens: int, temperature: float) -> None:  # noqa: ARG002
        self.calls.append(("complete_stream_async", dict(context)))


def test_streaming_dispatcher_selects_method_by_toggle() -> None:
    client = _DummyAIClient()
    dispatcher = AIRequestDispatcher(ai_client=client, task_manager=None, cancelled_task_keys=set())

    ctx1 = {"task_key": "t1"}
    assert dispatcher.send_request("p", ctx1, max_tokens=10, temperature=0.5, task_key="t1", stream_response=True) is True
    assert client.calls[0][0] == "complete_stream_async"
    assert client.calls[0][1]["stream_response"] is True
    assert isinstance(client.calls[0][1].get("request_id"), str)

    ctx2 = {"task_key": "t1"}
    assert dispatcher.send_request("p", ctx2, max_tokens=10, temperature=0.5, task_key="t1", stream_response=False) is True
    assert client.calls[1][0] == "complete_async"
    assert client.calls[1][1]["stream_response"] is False
    assert isinstance(client.calls[1][1].get("request_id"), str)

