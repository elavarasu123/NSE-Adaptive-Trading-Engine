import runpy
from pathlib import Path
from types import SimpleNamespace
import pytest
import app.database as database
import app.reliability as reliability

@pytest.mark.parametrize('allowed', [True, False])
def test_cli_fails_for_blocked_preflight_and_always_closes_db(monkeypatch, allowed):
    closed = []
    monkeypatch.setattr(database, 'SessionLocal', lambda: SimpleNamespace(close=lambda: closed.append(True)))
    monkeypatch.setattr(reliability, 'reliability_report', lambda db: {
        'status': 'HEALTHY' if allowed else 'BLOCKED', 'runtimeSource': 'TEST',
        'allowRuntime': allowed, 'marketData': {}, 'portfolio': {}, 'ledger': {}, 'checkpoint': {}})
    path = Path(__file__).resolve().parents[1] / 'scripts/reliability_status.py'
    if allowed:
        runpy.run_path(str(path))
    else:
        with pytest.raises(SystemExit) as error:
            runpy.run_path(str(path))
        assert error.value.code == 1
    assert closed == [True]
