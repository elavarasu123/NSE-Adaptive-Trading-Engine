import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cache import TTLCache
from app.sessions import add_trading_sessions
from app.sector import (
    sector_strength,
    apply_sector_strength,
)
from app.universe import (
    normalize_symbol,
    load_universe,
)


def test_symbol_normalization():
    assert normalize_symbol(
        "tcs.ns"
    ) == "TCS"

    assert normalize_symbol(
        " reliance "
    ) == "RELIANCE"


def test_universe_has_fallback():
    rows = load_universe(
        ROOT
        / "data"
        / "does-not-exist.csv"
    )

    assert len(rows) >= 15


def test_trading_sessions_skip_weekend():
    friday = datetime(
        2026,
        10,
        23,
        10,
        0,
        tzinfo=timezone.utc,
    )

    result = add_trading_sessions(
        friday,
        1,
    )

    assert result.date().isoformat() == (
        "2026-10-26"
    )


def test_five_sessions():
    monday = datetime(
        2026,
        10,
        26,
        tzinfo=timezone.utc,
    )

    result = add_trading_sessions(
        monday,
        5,
    )

    assert result.date().isoformat() == (
        "2026-11-02"
    )


def test_cache_round_trip():
    cache = TTLCache()

    cache.set(
        "x",
        {"ok": True},
        60,
    )

    assert cache.get("x") == {
        "ok": True
    }


def test_sector_strength():
    rows = [
        {
            "symbol": "AAA",
            "score": 80,
        },
        {
            "symbol": "BBB",
            "score": 60,
        },
        {
            "symbol": "CCC",
            "score": 90,
        },
    ]

    sectors = {
        "AAA": "IT",
        "BBB": "IT",
        "CCC": "BANK",
    }

    result = sector_strength(
        rows,
        sectors,
    )

    assert result["IT"] == 70
    assert result["BANK"] == 90


def test_sector_metadata_added():
    rows = [
        {
            "symbol": "AAA",
            "score": 80,
        }
    ]

    output, strengths = (
        apply_sector_strength(
            rows,
            {"AAA": "IT"},
        )
    )

    assert output[0]["sector"] == "IT"
    assert (
        output[0]["sectorStrength"]
        == 80
    )
