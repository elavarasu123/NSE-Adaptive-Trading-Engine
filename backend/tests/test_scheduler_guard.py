from datetime import datetime

from app.scheduler_guard import (
    IST,
    session_guard,
)


def test_market_window_runs():
    now = datetime(
        2026,
        10,
        26,
        10,
        15,
        tzinfo=IST,
    )

    result = session_guard(now)

    assert result.should_run is True
    assert (
        result.reason
        == "MARKET_WINDOW"
    )


def test_before_market_skips():
    now = datetime(
        2026,
        10,
        26,
        8,
        0,
        tzinfo=IST,
    )

    result = session_guard(now)

    assert result.should_run is False
    assert (
        result.reason
        == "OUTSIDE_MARKET_WINDOW"
    )


def test_weekend_skips():
    now = datetime(
        2026,
        10,
        25,
        11,
        0,
        tzinfo=IST,
    )

    result = session_guard(now)

    assert result.should_run is False
    assert (
        result.reason
        == "WEEKEND"
    )


def test_nse_holiday_skips():
    now = datetime(
        2026,
        10,
        20,
        10,
        15,
        tzinfo=IST,
    )

    result = session_guard(
        now
    )

    assert (
        result.should_run
        is False
    )

    assert (
        result.reason
        == "NSE_HOLIDAY"
    )
