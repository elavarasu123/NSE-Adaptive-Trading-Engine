import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.regime import (
    detect_regime,
    apply_regime,
)


class TrendProvider:
    def __init__(self, rising=True):
        self.rising = rising

    def history(self, symbol, period="2y"):
        dates = pd.date_range(
            "2025-01-01",
            periods=300,
            freq="B",
        )

        if self.rising:
            close = [
                100 + (80 * i / 299)
                for i in range(300)
            ]
        else:
            close = [
                180 - (90 * i / 299)
                for i in range(300)
            ]

        return pd.DataFrame(
            {
                "Close": close,
                "Volume": [1000000] * 300,
            },
            index=dates,
        )


def test_rising_market_is_not_defensive():
    regime = detect_regime(
        TrendProvider(rising=True)
    )

    assert regime.name in (
        "RISK_ON",
        "NEUTRAL",
    )

    assert regime.exposure_multiplier > 0


def test_falling_market_reduces_risk():
    regime = detect_regime(
        TrendProvider(rising=False)
    )

    assert regime.name in (
        "DEFENSIVE",
        "PANIC",
    )

    assert regime.exposure_multiplier <= 0.40


def test_panic_blocks_buy():
    class Panic:
        name = "PANIC"
        score = -8
        exposure_multiplier = 0
        buy_threshold = 101

    candidate = {
        "symbol": "TEST",
        "score": 99,
        "decision": "BUY",
    }

    result = apply_regime(
        candidate,
        Panic(),
    )

    assert result["decision"] == "REJECT"
