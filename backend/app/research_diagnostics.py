from collections import defaultdict

import numpy as np

from .backtest import (
    HORIZONS,
    enrich,
    feature_score,
    regime_at,
)
from .history_cache import load_history
from .universe import load_universe


def bootstrap_mean_ci(
    values,
    iterations=2000,
    seed=42,
):
    values = np.asarray(
        values,
        dtype=float,
    )

    values = values[
        ~np.isnan(values)
    ]

    if len(values) < 20:
        return {
            "n": len(values),
            "mean": (
                round(
                    float(
                        values.mean()
                    ),
                    6,
                )
                if len(values)
                else None
            ),
            "ciLow": None,
            "ciHigh": None,
            "significantPositive":
                False,
        }

    rng = np.random.default_rng(
        seed
    )

    means = np.empty(
        iterations
    )

    for i in range(iterations):
        sample = rng.choice(
            values,
            size=len(values),
            replace=True,
        )

        means[i] = sample.mean()

    low, high = np.percentile(
        means,
        [2.5, 97.5],
    )

    return {
        "n": len(values),
        "mean": round(
            float(values.mean()),
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
        "significantPositive":
            bool(low > 0),
    }


def score_bucket(score):
    if score >= 85:
        return "85-100"

    if score >= 75:
        return "75-84"

    if score >= 65:
        return "65-74"

    if score >= 50:
        return "50-64"

    return "<50"


def build_observations(
    start,
    end=None,
):
    benchmark = load_history(
        "^NSEI"
    )

    if benchmark is None:
        raise RuntimeError(
            "Nifty history missing"
        )

    benchmark = enrich(
        benchmark
    )

    universe = load_universe()

    frames = {}

    for stock in universe:
        df = load_history(
            stock.symbol
        )

        if (
            df is not None
            and len(df) >= 300
        ):
            frames[
                stock.symbol
            ] = enrich(df)

    dates = benchmark.index[
        benchmark.index
        >= start
    ]

    if end:
        dates = dates[
            dates <= end
        ]

    observations = []

    # Weekly observation avoids creating
    # huge numbers of nearly identical
    # consecutive daily samples.
    dates = dates[::5]

    for date in dates:
        b = benchmark.loc[
            date
        ]

        required = [
            "sma200",
            "mom6m",
            "rsi14",
            "vol20",
        ]

        if any(
            np.isnan(
                b.get(x, np.nan)
            )
            for x in required
        ):
            continue

        regime = regime_at(b)

        for stock in universe:
            df = frames.get(
                stock.symbol
            )

            if (
                df is None
                or date not in df.index
            ):
                continue

            row = df.loc[date]

            score = feature_score(
                row,
                b,
            )

            if score is None:
                continue

            observation = {
                "date":
                    str(date.date()),
                "symbol":
                    stock.symbol,
                "sector":
                    stock.sector,
                "score":
                    score,
                "scoreBucket":
                    score_bucket(
                        score
                    ),
                "regime":
                    regime,
            }

            for horizon in HORIZONS:
                stock_return = row.get(
                    f"forward_{horizon}"
                )

                nifty_return = b.get(
                    f"forward_{horizon}"
                )

                if (
                    np.isnan(
                        stock_return
                    )
                    or np.isnan(
                        nifty_return
                    )
                ):
                    observation[
                        f"excess{horizon}D"
                    ] = None
                else:
                    observation[
                        f"excess{horizon}D"
                    ] = round(
                        float(
                            stock_return
                            - nifty_return
                        ),
                        6,
                    )

            observations.append(
                observation
            )

    return observations


def summarize_group(
    observations,
    key,
):
    groups = defaultdict(
        list
    )

    for row in observations:
        groups[
            row[key]
        ].append(row)

    result = {}

    for name, rows in groups.items():
        result[name] = {}

        for horizon in HORIZONS:
            values = [
                row[
                    f"excess{horizon}D"
                ]
                for row in rows
                if row[
                    f"excess{horizon}D"
                ] is not None
            ]

            result[name][
                f"{horizon}D"
            ] = bootstrap_mean_ci(
                values
            )

    return result


def diagnostics(
    start,
    end=None,
):
    rows = build_observations(
        start,
        end,
    )

    return {
        "start": start,
        "end": end,
        "observations":
            len(rows),
        "scoreBuckets":
            summarize_group(
                rows,
                "scoreBucket",
            ),
        "regimes":
            summarize_group(
                rows,
                "regime",
            ),
        "sectors":
            summarize_group(
                rows,
                "sector",
            ),
        "methodology": {
            "target":
                "Stock forward return "
                "minus Nifty forward return",
            "sampling":
                "Every 5 trading sessions",
            "confidenceInterval":
                "95% bootstrap mean CI",
            "promotionRule":
                "Diagnostics generate "
                "hypotheses only. No "
                "automatic champion "
                "parameter changes.",
        },
    }
