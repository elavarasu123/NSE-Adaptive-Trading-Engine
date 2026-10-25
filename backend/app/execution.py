from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timezone,
)
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .forward_learning import (
    latest_predictions,
)
from .models import (
    Journal,
    PaperOrder,
    Position,
)
from .trading import (
    paper_buy,
    paper_sell,
)


MODEL_VERSION = (
    "champion-v0.2-frozen"
)

MAX_NEW_POSITIONS_PER_BATCH = int(
    os.getenv(
        "PAPER_BATCH_ENTRY_CAP",
        "2",
    )
)

BUY_SLIPPAGE_BPS = float(
    os.getenv(
        "PAPER_BUY_SLIPPAGE_BPS",
        "5",
    )
)

SELL_SLIPPAGE_BPS = float(
    os.getenv(
        "PAPER_SELL_SLIPPAGE_BPS",
        "5",
    )
)

FEE_BPS = float(
    os.getenv(
        "PAPER_FEE_BPS",
        "10",
    )
)


@dataclass(frozen=True)
class ExecutionPolicy:
    regime: str
    minimum_score: float
    exposure_multiplier: float
    entries_allowed: bool


def policy_for_regime(
    regime: str,
):
    regime = (
        regime
        or "PANIC"
    ).upper()

    if regime == "RISK_ON":
        return ExecutionPolicy(
            regime=regime,
            minimum_score=75.0,
            exposure_multiplier=1.0,
            entries_allowed=True,
        )

    if regime == "NEUTRAL":
        return ExecutionPolicy(
            regime=regime,
            minimum_score=80.0,
            exposure_multiplier=0.75,
            entries_allowed=True,
        )

    if regime == "DEFENSIVE":
        return ExecutionPolicy(
            regime=regime,
            minimum_score=88.0,
            exposure_multiplier=0.40,
            entries_allowed=True,
        )

    return ExecutionPolicy(
        regime="PANIC",
        minimum_score=101.0,
        exposure_multiplier=0.0,
        entries_allowed=False,
    )


def simulation_config():
    return {
        "buySlippageBps":
            BUY_SLIPPAGE_BPS,
        "sellSlippageBps":
            SELL_SLIPPAGE_BPS,
        "feeBpsPerSide":
            FEE_BPS,
        "batchEntryCap":
            MAX_NEW_POSITIONS_PER_BATCH,
        "note": (
            "Execution friction is a "
            "configurable paper assumption, "
            "not a broker fee quote."
        ),
    }


def _record_rejection(
    db: Session,
    prediction,
    reason: str,
):
    order = PaperOrder(
        prediction_id=
            prediction[
                "predictionId"
            ],
        prediction_date=
            prediction[
                "predictionDate"
            ],
        model_version=
            prediction[
                "modelVersion"
            ],
        symbol=
            prediction[
                "symbol"
            ],
        score=float(
            prediction["score"]
        ),
        regime=
            prediction.get(
                "regime",
                "UNKNOWN",
            ),
        status="REJECTED",
        quantity=0,
        signal_price=float(
            prediction[
                "entryPrice"
            ]
        ),
        reason=reason,
    )

    db.add(order)

    db.add(
        Journal(
            kind=
                "PAPER_ORDER_REJECTED",
            message=(
                f"{prediction['symbol']}: "
                f"{reason}; "
                f"score="
                f"{prediction['score']}; "
                f"regime="
                f"{prediction.get('regime')}"
            ),
        )
    )

    db.commit()

    return order


def _latest_batch():
    predictions = (
        latest_predictions()
    )

    if not predictions:
        return []

    latest_date = max(
        x["predictionDate"]
        for x in predictions
    )

    return sorted(
        [
            x
            for x in predictions
            if (
                x["predictionDate"]
                == latest_date
            )
        ],
        key=lambda x:
            float(x["score"]),
        reverse=True,
    )


def enter_latest_batch(
    db: Session,
    provider,
):
    predictions = (
        _latest_batch()
    )

    if not predictions:
        return {
            "predictionDate":
                None,
            "filled": [],
            "rejected": [],
            "existing": [],
        }

    batch_date = (
        predictions[0][
            "predictionDate"
        ]
    )

    already_filled = (
        db.query(PaperOrder)
        .filter(
            PaperOrder
            .prediction_date
            == batch_date,
            PaperOrder.status.in_(
                [
                    "FILLED",
                    "CLOSED",
                ]
            ),
        )
        .count()
    )

    remaining_slots = max(
        MAX_NEW_POSITIONS_PER_BATCH
        - already_filled,
        0,
    )

    filled = []
    rejected = []
    existing = []

    for prediction in predictions:
        prediction_id = (
            prediction[
                "predictionId"
            ]
        )

        prior = (
            db.query(PaperOrder)
            .filter(
                PaperOrder
                .prediction_id
                == prediction_id
            )
            .first()
        )

        if prior:
            existing.append(
                {
                    "symbol":
                        prediction[
                            "symbol"
                        ],
                    "status":
                        prior.status,
                    "reason":
                        prior.reason,
                }
            )

            continue

        if (
            prediction[
                "modelVersion"
            ]
            != MODEL_VERSION
        ):
            order = (
                _record_rejection(
                    db,
                    prediction,
                    "MODEL_NOT_CHAMPION",
                )
            )

            rejected.append(
                {
                    "symbol":
                        order.symbol,
                    "reason":
                        order.reason,
                }
            )

            continue

        policy = (
            policy_for_regime(
                prediction.get(
                    "regime"
                )
            )
        )

        if not policy.entries_allowed:
            order = (
                _record_rejection(
                    db,
                    prediction,
                    "PANIC_REGIME_BLOCK",
                )
            )

            rejected.append(
                {
                    "symbol":
                        order.symbol,
                    "reason":
                        order.reason,
                }
            )

            continue

        score = float(
            prediction["score"]
        )

        if (
            score
            < policy.minimum_score
        ):
            order = (
                _record_rejection(
                    db,
                    prediction,
                    (
                        "BELOW_REGIME_THRESHOLD:"
                        f"{policy.minimum_score}"
                    ),
                )
            )

            rejected.append(
                {
                    "symbol":
                        order.symbol,
                    "reason":
                        order.reason,
                }
            )

            continue

        if remaining_slots <= 0:
            order = (
                _record_rejection(
                    db,
                    prediction,
                    "BATCH_ENTRY_CAP",
                )
            )

            rejected.append(
                {
                    "symbol":
                        order.symbol,
                    "reason":
                        order.reason,
                }
            )

            continue

        symbol = (
            prediction[
                "symbol"
            ]
        )

        open_position = (
            db.query(Position)
            .filter(
                Position.symbol
                == symbol,
                Position.status
                == "OPEN",
            )
            .first()
        )

        if open_position:
            order = (
                _record_rejection(
                    db,
                    prediction,
                    "POSITION_ALREADY_OPEN",
                )
            )

            rejected.append(
                {
                    "symbol":
                        order.symbol,
                    "reason":
                        order.reason,
                }
            )

            continue

        try:
            position = paper_buy(
                db,
                provider,
                symbol,
                exposure_multiplier=
                    policy
                    .exposure_multiplier,
                slippage_bps=
                    BUY_SLIPPAGE_BPS,
                fee_bps=
                    FEE_BPS,
                reason=
                    "AUTO_FROZEN_PREDICTION",
            )

        except HTTPException as exc:
            order = (
                _record_rejection(
                    db,
                    prediction,
                    (
                        "RISK_GATE:"
                        f"{exc.detail}"
                    ),
                )
            )

            rejected.append(
                {
                    "symbol":
                        order.symbol,
                    "reason":
                        order.reason,
                }
            )

            continue

        gross = round(
            position.quantity
            * position.avg_price,
            2,
        )

        entry_fee = round(
            gross
            * FEE_BPS
            / 10000.0,
            2,
        )

        order = PaperOrder(
            prediction_id=
                prediction_id,
            prediction_date=
                prediction[
                    "predictionDate"
                ],
            model_version=
                prediction[
                    "modelVersion"
                ],
            symbol=symbol,
            score=score,
            regime=
                prediction.get(
                    "regime",
                    "UNKNOWN",
                ),
            status="FILLED",
            quantity=
                position.quantity,
            signal_price=float(
                prediction[
                    "entryPrice"
                ]
            ),
            fill_price=
                position.avg_price,
            stop_price=
                position.stop_price,
            target_price=
                position.target_price,
            entry_fee=
                entry_fee,
            reason=
                "AUTO_FROZEN_PREDICTION",
        )

        db.add(order)

        db.add(
            Journal(
                kind=
                    "AUTO_PAPER_ENTRY",
                message=(
                    f"{symbol}: "
                    f"prediction="
                    f"{prediction_id}; "
                    f"score={score}; "
                    f"regime="
                    f"{policy.regime}; "
                    f"qty="
                    f"{position.quantity}; "
                    f"fill="
                    f"₹{position.avg_price}; "
                    f"entry fee="
                    f"₹{entry_fee}"
                ),
            )
        )

        db.commit()
        db.refresh(order)

        remaining_slots -= 1

        filled.append(
            {
                "symbol":
                    symbol,
                "quantity":
                    order.quantity,
                "fill":
                    order.fill_price,
                "stop":
                    order.stop_price,
                "target":
                    order.target_price,
                "entryFee":
                    order.entry_fee,
            }
        )

    return {
        "predictionDate":
            batch_date,
        "filled":
            filled,
        "rejected":
            rejected,
        "existing":
            existing,
    }


def monitor_all_positions(
    db: Session,
    provider,
):
    positions = (
        db.query(Position)
        .filter(
            Position.status
            == "OPEN"
        )
        .all()
    )

    events = []

    for position in positions:
        try:
            quote = provider.quote(
                position.symbol
            )

            price = float(
                quote.price
            )

        except Exception as exc:
            events.append(
                {
                    "symbol":
                        position.symbol,
                    "action":
                        "DATA_ERROR",
                    "message":
                        str(exc),
                }
            )

            continue

        position.current_price = (
            price
        )

        reason = None

        if (
            price
            <= position.stop_price
        ):
            reason = "STOP_LOSS"

        elif (
            price
            >= position.target_price
        ):
            reason = "TARGET"

        if not reason:
            events.append(
                {
                    "symbol":
                        position.symbol,
                    "action":
                        "HOLD",
                    "price":
                        price,
                }
            )

            continue

        order = (
            db.query(PaperOrder)
            .filter(
                PaperOrder.symbol
                == position.symbol,
                PaperOrder.status
                == "FILLED",
            )
            .order_by(
                PaperOrder.id.desc()
            )
            .first()
        )

        automatic = (
            order is not None
        )

        result = paper_sell(
            db,
            provider,
            position.symbol,
            reason=reason,
            slippage_bps=(
                SELL_SLIPPAGE_BPS
                if automatic
                else 0
            ),
            fee_bps=(
                FEE_BPS
                if automatic
                else 0
            ),
            entry_fee=(
                order.entry_fee
                if automatic
                else 0
            ),
            price_override=price,
        )

        if order:
            order.status = "CLOSED"
            order.exit_price = (
                result["exit"]
            )
            order.exit_fee = (
                result["exitFee"]
            )
            order.realized_pnl = (
                result[
                    "realizedPnl"
                ]
            )
            order.reason = reason
            order.closed_at = (
                datetime.now(
                    timezone.utc
                )
            )

            db.add(order)

        db.add(
            Journal(
                kind=
                    "AUTO_PAPER_EXIT"
                    if automatic
                    else "PAPER_EXIT",
                message=(
                    f"{position.symbol}: "
                    f"{reason}; "
                    f"net PnL="
                    f"₹{result['realizedPnl']}"
                ),
            )
        )

        db.commit()

        events.append(
            {
                "symbol":
                    position.symbol,
                "action":
                    "SELL",
                "automatic":
                    automatic,
                "reason":
                    reason,
                "result":
                    result,
            }
        )

    db.commit()

    return events


def run_execution_cycle(
    db: Session,
    provider,
):
    exits = (
        monitor_all_positions(
            db,
            provider,
        )
    )

    entries = (
        enter_latest_batch(
            db,
            provider,
        )
    )

    return {
        "simulation":
            simulation_config(),
        "exits":
            exits,
        "entries":
            entries,
    }


def execution_status(
    db: Session,
):
    orders = (
        db.query(PaperOrder)
        .order_by(
            PaperOrder.id.desc()
        )
        .limit(100)
        .all()
    )

    return {
        "paperOnly":
            True,
        "brokerConnected":
            False,
        "modelVersion":
            MODEL_VERSION,
        "simulation":
            simulation_config(),
        "orders": [
            {
                "id":
                    order.id,
                "predictionId":
                    order
                    .prediction_id,
                "predictionDate":
                    order
                    .prediction_date,
                "symbol":
                    order.symbol,
                "score":
                    order.score,
                "regime":
                    order.regime,
                "status":
                    order.status,
                "quantity":
                    order.quantity,
                "signalPrice":
                    order
                    .signal_price,
                "fillPrice":
                    order.fill_price,
                "stop":
                    order.stop_price,
                "target":
                    order.target_price,
                "entryFee":
                    order.entry_fee,
                "exitPrice":
                    order.exit_price,
                "exitFee":
                    order.exit_fee,
                "realizedPnl":
                    order
                    .realized_pnl,
                "reason":
                    order.reason,
            }
            for order in orders
        ],
    }
