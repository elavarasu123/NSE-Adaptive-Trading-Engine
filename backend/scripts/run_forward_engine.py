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

from app.forward_learning import (
    generate_predictions,
    mature_outcomes,
    learning_status,
)


def main():
    print()
    print(
        "===== FORWARD PAPER ENGINE ====="
    )

    outcomes = mature_outcomes()

    print(
        "Matured outcomes:",
        outcomes[
            "outcomesCreated"
        ],
    )

    predictions = (
        generate_predictions(
            minimum_score=65,
            top_n=10,
        )
    )

    print(
        "Predictions created:",
        predictions["created"],
    )

    print(
        "Duplicate predictions skipped:",
        len(
            predictions[
                "skippedDuplicates"
            ]
        ),
    )

    print()
    print(
        json.dumps(
            learning_status(),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
