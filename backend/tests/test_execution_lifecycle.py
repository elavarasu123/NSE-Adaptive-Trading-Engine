"""Full simulated order lifecycles, isolated from any shared account."""
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import execution
from app.models import PaperOrder, PaperTrade, Portfolio, Position


class Provider:
    price = 1000.0

    def quote(self, symbol):
        return SimpleNamespace(price=self.price)

    def history(self, symbol, period="1y"):
        close = pd.Series([900 + i * 100 / 99 for i in range(100)])
        return pd.DataFrame({"close": close, "high": close + 10, "low": close - 10, "volume": 1000000})


@pytest.fixture(params=["sqlite", "postgres"])
def account(request):
    if request.param == "postgres":
        engine, _ = request.getfixturevalue("postgres")
    else:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Portfolio(initial_capital=100000, cash=100000, realized_pnl=0))
    db.commit()
    try:
        yield db
    finally:
        db.close(); engine.dispose()


def prediction(symbol="TEST", **changes):
    return {"predictionId": "prediction-" + symbol, "predictionDate": "2026-10-23",
            "modelVersion": execution.MODEL_VERSION, "symbol": symbol,
            "score": 90, "entryPrice": 1000, "regime": "RISK_ON", **changes}


def batch(monkeypatch, rows):
    monkeypatch.setattr(execution, "_latest_batch", lambda: rows)


def test_automatic_fill_is_idempotent(account, monkeypatch):
    batch(monkeypatch, [prediction()])
    first = execution.enter_latest_batch(account, Provider())
    cash = account.query(Portfolio).one().cash
    second = execution.enter_latest_batch(account, Provider())
    assert len(first["filled"]) == 1
    assert len(second["existing"]) == 1
    assert account.query(PaperOrder).count() == 1
    assert account.query(PaperTrade).count() == 1
    assert account.query(Position).count() == 1
    assert account.query(Portfolio).one().cash == cash
    assert account.query(Portfolio).one().initial_capital == 100000


@pytest.mark.parametrize("changes,reason", [
    ({"regime": "PANIC"}, "PANIC_REGIME_BLOCK"),
    ({"modelVersion": "challenger"}, "MODEL_NOT_CHAMPION"),
])
def test_rejected_prediction_cannot_debit_cash(account, monkeypatch, changes, reason):
    batch(monkeypatch, [prediction(**changes)])
    execution.enter_latest_batch(account, Provider())
    execution.enter_latest_batch(account, Provider())
    assert account.query(PaperOrder).one().reason == reason
    assert account.query(PaperTrade).count() == 0
    assert account.query(Position).count() == 0
    assert account.query(Portfolio).one().cash == 100000


@pytest.mark.parametrize("exit_kind", ["target", "stop_gap"])
def test_automatic_exit_preserves_net_accounting(account, monkeypatch, exit_kind):
    batch(monkeypatch, [prediction()])
    provider = Provider()
    execution.enter_latest_batch(account, provider)
    order = account.query(PaperOrder).one()
    provider.price = order.target_price + 20 if exit_kind == "target" else order.stop_price - 50
    events = execution.monitor_all_positions(account, provider)
    account.refresh(order)
    portfolio = account.query(Portfolio).one()
    assert events[0]["action"] == "SELL"
    assert order.status == "CLOSED"
    assert account.query(Position).one().status == "CLOSED"
    assert account.query(PaperTrade).count() == 2
    assert portfolio.cash == pytest.approx(100000 + order.realized_pnl, abs=0.01)
    assert portfolio.realized_pnl == order.realized_pnl
    if exit_kind == "stop_gap":
        assert order.exit_price < order.stop_price  # Do not assume a guaranteed stop fill.
        assert order.realized_pnl < 0
    else:
        assert order.realized_pnl > 0


def test_batch_cap_applies_across_repeated_cycles(account, monkeypatch):
    monkeypatch.setattr(execution, "MAX_NEW_POSITIONS_PER_BATCH", 2)
    batch(monkeypatch, [prediction(symbol) for symbol in ["AAA", "BBB", "CCC"]])
    execution.enter_latest_batch(account, Provider())
    execution.enter_latest_batch(account, Provider())
    assert account.query(Position).count() == 2
    assert account.query(PaperOrder).filter(PaperOrder.status == "REJECTED").one().reason == "BATCH_ENTRY_CAP"


def test_automatic_entry_obeys_portfolio_position_limit(account, monkeypatch):
    for i in range(6):
        account.add(Position(symbol=f"OPEN{i}", quantity=10, avg_price=1000,
                             current_price=1000, stop_price=950, target_price=1100, status="OPEN"))
    portfolio = account.query(Portfolio).one(); portfolio.cash = 40000
    account.commit()
    batch(monkeypatch, [prediction()])
    execution.enter_latest_batch(account, Provider())
    assert account.query(PaperOrder).one().reason.startswith("RISK_GATE:")
    assert account.query(PaperTrade).count() == 0
    assert portfolio.cash == 40000


def test_validated_threshold_changes_paper_entries_and_records_rejection(account, monkeypatch):
    batch(monkeypatch, [prediction(score=78)])
    policy = {'asOf': '2026-10-23', 'regimes': {'RISK_ON': {'status': 'ACTIVE', 'effectiveThreshold': 80}}}
    result = execution.enter_latest_batch(account, Provider(), adaptive_policy=policy)
    assert result['rejected'][0]['reason'] == 'BELOW_ADAPTIVE_THRESHOLD:80.0'
    assert account.query(PaperTrade).count() == 0
    assert account.query(Portfolio).one().cash == 100000


def test_stale_adaptive_revision_cannot_change_a_new_batch(account, monkeypatch):
    batch(monkeypatch, [prediction(score=78)])
    policy = {'asOf': '2026-10-22', 'regimes': {'RISK_ON': {'status': 'ACTIVE', 'effectiveThreshold': 80}}}
    result = execution.enter_latest_batch(account, Provider(), adaptive_policy=policy)
    assert len(result['filled']) == 1


def test_paper_entry_uses_observed_price_for_gap_and_position_sizing(account, monkeypatch):
    batch(monkeypatch, [prediction()])
    provider = Provider()
    provider.price = 1100  # Previous daily history still closes at 1000.
    execution.enter_latest_batch(account, provider)
    order = account.query(PaperOrder).one()
    assert order.fill_price == pytest.approx(1100 * 1.0005, abs=.01)
    assert account.query(Position).one().quantity * order.fill_price <= 15000


def test_entry_order_failure_rolls_back_cash_position_and_trade(account, monkeypatch):
    from sqlalchemy import event
    batch(monkeypatch, [prediction()])
    def fail_order(db, context, instances):
        if any(isinstance(row, PaperOrder) and row.status == 'FILLED' for row in db.new):
            raise RuntimeError('Simulated crash before order persistence')
    event.listen(account, 'before_flush', fail_order)
    try:
        with pytest.raises(RuntimeError, match='Simulated crash'):
            execution.enter_latest_batch(account, Provider())
    finally:
        event.remove(account, 'before_flush', fail_order)
    assert account.query(Portfolio).one().cash == 100000
    assert account.query(Position).count() == account.query(PaperTrade).count() == account.query(PaperOrder).count() == 0
    assert len(execution.enter_latest_batch(account, Provider())['filled']) == 1


def test_exit_order_failure_rolls_back_sell_and_restores_open_position(account, monkeypatch):
    from sqlalchemy import event
    batch(monkeypatch, [prediction()])
    provider = Provider()
    execution.enter_latest_batch(account, provider)
    order = account.query(PaperOrder).one()
    before_cash = account.query(Portfolio).one().cash
    provider.price = order.target_price + 10
    def fail_closed(db, context, instances):
        if any(isinstance(row, PaperOrder) and row.status == 'CLOSED' for row in db.dirty):
            raise RuntimeError('Simulated crash on exit order')
    event.listen(account, 'before_flush', fail_closed)
    try:
        with pytest.raises(RuntimeError, match='Simulated crash'):
            execution.monitor_all_positions(account, provider)
    finally:
        event.remove(account, 'before_flush', fail_closed)
    assert account.query(Portfolio).one().cash == before_cash
    assert account.query(Position).one().status == 'OPEN'
    assert account.query(PaperOrder).one().status == 'FILLED'
    assert account.query(PaperTrade).count() == 1


def test_reconciliation_detects_unexplained_cash_and_missing_order(account, monkeypatch):
    from app.reconciliation import reconcile_account
    batch(monkeypatch, [prediction()])
    execution.enter_latest_batch(account, Provider())
    assert reconcile_account(account)['status'] == 'OK'
    account.query(Portfolio).one().cash += 100
    account.commit()
    assert reconcile_account(account)['blocking'] is True
    account.delete(account.query(PaperOrder).one()); account.commit()
    assert any('buy fills' in issue for issue in reconcile_account(account)['issues'])


def test_missing_position_quote_pauses_entries_but_other_exits_continue(account, monkeypatch):
    batch(monkeypatch, [prediction('UNAVAILABLE'), prediction('VALID')])
    provider = Provider()
    execution.enter_latest_batch(account, provider)
    orders = account.query(PaperOrder).all()
    batch(monkeypatch, [prediction('NEW')])
    class PartialFeed(Provider):
        def quote(self, symbol):
            if symbol == 'UNAVAILABLE':
                raise RuntimeError('No quote')
            return SimpleNamespace(price=next(o.target_price + 10 for o in orders if o.symbol == 'VALID'))
    result = execution.run_execution_cycle(account, PartialFeed())
    assert result['entries']['pausedReason'] == 'OPEN_POSITION_DATA_UNAVAILABLE'
    assert result['entries']['filled'] == []
    assert any(event.get('action') == 'SELL' for event in result['exits'])
    assert account.query(PaperOrder).filter_by(symbol='UNAVAILABLE').one().status == 'FILLED'
    assert account.query(PaperOrder).filter_by(symbol='NEW').count() == 0


@pytest.mark.parametrize('cost', [-1, float('inf'), float('nan')])
def test_invalid_costs_cannot_create_cash_or_fill(account, monkeypatch, cost):
    batch(monkeypatch, [prediction()])
    monkeypatch.setattr(execution, 'FEE_BPS', cost)
    result = execution.enter_latest_batch(account, Provider())
    assert result['filled'] == []
    assert account.query(Portfolio).one().cash == 100000
    assert account.query(PaperTrade).count() == 0
