import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.universe import load_universe
from app.history_cache import (
    save_history,
)


def normalize_frame(
    data,
    ticker,
):
    if data is None or data.empty:
        return None

    frame = data.copy()

    if isinstance(
        frame.columns,
        pd.MultiIndex,
    ):
        try:
            frame = frame.xs(
                ticker,
                axis=1,
                level=1,
            )
        except Exception:
            try:
                frame = frame.xs(
                    ticker,
                    axis=1,
                    level=0,
                )
            except Exception:
                return None

    frame.columns = [
        str(c).lower()
        for c in frame.columns
    ]

    required = {
        "open",
        "high",
        "low",
        "close",
    }

    if not required.issubset(
        frame.columns
    ):
        return None

    return frame.dropna(
        subset=["close"]
    )


def refresh(symbols, period="2y", chunk=40, repair_only=False):
    from app.history_quality import inspect_symbol, history_quality, validated_frame, merge_recent_history
    from app.history_cache import CACHE_DIR, load_history
    from app.reliability import expected_closed_session
    import json
    expected = expected_closed_session()
    symbols = list(dict.fromkeys([*symbols, "^NSEI"]))
    failures = {}

    def pending():
        return [symbol for symbol in symbols if inspect_symbol(symbol, expected)["status"]
                in {"MISSING", "INVALID", "STALE"}]

    targets = pending() if repair_only else symbols
    # Retrying smaller batches avoids persisting a partial batch as a complete refresh.
    for attempt in range(3):
        if not targets:
            break
        width = chunk if attempt == 0 else min(10, chunk)
        for start in range(0, len(targets), width):
            batch = targets[start:start + width]
            tickers = [symbol if symbol == "^NSEI" else symbol + ".NS" for symbol in batch]
            print(f"History attempt {attempt + 1}: {start + 1}-{start + len(batch)} / {len(targets)}", flush=True)
            try:
                data = yf.download(tickers=tickers, period=period, interval="1d",
                                   auto_adjust=True, progress=False, threads=4,
                                   timeout=15, group_by="column")
            except Exception:
                for symbol in batch:
                    failures[symbol] = "Download failed"
                continue
            for symbol, ticker in zip(batch, tickers):
                frame = normalize_frame(data, ticker)
                if frame is None:
                    failures[symbol] = "Missing OHLC response"
                    continue
                frame = validated_frame(frame, expected)
                old = inspect_symbol(symbol, expected)
                # An incomplete response must not replace a newer or longer usable cache.
                if (frame.empty or len(frame) < min(300, old["rows"])
                        or (old["latestSession"] and not frame.empty
                            and str(frame.index[-1].date()) < old["latestSession"])):
                    failures[symbol] = "Incomplete response; previous cache retained"
                    continue
                save_history(symbol, frame)
                failures.pop(symbol, None)
            time.sleep(0.5)
        targets = pending()
    # A short-range Yahoo request can expose recent bars absent from its long
    # range response. Never splice differently adjusted price histories.
    stale = [symbol for symbol in targets if inspect_symbol(symbol, expected)["status"] == "STALE"]
    repaired = []
    for start in range(0, len(stale), 10):
        batch = stale[start:start + 10]
        tickers = [symbol if symbol == "^NSEI" else symbol + ".NS" for symbol in batch]
        try:
            data = yf.download(tickers=tickers, period="1mo", interval="1d", auto_adjust=True,
                               progress=False, threads=4, timeout=15, group_by="column")
        except Exception:
            continue
        for symbol, ticker in zip(batch, tickers):
            recent = validated_frame(normalize_frame(data, ticker), expected)
            previous = validated_frame(load_history(symbol), expected)
            combined = merge_recent_history(previous, recent, expected)
            if combined is not None:
                save_history(symbol, combined)
                repaired.append(symbol)
                failures.pop(symbol, None)
            else:
                failures[symbol] = "Recent range lacks the settled session or adjusted overlap does not match"
    report = history_quality(symbols, expected)
    report["recentRepair"] = {"attempted": len(stale), "recovered": len(repaired)}
    report["downloadFailures"] = failures
    (CACHE_DIR / "refresh_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if inspect_symbol("^NSEI", expected)["status"] != "READY":
        raise RuntimeError("Expected settled benchmark history unavailable after retries")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="5y")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--chunk", type=int, default=40)
    parser.add_argument("--repair-only", action="store_true")
    args = parser.parse_args()
    if args.chunk < 1:
        parser.error("--chunk must be positive")
    universe = load_universe()
    if args.limit:
        universe = universe[:args.limit]
    refresh([stock.symbol for stock in universe], args.period, args.chunk, args.repair_only)


if __name__ == "__main__":
    main()
