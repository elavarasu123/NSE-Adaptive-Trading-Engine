import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.scanner import scan_market


class FakeProvider:
    def history(self, symbol, period="2y"):
        dates = pd.date_range(
            "2025-01-01",
            periods=300,
            freq="B",
        )

        if symbol == "^NSEI":
            start = 100
            end = 120
        elif symbol == "STRONG":
            start = 100
            end = 180
        elif symbol == "WEAK":
            start = 100
            end = 85
        else:
            raise ValueError("missing symbol")

        close = pd.Series(
            [
                start
                + (end - start) * i / 299
                for i in range(300)
            ]
        )

        return pd.DataFrame(
            {
                "Close": close.values,
                "Volume": [1_000_000] * 300,
            },
            index=dates,
        )


def test_scanner_ranks_strong_above_weak():
    report = scan_market(
        FakeProvider(),
        universe=["STRONG", "WEAK"],
    )

    assert report["successful"] == 2
    assert report["failed"] == 0

    symbols = [
        row["symbol"]
        for row in report["results"]
    ]

    assert symbols[0] == "STRONG"

    strong = report["results"][0]
    weak = report["results"][1]

    assert strong["score"] > weak["score"]
    assert strong["relativeStrength6m"] > 0
    assert weak["relativeStrength6m"] < 0


def test_bad_symbol_does_not_crash_scan():
    report = scan_market(
        FakeProvider(),
        universe=["STRONG", "MISSING"],
    )

    assert report["successful"] == 1
    assert report["failed"] == 1
    assert report["warnings"][0]["symbol"] == "MISSING"
