import json
from pathlib import Path


path = Path(
    "data/backtests/"
    "signal_validation.json"
)

data = json.loads(
    path.read_text()
)


print()
print(
    "========== STRICT SIGNAL VALIDATION =========="
)
print()


for name, report in (
    data["periods"].items()
):
    print(
        "###",
        name,
        "| observations:",
        report["observations"],
    )

    for horizon in (
        "5D",
        "10D",
        "20D",
        "30D",
    ):
        h = report[
            "horizons"
        ][horizon]

        ic = h[
            "informationCoefficient"
        ]

        mono = h[
            "monotonicity"
        ]

        top = h[
            "top85VsUniverse"
        ]

        print(
            horizon,
            "| IC:",
            ic["mean"],
            "CI:",
            (
                ic["ciLow"],
                ic["ciHigh"],
            ),
            "| IC+:",
            ic[
                "positiveIcRate"
            ],
        )

        print(
            "   MONO:",
            mono["mean"],
            "CI:",
            (
                mono["ciLow"],
                mono["ciHigh"],
            ),
            "| 85+ spread:",
            top["mean"],
            "CI:",
            (
                top["ciLow"],
                top["ciHigh"],
            ),
        )

    print()
    print(
        "30D BUCKETS"
    )

    buckets = report[
        "horizons"
    ]["30D"]["buckets"]

    for bucket in (
        "<50",
        "50-64",
        "65-74",
        "75-84",
        "85-100",
    ):
        b = buckets[bucket]

        print(
            f" {bucket:7}",
            "Mean:",
            b["mean"],
            "CI:",
            (
                b["ciLow"],
                b["ciHigh"],
            ),
            "Ndates:",
            b["nDates"],
        )

    print()


print(
    "========== PERSISTENCE GATE =========="
)

print(
    json.dumps(
        data["gate"],
        indent=2,
    )
)
