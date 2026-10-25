import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from app.portfolio_backtest import (
    annualized_metrics,
    CHAMPION,
    CHALLENGER,
)


def test_equity_metrics_positive_curve():
    curve = [
        {
            "date":
                "2025-01-01",
            "equity":
                100000,
        },
        {
            "date":
                "2025-06-01",
            "equity":
                105000,
        },
        {
            "date":
                "2026-01-01",
            "equity":
                110000,
        },
    ]

    result = annualized_metrics(
        curve
    )

    assert (
        result["totalReturn"]
        > 0
    )

    assert (
        result["cagr"]
        > 0
    )

    assert (
        result["maxDrawdown"]
        == 0
    )


def test_drawdown_is_realistic():
    curve = [
        {
            "date":
                "2025-01-01",
            "equity":
                100000,
        },
        {
            "date":
                "2025-02-01",
            "equity":
                110000,
        },
        {
            "date":
                "2025-03-01",
            "equity":
                99000,
        },
        {
            "date":
                "2025-04-01",
            "equity":
                105000,
        },
    ]

    result = annualized_metrics(
        curve
    )

    assert round(
        result["maxDrawdown"],
        2,
    ) == -0.10


def test_champion_is_frozen_20d():
    assert (
        CHAMPION.name
        == "champion-v0.2"
    )

    assert (
        CHAMPION.holding_sessions
        == 20
    )

    assert (
        CHAMPION.min_score
        == 65
    )


def test_challenger_is_separate():
    assert (
        CHALLENGER.name
        != CHAMPION.name
    )

    assert (
        CHALLENGER.holding_sessions
        == 30
    )

    assert (
        CHALLENGER.min_score
        == 75
    )
