"""Settled-session coverage; short histories are distinct from stale feeds."""
from collections import Counter
import math
import pandas as pd
from .history_cache import load_history
from .reliability import expected_closed_session
from .universe import load_universe


def inspect_symbol(symbol, expected):
    result = {"symbol": symbol, "status": "MISSING", "rows": 0, "latestSession": None}
    try:
        frame = load_history(symbol)
        if frame is None or frame.empty:
            return result
        index = pd.to_datetime(frame.index)
        if index.tz is not None:
            index = index.tz_convert("Asia/Kolkata").tz_localize(None)
        frame = frame.copy()
        frame.index = index.normalize()
        frame = frame.loc[~frame.index.duplicated(keep="last")].sort_index()
        values = pd.to_numeric(frame["close"], errors="coerce")
        frame = frame.loc[(frame.index <= pd.Timestamp(expected)) & values.map(lambda v: math.isfinite(v) and v > 0)]
        if frame.empty:
            return result
        result.update(rows=len(frame), latestSession=str(frame.index[-1].date()))
        result["status"] = ("INSUFFICIENT" if len(frame) < 300 else
                            "READY" if frame.index[-1].date() == expected else "STALE")
    except (ValueError, TypeError, KeyError, OSError):
        result["status"] = "INVALID"
    return result


def history_quality(symbols=None, expected=None):
    expected = expected or expected_closed_session()
    symbols = symbols if symbols is not None else [s.symbol for s in load_universe()]
    rows = [inspect_symbol(symbol, expected) for symbol in symbols]
    counts = dict(Counter(row["status"] for row in rows))
    return {"expectedSession": str(expected), "status": "COMPLETE" if all(
        row["status"] in {"READY", "INSUFFICIENT"} for row in rows) else "PARTIAL",
        "counts": counts, "symbols": rows}
