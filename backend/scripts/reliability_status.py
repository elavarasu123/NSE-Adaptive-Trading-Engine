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

from app.database import (
    SessionLocal,
)
from app.reliability import (
    reliability_report,
)


db = SessionLocal()

try:
    report = (
        reliability_report(
            db
        )
    )

    print()
    print(
        "========== V0.9 RELIABILITY =========="
    )

    print(
        "Status:",
        report["status"],
    )

    print(
        "Runtime source:",
        report[
            "runtimeSource"
        ],
    )

    print(
        "Allow runtime:",
        report[
            "allowRuntime"
        ],
    )

    print()
    print(
        "MARKET DATA"
    )

    print(
        json.dumps(
            report[
                "marketData"
            ],
            indent=2,
        )
    )

    print()
    print(
        "PORTFOLIO"
    )

    print(
        json.dumps(
            report[
                "portfolio"
            ],
            indent=2,
        )
    )

    print()
    print(
        "FORWARD LEDGER"
    )

    print(
        json.dumps(
            report[
                "ledger"
            ],
            indent=2,
        )
    )

    print()
    print(
        "CHECKPOINT"
    )

    print(
        json.dumps(
            report[
                "checkpoint"
            ],
            indent=2,
        )
    )

    if not report["allowRuntime"]:
        raise SystemExit(1)

finally:
    db.close()
