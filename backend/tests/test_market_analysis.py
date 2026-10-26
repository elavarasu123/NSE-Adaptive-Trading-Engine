from datetime import datetime, timezone
from types import SimpleNamespace
import pandas as pd
import pytest
from fastapi.testclient import TestClient
import app.market_analysis as analysis
from app.adaptive_policy import learn_entry_policy
from app.forward_learning import LearningContext


def test_cycle_context_excludes_partial_bars_and_loads_each_symbol_once(monkeypatch):
    import app.forward_learning as forward
    calls = []
    frame = pd.DataFrame({'close': [100., 200., 999.]}, index=pd.to_datetime(['2026-10-22', '2026-10-23', '2026-10-26']))
    monkeypatch.setattr(forward, 'load_history', lambda symbol: calls.append(symbol) or frame)
    context = LearningContext(as_of=datetime(2026, 10, 23).date())
    assert context.frame('TEST').index[-1] == pd.Timestamp('2026-10-23')
    assert context.frame('TEST').iloc[-1]['close'] == 200
    assert calls == ['TEST']


def context():
    return SimpleNamespace(candidates=lambda: [{'symbol': 'TEST', 'score': 99, 'entryPrice': 100., 'regime': 'PANIC'}],
        benchmark_row={'close': 20000, 'sma20': 21000, 'sma50': 22000, 'sma200': 23000,
                       'mom1m': -.04, 'mom3m': -.08, 'rsi14': 30, 'vol20': .3},
        regime='PANIC', universe=[1, 2], coverage={'missing': 1}, market_date=pd.Timestamp('2026-10-23'))


def test_analysis_uses_execution_regime_not_demo_or_alternate_detector():
    report = analysis.build_market_analysis(context(), learn_entry_policy([], '2026-10-23'))
    assert report['regime']['name'] == 'PANIC'
    assert report['results'][0]['decision'] == 'REJECT'
    assert report['successful'] == 1 and report['failed'] == 1
    assert report['asOf'] == '2026-10-23'
    assert 'up' not in report['results'][0]  # No fabricated probabilities.


def test_saved_analysis_is_recomputed_for_staleness_without_mutation(monkeypatch):
    report = analysis.build_market_analysis(context(), learn_entry_policy([], '2026-10-23'))
    monkeypatch.setattr(analysis, 'shared_state_enabled', lambda: True)
    monkeypatch.setattr(analysis, 'latest_activity_of_type', lambda kind: {'data': {'analysis': report}})
    from app.reliability import IST
    assert analysis.load_market_analysis(datetime(2026, 10, 26, 14, tzinfo=IST))['status'] == 'AVAILABLE'
    stale = analysis.load_market_analysis(datetime(2026, 10, 26, 16, 5, tzinfo=IST))
    assert stale['status'] == 'STALE'
    assert stale['regime']['entriesAllowed'] is False
    assert stale['results'][0]['decision'] == 'WAIT'
    assert report['results'][0]['decision'] == 'REJECT'


def test_missing_persisted_analysis_does_not_fall_back_to_demo(monkeypatch):
    from app.main import app
    monkeypatch.setenv('PUBLIC_DASHBOARD_READ_ONLY', 'true')
    monkeypatch.setattr(analysis, 'shared_state_enabled', lambda: True)
    monkeypatch.setattr(analysis, 'latest_activity_of_type', lambda kind: None)
    with TestClient(app) as client:
        assert client.get('/api/candidates').json() == []
        assert client.get('/api/scanner/report').json()['status'] == 'UNAVAILABLE'
        assert client.get('/api/regime').json()['name'] == 'UNKNOWN'
        assert client.get('/api/market/analysis').json()['status'] == 'UNAVAILABLE'
        assert client.post('/api/engine/run').status_code == 403


def test_cycle_provider_reuses_quotes_and_settled_history():
    from app.market import CycleMarketProvider
    calls = []
    source = SimpleNamespace(quote=lambda symbol: calls.append(symbol) or SimpleNamespace(price=100))
    provider = CycleMarketProvider(source, SimpleNamespace(frame=lambda symbol: 'settled'))
    assert provider.history('TEST') == 'settled'
    assert provider.quote('TEST').price == provider.quote('TEST').price == 100
    assert calls == ['TEST']
