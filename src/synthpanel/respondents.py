"""LLM respondents: turn (concept, persona) tasks into free-text answers.

- `ClaudeRespondent`: real-time, concurrent (asyncio). Uses server-side refusal fallbacks
  (`fallbacks="default"`), so a request one model declines is re-run on a fallback model
  inside the same call.
- `ClaudeBatchRespondent`: Message Batches API, about half the token price, results usually
  within an hour. The Batches API does not accept `fallbacks`, so refusals are recorded as
  such. Prefer it for large panels.
- `ScriptedRespondent`: deterministic canned answers for tests and dry runs.

Claude Opus 5.5 does not accept `temperature`, so answer diversity comes from the persona
mix (and optionally several draws per persona), not from sampling settings.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from synthpanel.concepts import Concept
from synthpanel.personas import Persona
from synthpanel.prompts import SYSTEM_PROMPT, user_content

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class Task:
    concept: Concept
    persona: Persona
    draw: int = 0

    @property
    def task_id(self) -> str:
        return f"{self.concept.concept_id}|{self.persona.persona_id}|{self.draw}"


@dataclass
class Answer:
    task_id: str
    text: str
    status: str  # "ok" | "refused" | "error"
    model: str = ""
    detail: str = ""


class Respondent(Protocol):
    def answer(self, tasks: Sequence[Task]) -> list[Answer]: ...


def _text_of(message) -> str:
    return " ".join(b.text for b in message.content if b.type == "text").strip()


def _request_params(task: Task, model: str, effort: str, max_tokens: int) -> dict:
    content = user_content(task.concept, task.persona)
    # Cache the shared prefix (system + concept, including any image) across respondents.
    content[-2] = {**content[-2], "cache_control": {"type": "ephemeral"}}
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "output_config": {"effort": effort},
        "messages": [{"role": "user", "content": content}],
    }


class ClaudeRespondent:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
        max_tokens: int = 4000,
        concurrency: int = 16,
        client: anthropic.AsyncAnthropic | None = None,
    ):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens  # thinking counts toward this, so leave headroom
        self.concurrency = concurrency
        self._client = client

    def answer(self, tasks: Sequence[Task]) -> list[Answer]:
        return asyncio.run(self._answer_all(tasks))

    async def _answer_all(self, tasks: Sequence[Task]) -> list[Answer]:
        client = self._client or anthropic.AsyncAnthropic(max_retries=5)
        sem = asyncio.Semaphore(self.concurrency)

        async def one(task: Task) -> Answer:
            async with sem:
                return await self._answer_one(client, task)

        return list(await asyncio.gather(*(one(t) for t in tasks)))

    async def _answer_one(self, client: anthropic.AsyncAnthropic, task: Task) -> Answer:
        params = _request_params(task, self.model, self.effort, self.max_tokens)
        try:
            msg = await client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")
        except anthropic.BadRequestError as e:  # not retryable: the request itself is wrong
            return Answer(task.task_id, "", "error", detail=f"bad request: {e.message}")
        except anthropic.RateLimitError as e:  # SDK already retried with backoff
            return Answer(task.task_id, "", "error", detail=f"rate limited: {e.message}")
        except anthropic.APIStatusError as e:
            return Answer(task.task_id, "", "error", detail=f"HTTP {e.status_code}: {e.message}")
        except anthropic.APIConnectionError as e:
            return Answer(task.task_id, "", "error", detail=f"connection: {e}")
        if msg.stop_reason == "refusal":
            category = getattr(msg.stop_details, "category", None) if msg.stop_details else None
            return Answer(task.task_id, "", "refused", msg.model, detail=f"refusal: {category}")
        text = _text_of(msg)
        if not text:
            return Answer(task.task_id, "", "error", msg.model, detail=f"empty answer, stop_reason={msg.stop_reason}")
        return Answer(task.task_id, text, "ok", msg.model)


class ClaudeBatchRespondent:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
        max_tokens: int = 4000,
        poll_seconds: int = 60,
        client: anthropic.Anthropic | None = None,
    ):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.poll_seconds = poll_seconds
        self._client = client or anthropic.Anthropic(max_retries=5)

    def answer(self, tasks: Sequence[Task]) -> list[Answer]:
        # custom_id allows only [a-zA-Z0-9_-]{1,64}; map positions instead of raw ids.
        requests = [
            Request(custom_id=f"t{i}", params=MessageCreateParamsNonStreaming(
                **_request_params(t, self.model, self.effort, self.max_tokens)))
            for i, t in enumerate(tasks)
        ]
        answers: dict[str, Answer] = {}
        for start in range(0, len(requests), 100_000):
            batch = self._client.messages.batches.create(requests=requests[start : start + 100_000])
            log.info("Submitted batch %s (%d requests)", batch.id, len(requests[start : start + 100_000]))
            while (batch := self._client.messages.batches.retrieve(batch.id)).processing_status != "ended":
                time.sleep(self.poll_seconds)
            for res in self._client.messages.batches.results(batch.id):
                task = tasks[int(res.custom_id[1:])]
                answers[res.custom_id] = self._to_answer(task, res.result)
        return [answers.get(f"t{i}", Answer(t.task_id, "", "error", detail="missing from batch results"))
                for i, t in enumerate(tasks)]

    @staticmethod
    def _to_answer(task: Task, result) -> Answer:
        if result.type != "succeeded":
            detail = result.type
            if result.type == "errored":
                detail = f"errored: {result.error.type}"
            return Answer(task.task_id, "", "error", detail=detail)
        msg = result.message
        if msg.stop_reason == "refusal":
            return Answer(task.task_id, "", "refused", msg.model, detail="refusal")
        text = _text_of(msg)
        return Answer(task.task_id, text, "ok" if text else "error", msg.model,
                      detail="" if text else f"empty answer, stop_reason={msg.stop_reason}")


class ScriptedRespondent:
    """Returns `script(task)` for every task. For tests and pipeline dry runs only."""

    def __init__(self, script: Callable[[Task], str]):
        self.script = script

    def answer(self, tasks: Sequence[Task]) -> list[Answer]:
        return [Answer(t.task_id, self.script(t), "ok", "scripted") for t in tasks]
