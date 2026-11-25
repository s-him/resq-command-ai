# Optional LLM provider

The incident-agent pipeline uses a small `httpx` client for providers exposing
an OpenAI-compatible `POST /chat/completions` endpoint. LLM use is disabled by
default. If it is disabled, misconfigured, times out, returns non-JSON, or
returns JSON that fails Pydantic validation, the agent falls back to existing
deterministic code.

The model only adds advisory classification/narrative suggestions. Rule-based
severity, priority ordering, distance-aware inventory matching, validation,
operator review and dispatch safeguards remain authoritative.
