import sys
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from app.runtime import (
    runtime_status,
)


s = runtime_status()
r = s["runtime"]

print()
print(
    "========== ENGINE RUNTIME =========="
)

print(
    "Status:",
    r["status"],
)

print(
    "Cycles:",
    r["cycles"],
)

print(
    "Last success:",
    r["lastSuccessfulAt"],
)

print(
    "Last error:",
    r["lastError"],
)

print()

equity = s[
    "latestEquity"
]

if equity:
    print(
        "Equity:",
        equity["equity"],
    )

    print(
        "Cash:",
        equity["cash"],
    )

    print(
        "Market value:",
        equity["marketValue"],
    )

    print(
        "Total P&L:",
        equity["totalPnl"],
    )

    print(
        "Open positions:",
        equity["openPositions"],
    )

print()
print(
    "RECENT ACTIVITY"
)

for event in s[
    "activity"
][:10]:
    print(
        event["recordedAt"],
        "|",
        event["level"],
        "|",
        event["eventType"],
        "|",
        event["message"],
    )
