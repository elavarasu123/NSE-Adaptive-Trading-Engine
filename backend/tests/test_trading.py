import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "test_adaptive_engine.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

if TEST_DB.exists():
    TEST_DB.unlink()

from app.database import Base, engine, SessionLocal
from app.models import Portfolio, Position, PaperTrade
from app.trading import paper_buy, paper_sell


class FixedQuote:
    def __init__(self, symbol, price):
        self.symbol = symbol
        self.price = price
        self.source = "TEST"
        self.is_live = False


class FixedProvider:
    def __init__(self, price):
        self.price = price

    def quote(self, symbol):
        return FixedQuote(symbol, self.price)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    db.add(
        Portfolio(
            initial_capital=100000,
            cash=100000,
            realized_pnl=0,
        )
    )
    db.commit()
    db.close()


def test_buy_reduces_cash_and_creates_trade():
    db = SessionLocal()

    position = paper_buy(
        db,
        FixedProvider(1000),
        "TEST",
    )

    portfolio = db.query(Portfolio).first()
    trades = db.query(PaperTrade).all()

    assert position.status == "OPEN"
    assert position.quantity > 0
    assert portfolio.cash < 100000
    assert len(trades) == 1
    assert trades[0].side == "BUY"

    db.close()


def test_sell_returns_cash_and_realizes_profit():
    db = SessionLocal()

    position = paper_buy(
        db,
        FixedProvider(1000),
        "TEST",
    )

    qty = position.quantity

    result = paper_sell(
        db,
        FixedProvider(1100),
        "TEST",
        reason="TEST_TARGET",
    )

    portfolio = db.query(Portfolio).first()
    closed = db.query(Position).first()
    trades = db.query(PaperTrade).all()

    expected_profit = qty * 100

    assert closed.status == "CLOSED"
    assert result["realizedPnl"] == expected_profit
    assert portfolio.realized_pnl == expected_profit
    assert portfolio.cash == 100000 + expected_profit
    assert len(trades) == 2
    assert trades[-1].side == "SELL"

    db.close()
