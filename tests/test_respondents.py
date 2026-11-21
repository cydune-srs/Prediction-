"""ClaudeRespondent request shape and response handling, with a fake client (no API calls)."""

from types import SimpleNamespace

import anthropic
import httpx2 as httpx

from synthpanel.concepts import Concept
from synthpanel.personas import Persona
from synthpanel.respondents import FALLBACK_BETA, ClaudeBatchRespondent, ClaudeRespondent, Task


def _msg(text="I'd probably buy it.", stop_reason="end_turn"):
    content = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(content=content, stop_reason=stop_reason, stop_details=None, model="claude-opus-5-5")


class FakeBetaMessages:
    def __init__(self, behaviours):
        self.behaviours = list(behaviours)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        b = self.behaviours.pop(0)
        if isinstance(b, Exception):
            raise b
        return b


def _client(behaviours):
    msgs = FakeBetaMessages(behaviours)
    return SimpleNamespace(beta=SimpleNamespace(messages=msgs)), msgs


TASKS = [Task(Concept(f"c{i}", "N", "D"), Persona("p", {"age": "30"})) for i in range(4)]


def test_request_shape_and_statuses():
    bad_request = anthropic.BadRequestError(
        "bad", response=httpx.Response(400, request=httpx.Request("POST", "https://x")), body=None)
    client, msgs = _client([_msg(), _msg(stop_reason="refusal"), bad_request, _msg(text="")])
    answers = ClaudeRespondent(client=client, concurrency=1).answer(TASKS)
    assert [a.status for a in answers] == ["ok", "refused", "error", "error"]
    assert answers[0].text == "I'd probably buy it."

    call = msgs.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert "temperature" not in call and "thinking" not in call
    assert call["output_config"] == {"effort": "medium"}
    content = call["messages"][0]["content"]
    assert content[-2]["cache_control"] == {"type": "ephemeral"}  # concept block is the cached prefix
    assert "cache_control" not in content[-1]


def test_batch_results_mapped_by_custom_id_not_order():
    results = [
        SimpleNamespace(custom_id="t1", result=SimpleNamespace(type="succeeded", message=_msg("second"))),
        SimpleNamespace(custom_id="t0", result=SimpleNamespace(type="succeeded", message=_msg("first"))),
        SimpleNamespace(custom_id="t2", result=SimpleNamespace(type="errored", error=SimpleNamespace(type="api_error"))),
    ]
    batches = SimpleNamespace(
        create=lambda requests: SimpleNamespace(id="b1"),
        retrieve=lambda _id: SimpleNamespace(id=_id, processing_status="ended"),
        results=lambda _id: iter(results),
    )
    client = SimpleNamespace(messages=SimpleNamespace(batches=batches))
    answers = ClaudeBatchRespondent(client=client, poll_seconds=0).answer(TASKS)
    assert [a.text for a in answers[:2]] == ["first", "second"]
    assert answers[2].status == "error" and answers[3].detail == "missing from batch results"
