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

from app.database import SessionLocal
from app.runtime import (
    run_cycle,
    runtime_status,
)


def main():
    db = SessionLocal()

    try:
        result = run_cycle(db)

        print()
        print(
            "========== V0.7 RUNTIME =========="
        )

        print(
            json.dumps(
                result,
                indent=2,
                default=str,
            )
        )

        print()
        print(
            "========== STATUS =========="
        )

        status = runtime_status()

        print(
            "Runtime:",
            status["runtime"][
                "status"
            ],
        )

        print(
            "Cycles:",
            status["runtime"][
                "cycles"
            ],
        )

        equity = status.get(
            "latestEquity"
        )

        if equity:
            print(
                "Equity:",
                equity["equity"],
            )

            print(
                "Cash:",
                equity["cash"],
            )

            print(
                "Positions:",
                equity[
                    "openPositions"
                ],
            )

        print(
            "Paper only:",
            status["safety"][
                "paperOnly"
            ],
        )

        print(
            "Live broker orders:",
            status["safety"][
                "liveBrokerOrders"
            ],
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
