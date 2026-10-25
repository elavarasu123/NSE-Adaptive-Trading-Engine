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
        levels = frame.columns

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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--period",
        default="5y",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--chunk",
        type=int,
        default=40,
    )

    args = parser.parse_args()

    universe = load_universe()

    if args.limit:
        universe = universe[
            :args.limit
        ]

    symbols = [
        stock.symbol
        for stock in universe
    ]

    # Benchmark is cached too.
    yahoo_symbols = [
        f"{symbol}.NS"
        for symbol in symbols
    ]

    yahoo_symbols.append(
        "^NSEI"
    )

    successful = 0
    failed = []

    for start in range(
        0,
        len(yahoo_symbols),
        args.chunk,
    ):
        chunk = yahoo_symbols[
            start:start + args.chunk
        ]

        print(
            f"Downloading "
            f"{start + 1}-"
            f"{min(start + len(chunk), len(yahoo_symbols))}"
            f" / {len(yahoo_symbols)}"
        )

        try:
            data = yf.download(
                tickers=chunk,
                period=args.period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=True,
                group_by="column",
            )
        except Exception as exc:
            failed.extend(
                [
                    {
                        "symbol": x,
                        "reason": str(exc),
                    }
                    for x in chunk
                ]
            )

            continue

        for ticker in chunk:
            frame = normalize_frame(
                data,
                ticker,
            )

            if (
                frame is None
                or len(frame) < 100
            ):
                failed.append(
                    {
                        "symbol": ticker,
                        "reason":
                            "Insufficient data",
                    }
                )

                continue

            internal = (
                "^NSEI"
                if ticker == "^NSEI"
                else ticker.replace(
                    ".NS",
                    "",
                )
            )

            save_history(
                internal,
                frame,
            )

            successful += 1

        time.sleep(0.5)

    print()
    print(
        "History cache complete"
    )
    print(
        "Successful:",
        successful,
    )
    print(
        "Failed:",
        len(failed),
    )

    if failed:
        print(
            "First failures:",
            failed[:10],
        )


if __name__ == "__main__":
    main()
