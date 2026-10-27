"""The real execution/learning/report pipeline, with isolated state and no network."""
from datetime import date
from types import SimpleNamespace
import numpy as np
import pytest
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Portfolio, PaperOrder, PaperTrade, RuntimeActivity
from app import forward_learning, runtime, reliability, shared_state, market_analysis


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_complete_cycles_persist_real_analysis_and_preserve_account(tmp_path, monkeypatch, request, backend):
    if backend == "postgres":
        engine, _ = request.getfixturevalue("postgres")
    else:
        engine = create_engine('sqlite:///' + str(tmp_path / 'paper.db'))
        Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(shared_state, 'SessionLocal', sessions)
    monkeypatch.setenv('SHARED_STATE_BACKEND', 'db')
    monkeypatch.setattr(reliability, 'expected_closed_session', lambda now=None: date(2026, 10, 23))
    index = pd.bdate_range(end='2026-10-23', periods=350)

    def frame(symbol):
        close = np.linspace(200, 100, 350) if symbol == '^NSEI' else np.linspace(100, 200, 350)
        return pd.DataFrame({'close': close, 'high': close + 2, 'low': close - 2,
                             'open': close, 'volume': 1000000}, index=index)
    monkeypatch.setattr(forward_learning, 'load_history', frame)
    monkeypatch.setattr(reliability, 'load_history', frame)
    monkeypatch.setattr(forward_learning, 'load_universe', lambda: [
        SimpleNamespace(symbol=symbol, sector='TEST') for symbol in ['ONE', 'TWO', 'THREE']])

    class NoNetwork:
        def quote(self, symbol):
            raise RuntimeError('Delayed feed unavailable in isolated validation')
    monkeypatch.setattr(runtime, 'YahooProvider', NoNetwork)
    db = sessions()
    try:
        db.add(Portfolio(initial_capital=100000, cash=100000, realized_pnl=0)); db.commit()
        first = runtime.run_cycle(db)
        second = runtime.run_cycle(db)
        assert first['status'] == second['status'] == 'HEALTHY'
        assert second['steps']['predictions']['created'] == 0
        assert second['steps']['predictions']['duplicates'] == 3
        assert db.query(Portfolio).one().cash == 100000
        assert db.query(PaperOrder).count() == 3
        assert db.query(PaperTrade).count() == 0
        assert db.query(RuntimeActivity).filter_by(event_type='MARKET_ANALYSIS').count() == 2
        report = market_analysis.load_market_analysis()
        assert report['status'] == 'AVAILABLE'
        assert report['regime']['name'] == 'PANIC'
        assert report['adaptivePolicy']['status'] == 'BASELINE_RETAINED'
        assert report['benchmarkQuote']['status'] == 'UNAVAILABLE'
        assert report['results'][0]['source'] == 'EXECUTION_DAILY_CACHE'
        assert shared_state.load_runtime_state()['cycles'] == 2
        assert reliability.checkpoint_status()['status'] == 'MATCH'
        from app import execution
        original = execution.run_execution_cycle
        def interrupted(*args, **kwargs):
            raise RuntimeError("Injected process failure after forward stages")
        monkeypatch.setattr(execution, "run_execution_cycle", interrupted)
        with pytest.raises(RuntimeError, match="Injected process failure"):
            runtime.run_cycle(db)
        assert shared_state.load_runtime_state()["status"] == "ERROR"
        monkeypatch.setattr(execution, "run_execution_cycle", original)
        recovered = runtime.run_cycle(db)
        assert recovered["preflight"]["checkpoint"]["status"] == "RECOVERY_REQUIRED"
        assert recovered["status"] == "HEALTHY"
        assert shared_state.load_runtime_state()["cycles"] == 3
        assert reliability.checkpoint_status()["status"] == "MATCH"
        assert db.query(Portfolio).one().cash == 100000
        assert db.query(PaperOrder).count() == 3

    finally:
        db.close(); engine.dispose()


def test_incomplete_position_marks_preserve_value_and_report_missing_data(tmp_path, monkeypatch):
    from app.models import Position
    engine = create_engine('sqlite:///' + str(tmp_path / 'mark.db'))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setenv('SHARED_STATE_BACKEND', 'db')
    monkeypatch.setattr(shared_state, 'SessionLocal', sessions)
    db = sessions()
    try:
        db.add(Portfolio(initial_capital=100000, cash=90000, realized_pnl=0))
        db.add(Position(symbol='STALE', quantity=10, avg_price=1000, current_price=1100,
                        stop_price=900, target_price=1200, status='OPEN'))
        db.commit()
        class NoQuote:
            def quote(self, symbol):
                raise RuntimeError('Feed unavailable')
        snapshot = runtime.portfolio_snapshot(db, NoQuote())
        assert snapshot['positionsMarked'] == 0
        assert snapshot['openPositions'] == 1
        assert snapshot['marketValue'] == 11000
        assert snapshot['equity'] == 101000
    finally:
        db.close(); engine.dispose()
