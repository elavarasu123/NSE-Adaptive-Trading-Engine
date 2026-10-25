import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from app.signal_validation import (
    block_bootstrap_mean,
    daily_cross_section,
    persistence_gate,
)


def test_daily_cross_section():
    rows = [
        {
            "date": "2026-01-01",
            "score": 80,
            "excess30D": 0.02,
        },
        {
            "date": "2026-01-01",
            "score": 70,
            "excess30D": 0.01,
        },
        {
            "date": "2026-01-08",
            "score": 90,
            "excess30D": 0.03,
        },
    ]

    result = daily_cross_section(
        rows,
        30,
    )

    assert len(result) == 2
    assert (
        len(
            result[
                "2026-01-01"
            ]
        )
        == 2
    )


def test_block_bootstrap_positive():
    rows = [
        {
            "date":
                f"2026-01-{i:02d}",
            "value": 0.01,
        }
        for i in range(
            1,
            25,
        )
    ]

    result = (
        block_bootstrap_mean(
            rows,
            block_size=3,
            iterations=500,
        )
    )

    assert result["mean"] > 0
    assert result["ciLow"] > 0
    assert result["positive"] is True


def test_small_block_sample_not_promoted():
    rows = [
        {
            "date":
                f"2026-01-{i:02d}",
            "value": 0.10,
        }
        for i in range(
            1,
            5,
        )
    ]

    result = (
        block_bootstrap_mean(
            rows
        )
    )

    assert (
        result["positive"]
        is False
    )


def test_gate_never_auto_promotes():
    template = {
        "horizons": {
            "30D": {
                "informationCoefficient": {
                    "ciLow": 0.01,
                },
                "top85VsUniverse": {
                    "ciLow": 0.01,
                },
                "monotonicity": {
                    "ciLow": 0.01,
                },
            }
        }
    }

    result = persistence_gate(
        {
            "DEVELOPMENT":
                template,
            "VALIDATION":
                template,
            "OUT_OF_SAMPLE":
                template,
        }
    )

    assert (
        result[
            "candidateForChallengerResearch"
        ]
        is True
    )

    assert (
        result[
            "automaticPromotion"
        ]
        is False
    )
