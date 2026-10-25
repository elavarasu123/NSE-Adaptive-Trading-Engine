import os
import sys
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = (
    ROOT
    / "test_evaluation.db"
)

os.environ["DATABASE_URL"] = (
    f"sqlite:///{TEST_DB}"
)

from app.database import (
    Base,
    engine,
    SessionLocal,
)
from app.models import (
    Prediction,
    PredictionOutcome,
)
from app.evaluation import (
    actual_class,
    accuracy_report,
    create_checkpoints,
    evaluate_due_predictions,
)


class Quote:
    def __init__(self, price):
        self.price = price


class Provider:
    def __init__(self, price):
        self.price = price

    def quote(self, symbol):
        return Quote(
            self.price
        )


def setup_function():
    Base.metadata.drop_all(
        bind=engine
    )

    Base.metadata.create_all(
        bind=engine
    )


def make_prediction(db):
    p = Prediction(
        symbol="TEST",
        entry_price=100,
        up=0.70,
        sideways=0.20,
        down=0.10,
        confidence=0.80,
        decision="BUY",
        raw_decision="BUY",
        regime="RISK_ON",
        strategy_version=
            "champion-v0.2",
        frozen=True,
        status="PENDING",
    )

    db.add(p)
    db.commit()
    db.refresh(p)

    return p


def test_actual_class():
    assert actual_class(
        0.05
    ) == "UP"

    assert actual_class(
        -0.05
    ) == "DOWN"

    assert actual_class(
        0.01
    ) == "SIDEWAYS"


def test_four_checkpoints_created():
    db = SessionLocal()

    p = make_prediction(db)

    create_checkpoints(
        db,
        p,
    )

    db.commit()

    rows = (
        db.query(PredictionOutcome)
        .all()
    )

    assert len(rows) == 4

    assert sorted(
        row.horizon_days
        for row in rows
    ) == [
        5,
        10,
        20,
        30,
    ]

    db.close()


def test_due_prediction_matures():
    db = SessionLocal()

    p = make_prediction(db)

    create_checkpoints(
        db,
        p,
    )

    db.commit()

    rows = (
        db.query(PredictionOutcome)
        .all()
    )

    for row in rows:
        row.due_at = (
            datetime.now(
                timezone.utc
            )
            - timedelta(days=1)
        )

    db.commit()

    result = evaluate_due_predictions(
        db,
        Provider(110),
    )

    assert len(
        result["evaluated"]
    ) == 4

    matured = (
        db.query(PredictionOutcome)
        .filter(
            PredictionOutcome.status
            == "MATURED"
        )
        .all()
    )

    assert len(matured) == 4

    assert all(
        row.actual_class == "UP"
        for row in matured
    )

    assert all(
        row.correct is True
        for row in matured
    )

    db.close()


def test_accuracy_separates_horizons():
    db = SessionLocal()

    p = make_prediction(db)

    for days in (
        5,
        10,
    ):
        db.add(
            PredictionOutcome(
                prediction_id=p.id,
                symbol="TEST",
                horizon_days=days,
                entry_price=100,
                outcome_price=110,
                forward_return=0.10,
                predicted_class="UP",
                actual_class="UP",
                correct=True,
                brier_score=0.046667,
                status="MATURED",
            )
        )

    db.commit()

    report = accuracy_report(
        db
    )

    assert (
        report["byHorizon"]["5D"][
            "matured"
        ]
        == 1
    )

    assert (
        report["byHorizon"]["10D"][
            "matured"
        ]
        == 1
    )

    assert (
        report["byHorizon"]["20D"][
            "matured"
        ]
        == 0
    )

    db.close()
