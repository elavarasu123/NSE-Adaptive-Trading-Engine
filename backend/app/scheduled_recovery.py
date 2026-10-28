"""A scheduled recovery fills today's latest due slot, never replays old fills."""
from datetime import datetime, timezone
import os
from .scheduler_guard import session_guard
from .scheduler_schedule import latest_slot


def execution_due(state, now=None):
    now = now or datetime.now(timezone.utc)
    guard = session_guard(now)
    if not guard.should_run:
        return False, guard.reason
    target = latest_slot(now)
    if target is None:
        return False, "NO_SLOT_DUE"
    try:
        success = datetime.fromisoformat(state.get("lastSuccessfulAt", "").replace("Z", "+00:00"))
        if success.tzinfo and target <= success <= now and state.get("status") == "HEALTHY":
            return False, "SLOT_ALREADY_COMPLETED"
    except (TypeError, ValueError, AttributeError):
        pass
    return True, "LATEST_SLOT_DUE"


def main():
    from .runtime import load_state
    # Manual requests retain explicit refresh/validation behavior.
    if os.getenv("GITHUB_EVENT_NAME") == "schedule":
        due, reason = execution_due(load_state())
    else:
        due, reason = True, "MANUAL_REQUEST"
    print(reason)
    if output := os.getenv("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"should_run={str(due).lower()}\n")


if __name__ == "__main__":
    main()
