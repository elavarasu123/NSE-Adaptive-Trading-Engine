import json
import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

import app.runtime as rt


def test_activity_is_append_only(
    tmp_path,
    monkeypatch,
):
    path = (
        tmp_path
        / "activity.jsonl"
    )

    monkeypatch.setattr(
        rt,
        "ACTIVITY_PATH",
        path,
    )

    rt.activity(
        "TEST_ONE",
        "first",
    )

    rt.activity(
        "TEST_TWO",
        "second",
    )

    rows = rt.read_jsonl(
        path
    )

    assert len(rows) == 2

    assert (
        rows[0][
            "eventType"
        ]
        == "TEST_ONE"
    )

    assert (
        rows[1][
            "eventType"
        ]
        == "TEST_TWO"
    )


def test_state_round_trip(
    tmp_path,
    monkeypatch,
):
    path = (
        tmp_path
        / "state.json"
    )

    monkeypatch.setattr(
        rt,
        "STATE_PATH",
        path,
    )

    rt.save_state(
        {
            "version":
                "v0.7",
            "status":
                "HEALTHY",
            "cycles":
                7,
        }
    )

    loaded = rt.load_state()

    assert (
        loaded["status"]
        == "HEALTHY"
    )

    assert (
        loaded["cycles"]
        == 7
    )


def test_runtime_safety_flags(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        rt,
        "STATE_PATH",
        tmp_path
        / "state.json",
    )

    monkeypatch.setattr(
        rt,
        "ACTIVITY_PATH",
        tmp_path
        / "activity.jsonl",
    )

    monkeypatch.setattr(
        rt,
        "EQUITY_PATH",
        tmp_path
        / "equity.jsonl",
    )

    monkeypatch.setattr(
        rt,
        "learning_status",
        lambda: {},
    )

    status = (
        rt.runtime_status()
    )

    assert (
        status["safety"][
            "paperOnly"
        ]
        is True
    )

    assert (
        status["safety"][
            "liveBrokerOrders"
        ]
        is False
    )

    assert (
        status["safety"][
            "capitalResetsDaily"
        ]
        is False
    )

    assert (
        status["safety"][
            "automaticModelPromotion"
        ]
        is False
    )


def test_jsonl_limit(
    tmp_path,
):
    path = (
        tmp_path
        / "events.jsonl"
    )

    for i in range(10):
        with path.open(
            "a"
        ) as f:
            f.write(
                json.dumps(
                    {"n": i}
                )
                + "\n"
            )

    rows = rt.read_jsonl(
        path,
        limit=3,
    )

    assert [
        x["n"]
        for x in rows
    ] == [7, 8, 9]
