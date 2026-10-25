import json
from datetime import (
    date,
    datetime,
)
from pathlib import Path

import app.reliability as rel


def test_expected_session_before_close():
    now = datetime(
        2026,
        10,
        26,
        10,
        0,
        tzinfo=rel.IST,
    )

    result = (
        rel.expected_closed_session(
            now
        )
    )

    assert result == date(
        2026,
        10,
        23,
    )


def test_expected_session_post_close():
    now = datetime(
        2026,
        10,
        26,
        16,
        5,
        tzinfo=rel.IST,
    )

    result = (
        rel.expected_closed_session(
            now
        )
    )

    assert result == date(
        2026,
        10,
        26,
    )


def test_duplicate_prediction_breaks_ledger(
    tmp_path,
    monkeypatch,
):
    path = (
        tmp_path
        / "prediction_ledger.jsonl"
    )

    prediction = {
        "eventType":
            "PREDICTION",
        "predictionId":
            "one",
        "modelVersion":
            "frozen",
        "predictionDate":
            "2026-10-23",
        "symbol":
            "TCS",
    }

    duplicate = {
        **prediction,
        "predictionId":
            "two",
    }

    path.write_text(
        json.dumps(
            prediction
        )
        + "\n"
        + json.dumps(
            duplicate
        )
        + "\n"
    )

    monkeypatch.setattr(
        rel,
        "LEDGER_PATH",
        path,
    )

    result = (
        rel.ledger_integrity()
    )

    assert (
        result["status"]
        == "BROKEN"
    )

    assert (
        result["blocking"]
        is True
    )


def test_empty_ledger_is_safe(
    tmp_path,
    monkeypatch,
):
    path = (
        tmp_path
        / "missing.jsonl"
    )

    monkeypatch.setattr(
        rel,
        "LEDGER_PATH",
        path,
    )

    result = (
        rel.ledger_integrity()
    )

    assert (
        result["status"]
        == "EMPTY"
    )

    assert (
        result["blocking"]
        is False
    )


def test_runtime_source_default(
    monkeypatch,
):
    monkeypatch.delenv(
        "RUNTIME_SOURCE",
        raising=False,
    )

    assert (
        rel.runtime_source()
        == "LOCAL"
    )
