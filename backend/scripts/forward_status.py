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
    learning_status,
    latest_predictions,
)


status = learning_status()

print()
print(
    "========== FORWARD LEARNING =========="
)
print(
    "Model:",
    status["modelVersion"],
)
print(
    "Frozen:",
    status["modelFrozen"],
)
print(
    "Live trading:",
    status["liveTradingAllowed"],
)
print(
    "Predictions:",
    status["totalPredictions"],
)

print()

for horizon, metrics in (
    status["metrics"][
        "horizons"
    ].items()
):
    print(
        horizon,
        "| Matured:",
        metrics["matured"],
        "| Avg:",
        metrics["meanReturn"],
        "| Excess:",
        metrics["meanExcess"],
        "| Win:",
        metrics["winRate"],
        "| Excess Win:",
        metrics["excessWinRate"],
        "| IC:",
        metrics["ic"],
    )

print()
print(
    "LATEST PREDICTIONS"
)

for row in (
    latest_predictions()[:10]
):
    print(
        row["predictionDate"],
        row["symbol"],
        "| Score:",
        row["score"],
        "| Entry:",
        row["entryPrice"],
        "| Regime:",
        row["regime"],
        "| Matured:",
        ",".join(
            row["outcomes"].keys()
        ) or "none",
    )
