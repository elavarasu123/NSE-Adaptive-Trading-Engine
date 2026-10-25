from __future__ import annotations

from datetime import (
    datetime,
    time,
    timedelta,
)
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import os

from sqlalchemy.orm import Session

from .forward_learning import (
    LEDGER_PATH,
)
from .history_cache import (
    load_history,
)
from .models import (
    Portfolio,
    Position,
)
from .sessions import (
    is_trading_session,
    trading_sessions,
)


ROOT = Path(
    __file__
).resolve().parents[1]

RUNTIME_DIR = (
    ROOT
    / "data"
    / "runtime"
)

STATE_PATH = (
    RUNTIME_DIR
    / "runtime_state.json"
)

ACTIVITY_PATH = (
    RUNTIME_DIR
    / "activity.jsonl"
)

EQUITY_PATH = (
    RUNTIME_DIR
    / "equity.jsonl"
)

CHECKPOINT_PATH = (
    RUNTIME_DIR
    / "integrity_checkpoint.json"
)

IST = ZoneInfo(
    "Asia/Kolkata"
)

# We deliberately wait until after
# NSE's regular + closing sessions.
DATA_SETTLED_AFTER = time(
    16,
    5,
)


def runtime_source():
    return os.getenv(
        "RUNTIME_SOURCE",
        "LOCAL",
    )


def sha256_file(
    path: Path,
):
    if not path.exists():
        return None

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as f:
        for chunk in iter(
            lambda: f.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def fingerprints():
    return {
        "runtimeState":
            sha256_file(
                STATE_PATH
            ),
        "activity":
            sha256_file(
                ACTIVITY_PATH
            ),
        "equity":
            sha256_file(
                EQUITY_PATH
            ),
        "forwardLedger":
            sha256_file(
                LEDGER_PATH
            ),
    }


def previous_trading_session(
    day,
):
    current = (
        day
        - timedelta(days=1)
    )

    for _ in range(370):
        if is_trading_session(
            current
        ):
            return current

        current -= timedelta(
            days=1
        )

    raise RuntimeError(
        "Unable to locate previous "
        "NSE trading session."
    )


def expected_closed_session(
    now: datetime | None = None,
):
    if now is None:
        now = datetime.now(
            IST
        )

    elif now.tzinfo is None:
        now = now.replace(
            tzinfo=IST
        )

    else:
        now = now.astimezone(
            IST
        )

    day = now.date()

    local_time = (
        now.time()
        .replace(
            tzinfo=None
        )
    )

    if (
        is_trading_session(day)
        and local_time
        >= DATA_SETTLED_AFTER
    ):
        return day

    return previous_trading_session(
        day
    )


def market_data_status(
    now: datetime | None = None,
):
    expected = (
        expected_closed_session(
            now
        )
    )

    frame = load_history(
        "^NSEI"
    )

    if (
        frame is None
        or frame.empty
    ):
        return {
            "status": "MISSING",
            "blocking": True,
            "latestSession": None,
            "expectedSession":
                str(expected),
            "sessionsBehind": None,
        }

    latest = (
        frame.index.max()
        .date()
    )

    if latest >= expected:
        behind = 0
        status = "FRESH"

    else:
        start = (
            latest
            + timedelta(days=1)
        )

        behind = len(
            trading_sessions(
                start,
                expected,
            )
        )

        status = (
            "FRESH"
            if behind == 0
            else "STALE"
        )

    return {
        "status": status,
        "blocking":
            status != "FRESH",
        "latestSession":
            str(latest),
        "expectedSession":
            str(expected),
        "sessionsBehind":
            behind,
    }


def portfolio_integrity(
    db: Session,
):
    portfolios = (
        db.query(Portfolio)
        .all()
    )

    issues = []

    if len(portfolios) != 1:
        issues.append(
            "Expected exactly one "
            "paper portfolio."
        )

        return {
            "status": "BROKEN",
            "blocking": True,
            "issues": issues,
        }

    portfolio = portfolios[0]

    if (
        portfolio.initial_capital
        is None
        or float(
            portfolio.initial_capital
        ) <= 0
    ):
        issues.append(
            "Initial capital invalid."
        )

    if (
        portfolio.cash
        is None
        or float(
            portfolio.cash
        ) < -0.01
    ):
        issues.append(
            "Paper cash is negative."
        )

    positions = (
        db.query(Position)
        .filter(
            Position.status
            == "OPEN"
        )
        .all()
    )

    symbols = []

    for position in positions:
        symbols.append(
            position.symbol
        )

        if (
            position.quantity
            is None
            or int(
                position.quantity
            ) <= 0
        ):
            issues.append(
                f"{position.symbol}: "
                "invalid quantity."
            )

        if (
            position.avg_price
            is None
            or float(
                position.avg_price
            ) <= 0
        ):
            issues.append(
                f"{position.symbol}: "
                "invalid average price."
            )

    duplicates = sorted(
        {
            symbol
            for symbol in symbols
            if symbols.count(symbol) > 1
        }
    )

    if duplicates:
        issues.append(
            "Duplicate open positions: "
            + ", ".join(
                duplicates
            )
        )

    return {
        "status":
            (
                "OK"
                if not issues
                else "BROKEN"
            ),
        "blocking":
            bool(issues),
        "issues":
            issues,
        "initialCapital":
            float(
                portfolio
                .initial_capital
            ),
        "cash":
            float(
                portfolio.cash
            ),
        "openPositions":
            len(positions),
    }


def ledger_integrity():
    if not LEDGER_PATH.exists():
        return {
            "status": "EMPTY",
            "blocking": False,
            "events": 0,
            "predictions": 0,
            "outcomes": 0,
            "issues": [],
        }

    issues = []

    prediction_ids = set()
    prediction_keys = set()
    outcome_keys = set()

    outcomes = []
    events = 0

    with LEDGER_PATH.open(
        encoding="utf-8"
    ) as f:
        for number, raw in enumerate(
            f,
            start=1,
        ):
            line = raw.strip()

            if not line:
                continue

            events += 1

            try:
                event = json.loads(
                    line
                )
            except json.JSONDecodeError:
                issues.append(
                    f"Invalid JSON at "
                    f"ledger line {number}."
                )
                continue

            event_type = event.get(
                "eventType"
            )

            if event_type == "PREDICTION":
                prediction_id = (
                    event.get(
                        "predictionId"
                    )
                )

                key = (
                    event.get(
                        "modelVersion"
                    ),
                    event.get(
                        "predictionDate"
                    ),
                    event.get(
                        "symbol"
                    ),
                )

                if not prediction_id:
                    issues.append(
                        f"Prediction missing ID "
                        f"at line {number}."
                    )
                    continue

                if (
                    prediction_id
                    in prediction_ids
                ):
                    issues.append(
                        "Duplicate prediction ID: "
                        + prediction_id
                    )

                if (
                    key
                    in prediction_keys
                ):
                    issues.append(
                        "Duplicate frozen "
                        "prediction key: "
                        + repr(key)
                    )

                prediction_ids.add(
                    prediction_id
                )

                prediction_keys.add(
                    key
                )

            elif event_type == "OUTCOME":
                key = (
                    event.get(
                        "predictionId"
                    ),
                    event.get(
                        "horizon"
                    ),
                )

                if key in outcome_keys:
                    issues.append(
                        "Duplicate matured "
                        "outcome: "
                        + repr(key)
                    )

                outcome_keys.add(key)
                outcomes.append(key)

            else:
                issues.append(
                    f"Unknown ledger event "
                    f"at line {number}."
                )

    for prediction_id, horizon in outcomes:
        if (
            prediction_id
            not in prediction_ids
        ):
            issues.append(
                "Outcome references unknown "
                "prediction: "
                f"{prediction_id}/{horizon}"
            )

    return {
        "status":
            (
                "OK"
                if not issues
                else "BROKEN"
            ),
        "blocking":
            bool(issues),
        "events":
            events,
        "predictions":
            len(prediction_ids),
        "outcomes":
            len(outcome_keys),
        "issues":
            issues,
    }


def load_checkpoint():
    if not CHECKPOINT_PATH.exists():
        return None

    try:
        return json.loads(
            CHECKPOINT_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return {
            "invalid": True
        }


def _runtime_state_status():
    if not STATE_PATH.exists():
        return "NEVER_RUN"

    try:
        state = json.loads(
            STATE_PATH.read_text(
                encoding="utf-8"
            )
        )

        return state.get(
            "status",
            "UNKNOWN",
        )

    except Exception:
        return "STATE_ERROR"


def checkpoint_status():
    checkpoint = (
        load_checkpoint()
    )

    if checkpoint is None:
        return {
            "status":
                "NO_CHECKPOINT",
            "blocking":
                False,
            "differences":
                [],
        }

    if checkpoint.get(
        "invalid"
    ):
        return {
            "status":
                "INVALID_CHECKPOINT",
            "blocking":
                True,
            "differences":
                [],
        }

    expected = checkpoint.get(
        "fingerprints",
        {},
    )

    current = fingerprints()

    differences = [
        key
        for key in current
        if (
            current.get(key)
            != expected.get(key)
        )
    ]

    if not differences:
        return {
            "status": "MATCH",
            "blocking": False,
            "differences": [],
        }

    runtime_state = (
        _runtime_state_status()
    )

    # A failed/interrupted previous cycle
    # legitimately changes runtime files after
    # the previous good checkpoint. Permit a
    # recovery attempt if logical integrity is
    # still valid.
    if runtime_state in {
        "ERROR",
        "RUNNING",
    }:
        return {
            "status":
                "RECOVERY_REQUIRED",
            "blocking":
                False,
            "differences":
                differences,
        }

    return {
        "status":
            "MISMATCH",
        "blocking":
            True,
        "differences":
            differences,
    }


def reliability_report(
    db: Session,
    now: datetime | None = None,
):
    market = market_data_status(
        now
    )

    portfolio = (
        portfolio_integrity(
            db
        )
    )

    ledger = (
        ledger_integrity()
    )

    checkpoint = (
        checkpoint_status()
    )

    blockers = []

    if market["blocking"]:
        blockers.append(
            "MARKET_DATA"
        )

    if portfolio["blocking"]:
        blockers.append(
            "PORTFOLIO"
        )

    if ledger["blocking"]:
        blockers.append(
            "FORWARD_LEDGER"
        )

    if checkpoint["blocking"]:
        blockers.append(
            "CHECKPOINT"
        )

    allow = not blockers

    return {
        "status":
            (
                "HEALTHY"
                if allow
                else "BLOCKED"
            ),
        "allowRuntime":
            allow,
        "runtimeSource":
            runtime_source(),
        "marketData":
            market,
        "portfolio":
            portfolio,
        "ledger":
            ledger,
        "checkpoint":
            checkpoint,
        "blockers":
            blockers,
    }


def write_checkpoint(
    db: Session,
):
    payload = {
        "version": "v0.9",
        "createdAt":
            datetime.now(
                ZoneInfo("UTC")
            ).isoformat(),
        "runtimeSource":
            runtime_source(),
        "marketData":
            market_data_status(),
        "portfolio":
            portfolio_integrity(
                db
            ),
        "ledger":
            ledger_integrity(),
        "fingerprints":
            fingerprints(),
    }

    tmp = (
        CHECKPOINT_PATH
        .with_suffix(
            ".tmp"
        )
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    tmp.replace(
        CHECKPOINT_PATH
    )

    return payload
