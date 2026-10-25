from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .sessions import (
    is_trading_session,
)


IST = ZoneInfo(
    "Asia/Kolkata"
)

MARKET_OPEN = time(
    9,
    15,
)

MARKET_CLOSE = time(
    15,
    30,
)


@dataclass(frozen=True)
class SessionGuard:
    now_ist: str
    weekday: int
    is_weekday: bool
    is_trading_day: bool
    in_market_window: bool
    should_run: bool
    reason: str


def session_guard(
    now: datetime | None = None,
):
    if now is None:
        now = datetime.now(
            IST
        )

    elif now.tzinfo is None:
        now = now.replace(
            tzinfo=IST
        )

    else:
        now = now.astimezone(
            IST
        )

    is_weekday = (
        now.weekday() < 5
    )

    is_trading_day = (
        is_trading_session(
            now.date()
        )
    )

    current = (
        now.time()
        .replace(
            tzinfo=None
        )
    )

    in_market_window = (
        MARKET_OPEN
        <= current
        <= MARKET_CLOSE
    )

    should_run = (
        is_trading_day
        and in_market_window
    )

    if not is_weekday:
        reason = "WEEKEND"

    elif not is_trading_day:
        reason = "NSE_HOLIDAY"

    elif not in_market_window:
        reason = (
            "OUTSIDE_MARKET_WINDOW"
        )

    else:
        reason = "MARKET_WINDOW"

    return SessionGuard(
        now_ist=now.isoformat(),
        weekday=now.weekday(),
        is_weekday=is_weekday,
        is_trading_day=
            is_trading_day,
        in_market_window=
            in_market_window,
        should_run=should_run,
        reason=reason,
    )
