import runpy
from pathlib import Path
import pandas as pd
import pytest


@pytest.fixture
def recovery():
    path = Path(__file__).resolve().parents[1] / "scripts/ensure_market_history.py"
    return runpy.run_path(str(path))["ensure_history"]


def test_current_history_does_not_download(recovery, monkeypatch):
    monkeypatch.setitem(recovery.__globals__, "has_expected_session", lambda: True)
    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("unexpected download"))
    assert recovery() is False


@pytest.mark.parametrize("force", [False, True])
def test_refresh_is_revalidated_and_bounded(recovery, monkeypatch, force):
    checks = iter([force, True])
    monkeypatch.setitem(recovery.__globals__, "has_expected_session", lambda: next(checks))
    calls = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: calls.append((a, k)))
    assert recovery(force=force) is True
    assert len(calls) == 1 and calls[0][1] == {"check": True, "timeout": 1200}


def test_failed_refresh_remains_blocked(recovery, monkeypatch):
    monkeypatch.setitem(recovery.__globals__, "has_expected_session", lambda: False)
    monkeypatch.setattr("subprocess.run", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="expected settled"):
        recovery()


def test_partial_today_does_not_hide_missing_settled_session(recovery, monkeypatch):
    namespace = recovery.__globals__
    expected = pd.Timestamp("2026-10-27").date()
    monkeypatch.setitem(namespace, "expected_closed_session", lambda: expected)
    frame = pd.DataFrame({"close": [100., 200.]}, index=pd.to_datetime(["2026-10-26", "2026-10-28"]))
    monkeypatch.setitem(namespace, "load_history", lambda _: frame)
    assert namespace["has_expected_session"]() is False
    frame.loc[pd.Timestamp(expected), "close"] = 150.
    assert namespace["has_expected_session"]() is True


def test_execution_checkpoint_reports_latest_settled_bar(monkeypatch):
    from datetime import datetime
    import app.reliability as reliability
    frame = pd.DataFrame({"close": [100., 200.]}, index=pd.to_datetime(["2026-10-27", "2026-10-28"]))
    monkeypatch.setattr(reliability, "load_history", lambda _: frame)
    clock = datetime(2026, 10, 28, 12, tzinfo=reliability.IST)
    report = reliability.market_data_status(clock)
    assert report["status"] == "FRESH"
    assert report["latestSession"] == report["expectedSession"] == "2026-10-27"
    frame = frame.iloc[1:]
    assert reliability.market_data_status(clock)["blocking"] is True
