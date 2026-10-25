from datetime import datetime, timedelta, timezone
from math import log
from typing import Iterable

from sqlalchemy.orm import Session

from .sessions import add_trading_sessions

from .models import (
    Prediction,
    PredictionOutcome,
    Journal,
)


HORIZONS = (5, 10, 20, 30)

# Research definition for directional classification.
# +/-2% avoids treating tiny moves as meaningful direction.
SIDEWAYS_BAND = 0.02


def utc_now():
    return datetime.now(timezone.utc)


def predicted_class(prediction):
    probabilities = {
        "UP": prediction.up or 0,
        "SIDEWAYS": prediction.sideways or 0,
        "DOWN": prediction.down or 0,
    }

    return max(
        probabilities,
        key=probabilities.get,
    )


def actual_class(forward_return):
    if forward_return > SIDEWAYS_BAND:
        return "UP"

    if forward_return < -SIDEWAYS_BAND:
        return "DOWN"

    return "SIDEWAYS"


def multiclass_brier(
    up,
    sideways,
    down,
    actual,
):
    probabilities = {
        "UP": float(up or 0),
        "SIDEWAYS": float(sideways or 0),
        "DOWN": float(down or 0),
    }

    total = sum(probabilities.values())

    if total <= 0:
        return None

    probabilities = {
        key: value / total
        for key, value in probabilities.items()
    }

    score = 0.0

    for label, probability in probabilities.items():
        observed = 1.0 if label == actual else 0.0
        score += (probability - observed) ** 2

    return round(score / 3.0, 6)


def create_checkpoints(
    db: Session,
    prediction: Prediction,
):
    existing = (
        db.query(PredictionOutcome)
        .filter(
            PredictionOutcome.prediction_id
            == prediction.id
        )
        .count()
    )

    if existing:
        return

    created = prediction.created_at

    # SQLite may return naive datetimes even though the model
    # is timezone-aware. Normalize safely.
    if created.tzinfo is None:
        created = created.replace(
            tzinfo=timezone.utc
        )

    pclass = predicted_class(
        prediction
    )

    for days in HORIZONS:
        db.add(
            PredictionOutcome(
                prediction_id=prediction.id,
                symbol=prediction.symbol,
                horizon_days=days,
                due_at=add_trading_sessions(
                    created,
                    days,
                ),
                entry_price=prediction.entry_price,
                predicted_class=pclass,
                status="PENDING",
            )
        )


def evaluate_due_predictions(
    db: Session,
    provider,
    now=None,
):
    now = now or utc_now()

    outcomes = (
        db.query(PredictionOutcome)
        .filter(
            PredictionOutcome.status
            == "PENDING"
        )
        .all()
    )

    evaluated = []
    skipped = []

    for outcome in outcomes:
        due = outcome.due_at

        if due.tzinfo is None:
            due = due.replace(
                tzinfo=timezone.utc
            )

        if now < due:
            continue

        prediction = (
            db.query(Prediction)
            .filter(
                Prediction.id
                == outcome.prediction_id
            )
            .first()
        )

        if not prediction:
            skipped.append(
                {
                    "id": outcome.id,
                    "reason": "Prediction missing",
                }
            )
            continue

        try:
            quote = provider.quote(
                outcome.symbol
            )
        except Exception as exc:
            skipped.append(
                {
                    "id": outcome.id,
                    "symbol": outcome.symbol,
                    "reason": str(exc),
                }
            )
            continue

        if (
            outcome.entry_price is None
            or outcome.entry_price <= 0
        ):
            skipped.append(
                {
                    "id": outcome.id,
                    "symbol": outcome.symbol,
                    "reason": "Entry price missing",
                }
            )
            continue

        forward_return = (
            quote.price
            / outcome.entry_price
            - 1
        )

        aclass = actual_class(
            forward_return
        )

        correct = (
            outcome.predicted_class
            == aclass
        )

        brier = multiclass_brier(
            prediction.up,
            prediction.sideways,
            prediction.down,
            aclass,
        )

        outcome.outcome_price = quote.price
        outcome.forward_return = round(
            forward_return,
            6,
        )
        outcome.actual_class = aclass
        outcome.correct = correct
        outcome.brier_score = brier
        outcome.evaluated_at = now
        outcome.status = "MATURED"

        evaluated.append(
            {
                "id": outcome.id,
                "predictionId":
                    prediction.id,
                "symbol": outcome.symbol,
                "horizonDays":
                    outcome.horizon_days,
                "predicted":
                    outcome.predicted_class,
                "actual": aclass,
                "correct": correct,
                "forwardReturn":
                    outcome.forward_return,
                "brierScore": brier,
            }
        )

    if evaluated:
        db.add(
            Journal(
                kind="EVALUATION",
                message=(
                    f"Matured "
                    f"{len(evaluated)} "
                    f"prediction checkpoints."
                ),
            )
        )

    db.commit()

    return {
        "evaluated": evaluated,
        "skipped": skipped,
        "pending": (
            db.query(PredictionOutcome)
            .filter(
                PredictionOutcome.status
                == "PENDING"
            )
            .count()
        ),
    }


def accuracy_report(
    db: Session,
):
    rows = (
        db.query(PredictionOutcome)
        .filter(
            PredictionOutcome.status
            == "MATURED"
        )
        .all()
    )

    report = {}

    for horizon in HORIZONS:
        subset = [
            row
            for row in rows
            if row.horizon_days == horizon
        ]

        if not subset:
            report[f"{horizon}D"] = {
                "matured": 0,
                "accuracy": None,
                "avgBrier": None,
                "avgForwardReturn": None,
                "evidence": "INSUFFICIENT",
            }
            continue

        correct = sum(
            1
            for row in subset
            if row.correct
        )

        briers = [
            row.brier_score
            for row in subset
            if row.brier_score is not None
        ]

        returns = [
            row.forward_return
            for row in subset
            if row.forward_return is not None
        ]

        report[f"{horizon}D"] = {
            "matured": len(subset),
            "accuracy": round(
                correct / len(subset),
                4,
            ),
            "avgBrier": (
                round(
                    sum(briers)
                    / len(briers),
                    6,
                )
                if briers
                else None
            ),
            "avgForwardReturn": (
                round(
                    sum(returns)
                    / len(returns),
                    6,
                )
                if returns
                else None
            ),
            "evidence": (
                "EARLY"
                if len(subset) < 30
                else "USABLE"
            ),
        }

    return {
        "sidewaysBand": SIDEWAYS_BAND,
        "officialHorizons": list(
            HORIZONS
        ),
        "byHorizon": report,
        "totalMatured": len(rows),
    }
