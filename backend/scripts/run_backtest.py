import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backtest import (
    BacktestConfig,
    run_backtest,
)
from app.backtest_store import (
    save_report,
)
from app.walkforward import (
    run_walk_forward,
)
from app.backtest_store import (
    WALK_FORWARD,
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start",
        default=None,
    )

    parser.add_argument(
        "--end",
        default=None,
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=65,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--walk-forward",
        action="store_true",
    )

    args = parser.parse_args()

    if args.walk_forward:
        result = (
            run_walk_forward()
        )

        save_report(
            result,
            WALK_FORWARD,
        )

    else:
        result = run_backtest(
            start=args.start,
            end=args.end,
            config=BacktestConfig(
                min_score=
                    args.min_score,
                top_n=args.top,
            ),
        )

        save_report(result)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
