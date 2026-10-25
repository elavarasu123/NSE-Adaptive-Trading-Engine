from .backtest import (
    BacktestConfig,
    run_backtest,
)


PERIODS = [
    {
        "name": "DEVELOPMENT",
        "start": "2018-01-01",
        "end": "2021-12-31",
    },
    {
        "name": "VALIDATION",
        "start": "2022-01-01",
        "end": "2024-12-31",
    },
    {
        "name": "OUT_OF_SAMPLE",
        "start": "2025-01-01",
        "end": None,
    },
]


def run_walk_forward():
    output = {
        "status": "EXPLORATORY",
        "parameterPolicy": (
            "Parameters are fixed before "
            "validation/OOS evaluation. "
            "No automatic parameter "
            "optimization is performed."
        ),
        "periods": [],
    }

    config = BacktestConfig(
        rebalance_sessions=5,
        min_score=65,
        top_n=10,
        transaction_cost_per_side=
            0.0015,
    )

    for period in PERIODS:
        report = run_backtest(
            start=period["start"],
            end=period["end"],
            config=config,
        )

        output["periods"].append(
            {
                "name":
                    period["name"],
                "start":
                    period["start"],
                "end":
                    period["end"],
                "observations":
                    report[
                        "observations"
                    ],
                "horizons":
                    report[
                        "horizons"
                    ],
            }
        )

    return output
