from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import urllib.error
import zipfile

import pytest

from app import scheduler_health as health
from app.scheduler_schedule import ENGINE_CRONS, IST, SCHEDULE_TIMES_IST, due_slots


ACTIVATED = datetime(2026, 10, 26, 8, tzinfo=IST)
REPOSITORY = "example/paper"


def clock(hour, minute=0):
    return datetime(2026, 10, 26, hour, minute, tzinfo=IST)


def run(**overrides):
    return {
        "id": 123, "run_attempt": 1, "event": "schedule", "head_sha": "abc",
        "head_branch": "main", "created_at": "2026-10-26T03:51:00Z",
        "run_started_at": "2026-10-26T03:52:00Z", "status": "completed",
        "conclusion": "success", **overrides,
    }


def receipt(**overrides):
    return {
        "event": "schedule", "cron": ENGINE_CRONS[0], "run_id": "123",
        "run_attempt": 1, "sha": "abc", "repository": REPOSITORY,
        "ref": "refs/heads/main", "received_at": "2026-10-26T03:52:00Z",
        **overrides,
    }


def test_schedule_utc_conversion_and_workflow_contract():
    from app.scheduler_schedule import RECOVERY_CRONS
    assert SCHEDULE_TIMES_IST == (
        "09:20", "10:20", "11:20", "12:20", "13:20", "14:20", "15:20", "16:05",
    )
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/nse-paper-engine.yml").read_text()
    assert tuple(re.findall(r'- cron: "([^"]+)"', workflow)) == ENGINE_CRONS + RECOVERY_CRONS
    # Post-close forces refresh; any validated refresh is saved before preflight.
    assert "github.event.schedule == '35 10 * * 1-5'" in workflow
    assert "python scripts/ensure_market_history.py" in workflow
    assert "steps.history.outputs.refreshed == 'true'" in workflow
    assert workflow.index("name: Save refreshed market history") < workflow.index("name: Reliability preflight")
    watchdog = (root / ".github/workflows/scheduler-watchdog.yml").read_text()
    assert 'cron: "17 4-10 * * 1-5"' in watchdog
    assert 'cron: "7 11 * * 1-5"' in watchdog
    assert "actions: read" in watchdog
    assert "DATABASE_URL" not in watchdog
    assert "run_scheduled_runtime" not in watchdog
    assert '--runtime-url https://nse-adaptive-trading-engine.onrender.com/api/operations/health' in watchdog


def test_watchdog_identifies_recovery_delivery_without_claiming_original_delivery():
    from app.scheduler_schedule import RECOVERY_CRONS
    recovered = run(created_at=clock(9, 27).isoformat())
    proof = receipt(cron=RECOVERY_CRONS[0], nominal_slot=clock(9, 20).isoformat())
    rows = health.assess_slots(clock(9, 45), ACTIVATED, [recovered], {123: proof})
    assert rows[0]['status'] == 'RECOVERY_DELIVERED'
    assert 'verify shared runtime' in rows[0]['detail']


def test_delivery_grace_and_activation_cutoff():
    assert due_slots(clock(9, 39), ACTIVATED) == []
    assert len(due_slots(clock(9, 40), ACTIVATED)) == 1
    assert [x["cron"] for x in due_slots(clock(10, 40), clock(9, 21))] == [ENGINE_CRONS[1]]


@pytest.mark.parametrize("day", [20, 25])
def test_holiday_and_weekend_have_no_due_slots(day):
    now = datetime(2026, 10, day, 17, tzinfo=IST)
    assert due_slots(now, now.replace(hour=0)) == []


def test_manual_run_does_not_satisfy_scheduled_slot():
    rows = health.assess_slots(clock(9, 47), ACTIVATED, [run(event="workflow_dispatch")], {})
    assert rows[0]["status"] == "MISSING"


def test_scheduled_receipt_proves_delivery_not_trading_execution():
    rows = health.assess_slots(clock(9, 47), ACTIVATED, [run()], {123: receipt()})
    assert rows[0]["status"] == "SUCCESS"
    assert "does not prove" in health.summary(rows)


def test_late_previous_cron_cannot_satisfy_next_slot():
    late = run(created_at="2026-10-26T04:55:00Z")
    rows = health.assess_slots(clock(10, 47), ACTIVATED, [late], {123: receipt()})
    assert [r["status"] for r in rows] == ["LATE_DELIVERY", "MISSING"]


def test_even_successful_after_hours_delivery_is_not_healthy():
    late = run(created_at=clock(21, 10).isoformat(), run_started_at=clock(21, 11).isoformat())
    rows = health.assess_slots(clock(21, 30), ACTIVATED, [late], {123: receipt()})
    assert rows[0]['status'] == 'LATE_DELIVERY'


def runtime_health(**changes):
    report = {'checkedAt': clock(9, 47).isoformat(),
              'execution': {'status': 'CURRENT', 'lastSuccessfulAt': clock(9, 25).isoformat(), 'expectedCycleAt': clock(9, 20).isoformat()},
              'data': {'status': 'FRESH', 'blocking': False, 'latestSession': '2026-10-23', 'expectedSession': '2026-10-23'},
              'integrity': {'portfolio': {'status': 'OK', 'blocking': False}, 'ledger': {'status': 'OK', 'blocking': False}, 'checkpoint': {'status': 'MATCH', 'blocking': False}},
              'monitoring': {'status': 'UNCONFIGURED'}, 'readyForUnattendedExecution': False}
    report.update(changes)
    return report


def test_saved_healthy_delivery_cannot_mask_overdue_live_execution():
    report = runtime_health(execution={'status': 'OVERDUE', 'recordedStatus': 'HEALTHY'})
    assert health.assess_runtime(report, clock(9, 47))['status'] == 'BLOCKED'
    assert health.assess_runtime(runtime_health(), clock(9, 47))['status'] == 'HEALTHY'


@pytest.mark.parametrize('changes', [
    {'checkedAt': clock(8, 0).isoformat()}, {'checkedAt': clock(10, 0).isoformat()},
    {'execution': None}, {'integrity': {}}, {},
])
def test_missing_or_cached_health_cannot_pass(changes):
    report = runtime_health(**changes) if changes else {}
    assert health.assess_runtime(report, clock(9, 47))['status'] == 'EVIDENCE_UNAVAILABLE'


def test_live_account_or_data_failure_remains_blocking():
    report = runtime_health(data={'status': 'STALE', 'blocking': True, 'latestSession': '2026-10-22', 'expectedSession': '2026-10-23'})
    assert health.assess_runtime(report, clock(9, 47))['status'] == 'BLOCKED'
    report = runtime_health()
    report['integrity']['ledger']['status'] = 'BROKEN'
    assert health.assess_runtime(report, clock(9, 47))['status'] == 'BLOCKED'


def test_late_runner_admission_is_not_timely_even_when_run_created_on_time():
    rows = health.assess_slots(clock(10, 0), ACTIVATED, [run()],
                              {123: receipt(received_at=clock(9, 50).isoformat())})
    assert rows[0]['status'] == 'LATE_DELIVERY'


def test_inconsistent_current_timestamp_is_blocked():
    report = runtime_health()
    report['execution']['lastSuccessfulAt'] = clock(8, 0).isoformat()
    assert health.assess_runtime(report, clock(9, 47))['status'] == 'BLOCKED'


def test_http_503_for_unconfigured_alerts_still_checks_execution(monkeypatch):
    def open_request(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 503, 'Degraded', {},
                                     io.BytesIO(json.dumps(runtime_health()).encode()))
    monkeypatch.setattr(health.urllib.request, 'urlopen', open_request)
    assessor = health.assess_runtime
    monkeypatch.setattr(health, 'assess_runtime', lambda document, now: assessor(document, clock(9, 47)))
    assert health.inspect_runtime('https://example.com/api/operations/health')['status'] == 'HEALTHY'


def test_live_runtime_check_does_not_forward_github_credentials(monkeypatch):
    monkeypatch.setenv('GH_TOKEN', 'never-forward-me')
    def open_request(request, timeout):
        assert not request.has_header('Authorization')
        assert timeout == 30
        return io.BytesIO(json.dumps(runtime_health()).encode())
    monkeypatch.setattr(health.urllib.request, 'urlopen', open_request)
    monkeypatch.setattr(health, 'assess_runtime', lambda document, now: {'status': 'HEALTHY', 'detail': 'checked'})
    assert health.inspect_runtime('https://example.com/api/operations/health')['status'] == 'HEALTHY'
    assert health.inspect_runtime('https://user:secret@example.com/api/operations/health')['status'] == 'EVIDENCE_UNAVAILABLE'


def test_cli_fails_for_stale_runtime_even_with_successful_delivery(monkeypatch, capsys):
    monkeypatch.setenv('GITHUB_REPOSITORY', REPOSITORY)
    monkeypatch.setenv('DEFAULT_BRANCH', 'main')
    monkeypatch.setenv('GH_TOKEN', 'never-print-this')
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    monkeypatch.setattr(health, 'activation_time', lambda: ACTIVATED)
    monkeypatch.setattr(health, 'check', lambda *a, **k: [{'status': 'SUCCESS', 'slot': 'test', 'detail': 'delivered'}])
    monkeypatch.setattr(health, 'inspect_runtime', lambda url: {'status': 'BLOCKED', 'detail': 'Execution OVERDUE'})
    assert health.main(['check', '--runtime-url', 'https://example.com/api/operations/health']) == 1
    output = capsys.readouterr().out
    assert 'LIVE_RUNTIME_BLOCKED' in output
    assert 'never-print-this' not in output


@pytest.mark.parametrize("changes, expected", [
    ({"status": "completed", "conclusion": "failure"}, "FAILED"),
    ({"status": "completed", "conclusion": "cancelled"}, "FAILED"),
    ({"status": "completed", "conclusion": "timed_out"}, "FAILED"),
    ({"status": "in_progress"}, "PENDING"),
    ({"status": "queued", "run_started_at": None}, "PENDING"),
])
def test_run_states(changes, expected):
    assert health.run_status(run(**changes), clock(9, 47)) == expected


def test_running_and_queued_timeout():
    for state in ("queued", "in_progress"):
        assert health.run_status(run(status=state), clock(10, 10)) == "TIMED_OUT"


def test_unverified_evidence_never_counts_as_success():
    for errors in ({}, {123: True}):
        rows = health.assess_slots(clock(9, 47), ACTIVATED, [run()], {}, errors)
        assert rows[0]["status"] == "EVIDENCE_UNAVAILABLE"


def test_pending_receipt_is_distinct_from_api_failure():
    pending = run(status="in_progress")
    assert health.assess_slots(clock(9, 47), ACTIVATED, [pending], {})[0]["status"] == "PENDING"
    assert health.assess_slots(clock(9, 47), ACTIVATED, [pending], {}, {123: True})[0]["status"] == "EVIDENCE_UNAVAILABLE"


def test_duplicate_delivery_is_reported():
    rows = health.assess_slots(clock(9, 47), ACTIVATED, [run(), run(id=456)],
                              {123: receipt(), 456: receipt(run_id="456")})
    assert rows[0]["status"] == "DUPLICATE"


def test_next_watchdog_revisits_prior_post_close_run():
    activated = datetime(2026, 10, 23, 16, tzinfo=IST)
    old = run(created_at="2026-10-23T10:36:00Z", run_started_at="2026-10-23T10:37:00Z",
              status="in_progress")
    rows = health.assess_slots(clock(9, 47), activated, [old],
                              {123: receipt(cron=ENGINE_CRONS[-1])})
    assert rows[0]["slot"] == "2026-10-23 16:05 IST"
    assert rows[0]["status"] == "TIMED_OUT"


@pytest.mark.parametrize("change", [
    {"event": "workflow_dispatch"}, {"cron": "45 3 * * 1-5"}, {"run_id": "456"},
    {"run_attempt": 2}, {"sha": "changed"}, {"repository": "another/repo"},
    {"ref": "refs/heads/feature"},
])
def test_receipt_is_bound_to_exact_run_attempt_and_commit(change):
    with pytest.raises(health.EvidenceError):
        health.validate_receipt(receipt(**change), run(), REPOSITORY, "main")


def test_valid_receipt_and_malformed_receipt():
    assert health.validate_receipt(receipt(), run(), REPOSITORY, "main")["cron"] == ENGINE_CRONS[0]
    with pytest.raises(health.EvidenceError):
        health.validate_receipt([], run(), REPOSITORY, "main")


def test_receipt_only_writes_allowlisted_metadata(tmp_path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"schedule": ENGINE_CRONS[0], "secret": "do-not-copy"}))
    environ = {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": "schedule",
               "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "abc",
               "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
               "DATABASE_URL": "do-not-copy", "GH_TOKEN": "do-not-copy"}
    doc = health.receipt_document(environ, clock(9, 22))
    assert "do-not-copy" not in json.dumps(doc)
    assert doc["run_attempt"] == 1


class FakeGitHub:
    def __init__(self, state="active", runs=None, artifact=None):
        self.state = state
        self.runs = runs or []
        self.artifact = artifact

    def get(self, path):
        return {"state": self.state}

    def pages(self, path, key):
        assert "event=schedule" in path and "branch=main" in path
        return self.runs

    def receipt(self, run):
        if isinstance(self.artifact, Exception):
            raise self.artifact
        return self.artifact


def test_disabled_workflow_is_not_misreported_as_missing():
    with pytest.raises(health.EvidenceError, match="disabled"):
        health.check(clock(9, 47), ACTIVATED, FakeGitHub(state="disabled_manually"),
                     REPOSITORY, "main")


def test_reactivation_scopes_future_deliveries_without_claiming_recovery():
    client = FakeGitHub()
    client.get = lambda path: {"state": "active", "updated_at": "2026-10-26T13:41:49+05:30"}
    scope = {}
    rows = health.check(clock(14, 47), ACTIVATED, client, REPOSITORY, "main", scope=scope)
    assert [row["slot"] for row in rows] == ["2026-10-26 14:20 IST"]
    assert rows[0]["status"] == "MISSING"  # A registration reset is not proof of delivery.
    assert scope["activated_at"] == "2026-10-26T13:41:49+05:30"
    assert "Earlier failed checks remain" in health.summary(rows, scope=scope)


def test_invalid_registration_cannot_hide_missing_runs():
    client = FakeGitHub()
    client.get = lambda path: {"state": "active", "updated_at": "not-a-time"}
    with pytest.raises(health.EvidenceError):
        health.check(clock(9, 47), ACTIVATED, client, REPOSITORY, "main")


def test_github_annotation_exposes_diagnostic_without_log_storage(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("DEFAULT_BRANCH", "main")
    monkeypatch.setenv("GH_TOKEN", "never-print-this")
    monkeypatch.setattr(health, "activation_time", lambda: ACTIVATED)
    monkeypatch.setattr(health, "check", lambda *args, **kwargs: [
        {"status": "MISSING", "slot": "09:20 IST", "detail": "absent\n100%"}])
    assert health.main(["check"]) == 1
    output = capsys.readouterr().out
    assert "::error title=NSE scheduler health::MISSING: 09:20 IST: absent%0A100%25" in output
    assert "never-print-this" not in output


def test_api_check_filters_wrong_branch_and_handles_artifact_failures():
    client = FakeGitHub(runs=[run(head_branch="feature")], artifact=receipt())
    assert health.check(clock(9, 47), ACTIVATED, client, REPOSITORY, "main")[0]["status"] == "MISSING"
    client = FakeGitHub(runs=[run()], artifact=health.EvidenceError("Unavailable"))
    assert health.check(clock(9, 47), ACTIVATED, client, REPOSITORY, "main")[0]["status"] == "EVIDENCE_UNAVAILABLE"


def test_pagination_does_not_silently_truncate(monkeypatch):
    client = health.GitHub(REPOSITORY, "not-a-real-token")
    monkeypatch.setattr(client, "get", lambda path: {"runs": list(range(100))})
    with pytest.raises(health.EvidenceError, match="pagination incomplete"):
        client.pages("/runs", "runs")


def test_activation_uses_repository_root_and_first_parent(monkeypatch):
    def output(command, **kwargs):
        assert "--first-parent" in command
        assert command[-1] == health.WORKFLOW
        assert (kwargs["cwd"] / ".github/workflows/nse-paper-engine.yml").exists()
        return "2026-10-26T03:00:00Z\n"
    monkeypatch.setattr(health.subprocess, "check_output", output)
    assert health.activation_time() == datetime(2026, 10, 26, 3, tzinfo=timezone.utc)


def test_artifact_redirect_does_not_receive_github_token(monkeypatch):
    client = health.GitHub(REPOSITORY, "private-token")
    monkeypatch.setattr(client, "pages", lambda *args: [
        {"name": "scheduler-receipt-123-1", "id": 99, "expired": False}])

    class Redirect:
        def open(self, request, **kwargs):
            assert request.get_header("Authorization") == "Bearer private-token"
            raise urllib.error.HTTPError(request.full_url, 302, "Found",
                                         {"Location": "https://storage.example/artifact"}, None)

    monkeypatch.setattr(health.urllib.request, "build_opener", lambda *args: Redirect())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("scheduler-receipt.json", json.dumps(receipt()))

    def download(url, **kwargs):
        assert url == "https://storage.example/artifact"  # URL only; no Authorization header.
        return io.BytesIO(buffer.getvalue())
    monkeypatch.setattr(health.urllib.request, "urlopen", download)
    assert client.receipt(run())["run_id"] == "123"


@pytest.mark.parametrize("rows, error, exit_code", [
    ([{"status": "SUCCESS", "slot": "test", "detail": "run"}], None, 0),
    ([{"status": "MISSING", "slot": "test", "detail": "absent"}], None, 1),
    ([], health.EvidenceError("GitHub unavailable"), 1),
])
def test_cli_preserves_failure_status_and_writes_summary(monkeypatch, tmp_path, rows, error, exit_code):
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("DEFAULT_BRANCH", "main")
    monkeypatch.setenv("GH_TOKEN", "do-not-log")
    output = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(output))
    monkeypatch.setattr(health, "activation_time", lambda: ACTIVATED)

    def check(*args, **kwargs):
        if error:
            raise error
        return rows
    monkeypatch.setattr(health, "check", check)
    assert health.main(["check"]) == exit_code
    assert "do-not-log" not in output.read_text()
    assert "NSE scheduler health" in output.read_text()
