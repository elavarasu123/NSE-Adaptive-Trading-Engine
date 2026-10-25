from .portfolio_backtest import (
    CHAMPION,
    CHALLENGER,
    simulate,
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


def compact(result):
    return {
        "strategy":
            result["strategy"],
        "start":
            result["start"],
        "end":
            result["end"],
        "configuration":
            result[
                "configuration"
            ],
        "metrics":
            result["metrics"],
        "benchmark":
            result["benchmark"],
    }


def run_comparison():
    periods = []

    for period in PERIODS:
        champion = simulate(
            period["start"],
            period["end"],
            CHAMPION,
        )

        challenger = simulate(
            period["start"],
            period["end"],
            CHALLENGER,
        )

        periods.append(
            {
                "period":
                    period["name"],
                "champion":
                    compact(
                        champion
                    ),
                "challenger":
                    compact(
                        challenger
                    ),
            }
        )

    return {
        "status":
            "RESEARCH_ONLY",
        "championFrozen":
            True,
        "promotionPolicy": (
            "No challenger promotion "
            "from development results. "
            "A challenger must show "
            "consistent validation and "
            "out-of-sample improvement "
            "without materially worse "
            "drawdown before it can be "
            "considered for future "
            "paper-trading promotion."
        ),
        "periods":
            periods,
    }
