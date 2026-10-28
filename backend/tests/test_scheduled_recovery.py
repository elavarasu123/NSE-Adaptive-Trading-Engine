from datetime import datetime
from app.scheduler_schedule import IST
from app.scheduled_recovery import execution_due


def clock(hour, minute):
    return datetime(2026, 10, 28, hour, minute, tzinfo=IST)


def test_recovery_does_not_duplicate_completed_slot_or_replay_previous_slots():
    state = {"status": "HEALTHY", "lastSuccessfulAt": clock(9, 24).isoformat()}
    assert execution_due(state, clock(9, 27)) == (False, "SLOT_ALREADY_COMPLETED")
    assert execution_due(state, clock(10, 27)) == (True, "LATEST_SLOT_DUE")


def test_error_or_future_timestamp_cannot_suppress_recovery():
    assert execution_due({"status": "ERROR", "lastSuccessfulAt": clock(10, 21).isoformat()}, clock(10, 27))[0]
    assert execution_due({"status": "HEALTHY", "lastSuccessfulAt": clock(11, 21).isoformat()}, clock(10, 27))[0]


def test_late_recovery_never_forces_after_hours_execution():
    assert execution_due({}, clock(16, 17))[0]
    assert execution_due({}, clock(16, 21)) == (False, "OUTSIDE_MARKET_WINDOW")
    assert execution_due({}, clock(9, 17)) == (False, "NO_SLOT_DUE")


def test_verified_recovery_is_not_reported_as_original_trigger_punctuality():
    from app.operational_status import assess_operations
    state = {"status": "HEALTHY", "lastRunId": "r", "lastStartedAt": clock(10, 27).isoformat(),
             "lastSuccessfulAt": clock(10, 28).isoformat()}
    proof = {"event": "schedule", "scheduleEvidence": "VERIFIED", "attempt": "1",
             "originCreatedAt": clock(10, 26).isoformat(), "nominalSlot": clock(10, 20).isoformat(),
             "cron": "7,27,47 4-10 * * 1-5"}
    activity = [{"eventType": "RUNTIME_START", "data": {"runId": "r", "provenance": proof}}]
    report = assess_operations(state, activity, clock(10, 41))
    assert report["scheduler"]["status"] == "SCHEDULE_RECOVERY_OBSERVED"
    proof["attempt"] = "2"
    assert assess_operations(state, activity, clock(10, 41))["scheduler"]["status"] == "UNVERIFIED"
