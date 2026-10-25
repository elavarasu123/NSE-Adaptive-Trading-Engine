from datetime import date, datetime, timedelta, timezone


def is_weekday_session(day: date):
    """
    V0.3 fallback session calendar.

    Weekends are excluded. Exchange holidays will be loaded
    from a maintained NSE holiday dataset in the next layer.
    """
    return day.weekday() < 5


def add_trading_sessions(
    start,
    sessions,
):
    if isinstance(start, datetime):
        current = start.date()
        tz = start.tzinfo or timezone.utc
    else:
        current = start
        tz = timezone.utc

    count = 0

    while count < sessions:
        current += timedelta(days=1)

        if is_weekday_session(current):
            count += 1

    return datetime(
        current.year,
        current.month,
        current.day,
        15,
        30,
        tzinfo=tz,
    )
