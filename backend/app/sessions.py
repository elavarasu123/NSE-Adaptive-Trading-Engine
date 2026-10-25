import csv
from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def holiday_file(year):
    return (
        DATA
        / f"nse_holidays_{year}.csv"
    )


def holidays(year):
    path = holiday_file(year)

    if not path.exists():
        return set()

    result = set()

    with path.open(
        newline="",
        encoding="utf-8",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            result.add(
                date.fromisoformat(
                    row["date"]
                )
            )

    return result


def is_trading_session(day):
    if day.weekday() >= 5:
        return False

    return day not in holidays(
        day.year
    )


def add_trading_sessions(
    start,
    sessions,
):
    if isinstance(start, datetime):
        current = start.date()
        tz = (
            start.tzinfo
            or timezone.utc
        )
    else:
        current = start
        tz = timezone.utc

    count = 0

    while count < sessions:
        current += timedelta(days=1)

        if is_trading_session(
            current
        ):
            count += 1

    # Stored as an evaluation boundary.
    return datetime.combine(
        current,
        time(15, 30),
        tzinfo=tz,
    )


def trading_sessions(
    start,
    end,
):
    current = start
    output = []

    while current <= end:
        if is_trading_session(
            current
        ):
            output.append(current)

        current += timedelta(days=1)

    return output
