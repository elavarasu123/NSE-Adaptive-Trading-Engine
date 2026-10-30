from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from app.database import Base
from app.models import Portfolio
from app.scheduler_schedule import IST
import app.paper_worker as worker


def clock(hour=10, minute=25):
    return datetime(2026, 10, 30, hour, minute, tzinfo=IST)


def configuration():
    return {'DATABASE_URL': 'postgresql://user:private@host/existing', 'SHARED_STATE_BACKEND': 'db',
            'RUNTIME_SOURCE': 'SCHEDULED_PAPER_WORKER', 'PUBLIC_DASHBOARD_READ_ONLY': 'false',
            'MARKET_PROVIDER': 'yahoo', 'FORCE_RUNTIME': 'false'}


@pytest.mark.parametrize('changes', [
    {'DATABASE_URL': 'sqlite:///test.db'}, {'DATABASE_URL': 'invalid-secret'},
    {'SHARED_STATE_BACKEND': 'file'}, {'RUNTIME_SOURCE': 'RENDER_DASHBOARD'},
    {'PUBLIC_DASHBOARD_READ_ONLY': 'true'}, {'MARKET_PROVIDER': 'demo'}, {'FORCE_RUNTIME': 'true'},
])
def test_unsafe_configuration_is_rejected_without_leaking_credentials(changes):
    config = {**configuration(), **changes}
    with pytest.raises(RuntimeError) as error:
        worker.validate_configuration(config)
    assert 'private' not in str(error.value) and 'invalid-secret' not in str(error.value)


def test_worker_is_disabled_by_default_without_touching_account(monkeypatch, capsys):
    monkeypatch.delenv('WORKER_EXECUTION_ENABLED', raising=False)
    monkeypatch.setattr(worker, 'SessionLocal', lambda: pytest.fail('Disabled worker connected'))
    assert worker.main() == 0
    assert 'DISABLED' in capsys.readouterr().out


@pytest.fixture(params=['sqlite', 'postgres'])
def db(tmp_path, request):
    if request.param == 'postgres':
        engine, _ = request.getfixturevalue('postgres')
    else:
        engine = create_engine('sqlite:///' + str(tmp_path / 'worker.db'))
        Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        if request.param == 'sqlite':
            engine.dispose()


def test_worker_never_seeds_or_funds_an_account(db):
    with pytest.raises(RuntimeError, match='will not initialize'):
        worker.existing_portfolio(db)
    assert db.query(Portfolio).count() == 0


def test_due_recheck_under_lock_prevents_duplicate_and_after_hours_cycles(db, monkeypatch):
    db.add(Portfolio(id=1, initial_capital=100000, cash=93622.19))
    db.commit()
    monkeypatch.setattr(worker, 'load_state', lambda: {'status': 'HEALTHY', 'lastSuccessfulAt': clock(10, 22).isoformat()})
    monkeypatch.setattr(worker, 'now', lambda: clock())
    monkeypatch.setattr(worker, 'run_cycle', lambda db: pytest.fail('Duplicate execution'))
    assert worker.execute_due(db)['reason'] == 'SLOT_ALREADY_COMPLETED'
    monkeypatch.setattr(worker, 'now', lambda: clock(17, 0))
    assert worker.execute_due(db)['reason'] == 'OUTSIDE_MARKET_WINDOW'
    assert db.get(Portfolio, 1).cash == 93622.19


def test_due_worker_calls_existing_engine_without_changing_funded_capital(db, monkeypatch):
    db.add(Portfolio(id=1, initial_capital=100000, cash=93622.19))
    db.commit()
    monkeypatch.setattr(worker, 'load_state', lambda: {'status': 'HEALTHY', 'lastSuccessfulAt': clock(9, 22).isoformat()})
    monkeypatch.setattr(worker, 'now', lambda: clock())
    monkeypatch.setattr(worker, 'run_cycle', lambda owned_db: {'status': 'HEALTHY', 'sameSession': owned_db is db})
    assert worker.execute_due(db) == {'status': 'HEALTHY', 'sameSession': True}
    assert db.get(Portfolio, 1).initial_capital == 100000
    assert db.get(Portfolio, 1).cash == 93622.19


@pytest.mark.parametrize('race', ['completed_elsewhere', 'window_closed'])
def test_after_refresh_main_rechecks_slot_and_window_before_execution(db, monkeypatch, race):
    for key, value in configuration().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('WORKER_EXECUTION_ENABLED', 'true')
    db.add(Portfolio(id=1, initial_capital=100000, cash=93622.19))
    db.commit()
    state = {'status': 'HEALTHY', 'lastSuccessfulAt': clock(9, 22).isoformat()}
    clocks = [clock()]
    monkeypatch.setattr(worker, 'SessionLocal', lambda: db)
    monkeypatch.setattr(worker, 'now', lambda: clocks[0])
    monkeypatch.setattr(worker, 'load_state', lambda: state)
    monkeypatch.setattr(worker, 'run_cycle', lambda db: pytest.fail('Unsafe repeated/after-hours execution'))
    def refresh(force):
        assert force is False
        if race == 'completed_elsewhere':
            state['lastSuccessfulAt'] = clock(10, 22).isoformat()
        else:
            clocks[0] = clock(17, 0)
    monkeypatch.setattr(worker, 'ensure_history', refresh)
    assert worker.main() == 0
    assert db.get(Portfolio, 1).cash == 93622.19
