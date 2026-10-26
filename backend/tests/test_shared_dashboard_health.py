from datetime import datetime

from fastapi.testclient import TestClient
import pytest

import app.reliability as reliability
import app.runtime as runtime


BEFORE_CLOSE = datetime(2026, 10, 26, 14, 0, tzinfo=reliability.IST)


@pytest.fixture
def shared_dashboard(monkeypatch):
    monkeypatch.setenv("SHARED_STATE_BACKEND", "db")
    monkeypatch.setenv("PUBLIC_DASHBOARD_READ_ONLY", "true")
    monkeypatch.setattr(reliability, "portfolio_integrity", lambda db: {"status": "OK", "blocking": False})
    monkeypatch.setattr(reliability, "ledger_integrity", lambda: {"status": "OK", "blocking": False})
    monkeypatch.setattr(reliability, "checkpoint_status", lambda: {"status": "MATCH", "blocking": False})
    monkeypatch.setattr(reliability, "load_shared_checkpoint", lambda: {
        "createdAt": "2026-10-26T04:56:00Z", "runtimeSource": "GITHUB_ACTIONS",
        "marketData": {"latestSession": "2026-10-23"},
    })


def test_render_uses_checkpoint_not_missing_local_csvs(shared_dashboard, monkeypatch):
    def no_local_history(*args):
        raise AssertionError("Render must not require market-history CSVs")
    monkeypatch.setattr(reliability, "load_history", no_local_history)
    report = reliability.dashboard_reliability_report(None, BEFORE_CLOSE)
    assert report["status"] == "HEALTHY"
    assert report["marketData"]["latestSession"] == "2026-10-23"
    assert report["evidenceSource"] == "SHARED_CHECKPOINT"
    assert report["executionSource"] == "GITHUB_ACTIONS"
    assert report["displayOnly"] is True


def test_checkpoint_freshness_is_recomputed_after_close(shared_dashboard):
    after_close = BEFORE_CLOSE.replace(hour=16, minute=5)
    report = reliability.dashboard_reliability_report(None, after_close)
    assert report["status"] == "BLOCKED"
    assert report["marketData"]["status"] == "STALE"
    assert report["marketData"]["expectedSession"] == "2026-10-26"
    assert report["marketData"]["sessionsBehind"] == 1


@pytest.mark.parametrize("saved,status", [
    (None, "UNAVAILABLE"), ({}, "UNAVAILABLE"),
    ({"marketData": {"latestSession": "invalid"}}, "UNAVAILABLE"),
    ({"marketData": None}, "UNAVAILABLE"),
    ({"marketData": {"latestSession": "2026-10-27"}}, "INVALID"),
])
def test_unknown_or_future_market_evidence_is_not_healthy(shared_dashboard, monkeypatch, saved, status):
    monkeypatch.setattr(reliability, "load_shared_checkpoint", lambda: saved)
    report = reliability.dashboard_reliability_report(None, BEFORE_CLOSE)
    assert report["marketData"]["status"] == status
    assert report["allowRuntime"] is False
    assert "MARKET_DATA" in report["blockers"]


@pytest.mark.parametrize("check,blocker", [("ledger_integrity", "FORWARD_LEDGER"), ("checkpoint_status", "CHECKPOINT")])
def test_shared_integrity_failure_remains_blocking(shared_dashboard, monkeypatch, check, blocker):
    monkeypatch.setattr(reliability, check, lambda: {"status": "BROKEN", "blocking": True})
    report = reliability.dashboard_reliability_report(None, BEFORE_CLOSE)
    assert report["marketData"]["status"] == "FRESH"
    assert report["allowRuntime"] is False
    assert blocker in report["blockers"]


def test_execution_preflight_still_checks_its_actual_cache(shared_dashboard, monkeypatch):
    monkeypatch.setattr(reliability, "market_data_status", lambda now: {"status": "MISSING", "blocking": True})
    # Even with the display variables present, the runtime's existing function
    # cannot silently substitute a healthy persisted checkpoint.
    report = reliability.reliability_report(None, BEFORE_CLOSE)
    assert report["allowRuntime"] is False
    assert report["marketData"]["status"] == "MISSING"


@pytest.mark.parametrize("variable,value", [("SHARED_STATE_BACKEND", "file"), ("PUBLIC_DASHBOARD_READ_ONLY", "false")])
def test_other_roles_keep_local_preflight(shared_dashboard, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    monkeypatch.setattr(reliability, "market_data_status", lambda now: {"status": "MISSING", "blocking": True})
    report = reliability.dashboard_reliability_report(None, BEFORE_CLOSE)
    assert report["allowRuntime"] is False
    assert report.get("displayOnly") is None


def test_runtime_history_api_uses_shared_backend(monkeypatch):
    from app.main import app
    activity = [{"eventId": "older"}, {"eventId": "newer"}]
    equity = [{"timestamp": "older", "equity": 100000}, {"timestamp": "newer", "equity": 100100}]
    calls = []
    monkeypatch.setenv("PUBLIC_DASHBOARD_READ_ONLY", "true")
    monkeypatch.setattr(runtime, "shared_state_enabled", lambda: True)
    monkeypatch.setattr(runtime, "read_activity", lambda limit: calls.append(("activity", limit)) or activity)
    monkeypatch.setattr(runtime, "read_equity", lambda limit: calls.append(("equity", limit)) or equity)
    monkeypatch.setattr(runtime, "read_jsonl", lambda *args, **kwargs: pytest.fail("Unexpected local file read"))
    with TestClient(app) as client:
        assert client.get("/api/runtime/activity").json() == {"activity": list(reversed(activity))}
        assert client.get("/api/runtime/equity").json() == {"equity": equity}
        assert client.post("/health").status_code == 403
    assert calls == [("activity", 100), ("equity", 500)]


def test_file_runtime_history_fallback_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "shared_state_enabled", lambda: False)
    a = tmp_path / "activity.jsonl"; a.write_text('{"eventId":"one"}\n')
    e = tmp_path / "equity.jsonl"; e.write_text('{"equity":100000}\n')
    monkeypatch.setattr(runtime, "ACTIVITY_PATH", a)
    monkeypatch.setattr(runtime, "EQUITY_PATH", e)
    assert runtime.read_runtime_activity() == [{"eventId": "one"}]
    assert runtime.read_runtime_equity() == [{"equity": 100000}]
