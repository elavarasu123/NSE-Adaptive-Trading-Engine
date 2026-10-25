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

from app.research_diagnostics import (
    diagnostics,
)


OUTPUT = (
    ROOT
    / "data"
    / "backtests"
    / "diagnostics.json"
)


def main():
    periods = [
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

    result = {}

    for name, start, end in periods:
        print(
            "Running",
            name,
            "..."
        )

        result[name] = diagnostics(
            start,
            end,
        )

    OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
        )
    )

    print(
        "Saved:",
        OUTPUT,
    )


if __name__ == "__main__":
    main()
