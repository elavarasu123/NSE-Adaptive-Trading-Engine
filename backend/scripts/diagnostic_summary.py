import json
from pathlib import Path


p = Path(
    "data/backtests/"
    "diagnostics.json"
)

d = json.loads(
    p.read_text()
)


def show_group(
    period,
    group_name,
):
    groups = period[
        group_name
    ]

    print(
        "\n",
        group_name.upper(),
    )

    for name, horizons in groups.items():
        h = horizons[
            "30D"
        ]

        print(
            f"{name:25}",
            "N=", h["n"],
            "Mean=", h["mean"],
            "CI=",
            (
                h["ciLow"],
                h["ciHigh"],
            ),
            "Positive=",
            h[
                "significantPositive"
            ],
        )


for period_name, period in d.items():
    print()
    print(
        "=" * 70
    )
    print(
        period_name,
        "| observations:",
        period["observations"],
    )

    show_group(
        period,
        "scoreBuckets",
    )

    show_group(
        period,
        "regimes",
    )

    show_group(
        period,
        "sectors",
    )
