"""Strategy implementations for LLM backends used by Light-RAG."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx
import structlog
from openai import AsyncOpenAI

from epip.config import LightRAGConfig

logger = structlog.get_logger()

ChatHistory = Sequence[dict[str, str]] | None


def _normalize_history(history: ChatHistory) -> list[dict[str, str]]:
    """Drop malformed entries and normalize missing fields."""
    if not history:
        return []
    normalized: list[dict[str, str]] = []
    for entry in history:
        content = entry.get("content")
        if not content:
            continue
        role = entry.get("role", "user")
        normalized.append({"role": role, "content": content})
    return normalized


def _build_messages(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: ChatHistory = None,
) -> list[dict[str, str]]:
    """Compose OpenAI-style chat messages."""
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(_normalize_history(history_messages))
    messages.append({"role": "user", "content": prompt})
    return messages


def _render_prompt(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: ChatHistory = None,
) -> str:
    """Create a text prompt compatible with simple completion APIs."""
    sections = []
    if system_prompt:
        sections.append(f"System:\n{system_prompt}")
    for message in _normalize_history(history_messages):
        role = message.get("role", "user").capitalize()
        sections.append(f"{role}:\n{message.get('content', '')}")
    sections.append(f"User:\n{prompt}")
    return "\n\n".join(sections)


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""

    def __init__(self, *, timeout: float | None = None) -> None:
        self._timeout = timeout

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history_messages: ChatHistory = None,
        **kwargs: Any,
    ) -> str:
        """Return the completion for the supplied prompt."""

    async def generate_stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history_messages: ChatHistory = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream the completion."""
        raise NotImplementedError("Streaming is not supported by this backend.")


class OllamaBackend(LLMBackend):
    """Ollama HTTP backend implementation."""

    def __init__(self, url: str, model: str, *, timeout: float | None = 120.0) -> None:
        super().__init__(timeout=timeout)
        self._url = url.rstrip("/")
        self._model = model

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history_messages: ChatHistory = None,
        **kwargs: Any,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": _render_prompt(prompt, system_prompt, history_messages),
            "stream": False,  # 禁用流式响应，返回单个 JSON
        }
        options: dict[str, Any] = {}
        if max_tokens := kwargs.get("max_tokens"):
            options["num_predict"] = max_tokens
        if temperature := kwargs.get("temperature"):
            options["temperature"] = temperature
        if top_p := kwargs.get("top_p"):
            options["top_p"] = top_p
        if options:
            payload["options"] = options

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def generate_stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history_messages: ChatHistory = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": _render_prompt(prompt, system_prompt, history_messages),
            "stream": True,
        }
        options: dict[str, Any] = {}
        if max_tokens := kwargs.get("max_tokens"):
            options["num_predict"] = max_tokens
        if temperature := kwargs.get("temperature"):
            options["temperature"] = temperature
        if top_p := kwargs.get("top_p"):
            options["top_p"] = top_p
        if options:
            payload["options"] = options

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", f"{self._url}/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("Discarding malformed Ollama chunk", chunk=line)
                        continue
                    text = chunk.get("response")
                    if text:
                        yield text


class OpenAIBackend(LLMBackend):
    """OpenAI Chat Completions backend."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
        timeout: float | None = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI backend requires a valid API key.")
        super().__init__(timeout=timeout)
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history_messages: ChatHistory = None,
        **kwargs: Any,
    ) -> str:
        messages = _build_messages(prompt, system_prompt, history_messages)
        request_kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if kwargs.get("max_tokens") is not None:
            request_kwargs["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("temperature") is not None:
            request_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("top_p") is not None:
            request_kwargs["top_p"] = kwargs["top_p"]

        response = await self._client.chat.completions.create(**request_kwargs)
        choice = response.choices[0]
        return choice.message.content or ""

    async def generate_stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        history_messages: ChatHistory = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        messages = _build_messages(prompt, system_prompt, history_messages)
        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if kwargs.get("max_tokens") is not None:
            request_kwargs["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("temperature") is not None:
            request_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("top_p") is not None:
            request_kwargs["top_p"] = kwargs["top_p"]

        stream = await self._client.chat.completions.create(**request_kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            text = delta.content
            if text:
                yield text


def create_llm_backend(config: LightRAGConfig, *, timeout: float | None = None) -> LLMBackend:
    """Factory that builds the configured backend."""
    backend_type = config.llm_backend.lower()
    if backend_type == "ollama":
        return OllamaBackend(
            config.ollama_url,
            config.ollama_model,
            timeout=timeout or 300.0,  # 增加到 300 秒
        )
    if backend_type == "openai":
        api_key = config.llm_api_key or config.openai_api_key
        if not api_key:
            raise ValueError("OpenAI backend selected but no API key configured.")
        resolved_timeout = timeout or float(config.llm_timeout)
        base_url = getattr(config, "llm_base_url", None)
        return OpenAIBackend(
            api_key,
            config.llm_model,
            base_url=base_url,
            timeout=resolved_timeout,
        )
    raise ValueError(f"Unsupported LLM backend: {config.llm_backend}")
