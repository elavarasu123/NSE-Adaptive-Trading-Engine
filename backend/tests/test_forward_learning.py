import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

import app.forward_learning as fl


def test_model_is_frozen():
    assert (
        fl.MODEL_VERSION
        == "champion-v0.2-frozen"
    )


def test_horizons_are_not_1d():
    assert (
        fl.HORIZONS
        == (5, 10, 20, 30)
    )


def test_append_only_ledger(
    tmp_path,
    monkeypatch,
):
    path = (
        tmp_path
        / "ledger.jsonl"
    )

    monkeypatch.setattr(
        fl,
        "LEDGER_PATH",
        path,
    )

    fl.append_event(
        {
            "eventType":
                "PREDICTION",
            "predictionId":
                "abc",
        }
    )

    fl.append_event(
        {
            "eventType":
                "OUTCOME",
            "predictionId":
                "abc",
            "horizon":
                5,
        }
    )

    lines = (
        path.read_text()
        .strip()
        .splitlines()
    )

    assert len(lines) == 2

    assert (
        json.loads(
            lines[0]
        )["eventType"]
        == "PREDICTION"
    )

    assert (
        json.loads(
            lines[1]
        )["eventType"]
        == "OUTCOME"
    )


def test_maturity_uses_future_sessions():
    index = (
        pd.bdate_range(
            "2026-01-01",
            periods=20,
        )
    )

    frame = pd.DataFrame(
        {
            "close":
                range(
                    100,
                    120,
                )
        },
        index=index,
    )

    maturity = fl._maturity_date(
        frame,
        index[0],
        5,
    )

    assert maturity == index[5]


def test_learning_status_blocks_live():
    original = (
        fl.latest_predictions
    )

    try:
        fl.latest_predictions = (
            lambda: []
        )

        status = (
            fl.learning_status()
        )

        assert (
            status[
                "modelFrozen"
            ]
            is True
        )

        assert (
            status[
                "liveTradingAllowed"
            ]
            is False
        )

    finally:
        fl.latest_predictions = (
            original
        )
