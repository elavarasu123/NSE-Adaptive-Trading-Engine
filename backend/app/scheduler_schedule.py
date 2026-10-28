"""Nominal delivery times; GitHub scheduling is best-effort, not real-time."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .sessions import is_trading_session


IST = ZoneInfo("Asia/Kolkata")
ENGINE_CRONS = tuple(f"50 {hour} * * 1-5" for hour in range(3, 10)) + (
    "35 10 * * 1-5",
)
SCHEDULE_TIMES_IST = tuple(
    datetime(2000, 1, 1, int(cron.split()[1]), int(cron.split()[0]),
             tzinfo=timezone.utc).astimezone(IST).strftime("%H:%M")
    for cron in ENGINE_CRONS
)
DELIVERY_GRACE = timedelta(minutes=20)
RUN_TIMEOUT = timedelta(minutes=45)
RECOVERY_CRONS = ("57 3 * * 1-5", "7,27,47 4-10 * * 1-5")


def latest_slot(now):
    local = now.astimezone(IST)
    if not is_trading_session(local.date()):
        return None
    slots = []
    for clock in SCHEDULE_TIMES_IST:
        hour, minute = map(int, clock.split(":"))
        at = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if at <= local:
            slots.append(at)
    return slots[-1] if slots else None


def due_slots(now, activated_at, lookback_days=0):
    """Trading-day slots whose delivery grace has elapsed.

    Do not invent missed runs from before this schedule reached main.
    """
    slots = []
    today = now.astimezone(IST).date()
    for days_ago in range(lookback_days, -1, -1):
        day = today - timedelta(days=days_ago)
        if not is_trading_session(day):
            continue
        for cron, clock in zip(ENGINE_CRONS, SCHEDULE_TIMES_IST):
            hour, minute = map(int, clock.split(":"))
            expected = datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)
            if activated_at <= expected and expected + DELIVERY_GRACE <= now:
                slots.append({"cron": cron, "expected_at": expected})
    return slots
