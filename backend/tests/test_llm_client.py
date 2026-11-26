"""Mocked tests for strict JSON LLM requests and offline fallback behavior."""

import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.llm import (
    LLMClient,
    LLMDisabledError,
    LLMInvalidResponse,
    LLMTimeoutError,
)


class ExampleReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=3)


def settings(enabled=True):
    return {
        "enabled": enabled,
        "base_url": "https://llm.example.test/v1",
        "api_key": "test-key",
        "model": "test-model",
        "timeout_seconds": 1.5,
    }


def completion(content):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_client_requests_json_mode_and_validates_pydantic_schema():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return completion('{"summary":"validated response"}')

    client = LLMClient(
        settings_provider=lambda: settings(),
        transport=httpx.MockTransport(handler),
    )
    result = client.complete_json(
        system_prompt="Return a short summary.",
        user_payload={"incident_id": 42},
        response_model=ExampleReply,
    )

    assert result.summary == "validated response"
    assert seen["url"] == "https://llm.example.test/v1/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer test-key"
    assert seen["body"]["model"] == "test-model"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "JSON schema" in seen["body"]["messages"][0]["content"]
    assert json.loads(seen["body"]["messages"][1]["content"]) == {"incident_id": 42}


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"summary":"ok","unexpected":"extra field"}',
        '{"summary":""}',
    ],
)
def test_client_rejects_invalid_json_or_schema(content):
    client = LLMClient(
        settings_provider=lambda: settings(),
        transport=httpx.MockTransport(lambda request: completion(content)),
    )
    with pytest.raises(LLMInvalidResponse):
        client.complete_json(
            system_prompt="Return JSON only.",
            user_payload={},
            response_model=ExampleReply,
        )


def test_client_converts_timeout_to_clear_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout("timed out")

    client = LLMClient(
        settings_provider=lambda: settings(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMTimeoutError):
        client.complete_json(
            system_prompt="Return JSON only.",
            user_payload={},
            response_model=ExampleReply,
        )


def test_disabled_client_never_calls_provider():
    def handler(request):
        raise AssertionError("Provider must not be called while LLM is disabled.")

    client = LLMClient(
        settings_provider=lambda: settings(enabled=False),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMDisabledError):
        client.complete_json(
            system_prompt="Return JSON only.",
            user_payload={},
            response_model=ExampleReply,
        )
