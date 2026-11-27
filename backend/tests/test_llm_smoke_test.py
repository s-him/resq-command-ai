"""Tests for the opt-in LLM pipeline smoke-test script."""

from types import SimpleNamespace

from scripts.llm_smoke_test import run_smoke_test


def test_smoke_test_skips_without_creating_incident_when_llm_is_disabled():
    messages = []

    def forbidden():
        raise AssertionError("disabled mode must not create a database record")

    result = run_smoke_test(
        {"enabled": False, "api_key": "not-used"},
        incident_creator=forbidden,
        output=messages.append,
    )

    assert result == 0
    assert len(messages) == 1
    assert "skipped" in messages[0].lower()
    assert "LLM_ENABLED is false" in messages[0]


def test_smoke_test_skips_without_key_and_does_not_create_incident():
    messages = []

    def forbidden():
        raise AssertionError("missing key must not create a database record")

    result = run_smoke_test(
        {"enabled": True, "api_key": ""},
        incident_creator=forbidden,
        output=messages.append,
    )

    assert result == 0
    assert "LLM_API_KEY is not set" in messages[0]


def test_smoke_test_prints_each_agent_mode_and_rationale():
    messages = []
    created = []

    def create_incident():
        created.append(True)
        return SimpleNamespace(id=42)

    def pipeline(incident_id):
        assert incident_id == 42
        return {
            "agents": [
                {"name": "MonitoringAgent", "mode": "llm", "rationale": "Provider reviewed evidence."},
                {"name": "SeverityAgent", "mode": "llm", "rationale": "Rules kept the score authoritative."},
            ]
        }

    result = run_smoke_test(
        {"enabled": True, "api_key": "never-print-this"},
        incident_creator=create_incident,
        pipeline_runner=pipeline,
        output=messages.append,
    )

    rendered = "\n".join(messages)
    assert result == 0
    assert created == [True]
    assert "MonitoringAgent: mode=llm" in rendered
    assert "SeverityAgent: mode=llm" in rendered
    assert "Provider reviewed evidence." in rendered
    assert "LLM smoke test passed" in rendered
    assert "never-print-this" not in rendered


def test_smoke_test_reports_provider_fallback_without_traceback():
    messages = []

    result = run_smoke_test(
        {"enabled": True, "api_key": "redacted"},
        incident_creator=lambda: SimpleNamespace(id=7),
        pipeline_runner=lambda _incident_id: {
            "agents": [
                {
                    "name": "MonitoringAgent",
                    "mode": "rules",
                    "rationale": "LLM unavailable or invalid (LLMRequestError); deterministic rules used.",
                }
            ]
        },
        output=messages.append,
    )

    rendered = "\n".join(messages)
    assert result == 1
    assert "mode=rules" in rendered
    assert "deterministic rules" in rendered
    assert "smoke test failed" in rendered.lower()
    assert "Traceback" not in rendered


def test_smoke_test_handles_pipeline_exception_without_leaking_exception_text():
    messages = []

    def fail(_incident_id):
        raise RuntimeError("provider returned private response metadata")

    result = run_smoke_test(
        {"enabled": True, "api_key": "redacted"},
        incident_creator=lambda: SimpleNamespace(id=9),
        pipeline_runner=fail,
        output=messages.append,
    )

    rendered = "\n".join(messages)
    assert result == 1
    assert "RuntimeError" in rendered
    assert "private response metadata" not in rendered
    assert "Traceback" not in rendered
