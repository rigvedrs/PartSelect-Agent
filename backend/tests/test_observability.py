import logging
from app.observability import (
    RequestTrace,
    get_log_settings,
    log_event,
    new_request_id,
    safe_preview,
    sanitize_fields,
    span,
    trace_request,
)


def test_log_settings_defaults(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    monkeypatch.delenv("LOG_COLOR", raising=False)
    settings = get_log_settings()
    assert settings.level == "INFO"
    assert settings.format == "pretty"
    assert settings.color is True


def test_log_settings_json_mode(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_COLOR", "false")
    settings = get_log_settings()
    assert settings.level == "DEBUG"
    assert settings.format == "json"
    assert settings.color is False


def test_safe_preview_truncates_long_values():
    assert safe_preview("abcdef", limit=4) == "a..."
    assert safe_preview(None) == ""


def test_sanitize_fields_redacts_secrets_and_summarizes_collections():
    fields = sanitize_fields({
        "api_key": "secret-value",
        "password": "pw",
        "parts": [{"ps_number": "PS1"}, {"ps_number": "PS2"}],
        "payload": {"a": 1, "b": 2},
        "message": "hello",
    })
    assert fields["api_key"] == "[redacted]"
    assert fields["password"] == "[redacted]"
    assert fields["parts"] == "list(len=2)"
    assert fields["payload"] == "dict(keys=2)"
    assert fields["message"] == "hello"


def test_log_event_emits_event_name(caplog):
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("test.observability")
    log_event(logger, "unit.test", answer=42)
    assert any("unit.test" in r.message and "answer=42" in r.message for r in caplog.records)


def test_span_records_elapsed_ms():
    trace = RequestTrace(req_id="abc")
    with trace.activate():
        with span("db"):
            pass
    assert "db" in trace.timings
    assert trace.timings["db"] >= 0


def test_trace_request_emits_summary(caplog):
    caplog.set_level(logging.INFO, logger="app.observability")
    with trace_request("abc", route="search"):
        with span("intent"):
            pass
    assert any("req=abc" in r.message and "intent=" in r.message for r in caplog.records)
