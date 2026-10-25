import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.risk import (
    position_size,
    build_trade_plan,
)


def sample_history():
    rows = []

    for i in range(100):
        close = 100 + i * 0.25

        rows.append(
            {
                "High": close + 2,
                "Low": close - 2,
                "Close": close,
                "Volume": 1000000,
            }
        )

    return pd.DataFrame(rows)


def test_position_size_respects_capital_risk():
    qty = position_size(
        cash=100000,
        capital=100000,
        entry=1000,
        stop=950,
        risk=0.01,
        cap=0.15,
    )

    assert qty <= 15
    assert qty * 50 <= 1000


def test_regime_reduces_position_size():
    normal = position_size(
        cash=100000,
        capital=100000,
        entry=1000,
        stop=950,
        exposure_multiplier=1.0,
    )

    defensive = position_size(
        cash=100000,
        capital=100000,
        entry=1000,
        stop=950,
        exposure_multiplier=0.40,
    )

    assert defensive < normal


def test_panic_blocks_position():
    qty = position_size(
        cash=100000,
        capital=100000,
        entry=1000,
        stop=950,
        exposure_multiplier=0,
    )

    assert qty == 0


def test_trade_plan_has_valid_rr():
    plan = build_trade_plan(
        sample_history(),
        cash=100000,
        capital=100000,
    )

    assert plan.stop < plan.entry
    assert plan.target > plan.entry
    assert plan.reward_risk >= 1.99
    assert plan.quantity > 0
    assert plan.capital_risk <= 1000
    assert plan.position_value <= 15000
