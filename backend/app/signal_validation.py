from collections import defaultdict

import numpy as np
import pandas as pd

from .research_diagnostics import build_observations


HORIZONS = (5, 10, 20, 30)

BUCKET_ORDER = (
    "<50",
    "50-64",
    "65-74",
    "75-84",
    "85-100",
)


def _valid_rows(rows, horizon):
    key = f"excess{horizon}D"

    return [
        row
        for row in rows
        if row.get(key) is not None
        and row.get("score") is not None
    ]


def daily_cross_section(rows, horizon):
    """
    Collapse stock observations into independent-ish
    date-level cross sections.

    Returns:
      date -> list[observation]
    """
    key = f"excess{horizon}D"

    grouped = defaultdict(list)

    for row in rows:
        value = row.get(key)

        if value is None:
            continue

        grouped[row["date"]].append(row)

    return dict(grouped)


def spearman_ic(rows, horizon):
    """
    Cross-sectional Spearman correlation between
    engine score and future excess return.

    One IC value per observation date.
    """
    grouped = daily_cross_section(
        rows,
        horizon,
    )

    values = []

    for date, sample in grouped.items():
        if len(sample) < 20:
            continue

        score = pd.Series(
            [
                float(x["score"])
                for x in sample
            ],
            dtype=float,
        )

        future = pd.Series(
            [
                float(
                    x[
                        f"excess{horizon}D"
                    ]
                )
                for x in sample
            ],
            dtype=float,
        )

        # Spearman = Pearson correlation
        # of the ranked observations.
        # Implemented directly so the engine
        # does not require SciPy.
        score_rank = score.rank(
            method="average"
        )

        future_rank = future.rank(
            method="average"
        )

        ic = score_rank.corr(
            future_rank,
            method="pearson",
        )

        if pd.notna(ic):
            values.append(
                {
                    "date": date,
                    "ic": float(ic),
                }
            )

    return values


def block_bootstrap_mean(
    dated_values,
    block_size=6,
    iterations=2000,
    seed=42,
):
    """
    Moving-block bootstrap over DATE-LEVEL values.

    For 30D research sampled every ~5 sessions,
    block_size=6 roughly respects one 30-session
    overlapping horizon.

    This is intentionally more conservative than
    resampling individual stocks.
    """
    if not dated_values:
        return {
            "nDates": 0,
            "mean": None,
            "ciLow": None,
            "ciHigh": None,
            "positive": False,
        }

    ordered = sorted(
        dated_values,
        key=lambda x: x["date"],
    )

    values = np.asarray(
        [
            float(x["value"])
            for x in ordered
        ],
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    n = len(values)

    if n < max(
        12,
        block_size * 2,
    ):
        return {
            "nDates": n,
            "mean": (
                round(
                    float(
                        np.mean(values)
                    ),
                    6,
                )
                if n
                else None
            ),
            "ciLow": None,
            "ciHigh": None,
            "positive": False,
        }

    rng = np.random.default_rng(
        seed
    )

    block_size = min(
        block_size,
        n,
    )

    starts = np.arange(
        0,
        n - block_size + 1,
    )

    boot = np.empty(
        iterations,
        dtype=float,
    )

    blocks_needed = int(
        np.ceil(
            n / block_size
        )
    )

    for i in range(iterations):
        sampled = []

        chosen = rng.choice(
            starts,
            size=blocks_needed,
            replace=True,
        )

        for start in chosen:
            sampled.extend(
                values[
                    start:
                    start + block_size
                ]
            )

        sampled = np.asarray(
            sampled[:n],
            dtype=float,
        )

        boot[i] = float(
            np.mean(sampled)
        )

    low, high = np.percentile(
        boot,
        [2.5, 97.5],
    )

    return {
        "nDates": n,
        "mean": round(
            float(
                np.mean(values)
            ),
            6,
        ),
        "ciLow": round(
            float(low),
            6,
        ),
        "ciHigh": round(
            float(high),
            6,
        ),
        "positive": bool(
            low > 0
        ),
    }


def ic_summary(
    rows,
    horizon,
):
    values = spearman_ic(
        rows,
        horizon,
    )

    dated = [
        {
            "date": x["date"],
            "value": x["ic"],
        }
        for x in values
    ]

    result = block_bootstrap_mean(
        dated,
        block_size=max(
            1,
            int(
                np.ceil(
                    horizon / 5
                )
            ),
        ),
    )

    raw = [
        x["ic"]
        for x in values
    ]

    result.update(
        {
            "positiveIcRate": (
                round(
                    sum(
                        x > 0
                        for x in raw
                    )
                    / len(raw),
                    4,
                )
                if raw
                else None
            ),
            "medianIc": (
                round(
                    float(
                        np.median(raw)
                    ),
                    6,
                )
                if raw
                else None
            ),
        }
    )

    return result


def bucket_date_returns(
    rows,
    horizon,
):
    """
    For every date, calculate mean future excess
    return for each score bucket.

    We bootstrap these DATE means rather than
    thousands of individual stocks.
    """
    grouped = daily_cross_section(
        rows,
        horizon,
    )

    output = {
        bucket: []
        for bucket in BUCKET_ORDER
    }

    for date, sample in grouped.items():
        bucket_values = defaultdict(
            list
        )

        for row in sample:
            bucket = row[
                "scoreBucket"
            ]

            bucket_values[
                bucket
            ].append(
                float(
                    row[
                        f"excess{horizon}D"
                    ]
                )
            )

        for bucket in BUCKET_ORDER:
            values = bucket_values.get(
                bucket
            )

            if not values:
                continue

            output[
                bucket
            ].append(
                {
                    "date": date,
                    "value": float(
                        np.mean(values)
                    ),
                }
            )

    return output


def bucket_summary(
    rows,
    horizon,
):
    data = bucket_date_returns(
        rows,
        horizon,
    )

    block_size = max(
        1,
        int(
            np.ceil(
                horizon / 5
            )
        ),
    )

    return {
        bucket:
            block_bootstrap_mean(
                values,
                block_size=
                    block_size,
            )
        for bucket, values
        in data.items()
    }


def monotonicity(
    rows,
    horizon,
):
    """
    Measures whether higher score buckets generally
    produce higher same-date future excess returns.

    Perfect monotonic ranking = 1.0.
    Reverse monotonic ranking = -1.0.
    """
    grouped = daily_cross_section(
        rows,
        horizon,
    )

    date_scores = []

    numeric_bucket = {
        "<50": 1,
        "50-64": 2,
        "65-74": 3,
        "75-84": 4,
        "85-100": 5,
    }

    for date, sample in grouped.items():
        values = defaultdict(list)

        for row in sample:
            values[
                row["scoreBucket"]
            ].append(
                float(
                    row[
                        f"excess{horizon}D"
                    ]
                )
            )

        xs = []
        ys = []

        for bucket in BUCKET_ORDER:
            bucket_returns = (
                values.get(bucket)
            )

            if not bucket_returns:
                continue

            xs.append(
                numeric_bucket[
                    bucket
                ]
            )

            ys.append(
                float(
                    np.mean(
                        bucket_returns
                    )
                )
            )

        if len(xs) < 3:
            continue

        x_series = pd.Series(
            xs,
            dtype=float,
        )

        y_series = pd.Series(
            ys,
            dtype=float,
        )

        correlation = (
            x_series.rank(
                method="average"
            )
            .corr(
                y_series.rank(
                    method="average"
                ),
                method="pearson",
            )
        )

        if pd.notna(correlation):
            date_scores.append(
                {
                    "date": date,
                    "value":
                        float(
                            correlation
                        ),
                }
            )

    result = block_bootstrap_mean(
        date_scores,
        block_size=max(
            1,
            int(
                np.ceil(
                    horizon / 5
                )
            ),
        ),
    )

    raw = [
        x["value"]
        for x in date_scores
    ]

    result["positiveRate"] = (
        round(
            sum(
                x > 0
                for x in raw
            )
            / len(raw),
            4,
        )
        if raw
        else None
    )

    return result


def same_date_top_vs_universe(
    rows,
    horizon,
    threshold=85,
):
    """
    On each date compare >= threshold stocks against
    the average eligible universe on that SAME date.

    This removes much of the broad market/time-period
    effect from the comparison.
    """
    grouped = daily_cross_section(
        rows,
        horizon,
    )

    values = []

    key = f"excess{horizon}D"

    for date, sample in grouped.items():
        universe = [
            float(x[key])
            for x in sample
        ]

        selected = [
            float(x[key])
            for x in sample
            if float(
                x["score"]
            ) >= threshold
        ]

        if (
            len(universe) < 20
            or len(selected) < 3
        ):
            continue

        spread = (
            float(
                np.mean(selected)
            )
            - float(
                np.mean(universe)
            )
        )

        values.append(
            {
                "date": date,
                "value": spread,
            }
        )

    return block_bootstrap_mean(
        values,
        block_size=max(
            1,
            int(
                np.ceil(
                    horizon / 5
                )
            ),
        ),
    )


def factor_attribution(
    rows,
    horizon=30,
):
    """
    Attribution of persistent categorical effects.

    This does NOT claim causality. It measures
    same-date relative performance associated with
    regime and sector.
    """
    grouped = daily_cross_section(
        rows,
        horizon,
    )

    regimes = defaultdict(list)
    sectors = defaultdict(list)

    key = f"excess{horizon}D"

    for date, sample in grouped.items():
        all_values = [
            float(x[key])
            for x in sample
        ]

        if len(all_values) < 20:
            continue

        universe_mean = float(
            np.mean(all_values)
        )

        by_sector = defaultdict(
            list
        )

        by_regime = defaultdict(
            list
        )

        for row in sample:
            value = float(
                row[key]
            )

            by_sector[
                row["sector"]
            ].append(value)

            by_regime[
                row["regime"]
            ].append(value)

        for sector, values in (
            by_sector.items()
        ):
            if len(values) < 3:
                continue

            sectors[
                sector
            ].append(
                {
                    "date": date,
                    "value":
                        float(
                            np.mean(values)
                            - universe_mean
                        ),
                }
            )

        for regime, values in (
            by_regime.items()
        ):
            regimes[
                regime
            ].append(
                {
                    "date": date,
                    "value":
                        float(
                            np.mean(values)
                            - universe_mean
                        ),
                }
            )

    block = max(
        1,
        int(
            np.ceil(
                horizon / 5
            )
        ),
    )

    return {
        "sectors": {
            key:
                block_bootstrap_mean(
                    value,
                    block_size=block,
                )
            for key, value
            in sectors.items()
        },
        "regimes": {
            key:
                block_bootstrap_mean(
                    value,
                    block_size=block,
                )
            for key, value
            in regimes.items()
        },
    }


def validate_period(
    start,
    end=None,
):
    rows = build_observations(
        start,
        end,
    )

    result = {
        "start": start,
        "end": end,
        "observations":
            len(rows),
        "horizons": {},
    }

    for horizon in HORIZONS:
        result["horizons"][
            f"{horizon}D"
        ] = {
            "informationCoefficient":
                ic_summary(
                    rows,
                    horizon,
                ),
            "monotonicity":
                monotonicity(
                    rows,
                    horizon,
                ),
            "buckets":
                bucket_summary(
                    rows,
                    horizon,
                ),
            "top85VsUniverse":
                same_date_top_vs_universe(
                    rows,
                    horizon,
                    threshold=85,
                ),
        }

    result[
        "factorAttribution30D"
    ] = factor_attribution(
        rows,
        horizon=30,
    )

    return result


def persistence_gate(
    reports,
    horizon="30D",
):
    """
    Research gate only.

    It does NOT promote anything automatically.
    """
    checks = {}

    for period, report in (
        reports.items()
    ):
        h = report[
            "horizons"
        ][horizon]

        ic = h[
            "informationCoefficient"
        ]

        top = h[
            "top85VsUniverse"
        ]

        mono = h[
            "monotonicity"
        ]

        checks[period] = {
            "icPositive":
                bool(
                    ic.get(
                        "ciLow"
                    ) is not None
                    and ic[
                        "ciLow"
                    ] > 0
                ),
            "top85Positive":
                bool(
                    top.get(
                        "ciLow"
                    ) is not None
                    and top[
                        "ciLow"
                    ] > 0
                ),
            "monotonicPositive":
                bool(
                    mono.get(
                        "ciLow"
                    ) is not None
                    and mono[
                        "ciLow"
                    ] > 0
                ),
        }

    validation = checks.get(
        "VALIDATION",
        {}
    )

    oos = checks.get(
        "OUT_OF_SAMPLE",
        {}
    )

    candidate = all(
        [
            validation.get(
                "icPositive",
                False,
            ),
            validation.get(
                "top85Positive",
                False,
            ),
            oos.get(
                "icPositive",
                False,
            ),
            oos.get(
                "top85Positive",
                False,
            ),
        ]
    )

    return {
        "checks": checks,
        "candidateForChallengerResearch":
            candidate,
        "automaticPromotion":
            False,
        "note": (
            "Passing this gate only permits "
            "construction of a new research "
            "challenger. Portfolio simulation "
            "and forward paper evidence are "
            "still required."
        ),
    }
