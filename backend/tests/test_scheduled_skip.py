import runpy
from pathlib import Path
from types import SimpleNamespace


def test_outside_hours_skip_never_mutates_canonical_state(monkeypatch, capsys):
    import app.runtime as runtime
    import app.bootstrap as bootstrap
    import app.scheduler_guard as guard
    def forbidden(*args, **kwargs):
        raise AssertionError('Skipped requests must not mutate or initialize shared state')
    monkeypatch.setenv('FORCE_RUNTIME', 'false')
    monkeypatch.setattr(runtime, 'activity', forbidden)
    monkeypatch.setattr(runtime, 'run_cycle', forbidden)
    monkeypatch.setattr(bootstrap, 'ensure_paper_database', forbidden)
    monkeypatch.setattr(guard, 'session_guard', lambda: SimpleNamespace(should_run=False, reason='OUTSIDE_MARKET_WINDOW'))
    path = Path(__file__).resolve().parents[1] / 'scripts/run_scheduled_runtime.py'
    script = runpy.run_path(str(path))
    script['main']()
    assert 'SKIPPED: OUTSIDE_MARKET_WINDOW' in capsys.readouterr().out
