"""Anthropic client wrapper: settings, structured calls, usage tracking, refusal handling."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TypeVar

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from .cost import UsageTracker

load_dotenv()

T = TypeVar("T", bound=BaseModel)


@dataclass
class Settings:
    model_explain: str = os.getenv("CBCL_MODEL_EXPLAIN", "claude-opus-5-5")
    model_chat: str = os.getenv("CBCL_MODEL_CHAT", "claude-opus-5-5")
    model_judge: str = os.getenv("CBCL_MODEL_JUDGE", "claude-haiku-5-5")
    effort: str = os.getenv("CBCL_EFFORT", "medium")


class RefusedError(RuntimeError):
    """The model declined the request (stop_reason == 'refusal')."""


class LLM:
    def __init__(self, settings: Settings | None = None, tracker: UsageTracker | None = None):
        self.settings = settings or Settings()
        self.tracker = tracker or UsageTracker()
        self.client = anthropic.Anthropic()

    def parse(
        self,
        *,
        label: str,
        model: str,
        system: list[dict] | str,
        messages: list[dict],
        output_format: type[T],
        effort: str | None = None,
        max_tokens: int = 8000,
    ) -> T:
        """Structured-output call. Raises RefusedError on a safety refusal."""
        response = self.client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_format=output_format,
            output_config={"effort": effort or self.settings.effort},
        )
        self.tracker.add(label, model, response.usage)
        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            raise RefusedError(f"model refused: {getattr(detail, 'category', None)}")
        if response.parsed_output is None:
            raise RuntimeError(f"no parsed output (stop_reason={response.stop_reason})")
        return response.parsed_output
