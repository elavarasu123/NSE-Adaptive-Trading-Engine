from datetime import datetime
from app.scheduler_schedule import IST
from app.operational_status import assess_operations


def state(at='2026-10-26T16:08:00+05:30', **changes):
    return {'status': 'HEALTHY', 'lastSuccessfulAt': at, 'lastStartedAt': at, 'lastRunId': 'current', **changes}


def test_saved_healthy_snapshot_cannot_hide_a_missed_cycle():
    result = assess_operations(state(), now=datetime(2026, 10, 27, 9, 41, tzinfo=IST))
    assert result['execution']['status'] == 'OVERDUE'
    assert result['execution']['recordedStatus'] == 'HEALTHY'
    assert result['scheduler']['status'] == 'UNVERIFIED'


def test_inside_grace_is_due_and_overnight_does_not_invent_slots():
    assert assess_operations(state(), now=datetime(2026, 10, 27, 9, 30, tzinfo=IST))['execution']['status'] == 'DUE'
    assert assess_operations(state(), now=datetime(2026, 10, 27, 8, tzinfo=IST))['execution']['status'] == 'CURRENT'


def test_manual_fallback_updates_execution_not_schedule_proof():
    events = [{'eventType': 'RUNTIME_START', 'data': {'runId': 'current', 'provenance': {'event': 'workflow_dispatch'}}}]
    result = assess_operations(state('2026-10-27T10:00:00+05:30'), events, datetime(2026, 10, 27, 10, 1, tzinfo=IST))
    assert result['execution']['status'] == 'CURRENT'
    assert result['scheduler']['status'] == 'UNVERIFIED'
    assert result['scheduler']['lastRunEvent'] == 'workflow_dispatch'


def test_exact_schedule_provenance_only_attests_its_slot():
    events = [{'eventType': 'RUNTIME_START', 'data': {'runId': 'current', 'provenance': {'event': 'schedule', 'scheduleEvidence': 'VERIFIED', 'attempt': '1', 'originCreatedAt': '2026-10-27T09:20:00+05:30', 'cron': '50 3 * * 1-5'}}}]
    result = assess_operations(state('2026-10-27T09:25:00+05:30'), events, datetime(2026, 10, 27, 9, 45, tzinfo=IST))
    assert result['scheduler']['status'] == 'SCHEDULE_EVENT_OBSERVED'
    later = assess_operations(state('2026-10-27T09:25:00+05:30'), events, datetime(2026, 10, 27, 10, 45, tzinfo=IST))
    assert later['execution']['status'] == 'OVERDUE'
    assert later['scheduler']['status'] == 'UNVERIFIED'


def test_invalid_future_timestamp_is_unknown_not_current():
    assert assess_operations(state('2099-01-01T00:00:00Z'), now=datetime(2026, 10, 27, 10, tzinfo=IST))['execution']['status'] == 'UNKNOWN'


def test_running_timeout_and_error_are_visible():
    now = datetime(2026, 10, 27, 10, tzinfo=IST)
    assert assess_operations(state(status='RUNNING'), now=now)['execution']['status'] == 'STALLED'
    assert assess_operations(state(status='ERROR'), now=now)['execution']['status'] == 'ERROR'


def test_weekend_uses_last_trading_slot_not_weekend_slots():
    result = assess_operations(state('2026-10-30T16:10:00+05:30'), now=datetime(2026, 10, 31, 12, tzinfo=IST))
    assert result['execution']['status'] == 'CURRENT'
    assert result['execution']['nextExpectedAt'].startswith('2026-11-02T09:20')


def test_degraded_risk_data_cannot_be_reported_as_current_success():
    result = assess_operations(state('2026-10-27T10:00:00+05:30', status='DEGRADED'),
                               now=datetime(2026, 10, 27, 10, 1, tzinfo=IST))
    assert result['execution']['status'] == 'DEGRADED'


def test_legacy_malformed_activity_does_not_fabricate_provenance_or_crash():
    result = assess_operations(state(), [{'eventType': 'RUNTIME_START', 'data': None}],
                               datetime(2026, 10, 27, 10, tzinfo=IST))
    assert result['scheduler']['status'] == 'UNVERIFIED'


def test_observer_endpoint_returns_unavailable_when_no_current_proof(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    import app.operational_status as operations
    monkeypatch.setenv('PUBLIC_DASHBOARD_READ_ONLY', 'true')
    monkeypatch.setattr(operations, 'health_report', lambda db: {
        'status': 'DEGRADED', 'readyForUnattendedExecution': False})
    with TestClient(app) as client:
        response = client.get('/api/operations/health')
        assert response.status_code == 503
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json()['readyForUnattendedExecution'] is False
        assert client.post('/api/operations/health').status_code == 403


def test_next_cycle_in_progress_retains_previous_completed_slot_proof():
    events = [{'eventType': 'RUNTIME_COMPLETE', 'data': {'runId': 'prior', 'status': 'HEALTHY',
               'startedAt': '2026-10-27T09:21:00+05:30', 'completedAt': '2026-10-27T09:25:00+05:30',
               'provenance': {'event': 'schedule', 'scheduleEvidence': 'VERIFIED', 'attempt': '1', 'originCreatedAt': '2026-10-27T09:20:00+05:30', 'cron': '50 3 * * 1-5', 'githubRunId': 'prior'}}},
              {'eventType': 'RUNTIME_START', 'data': {'runId': 'current',
               'provenance': {'event': 'schedule', 'cron': '50 4 * * 1-5'}}}]
    result = assess_operations(state('2026-10-27T09:25:00+05:30', status='RUNNING',
                                      lastStartedAt='2026-10-27T10:21:00+05:30'),
                               events, datetime(2026, 10, 27, 10, 22, tzinfo=IST))
    assert result['execution']['status'] == 'RUNNING'
    assert result['scheduler']['status'] == 'SCHEDULE_EVENT_OBSERVED'
    assert result['scheduler']['observedRunId'] == 'prior'


def test_normal_running_cycle_does_not_fail_observer_for_expected_checkpoint_updates(monkeypatch):
    import app.runtime as runtime
    import app.reliability as reliability
    from app.operational_status import health_report
    saved = state('2026-10-27T09:25:00+05:30', status='RUNNING', lastStartedAt='2026-10-27T10:21:00+05:30')
    events = [{'eventType': 'RUNTIME_COMPLETE', 'data': {'status': 'HEALTHY',
               'startedAt': '2026-10-27T09:21:00+05:30', 'completedAt': saved['lastSuccessfulAt'],
               'provenance': {'event': 'schedule', 'scheduleEvidence': 'VERIFIED', 'attempt': '1', 'originCreatedAt': '2026-10-27T09:20:00+05:30', 'cron': '50 3 * * 1-5'}}}]
    report = {'allowRuntime': False, 'blockers': ['CHECKPOINT'], 'marketData': {'status': 'FRESH', 'blocking': False},
              'portfolio': {'status': 'OK', 'blocking': False}, 'ledger': {'status': 'OK', 'blocking': False},
              'checkpoint': {'status': 'DIFFERENT', 'blocking': True}}
    monkeypatch.setattr(runtime, 'load_state', lambda: saved)
    monkeypatch.setattr(runtime, 'read_runtime_activity', lambda limit: events)
    monkeypatch.setattr(reliability, 'dashboard_reliability_report', lambda db, now: report)
    checked = datetime(2026, 10, 27, 10, 22, tzinfo=IST)
    result = health_report(None, checked)
    assert result['executionReady'] is True
    assert result['readyForUnattendedExecution'] is False  # independent alerts are still unconfigured
    assert result['integrity']['checkpoint']['status'] == 'UPDATING'
    report['portfolio']['blocking'] = True
    assert health_report(None, checked)['readyForUnattendedExecution'] is False


def test_rerun_or_previous_day_origin_cannot_prove_current_scheduled_delivery():
    proof = {'event': 'schedule', 'cron': '50 3 * * 1-5', 'attempt': '2',
             'scheduleEvidence': 'VERIFIED', 'originCreatedAt': '2026-10-26T09:20:00+05:30'}
    events = [{'eventType': 'RUNTIME_START', 'data': {'runId': 'current', 'provenance': proof}}]
    saved = state('2026-10-27T09:25:00+05:30')
    assert assess_operations(saved, events, datetime(2026, 10, 27, 9, 45, tzinfo=IST))['scheduler']['status'] == 'UNVERIFIED'
    proof['attempt'] = '1'
    assert assess_operations(saved, events, datetime(2026, 10, 27, 9, 45, tzinfo=IST))['scheduler']['status'] == 'UNVERIFIED'


def test_head_monitor_has_the_same_readiness_status_without_response_body(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    import app.operational_status as operations
    monkeypatch.setattr(operations, 'health_report', lambda db: {'status': 'READY', 'readyForUnattendedExecution': True})
    with TestClient(app) as client:
        response = client.head('/api/operations/health')
        assert response.status_code == 200 and response.content == b''
        assert response.headers['cache-control'] == 'no-store'


def test_execution_monitor_can_check_delivery_without_claiming_alerts_configured(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    import app.operational_status as operations
    monkeypatch.setattr(operations, 'health_report', lambda db: {
        'executionReady': True, 'readyForUnattendedExecution': False})
    with TestClient(app) as client:
        assert client.get('/api/operations/execution-health').status_code == 200
        assert client.get('/api/operations/health').status_code == 503
