import sys
from datetime import (
    date,
)
from pathlib import Path

import pandas as pd


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from app.backtest import (
    enrich,
    feature_score,
    metrics,
)
from app.sessions import (
    is_trading_session,
    add_trading_sessions,
)


def sample_frame():
    dates = pd.bdate_range(
        "2025-01-01",
        periods=320,
    )

    close = pd.Series(
        [
            100 + i * 0.5
            for i in range(
                len(dates)
            )
        ],
        index=dates,
    )

    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1_000_000,
        }
    )


def test_enrich_has_forward_returns():
    result = enrich(
        sample_frame()
    )

    assert "forward_5" in result
    assert "forward_30" in result
    assert "sma200" in result


def test_strong_stock_scores_high():
    frame = enrich(
        sample_frame()
    )

    # Pick the latest row with all historical
    # features available. Forward returns are
    # irrelevant to feature_score().
    mature = frame.dropna(
        subset=[
            "sma20",
            "sma50",
            "sma200",
            "rsi14",
            "mom1m",
            "mom3m",
            "mom6m",
            "high52",
            "low52",
            "vol20",
        ]
    )

    assert not mature.empty

    row = mature.iloc[-1]
    benchmark = mature.iloc[-1]

    score = feature_score(
        row,
        benchmark,
    )

    assert score is not None
    assert score >= 50


def test_metrics():
    result = metrics(
        [
            0.10,
            0.05,
            -0.02,
            0.03,
        ]
    )

    assert result["trades"] == 4
    assert result["winRate"] == 0.75
    assert (
        result["averageReturn"]
        > 0
    )


def test_nse_holiday():
    assert (
        is_trading_session(
            date(
                2026,
                10,
                20,
            )
        )
        is False
    )


def test_session_skips_dussehra():
    result = (
        add_trading_sessions(
            date(
                2026,
                10,
                19,
            ),
            1,
        )
    )

    assert (
        result.date()
        == date(
            2026,
            10,
            21,
        )
    )


def test_portfolio_returns_group_same_date():
    from app.backtest import (
        portfolio_period_returns,
    )

    rows = [
        {
            "date": "2026-01-01",
            "return20D": 0.10,
        },
        {
            "date": "2026-01-01",
            "return20D": -0.02,
        },
        {
            "date": "2026-02-01",
            "return20D": 0.04,
        },
    ]

    result = portfolio_period_returns(
        rows,
        20,
    )

    assert len(result) == 2
    assert round(result[0], 6) == 0.04
    assert round(result[1], 6) == 0.04
