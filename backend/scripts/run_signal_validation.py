import json
import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from app.signal_validation import (
    validate_period,
    persistence_gate,
)


OUTPUT = (
    ROOT
    / "data"
    / "backtests"
    / "signal_validation.json"
)


PERIODS = [
    (
        "DEVELOPMENT",
        "2018-01-01",
        "2021-12-31",
    ),
    (
        "VALIDATION",
        "2022-01-01",
        "2024-12-31",
    ),
    (
        "OUT_OF_SAMPLE",
        "2025-01-01",
        None,
    ),
]


def main():
    reports = {}

    for name, start, end in PERIODS:
        print()
        print(
            "Running strict validation:",
            name,
        )

        reports[name] = (
            validate_period(
                start,
                end,
            )
        )

    result = {
        "status":
            "RESEARCH_ONLY",
        "methodology": {
            "bootstrap":
                "Moving block bootstrap "
                "over date-level cross "
                "sections.",
            "ic":
                "Cross-sectional Spearman "
                "correlation of engine score "
                "with future stock excess "
                "return vs Nifty.",
            "topBucketTest":
                "Score >=85 compared with "
                "same-date eligible universe.",
            "promotion":
                "No automatic strategy "
                "promotion.",
        },
        "periods": reports,
        "gate":
            persistence_gate(
                reports,
                horizon="30D",
            ),
    }

    OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
        )
    )

    print()
    print(
        "Saved:",
        OUTPUT,
    )


if __name__ == "__main__":
    main()
