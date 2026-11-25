"""Minimal, provider-agnostic client for OpenAI-compatible JSON chat completions.

No SDK is required. The caller supplies a Pydantic model; every response is
parsed and validated before it can be consumed by an agent.
"""

import json
from typing import Any, Callable, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_llm_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Base error for optional LLM failures."""


class LLMDisabledError(LLMError):
    """Raised when LLM use is disabled by configuration."""


class LLMRequestError(LLMError):
    """Raised when the configured LLM endpoint cannot complete a request."""


class LLMTimeoutError(LLMRequestError):
    """Raised when an LLM request exceeds its configured timeout."""


class LLMInvalidResponse(LLMError):
    """Raised when the endpoint response is not valid JSON for the requested schema."""


class LLMClient:
    """Call an OpenAI-compatible /chat/completions endpoint with JSON-mode output."""

    def __init__(
        self,
        settings_provider: Callable[[], dict[str, Any]] = get_llm_settings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._transport = transport

    @property
    def enabled(self) -> bool:
        """Return the current runtime setting, rather than a cached import-time value."""
        return bool(self._settings_provider().get("enabled", False))

    @staticmethod
    def _endpoint(base_url: str) -> str:
        base = base_url.strip().rstrip("/")
        if not base:
            raise LLMRequestError("LLM_BASE_URL is empty.")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        response_model: type[T],
    ) -> T:
        """Request one JSON object and validate it against response_model.

        The JSON schema is sent in the system prompt and JSON-object response
        mode is requested from compatible providers. Pydantic validation remains
        mandatory because compatible servers do not all enforce the same schema.
        """
        settings = self._settings_provider()
        if not settings.get("enabled", False):
            raise LLMDisabledError("LLM_ENABLED is false; use deterministic rules.")
        model = str(settings.get("model", "")).strip()
        if not model:
            raise LLMRequestError("LLM_MODEL is not configured.")

        timeout_seconds = float(settings.get("timeout_seconds", 8.0))
        if timeout_seconds <= 0:
            raise LLMRequestError("LLM_TIMEOUT_SECONDS must be greater than zero.")

        schema = response_model.model_json_schema()
        strict_prompt = (
            f"{system_prompt.strip()}\n\n"
            "Return exactly one JSON object. Do not include Markdown fences, "
            "comments, or prose outside JSON. The object must satisfy this "
            f"JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
        )
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": strict_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, default=str),
                },
            ],
        }
        headers = {"Content-Type": "application/json"}
        api_key = str(settings.get("api_key", "")).strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = self._endpoint(str(settings.get("base_url", "")))
        try:
            with httpx.Client(
                timeout=timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"LLM request timed out after {timeout_seconds:g} seconds."
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMRequestError(
                f"LLM request failed ({type(exc).__name__})."
            ) from exc

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("The assistant message content was empty.")
            return response_model.model_validate_json(content)
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            raise LLMInvalidResponse(
                "The LLM response was not valid JSON for the requested schema."
            ) from exc
