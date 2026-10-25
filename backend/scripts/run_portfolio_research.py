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

from app.champion_challenger import (
    run_comparison,
)
from app.backtest_store import (
    save_report,
)


OUTPUT = (
    ROOT
    / "data"
    / "backtests"
    / "portfolio_research.json"
)


def main():
    print(
        "Running champion vs "
        "challenger portfolio research..."
    )

    result = run_comparison()

    save_report(
        result,
        OUTPUT,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
