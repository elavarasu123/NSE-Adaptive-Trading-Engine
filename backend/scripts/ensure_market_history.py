"""Recover a missing settled-session cache before the read-only preflight."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.history_cache import load_history
from app.reliability import expected_closed_session
from app.history_quality import history_quality


def has_expected_session():
    frame = load_history("^NSEI")
    expected = expected_closed_session()
    # A partial current-day bar cannot substitute for yesterday's settled bar.
    return frame is not None and any(
        stamp.date() == expected and math.isfinite(value) and value > 0
        for stamp, value in frame["close"].dropna().items()
    )


def ensure_history(force=False):
    try:
        fresh = has_expected_session()
    except (ValueError, KeyError, OSError):
        fresh = False
    repair = history_quality()["status"] == "PARTIAL"
    if fresh and not force and not repair:
        print("Settled market cache is current; no download required.")
        return False
    print("Refreshing missing/stale market history before reliability preflight.", flush=True)
    # One bounded attempt. Failure never bypasses the preflight or touches capital.
    command = [sys.executable, str(ROOT / "scripts/cache_history.py"),
               "--period", "2y", "--chunk", "50"]
    if fresh and not force:
        command.append("--repair-only")
    subprocess.run(
        command,
        check=True, timeout=1200,
    )
    if not has_expected_session():
        raise RuntimeError("Refresh did not supply the expected settled benchmark session")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    refreshed = ensure_history(args.force)
    print(json.dumps({"refreshed": refreshed, "expectedSession": str(expected_closed_session())}))
    if output := os.getenv("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"refreshed={str(refreshed).lower()}\n")


if __name__ == "__main__":
    main()
