from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
import os
import uuid

from .database import (
    DATABASE_URL,
    SessionLocal,
)
from .models import (
    EquitySnapshot,
    ForwardEvent,
    IntegrityCheckpoint,
    RuntimeActivity,
    RuntimeState,
)


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def shared_state_enabled():
    """
    Shared DB state is enabled only when explicitly
    requested.

    This keeps local development and pytest isolated
    from the cloud paper account.
    """
    return (
        os.getenv(
            "SHARED_STATE_BACKEND",
            "file",
        ).lower()
        == "db"
    )


# ============================================================
# FORWARD LEDGER
# ============================================================

def append_forward_event(
    event,
):
    payload = dict(event)

    payload.setdefault(
        "recordedAt",
        utc_now(),
    )

    payload.setdefault(
        "ledgerEventId",
        str(uuid.uuid4()),
    )

    db = SessionLocal()

    try:
        row = ForwardEvent(
            event_id=
                payload[
                    "ledgerEventId"
                ],
            event_type=
                payload.get(
                    "eventType"
                ),
            prediction_id=
                payload.get(
                    "predictionId"
                ),
            horizon=
                payload.get(
                    "horizon"
                ),
            model_version=
                payload.get(
                    "modelVersion"
                ),
            prediction_date=
                payload.get(
                    "predictionDate"
                ),
            symbol=
                payload.get(
                    "symbol"
                ),
            payload=
                payload,
        )

        db.add(row)
        db.commit()

        return payload

    finally:
        db.close()


def read_forward_events():
    db = SessionLocal()

    try:
        rows = (
            db.query(
                ForwardEvent
            )
            .order_by(
                ForwardEvent.id.asc()
            )
            .all()
        )

        return [
            dict(row.payload)
            for row in rows
        ]

    finally:
        db.close()


# ============================================================
# RUNTIME STATE
# ============================================================

def default_runtime_state():
    return {
        "version":
            "v1.1",
        "source":
            os.getenv(
                "RUNTIME_SOURCE",
                "LOCAL",
            ),
        "status":
            "NEVER_RUN",
        "lastStartedAt":
            None,
        "lastCompletedAt":
            None,
        "lastSuccessfulAt":
            None,
        "lastRunId":
            None,
        "lastError":
            None,
        "cycles":
            0,
    }


def load_runtime_state():
    db = SessionLocal()

    try:
        row = db.get(
            RuntimeState,
            1,
        )

        if row is None:
            return (
                default_runtime_state()
            )

        return {
            "version":
                row.version,
            "source":
                row.source,
            "status":
                row.status,
            "lastStartedAt":
                row.last_started_at,
            "lastCompletedAt":
                row.last_completed_at,
            "lastSuccessfulAt":
                row.last_successful_at,
            "lastRunId":
                row.last_run_id,
            "lastError":
                row.last_error,
            "cycles":
                row.cycles or 0,
        }

    finally:
        db.close()


def save_runtime_state(
    state,
):
    db = SessionLocal()

    try:
        row = db.get(
            RuntimeState,
            1,
        )

        if row is None:
            row = RuntimeState(
                id=1
            )
            db.add(row)

        row.version = (
            state.get(
                "version",
                "v1.1",
            )
        )

        row.source = (
            state.get(
                "source",
                "LOCAL",
            )
        )

        row.status = (
            state.get(
                "status",
                "UNKNOWN",
            )
        )

        row.last_started_at = (
            state.get(
                "lastStartedAt"
            )
        )

        row.last_completed_at = (
            state.get(
                "lastCompletedAt"
            )
        )

        row.last_successful_at = (
            state.get(
                "lastSuccessfulAt"
            )
        )

        row.last_run_id = (
            state.get(
                "lastRunId"
            )
        )

        row.last_error = (
            state.get(
                "lastError"
            )
        )

        row.cycles = int(
            state.get(
                "cycles",
                0,
            )
        )

        db.commit()

    finally:
        db.close()


# ============================================================
# ACTIVITY
# ============================================================

def record_activity(
    payload,
):
    record = dict(payload)

    record.setdefault(
        "recordedAt",
        utc_now(),
    )

    record.setdefault(
        "eventId",
        str(uuid.uuid4()),
    )

    db = SessionLocal()

    try:
        db.add(
            RuntimeActivity(
                event_id=
                    record[
                        "eventId"
                    ],
                event_type=
                    record.get(
                        "eventType",
                        "UNKNOWN",
                    ),
                level=
                    record.get(
                        "level",
                        "INFO",
                    ),
                message=
                    record.get(
                        "message",
                        "",
                    ),
                data=
                    record.get(
                        "data",
                        {},
                    ),
                recorded_at=
                    record[
                        "recordedAt"
                    ],
            )
        )

        db.commit()

        return record

    finally:
        db.close()


def read_activity(
    limit=25,
):
    db = SessionLocal()

    try:
        rows = (
            db.query(
                RuntimeActivity
            )
            .order_by(
                RuntimeActivity
                .id.desc()
            )
            .limit(limit)
            .all()
        )

        rows.reverse()

        return [
            {
                "eventId":
                    row.event_id,
                "eventType":
                    row.event_type,
                "level":
                    row.level,
                "message":
                    row.message,
                "data":
                    row.data or {},
                "recordedAt":
                    row.recorded_at,
            }
            for row in rows
        ]

    finally:
        db.close()


# ============================================================
# EQUITY
# ============================================================

def record_equity(
    snapshot,
):
    db = SessionLocal()

    try:
        db.add(
            EquitySnapshot(
                timestamp=
                    snapshot[
                        "timestamp"
                    ],
                initial_capital=
                    snapshot[
                        "initialCapital"
                    ],
                cash=
                    snapshot[
                        "cash"
                    ],
                market_value=
                    snapshot[
                        "marketValue"
                    ],
                equity=
                    snapshot[
                        "equity"
                    ],
                realized_pnl=
                    snapshot[
                        "realizedPnl"
                    ],
                unrealized_pnl=
                    snapshot[
                        "unrealizedPnl"
                    ],
                total_pnl=
                    snapshot[
                        "totalPnl"
                    ],
                open_positions=
                    snapshot[
                        "openPositions"
                    ],
                positions_marked=
                    snapshot[
                        "positionsMarked"
                    ],
            )
        )

        db.commit()

    finally:
        db.close()


def read_equity(
    limit=100,
):
    db = SessionLocal()

    try:
        rows = (
            db.query(
                EquitySnapshot
            )
            .order_by(
                EquitySnapshot
                .id.desc()
            )
            .limit(limit)
            .all()
        )

        rows.reverse()

        return [
            {
                "timestamp":
                    row.timestamp,
                "initialCapital":
                    row.initial_capital,
                "cash":
                    row.cash,
                "marketValue":
                    row.market_value,
                "equity":
                    row.equity,
                "realizedPnl":
                    row.realized_pnl,
                "unrealizedPnl":
                    row.unrealized_pnl,
                "totalPnl":
                    row.total_pnl,
                "openPositions":
                    row.open_positions,
                "positionsMarked":
                    row.positions_marked,
            }
            for row in rows
        ]

    finally:
        db.close()


# ============================================================
# INTEGRITY CHECKPOINT
# ============================================================

def load_shared_checkpoint():
    db = SessionLocal()

    try:
        row = db.get(
            IntegrityCheckpoint,
            1,
        )

        return (
            dict(row.payload)
            if row
            else None
        )

    finally:
        db.close()


def save_shared_checkpoint(
    payload,
):
    db = SessionLocal()

    try:
        row = db.get(
            IntegrityCheckpoint,
            1,
        )

        if row is None:
            row = (
                IntegrityCheckpoint(
                    id=1,
                    payload=payload,
                )
            )

            db.add(row)

        else:
            row.payload = payload

        db.commit()

    finally:
        db.close()
