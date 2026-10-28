from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import math
import os
import traceback
import uuid

from sqlalchemy.orm import Session
from .transactions import exclusive_cycle

from .forward_learning import (
    LearningContext,
    latest_predictions,
    generate_predictions,
    learning_status,
    mature_outcomes,
)
from .market import YahooProvider
from .trading import monitor_positions

from .shared_state import (
    load_runtime_state,
    read_activity,
    read_equity,
    record_activity,
    record_equity,
    save_runtime_state,
    shared_state_enabled,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "data" / "runtime"

ACTIVITY_PATH = RUNTIME_DIR / "activity.jsonl"
EQUITY_PATH = RUNTIME_DIR / "equity.jsonl"
STATE_PATH = RUNTIME_DIR / "runtime_state.json"

RUNTIME_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def append_jsonl(
    path: Path,
    payload: dict[str, Any],
):
    record = {
        **payload,
        "recordedAt": utc_now(),
    }

    with path.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(
                record,
                separators=(",", ":"),
                default=str,
            )
            + "\n"
        )

    return record


def read_jsonl(
    path: Path,
    limit: int | None = None,
):
    if not path.exists():
        return []

    rows = []

    with path.open(
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(
                    json.loads(line)
                )
            except json.JSONDecodeError:
                continue

    if limit is not None:
        rows = rows[-limit:]

    return rows


def activity(
    event_type: str,
    message: str,
    *,
    level: str = "INFO",
    data: dict[str, Any] | None = None,
):
    payload = {
        "eventId":
            str(uuid.uuid4()),
        "eventType":
            event_type,
        "level":
            level,
        "message":
            message,
        "data":
            data or {},
    }

    if shared_state_enabled():
        return record_activity(
            payload
        )

    return append_jsonl(
        ACTIVITY_PATH,
        payload,
    )


def load_state():
    if shared_state_enabled():
        return (
            load_runtime_state()
        )

    if not STATE_PATH.exists():
        return {
            "version": "v1.1",
            "source": os.getenv(
                "RUNTIME_SOURCE",
                "LOCAL",
            ),
            "status": "NEVER_RUN",
            "lastStartedAt": None,
            "lastCompletedAt": None,
            "lastSuccessfulAt": None,
            "lastRunId": None,
            "lastError": None,
            "cycles": 0,
        }

    try:
        return json.loads(
            STATE_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return {
            "version": "v1.1",
            "source": os.getenv(
                "RUNTIME_SOURCE",
                "LOCAL",
            ),
            "status": "STATE_ERROR",
            "lastStartedAt": None,
            "lastCompletedAt": None,
            "lastSuccessfulAt": None,
            "lastRunId": None,
            "lastError":
                "Runtime state unreadable",
            "cycles": 0,
        }


def save_state(state):
    if shared_state_enabled():
        save_runtime_state(
            state
        )
        return

    tmp = STATE_PATH.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            state,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    tmp.replace(STATE_PATH)


def _number(
    value,
    default=0.0,
):
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def portfolio_snapshot(
    db: Session,
    provider=None,
):
    """
    Build one mark-to-market paper equity snapshot.

    This NEVER resets capital and NEVER creates
    a new portfolio.
    """
    from .models import (
        Portfolio,
        Position,
    )

    portfolio = (
        db.query(Portfolio)
        .first()
    )

    if portfolio is None:
        raise RuntimeError(
            "Paper portfolio not initialized."
        )

    provider = (
        provider or YahooProvider()
    )

    open_positions = (
        db.query(Position)
        .filter(
            Position.status == "OPEN"
        )
        .all()
    )

    market_value = 0.0
    unrealized = 0.0
    marked = 0

    for position in open_positions:
        current = _number(
            getattr(
                position,
                "current_price",
                None,
            ),
            default=_number(
                position.avg_price
            ),
        )

        try:
            quote = provider.quote(
                position.symbol
            )

            quote_price = _number(
                getattr(
                    quote,
                    "price",
                    None,
                ),
                default=0,
            )

            if not math.isfinite(quote_price) or quote_price <= 0:
                raise ValueError("Invalid position quote")
            if quote_price > 0:
                current = quote_price
                marked += 1

                if hasattr(
                    position,
                    "current_price",
                ):
                    position.current_price = (
                        current
                    )

        except Exception:
            pass

        quantity = int(
            position.quantity
        )

        average = _number(
            position.avg_price
        )

        market_value += (
            current * quantity
        )

        unrealized += (
            current - average
        ) * quantity

    cash = _number(
        portfolio.cash
    )

    realized = _number(
        getattr(
            portfolio,
            "realized_pnl",
            0.0,
        )
    )

    initial = _number(
        portfolio.initial_capital
    )

    equity = (
        cash + market_value
    )

    total_pnl = (
        equity - initial
    )

    snapshot = {
        "timestamp":
            utc_now(),
        "initialCapital":
            round(initial, 2),
        "cash":
            round(cash, 2),
        "marketValue":
            round(
                market_value,
                2,
            ),
        "equity":
            round(equity, 2),
        "realizedPnl":
            round(realized, 2),
        "unrealizedPnl":
            round(
                unrealized,
                2,
            ),
        "totalPnl":
            round(total_pnl, 2),
        "openPositions":
            len(open_positions),
        "positionsMarked":
            marked,
    }

    if shared_state_enabled():
        record_equity(
            snapshot
        )
    else:
        append_jsonl(
            EQUITY_PATH,
            snapshot,
        )

    db.commit()

    return snapshot


def read_runtime_activity(limit=25):
    """Chronological activity from the configured canonical backend."""
    if shared_state_enabled():
        return read_activity(limit=limit)
    return read_jsonl(ACTIVITY_PATH, limit=limit)


def read_runtime_equity(limit=100):
    """Chronological equity from the configured canonical backend."""
    if shared_state_enabled():
        return read_equity(limit=limit)
    return read_jsonl(EQUITY_PATH, limit=limit)


def execution_provenance():
    """Whitelist provenance; API tokens are never included in saved evidence."""
    cron = None
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if event_path:
        try:
            with open(event_path, encoding="utf-8") as handle:
                cron = json.load(handle).get("schedule")
        except (OSError, ValueError, AttributeError):
            pass
    result = {"event": os.getenv("GITHUB_EVENT_NAME", "LOCAL"),
              "githubRunId": os.getenv("GITHUB_RUN_ID"), "cron": cron,
              "commit": os.getenv("GITHUB_SHA"), "attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
              "scheduleEvidence": "UNVERIFIED"}
    if result["event"] == "schedule":
        from .scheduler_schedule import latest_slot
        slot = latest_slot(datetime.now(timezone.utc))
        result["nominalSlot"] = slot.isoformat() if slot else None
    token, repository = os.getenv("SCHEDULER_EVIDENCE_TOKEN"), os.getenv("GITHUB_REPOSITORY", "")
    if result["event"] != "schedule" or not token or not (result["githubRunId"] or "").isdigit():
        return result
    import re
    import urllib.request
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        return result
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/runs/{result['githubRunId']}",
        headers={"Authorization": "Bearer " + token, "User-Agent": "nse-run-provenance",
                 "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=5) as response:
            run = json.loads(response.read(512000))
        if (str(run.get("id")) == result["githubRunId"] and run.get("event") == "schedule"
                and run.get("head_sha") == result["commit"]
                and str(run.get("run_attempt")) == result["attempt"]):
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            if created.tzinfo is not None:
                result.update(scheduleEvidence="VERIFIED", originCreatedAt=created.isoformat())
    except Exception:
        # Telemetry failure must not stop paper execution or become proof.
        pass
    return result


def runtime_status():
    state = load_state()
    activities = read_runtime_activity(limit=25)
    equity = read_runtime_equity(limit=100)

    try:
        forward = learning_status()

    except Exception as exc:
        forward = {
            "error": str(exc)
        }

    from .operational_status import assess_operations
    return {
        "operational": assess_operations(state, activities),
        "runtime":
            state,
        "forwardLearning":
            forward,
        "latestEquity":
            (
                equity[-1]
                if equity
                else None
            ),
        "equityHistory":
            equity,
        "activity":
            list(
                reversed(
                    activities
                )
            ),
        "safety": {
            "paperOnly": True,
            "liveBrokerOrders":
                False,
            "capitalResetsDaily":
                False,
            "automaticModelPromotion":
                False,
            "automaticPaperPolicyUpdates": True,
        },
    }


@exclusive_cycle
def run_cycle(
    db: Session,
    *,
    refresh_cache: bool = False,
):
    """
    One complete V0.7 runtime cycle.

    Safe to invoke repeatedly:
    - prediction generation is idempotent
    - matured outcomes are append-only
    - portfolio capital is never reset
    - no broker orders are possible
    """
    from .schema_integrity import ensure_event_indexes
    ensure_event_indexes(db.get_bind())
    from .reliability import (
        reliability_report,
    )

    preflight = (
        reliability_report(
            db
        )
    )

    if not preflight[
        "allowRuntime"
    ]:
        raise RuntimeError(
            "Reliability preflight blocked "
            "runtime: "
            + ", ".join(
                preflight[
                    "blockers"
                ]
            )
        )

    run_id = str(
        uuid.uuid4()
    )

    started = utc_now()
    provenance = execution_provenance()

    state = load_state()

    state.update(
        {
            "version": "v1.1",
            "source": os.getenv(
                "RUNTIME_SOURCE",
                "LOCAL",
            ),
            "status": "RUNNING",
            "lastStartedAt":
                started,
            "lastRunId":
                run_id,
            "lastError":
                None,
        }
    )

    save_state(state)

    activity(
        "RUNTIME_START",
        "Paper runtime cycle started.",
        data={
            "runId": run_id,
            "provenance": provenance,
            "recovery": preflight.get("checkpoint", {}).get("status") == "RECOVERY_REQUIRED",
        },
    )

    result = {
        "runId": run_id,
        "startedAt": started,
        "refreshRequested":
            refresh_cache,
        "preflight":
            preflight,
        "steps": {},
    }

    try:
        provider = YahooProvider()

        # ----------------------------------------------------
        # STEP 1 — Mature existing forward predictions
        # ----------------------------------------------------
        context = LearningContext()
        from .market import CycleMarketProvider
        provider = CycleMarketProvider(provider, context)
        matured = mature_outcomes(context=context)

        result["steps"][
            "matureOutcomes"
        ] = matured

        activity(
            "OUTCOME_MATURITY",
            (
                "Forward outcomes checked: "
                f"{matured.get('outcomesCreated', 0)} "
                "new."
            ),
            data={
                "runId": run_id,
                "created":
                    matured.get(
                        "outcomesCreated",
                        0,
                    ),
            },
        )

        # ----------------------------------------------------
        # STEP 2 — Generate latest frozen-model observations
        # ----------------------------------------------------
        predictions = (
            generate_predictions(
                minimum_score=65,
                top_n=10,
                context=context,
            )
        )

        result["steps"][
            "predictions"
        ] = {
            "predictionDate":
                predictions.get(
                    "predictionDate"
                ),
            "created":
                predictions.get(
                    "created",
                    0,
                ),
            "duplicates":
                len(
                    predictions.get(
                        "skippedDuplicates",
                        [],
                    )
                ),
        }

        activity(
            "PREDICTION_BATCH",
            (
                "Forward prediction cycle completed: "
                f"{predictions.get('created', 0)} new."
            ),
            data={
                "runId": run_id,
                "predictionDate":
                    predictions.get(
                        "predictionDate"
                    ),
                "created":
                    predictions.get(
                        "created",
                        0,
                    ),
            },
        )

        from .adaptive_policy import learn_entry_policy
        from .market_analysis import build_market_analysis
        from .execution import BUY_SLIPPAGE_BPS, SELL_SLIPPAGE_BPS, FEE_BPS
        adaptive = learn_entry_policy(
            latest_predictions(), str(context.market_date.date()),
            round_trip_cost=(BUY_SLIPPAGE_BPS + SELL_SLIPPAGE_BPS + 2 * FEE_BPS) / 10000,
        )
        analysis = build_market_analysis(context, adaptive, provider)
        activity("MARKET_ANALYSIS", "Settled market analysis and validated adaptive entry policy updated.",
                 data={"runId": run_id, "analysis": analysis})
        result["steps"]["marketAnalysis"] = {
            "asOf": analysis["asOf"], "regime": analysis["regime"],
            "coverage": analysis["coverage"], "adaptivePolicy": adaptive,
        }

        # ----------------------------------------------------
        # STEP 3 — V1.0 automatic paper execution
        # ----------------------------------------------------
        from .execution import (
            run_execution_cycle,
        )

        execution = (
            run_execution_cycle(
                db,
                provider,
                adaptive_policy=adaptive,
            )
        )

        result["steps"][
            "paperExecution"
        ] = execution

        entry_data = execution[
            "entries"
        ]

        activity(
            "PAPER_EXECUTION",
            (
                "Automatic paper execution: "
                f"{len(entry_data['filled'])} filled, "
                f"{len(entry_data['rejected'])} rejected; "
                f"{sum(1 for x in execution['exits'] if x.get('action') == 'SELL')} exits."
                + (f" New entries paused: {entry_data['pausedReason']}." if entry_data.get('pausedReason') else "")
            ),
            data={
                "runId":
                    run_id,
                "adaptivePolicyRevision": adaptive["revision"],
                "pausedReason": entry_data.get("pausedReason"),
                "filled":
                    len(
                        entry_data[
                            "filled"
                        ]
                    ),
                "rejected":
                    len(
                        entry_data[
                            "rejected"
                        ]
                    ),
                "exits":
                    len(
                        [
                            x
                            for x in execution[
                                "exits"
                            ]
                            if (
                                x.get(
                                    "action"
                                )
                                == "SELL"
                            )
                        ]
                    ),
            },
        )

        # ----------------------------------------------------
        # STEP 4 — Mark portfolio and persist equity
        # ----------------------------------------------------
        snapshot = (
            portfolio_snapshot(
                db,
                provider,
            )
        )

        result["steps"][
            "equity"
        ] = snapshot

        activity(
            "EQUITY_SNAPSHOT",
            (
                "Paper equity snapshot recorded: "
                f"₹{snapshot['equity']:,.2f}"
            ),
            data={
                "runId":
                    run_id,
                "equity":
                    snapshot[
                        "equity"
                    ],
                "cash":
                    snapshot[
                        "cash"
                    ],
                "openPositions":
                    snapshot[
                        "openPositions"
                    ],
            },
        )

        degraded = bool(entry_data.get("pausedReason")) or snapshot["positionsMarked"] < snapshot["openPositions"]
        cycle_status = "DEGRADED" if degraded else "HEALTHY"
        completed = utc_now()

        state = load_state()

        state.update(
            {
                "version":
                    "v0.9",
                "source":
                    os.getenv(
                        "RUNTIME_SOURCE",
                        "LOCAL",
                    ),
                "status":
                    cycle_status,
                "lastCompletedAt":
                    completed,
                "lastSuccessfulAt":
                    state.get("lastSuccessfulAt") if degraded else completed,
                "lastRunId":
                    run_id,
                "lastError":
                    "Risk-data checks incomplete; new entries paused." if degraded else None,
                "cycles":
                    int(
                        state.get(
                            "cycles",
                            0,
                        )
                    )
                    + 1,
            }
        )

        save_state(state)

        result[
            "completedAt"
        ] = completed

        result[
            "status"
        ] = cycle_status

        activity(
            "RUNTIME_COMPLETE",
            "Paper runtime cycle completed with incomplete risk data." if degraded else "Paper runtime cycle completed.",
            data={
                "runId": run_id,
                "startedAt": started, "completedAt": completed,
                "status": cycle_status, "provenance": provenance,
            },
        )

        from .reliability import (
            write_checkpoint,
        )

        checkpoint = (
            write_checkpoint(
                db
            )
        )

        result[
            "checkpoint"
        ] = {
            "version":
                checkpoint[
                    "version"
                ],
            "runtimeSource":
                checkpoint[
                    "runtimeSource"
                ],
        }

        return result

    except Exception as exc:
        completed = utc_now()

        error_text = str(exc)

        state = load_state()

        state.update(
            {
                "version":
                    "v0.9",
                "source":
                    os.getenv(
                        "RUNTIME_SOURCE",
                        "LOCAL",
                    ),
                "status":
                    "ERROR",
                "lastCompletedAt":
                    completed,
                "lastRunId":
                    run_id,
                "lastError":
                    error_text,
            }
        )

        save_state(state)

        activity(
            "RUNTIME_ERROR",
            "Paper runtime cycle failed.",
            level="ERROR",
            data={
                "runId":
                    run_id,
                "error":
                    error_text,
                "trace":
                    traceback.format_exc()[
                        -4000:
                    ],
            },
        )

        raise
