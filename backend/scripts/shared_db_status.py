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
    DATABASE_URL,
    SessionLocal,
    is_postgres,
)
from app.models import (
    EquitySnapshot,
    ForwardEvent,
    Journal,
    PaperOrder,
    Portfolio,
    Position,
    RuntimeActivity,
)
from app.shared_state import (
    shared_state_enabled,
)


def masked_backend():
    if is_postgres():
        return (
            "POSTGRESQL"
        )

    return "SQLITE"


db = SessionLocal()

try:
    print()
    print(
        "===== V1.1 SHARED DATABASE ====="
    )

    print(
        "Database:",
        masked_backend(),
    )

    print(
        "Shared state:",
        shared_state_enabled(),
    )

    print(
        "Portfolio rows:",
        db.query(
            Portfolio
        ).count(),
    )

    print(
        "Open positions:",
        db.query(
            Position
        )
        .filter(
            Position.status
            == "OPEN"
        )
        .count(),
    )

    print(
        "Paper orders:",
        db.query(
            PaperOrder
        ).count(),
    )

    print(
        "Forward events:",
        db.query(
            ForwardEvent
        ).count(),
    )

    print(
        "Activities:",
        db.query(
            RuntimeActivity
        ).count(),
    )

    print(
        "Equity snapshots:",
        db.query(
            EquitySnapshot
        ).count(),
    )

    print(
        "Journal rows:",
        db.query(
            Journal
        ).count(),
    )

finally:
    db.close()
