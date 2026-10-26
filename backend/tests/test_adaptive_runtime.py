"""The real execution/learning/report pipeline, with isolated state and no network."""
from datetime import date
from types import SimpleNamespace
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Portfolio, PaperOrder, PaperTrade, RuntimeActivity
from app import forward_learning, runtime, reliability, shared_state, market_analysis


def test_complete_cycles_persist_real_analysis_and_preserve_account(tmp_path, monkeypatch):
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
    finally:
        db.close(); engine.dispose()
