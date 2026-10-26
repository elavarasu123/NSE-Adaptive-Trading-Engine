from __future__ import annotations

import json
import os
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
from app.bootstrap import ensure_paper_database
from app.runtime import run_cycle
from app.scheduler_guard import session_guard


def truthy(value: str | None) -> bool:
    return str(
        value or ""
    ).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def main():
    guard = session_guard()

    force = truthy(
        os.getenv(
            "FORCE_RUNTIME"
        )
    )

    print(
        "========== V0.8 SCHEDULER =========="
    )

    print(
        json.dumps(
            {
                **guard.__dict__,
                "force": force,
            },
            indent=2,
        )
    )

    if (
        not guard.should_run
        and not force
    ):
        # A skipped request must not invalidate the last execution checkpoint.
        # Its guard decision is already preserved in the Actions log/receipt.
        print(
            "SKIPPED:",
            guard.reason,
        )

        return

    bootstrap = ensure_paper_database()

    print()
    print(
        "Database bootstrap:",
        json.dumps(
            bootstrap,
            indent=2,
        ),
    )

    db = SessionLocal()

    try:
        result = run_cycle(db)

        print()
        print(
            json.dumps(
                result,
                indent=2,
                default=str,
            )
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
