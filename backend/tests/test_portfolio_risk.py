import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "test_portfolio_risk.db"
os.environ["DATABASE_URL"] = (
    f"sqlite:///{TEST_DB}"
)

from app.database import (
    Base,
    engine,
    SessionLocal,
)
from app.models import Position
from app.portfolio_risk import (
    portfolio_risk,
    validate_new_trade,
)


def setup_function():
    Base.metadata.drop_all(
        bind=engine
    )
    Base.metadata.create_all(
        bind=engine
    )


def add_position(
    db,
    symbol,
    qty,
    entry,
    stop,
):
    db.add(
        Position(
            symbol=symbol,
            quantity=qty,
            avg_price=entry,
            current_price=entry,
            stop_price=stop,
            target_price=(
                entry
                + 2 * (entry - stop)
            ),
            status="OPEN",
        )
    )

    db.commit()


def test_portfolio_risk_calculation():
    db = SessionLocal()

    add_position(
        db,
        "AAA",
        10,
        1000,
        950,
    )

    result = portfolio_risk(
        db,
        100000,
    )

    assert result.open_positions == 1
    assert result.market_value == 10000
    assert result.capital_at_risk == 500
    assert result.exposure_pct == 10
    assert result.risk_pct == 0.5

    db.close()


def test_trade_rejected_above_total_risk():
    db = SessionLocal()

    add_position(
        db,
        "AAA",
        30,
        1000,
        900,
    )

    gate = validate_new_trade(
        db=db,
        capital=100000,
        proposed_value=10000,
        proposed_risk=1500,
    )

    assert gate.approved is False
    assert "risk" in gate.reason.lower()

    db.close()


def test_trade_rejected_above_exposure():
    db = SessionLocal()

    add_position(
        db,
        "AAA",
        60,
        1000,
        990,
    )

    gate = validate_new_trade(
        db=db,
        capital=100000,
        proposed_value=15000,
        proposed_risk=100,
    )

    assert gate.approved is False
    assert "exposure" in gate.reason.lower()

    db.close()


def test_valid_trade_passes():
    db = SessionLocal()

    add_position(
        db,
        "AAA",
        10,
        1000,
        950,
    )

    gate = validate_new_trade(
        db=db,
        capital=100000,
        proposed_value=12000,
        proposed_risk=600,
    )

    assert gate.approved is True

    db.close()
