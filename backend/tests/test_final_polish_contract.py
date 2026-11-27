"""Final polish regression checks for startup defaults and safety boundaries."""

from pathlib import Path

from app import config

ROOT = Path(__file__).resolve().parents[2]


def test_application_defaults_do_not_require_environment_variables(monkeypatch):
    monkeypatch.delenv("RESQ_ALERT_AUTO_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("RESQ_GDACS_SYNC_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("RESQ_USGS_SYNC_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("RESQ_ALLOW_AUTO_DISPATCH", raising=False)

    assert config._read_bool("RESQ_ALERT_AUTO_SYNC_ENABLED", True) is True
    assert config._read_positive_int("RESQ_GDACS_SYNC_INTERVAL_SECONDS", 360) == 360
    assert config._read_positive_int("RESQ_USGS_SYNC_INTERVAL_SECONDS", 60) == 60
    assert config.get_llm_settings()["enabled"] is False
    assert config.get_llm_settings()["api_key"] == ""
    assert config.auto_dispatch_allowed() is False


def test_unused_safety_banner_is_removed_without_removing_documentation():
    assert not (ROOT / "frontend/src/components/layout/SafetyBanner.jsx").exists()
    frontend_sources = ROOT / "frontend/src"
    assert all(
        "SafetyBanner" not in path.read_text(encoding="utf-8")
        for path in frontend_sources.rglob("*.jsx")
        if path.name != "SafetyBanner.jsx"
    )

    for relative in ("README.md", "docs/TEST_REPORT.md", "docs/TRACEABILITY.md", "docs/FINAL_REPORT.md"):
        content = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert "academic prototype" in content
        assert "virtual dispatch" in content or "simulated dispatch" in content or "auto dispatch is virtual" in content
        assert "not for real emergency" in content or "not for real emergencies" in content or "not suitable for real emergency" in content
