"""AI provider abstraction for Career OS.

Replaceable provider per ADR 0005. Default: Groq.
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
import groq

load_dotenv()


@dataclass(frozen=True)
class AIResult:
    content: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class AIProvider(ABC):
    @abstractmethod
    def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> AIResult: ...


class GroqProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "llama3-70b-8192",
        timeout: int = 30,
    ) -> None:
        self._client = groq.Groq(api_key=api_key, timeout=timeout)
        self._model = model

    def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> AIResult:
        start = time.monotonic()
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)
        elapsed = int((time.monotonic() - start) * 1000)
        choice = response.choices[0]
        return AIResult(
            content=choice.message.content or "",
            model=response.model,
            latency_ms=elapsed,
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
        )


def create_provider() -> AIProvider:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Set environment variable or create .env file."
        )
    model = os.environ.get("GROQ_MODEL", "llama3-70b-8192")
    timeout = int(os.environ.get("AI_TIMEOUT", "30"))
    return GroqProvider(api_key=api_key, model=model, timeout=timeout)


def extract_json(text: str) -> dict[str, Any]:
    start = text.index("{")
    end = text.rindex("}") + 1
    return json.loads(text[start:end])
