"""Freshness of execution is independent from saved data/checkpoint health."""
from datetime import datetime, timedelta, timezone
from .scheduler_schedule import IST, ENGINE_CRONS, RECOVERY_CRONS, SCHEDULE_TIMES_IST, DELIVERY_GRACE, RUN_TIMEOUT
from .sessions import is_trading_session


def _timestamp(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Execution timestamps must include timezone')
    return parsed


def assess_operations(state, activities=(), now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    local = now.astimezone(IST)
    slots = []
    for offset in range(-10, 11):
        day = local.date() + timedelta(days=offset)
        if not is_trading_session(day):
            continue
        for clock, cron in zip(SCHEDULE_TIMES_IST, ENGINE_CRONS):
            hour, minute = map(int, clock.split(':'))
            at = datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)
            slots.append((at, cron))
    due = [x for x in slots if x[0] + DELIVERY_GRACE <= now]
    elapsed = [x for x in slots if x[0] <= now]
    future = [x for x in slots if x[0] > now]
    expected, expected_cron = due[-1] if due else (None, None)
    recent, recent_cron = elapsed[-1] if elapsed else (None, None)
    next_at = future[0][0] if future else None
    provenance = {}
    for activity in reversed(activities):
        data = activity.get("data") if isinstance(activity, dict) else None
        if (isinstance(data, dict) and activity.get("eventType") == "RUNTIME_START"
                and data.get("runId") == state.get("lastRunId")):
            value = data.get("provenance")
            provenance = value if isinstance(value, dict) else {}
            break
    execution = {'status': 'UNKNOWN', 'recordedStatus': state.get('status', 'NEVER_RUN'),
                 'lastSuccessfulAt': state.get('lastSuccessfulAt'),
                 'expectedCycleAt': expected.isoformat() if expected else None,
                 'nextExpectedAt': next_at.isoformat() if next_at else None,
                 'graceMinutes': int(DELIVERY_GRACE.total_seconds() // 60)}
    success = started = None
    try:
        success, started = _timestamp(state.get('lastSuccessfulAt')), _timestamp(state.get('lastStartedAt'))
        if (success and success > now) or (started and started > now):
            raise ValueError('Future execution timestamp')
        recorded = state.get('status')
        if recorded in {'ERROR', 'DEGRADED'}:
            status = recorded
        elif recorded == 'RUNNING':
            status = 'RUNNING' if started and now - started <= RUN_TIMEOUT else 'STALLED'
        elif not success:
            status = 'NEVER_RUN'
        elif expected and success < expected:
            status = 'OVERDUE'
        elif recent and success < recent:
            status = 'DUE'
        else:
            status = 'CURRENT'
        execution['status'] = status
        if status == 'DUE':
            execution['expectedCycleAt'] = recent.isoformat()
    except (ValueError, TypeError, AttributeError):
        execution['status'] = 'UNKNOWN'
    successful_provenance = provenance if state.get("status") == "HEALTHY" else {}
    successful_started = started if state.get("status") == "HEALTHY" else None
    for activity in reversed(activities):
        data = activity.get("data") if isinstance(activity, dict) else None
        if (isinstance(data, dict) and activity.get("eventType") == "RUNTIME_COMPLETE"
                and data.get("completedAt") == state.get("lastSuccessfulAt")
                and data.get("status") == "HEALTHY"):
            value = data.get("provenance")
            successful_provenance = value if isinstance(value, dict) else {}
            try:
                successful_started = _timestamp(data.get("startedAt"))
            except (TypeError, ValueError, AttributeError):
                successful_started = None
            break
    scheduler = {'status': 'UNVERIFIED', 'lastRunEvent': provenance.get('event', 'UNKNOWN'),
                 'githubRunId': provenance.get('githubRunId'),
                 'detail': 'Execution freshness cannot prove GitHub schedule delivery. Manual cycles are not schedule evidence.'}
    try:
        origin_created = _timestamp(successful_provenance.get("originCreatedAt"))
    except (ValueError, TypeError, AttributeError):
        origin_created = None
    # Attest only the exact latest expected slot, never all historical slots.
    if (execution['status'] in {'CURRENT', 'DUE', 'RUNNING'}
            and successful_provenance.get('event') == 'schedule'
            and successful_provenance.get('scheduleEvidence') == 'VERIFIED'
            and str(successful_provenance.get('attempt')) == '1'
            and origin_created and expected and successful_started
            and origin_created.astimezone(IST).date() == expected.date()
            and expected <= origin_created <= successful_started
            and successful_provenance.get('cron') == expected_cron and expected and successful_started and success
            and successful_started.astimezone(IST).date() == expected.date()
            and expected <= successful_started <= success):
        scheduler.update(status='SCHEDULE_EVENT_OBSERVED', observedSlot=expected.isoformat(),
                         observedRunId=successful_provenance.get('githubRunId'),
                         detail='The latest due slot has a completed cycle with recorded schedule-event provenance.')
    try:
        nominal = _timestamp(successful_provenance.get('nominalSlot'))
    except (ValueError, TypeError, AttributeError):
        nominal = None
    if (scheduler['status'] == 'UNVERIFIED' and nominal and expected and origin_created and success and successful_started
            and execution['status'] in {'CURRENT', 'DUE', 'RUNNING'}
            and successful_provenance.get('event') == 'schedule'
            and successful_provenance.get('scheduleEvidence') == 'VERIFIED'
            and str(successful_provenance.get('attempt')) == '1'
            and successful_provenance.get('cron') in (*ENGINE_CRONS, *RECOVERY_CRONS)
            and origin_created.astimezone(IST).date() == nominal.astimezone(IST).date()
            and expected <= nominal <= successful_started <= success <= now
            and origin_created <= successful_started):
        scheduler.update(status='SCHEDULE_RECOVERY_OBSERVED', observedSlot=nominal.isoformat(),
                         observedRunId=successful_provenance.get('githubRunId'),
                         detail='A verified scheduled delivery recovered the latest slot; original trigger punctuality is not guaranteed.')
    return {'checkedAt': now.isoformat(), 'execution': execution, 'scheduler': scheduler,
            'monitoring': {'status': 'UNCONFIGURED',
                           'detail': 'No independent alert destination or delivery check is configured.'}}


def health_report(db, now=None):
    from .runtime import load_state, read_runtime_activity
    from .reliability import dashboard_reliability_report
    operations = assess_operations(load_state(), read_runtime_activity(25), now)
    reliability = dashboard_reliability_report(db, now)
    updating = (operations['execution']['status'] == 'RUNNING'
                and set(reliability.get('blockers', [])) <= {'CHECKPOINT'}
                and not reliability['marketData'].get('blocking')
                and not reliability['portfolio'].get('blocking')
                and not reliability['ledger'].get('blocking'))
    errors = operations['execution']['status'] not in {'CURRENT', 'DUE', 'RUNNING'} or not (reliability['allowRuntime'] or updating)
    observed = operations['scheduler']['status'] in {'SCHEDULE_EVENT_OBSERVED', 'SCHEDULE_RECOVERY_OBSERVED'}
    execution_ready = not errors and observed
    monitoring_ready = operations['monitoring']['status'] == 'VERIFIED'
    return {**operations, 'status': 'BLOCKED' if errors else 'READY' if execution_ready and monitoring_ready else 'DEGRADED',
            'executionReady': execution_ready,
            'readyForUnattendedExecution': execution_ready and monitoring_ready,
            'data': reliability['marketData'],
            'integrity': {**{key: reliability[key] for key in ['portfolio', 'ledger']},
                          'checkpoint': {'status': 'UPDATING'} if updating else reliability['checkpoint']}}
