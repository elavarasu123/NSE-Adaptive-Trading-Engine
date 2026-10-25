from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import (
    sessionmaker,
)


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from app.database import (
    Base,
    SessionLocal,
    engine,
)
from app.models import (
    EquitySnapshot,
    ForwardEvent,
    Journal,
    PaperOrder,
    PaperTrade,
    Portfolio,
    Position,
    RuntimeActivity,
    RuntimeState,
    StrategyVersion,
)
from app.shared_state import (
    append_forward_event,
    record_activity,
    record_equity,
    save_runtime_state,
    shared_state_enabled,
)


LEGACY_DB = (
    ROOT
    / "adaptive_engine.db"
)

FORWARD_LEDGER = (
    ROOT
    / "data"
    / "forward"
    / "prediction_ledger.jsonl"
)

RUNTIME_STATE = (
    ROOT
    / "data"
    / "runtime"
    / "runtime_state.json"
)

ACTIVITY = (
    ROOT
    / "data"
    / "runtime"
    / "activity.jsonl"
)

EQUITY = (
    ROOT
    / "data"
    / "runtime"
    / "equity.jsonl"
)


def copy_model(
    source,
    target,
    model,
):
    try:
        existing = (
            target.query(model)
            .count()
        )

        if existing:
            return 0

        rows = (
            source.query(model)
            .all()
        )

    except Exception:
        return 0

    copied = 0

    for row in rows:
        data = {}

        for column in (
            model.__table__.columns
        ):
            if column.name == "id":
                continue

            data[
                column.name
            ] = getattr(
                row,
                column.name,
            )

        target.add(
            model(**data)
        )

        copied += 1

    target.commit()

    return copied


def main():
    if not shared_state_enabled():
        raise SystemExit(
            "Shared DB backend is not enabled."
        )

    Base.metadata.create_all(
        bind=engine
    )

    destination = (
        SessionLocal()
    )

    copied = {}

    try:
        if LEGACY_DB.exists():
            legacy_engine = (
                create_engine(
                    "sqlite:///"
                    + str(LEGACY_DB),
                    connect_args={
                        "check_same_thread":
                            False
                    },
                )
            )

            LegacySession = (
                sessionmaker(
                    bind=
                        legacy_engine
                )
            )

            source = (
                LegacySession()
            )

            try:
                for model in [
                    Portfolio,
                    Position,
                    PaperTrade,
                    StrategyVersion,
                    Journal,
                    PaperOrder,
                ]:
                    copied[
                        model.__name__
                    ] = copy_model(
                        source,
                        destination,
                        model,
                    )

            finally:
                source.close()

        # ------------------------------------------
        # Forward immutable ledger
        # ------------------------------------------
        if (
            destination
            .query(
                ForwardEvent
            )
            .count()
            == 0
            and FORWARD_LEDGER.exists()
        ):
            count = 0

            for line in (
                FORWARD_LEDGER
                .read_text()
                .splitlines()
            ):
                line = (
                    line.strip()
                )

                if not line:
                    continue

                append_forward_event(
                    json.loads(
                        line
                    )
                )

                count += 1

            copied[
                "ForwardEvent"
            ] = count

        # ------------------------------------------
        # Runtime state
        # ------------------------------------------
        if (
            destination
            .query(
                RuntimeState
            )
            .count()
            == 0
            and RUNTIME_STATE.exists()
        ):
            save_runtime_state(
                json.loads(
                    RUNTIME_STATE
                    .read_text()
                )
            )

            copied[
                "RuntimeState"
            ] = 1

        # ------------------------------------------
        # Runtime activity
        # ------------------------------------------
        if (
            destination
            .query(
                RuntimeActivity
            )
            .count()
            == 0
            and ACTIVITY.exists()
        ):
            count = 0

            for line in (
                ACTIVITY
                .read_text()
                .splitlines()
            ):
                line = (
                    line.strip()
                )

                if not line:
                    continue

                record_activity(
                    json.loads(
                        line
                    )
                )

                count += 1

            copied[
                "RuntimeActivity"
            ] = count

        # ------------------------------------------
        # Equity history
        # ------------------------------------------
        if (
            destination
            .query(
                EquitySnapshot
            )
            .count()
            == 0
            and EQUITY.exists()
        ):
            count = 0

            for line in (
                EQUITY
                .read_text()
                .splitlines()
            ):
                line = (
                    line.strip()
                )

                if not line:
                    continue

                record_equity(
                    json.loads(
                        line
                    )
                )

                count += 1

            copied[
                "EquitySnapshot"
            ] = count

        destination.commit()

        print()
        print(
            "===== SHARED DB MIGRATION ====="
        )

        print(
            json.dumps(
                copied,
                indent=2,
            )
        )

        print(
            "Portfolio rows:",
            destination
            .query(Portfolio)
            .count(),
        )

        print(
            "Paper orders:",
            destination
            .query(PaperOrder)
            .count(),
        )

        print(
            "Forward events:",
            destination
            .query(ForwardEvent)
            .count(),
        )

        print(
            "Runtime activities:",
            destination
            .query(RuntimeActivity)
            .count(),
        )

        print(
            "Equity snapshots:",
            destination
            .query(EquitySnapshot)
            .count(),
        )

    finally:
        destination.close()


if __name__ == "__main__":
    main()
