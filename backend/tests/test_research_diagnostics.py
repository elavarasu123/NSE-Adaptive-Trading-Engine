import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from app.research_diagnostics import (
    bootstrap_mean_ci,
    score_bucket,
)


def test_score_buckets():
    assert (
        score_bucket(90)
        == "85-100"
    )

    assert (
        score_bucket(80)
        == "75-84"
    )

    assert (
        score_bucket(70)
        == "65-74"
    )

    assert (
        score_bucket(55)
        == "50-64"
    )


def test_positive_bootstrap():
    values = [
        0.01,
        0.02,
        0.03,
        0.015,
    ] * 20

    result = (
        bootstrap_mean_ci(
            values,
            iterations=500,
        )
    )

    assert result["mean"] > 0
    assert (
        result[
            "significantPositive"
        ]
        is True
    )


def test_small_sample_not_promoted():
    result = (
        bootstrap_mean_ci(
            [0.10] * 5
        )
    )

    assert (
        result[
            "significantPositive"
        ]
        is False
    )
