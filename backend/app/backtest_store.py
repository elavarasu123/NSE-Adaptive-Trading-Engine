import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DIR = (
    ROOT
    / "data"
    / "backtests"
)

DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LATEST = DIR / "latest.json"

WALK_FORWARD = (
    DIR
    / "walk_forward.json"
)


def save_report(
    report,
    path=LATEST,
):
    payload = {
        "generatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),
        **report,
    }

    path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
    )

    return payload


def load_report(
    path=LATEST,
):
    if not path.exists():
        return None

    return json.loads(
        path.read_text()
    )
