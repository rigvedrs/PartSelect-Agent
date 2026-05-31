import logging
from app.observability import RequestTrace, span, trace_request, new_request_id


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
