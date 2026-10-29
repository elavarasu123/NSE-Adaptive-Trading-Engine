"""Read-only GitHub schedule diagnostics. Never imports the trading runtime.

    python -m app.scheduler_health receipt --output PATH
    python -m app.scheduler_health check

The check uses the built-in GitHub token with actions:read and contents:read.
No database access, workflow dispatch, rerun, or trading operation exists here.
"""

import argparse
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from .scheduler_schedule import ENGINE_CRONS, RECOVERY_CRONS, IST, RUN_TIMEOUT, DELIVERY_GRACE, due_slots, latest_slot


WORKFLOW = ".github/workflows/nse-paper-engine.yml"
GOOD_STATUSES = {"SUCCESS", "PENDING", "RECOVERY_DELIVERED"}


class EvidenceError(Exception):
    """Only credential-free diagnostic messages may be stored here."""


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return result


def activation_time():
    # First-parent history includes the merge that introduced the cron change,
    # rather than the earlier timestamp of a commit on a development branch.
    value = subprocess.check_output(
        ["git", "log", "--first-parent", "-1", "--format=%cI",
         "-G", r"^[[:space:]]*- cron:", "--", WORKFLOW],
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    ).strip()
    if not value:
        raise EvidenceError("Cannot establish schedule activation from Git history")
    return timestamp(value)


def receipt_document(environ, now):
    with open(environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    return {
        "event": environ["GITHUB_EVENT_NAME"],
        "cron": event.get("schedule"),
        "run_id": environ["GITHUB_RUN_ID"],
        "run_attempt": int(environ["GITHUB_RUN_ATTEMPT"]),
        "sha": environ["GITHUB_SHA"],
        "repository": environ["GITHUB_REPOSITORY"],
        "ref": environ["GITHUB_REF"],
        "received_at": now.isoformat(),
        "nominal_slot": latest_slot(now).isoformat() if latest_slot(now) else None,
    }


def validate_receipt(receipt, run, repository, branch):
    if not isinstance(receipt, dict) or not (
        receipt.get("event") == "schedule"
        and receipt.get("cron") in (*ENGINE_CRONS, *RECOVERY_CRONS)
        and receipt.get("run_id") == str(run["id"])
        and receipt.get("run_attempt") == run["run_attempt"]
        and receipt.get("sha") == run["head_sha"]
        and receipt.get("repository") == repository
        and receipt.get("ref") == f"refs/heads/{branch}"
    ):
        raise EvidenceError("Receipt does not match its scheduled run/attempt/commit")
    timestamp(receipt["received_at"])
    return receipt


def run_status(run, now):
    if run["status"] == "completed":
        return "SUCCESS" if run.get("conclusion") == "success" else "FAILED"
    started = timestamp(run.get("run_started_at") or run["created_at"])
    return "TIMED_OUT" if now - started > RUN_TIMEOUT else "PENDING"


def assess_slots(now, activated_at, runs, receipts, errors=None):
    """Receipts disambiguate late deliveries from the next hour's trigger.

    Missing/unreadable receipts are unknown evidence, never successful runs.
    Manual dispatches cannot satisfy a scheduled slot.
    """
    errors = errors or {}
    runs = [r for r in runs if r.get("event") == "schedule"]
    results = []
    # Revisit earlier slots so a pending post-close run is checked again even
    # when its timeout occurs after the last watchdog invocation of the day.
    for slot in due_slots(now, activated_at, lookback_days=6):
        expected = slot["expected_at"]
        matches = []
        uncertain = []
        for run in runs:
            created = timestamp(run["created_at"])
            if created.astimezone(IST).date() != expected.date() or created < expected:
                continue
            receipt = receipts.get(run["id"])
            if receipt and receipt["cron"] == slot["cron"]:
                matches.append(run)
            elif not receipt:
                # Only associate an unidentified run with its delivery window.
                # Post-close has no following trading slot today.
                end = (expected + timedelta(hours=1) if slot["cron"] != ENGINE_CRONS[-1]
                       else expected.replace(hour=23, minute=59, second=59))
                if created < end:
                    uncertain.append(run)
        row = {"slot": expected.strftime("%Y-%m-%d %H:%M IST"),
               "cron": slot["cron"], "status": "MISSING",
               "detail": "No scheduled delivery observed after the 20-minute grace"}
        if matches:
            run = max(matches, key=lambda r: (r["created_at"], r["id"]))
            row.update(status=run_status(run, now),
                       detail=f"Run {run['id']}, attempt {run['run_attempt']}")
            received = timestamp(receipts[run['id']]['received_at'])
            if row['status'] in GOOD_STATUSES and max(timestamp(run['created_at']), received) > expected + DELIVERY_GRACE:
                row.update(status='LATE_DELIVERY', detail=f"Run {run['id']} arrived after delivery grace; workflow success does not prove timely execution")
            if len(matches) > 1:
                row.update(status="DUPLICATE", detail="Multiple scheduled runs claim this slot")
        elif uncertain:
            run = max(uncertain, key=lambda r: (r["created_at"], r["id"]))
            state = run_status(run, now)
            row.update(
                status="PENDING" if state == "PENDING" and run["id"] not in errors
                else "EVIDENCE_UNAVAILABLE",
                detail=f"Run {run['id']}: {state}; no verified receipt for this slot",
            )
        if row['status'] == 'MISSING':
            for run in runs:
                receipt = receipts.get(run['id'], {})
                if (receipt.get('cron') in RECOVERY_CRONS
                        and receipt.get('nominal_slot') == expected.isoformat()
                        and timestamp(run['created_at']).astimezone(IST).date() == expected.date()
                        and timestamp(run['created_at']) <= expected + DELIVERY_GRACE
                        and timestamp(receipt['received_at']) <= expected + DELIVERY_GRACE
                        and run_status(run, now) == 'SUCCESS'):
                    row.update(status='RECOVERY_DELIVERED', detail=f"Recovery workflow {run['id']} succeeded; verify shared runtime evidence for execution")
                    break
        results.append(row)
    return results


def assess_runtime(document, now):
    """An old HEALTHY checkpoint cannot satisfy current execution freshness."""
    try:
        checked = timestamp(document['checkedAt'])
        if not -30 <= (now - checked).total_seconds() <= 120:
            raise ValueError('Old or future response')
        execution, data, integrity = document['execution'], document['data'], document['integrity']
        status = execution['status']
        if status not in {'CURRENT', 'DUE', 'RUNNING'}:
            return {'status': 'BLOCKED', 'detail': f"Execution {status}; last success {execution.get('lastSuccessfulAt')}"}
        success, expected = timestamp(execution['lastSuccessfulAt']), timestamp(execution['expectedCycleAt'])
        datetime.strptime(data['latestSession'], '%Y-%m-%d')
        datetime.strptime(data['expectedSession'], '%Y-%m-%d')
        if success > now or expected > now:
            raise ValueError('Future execution evidence')
        if ((status == 'CURRENT' and success < expected)
                or (status == 'DUE' and now > expected + DELIVERY_GRACE)):
            return {'status': 'BLOCKED', 'detail': 'Execution timestamps do not cover the expected slot'}
        checkpoint = integrity['checkpoint']['status']
        checkpoint_ok = ((checkpoint == 'MATCH' and integrity['checkpoint'].get('blocking') is False)
                         or (status == 'RUNNING' and checkpoint in {'UPDATING', 'MISMATCH', 'RECOVERY_REQUIRED'}))
        if (data['status'] != 'FRESH' or data.get('blocking') is not False
                or not data.get('latestSession') or data.get('latestSession') != data.get('expectedSession')
                or integrity['portfolio']['status'] != 'OK' or integrity['ledger']['status'] != 'OK'
                or integrity['portfolio'].get('blocking') is not False or integrity['ledger'].get('blocking') is not False
                or not checkpoint_ok):
            return {'status': 'BLOCKED', 'detail': 'Live data or portfolio/ledger/checkpoint checks are not healthy'}
        return {'status': 'HEALTHY', 'detail': f"Execution {status}; settled data {data.get('latestSession')}; last success {execution.get('lastSuccessfulAt')}. Independent alerts and schedule provenance are separate checks."}
    except (ValueError, TypeError, KeyError, AttributeError):
        return {'status': 'EVIDENCE_UNAVAILABLE', 'detail': 'Live runtime evidence is malformed, cached or incomplete'}


def inspect_runtime(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path != '/api/operations/health'):
        return {'status': 'EVIDENCE_UNAVAILABLE', 'detail': 'Invalid HTTPS operational health URL'}
    try:
        request = urllib.request.Request(url, headers={'Accept': 'application/json', 'Cache-Control': 'no-cache',
                                                      'User-Agent': 'nse-read-only-watchdog'})
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            if error.code != 503:
                raise
            response = error  # DEGRADED may mean alerts unconfigured; inspect each check.
        with response:
            payload = response.read(512001)
        if len(payload) > 512000:
            raise ValueError('Oversized health response')
        return assess_runtime(json.loads(payload), datetime.now(timezone.utc))
    except Exception:
        return {'status': 'EVIDENCE_UNAVAILABLE', 'detail': 'Live runtime health endpoint unavailable or invalid'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, repository, token):
        self.root = f"https://api.github.com/repos/{repository}"
        self.headers = {"Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "User-Agent": "nse-scheduler-watchdog"}

    def get(self, path):
        request = urllib.request.Request(self.root + path, headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                document = json.load(response)
                if not isinstance(document, dict):
                    raise EvidenceError("Unexpected GitHub API response")
                return document
        except (urllib.error.URLError, ValueError):
            raise EvidenceError("GitHub API evidence unavailable; check Actions read permission/network") from None

    def pages(self, path, key):
        result = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 21):
            data = self.get(f"{path}{separator}per_page=100&page={page}")
            batch = data[key]
            if not isinstance(batch, list):
                raise EvidenceError("Unexpected GitHub pagination response")
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise EvidenceError("GitHub pagination incomplete; refusing a partial health assessment")

    def receipt(self, run):
        artifacts = self.pages(f"/actions/runs/{run['id']}/artifacts", "artifacts")
        name = f"scheduler-receipt-{run['id']}-{run['run_attempt']}"
        matches = [a for a in artifacts if a["name"] == name and not a["expired"]]
        if not matches:
            return None
        request = urllib.request.Request(
            self.root + f"/actions/artifacts/{matches[0]['id']}/zip", headers=self.headers)
        try:
            # Never forward Authorization to the artifact storage redirect.
            try:
                with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                    payload = response.read(1024 * 1024 + 1)
            except urllib.error.HTTPError as response:
                if response.code != 302:
                    raise EvidenceError("Receipt download unavailable") from None
                location = response.headers.get("Location", "")
                parsed = urllib.parse.urlsplit(location)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username:
                    raise EvidenceError("Invalid artifact redirect")
                with urllib.request.urlopen(location, timeout=30) as artifact:
                    payload = artifact.read(1024 * 1024 + 1)
            if len(payload) > 1024 * 1024:
                raise EvidenceError("Receipt archive exceeds size limit")
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                info = archive.getinfo("scheduler-receipt.json")
                if info.file_size > 16384:
                    raise EvidenceError("Receipt exceeds size limit")
                return json.loads(archive.read(info))
        except (urllib.error.URLError, ValueError, KeyError, zipfile.BadZipFile, OSError):
            raise EvidenceError("Receipt artifact unreadable or unavailable") from None


def check(now, activated_at, github, repository, branch, scope=None):
    workflow = github.get("/actions/workflows/nse-paper-engine.yml")
    if workflow["state"] != "active":
        raise EvidenceError("Engine workflow is disabled; enable it in GitHub Actions")
    # Re-enabling starts a new delivery registration. Do not demand retroactive
    # delivery of slots from before the repair; previous runs retain that audit.
    if workflow.get("updated_at"):
        try:
            registration = timestamp(workflow["updated_at"])
        except (ValueError, TypeError, AttributeError):
            raise EvidenceError("Invalid workflow registration timestamp") from None
        if registration > now + timedelta(minutes=1):
            raise EvidenceError("Workflow registration timestamp is in the future")
        activated_at = max(activated_at, registration)
    if scope is not None:
        scope["activated_at"] = activated_at.isoformat()
    day = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    query = urllib.parse.urlencode({"event": "schedule", "branch": branch,
                                  "created": ">=" + day.astimezone(timezone.utc).isoformat()})
    runs = github.pages(f"/actions/workflows/nse-paper-engine.yml/runs?{query}", "workflow_runs")
    runs = [r for r in runs if r.get("event") == "schedule" and r["head_branch"] == branch]
    receipts, errors = {}, {}
    for run in runs:
        try:
            receipt = github.receipt(run)
            if receipt is not None:
                receipts[run["id"]] = validate_receipt(receipt, run, repository, branch)
        except (EvidenceError, ValueError, KeyError):
            errors[run["id"]] = True
    return assess_slots(now, activated_at, runs, receipts, errors)


def summary(rows, error=None, scope=None):
    lines = ["## NSE scheduler health", "",
             "GitHub delivery/workflow evidence only. Success does not prove that a paper cycle "
             "executed: inspect session-guard and runtime evidence.", ""]
    if scope and scope.get("activated_at"):
        lines.extend([
            "Delivery scope starts at " + timestamp(scope["activated_at"]).astimezone(IST).isoformat()
            + " (latest cron publication or workflow registration update). "
            "Earlier failed checks remain in Actions history.", "",
        ])
    if error:
        lines.append(f"**EVIDENCE_UNAVAILABLE:** {error}")
    elif not rows:
        lines.append("No trading-day slots are due after activation and delivery grace.")
    else:
        lines.extend(["| Expected slot | Status | Evidence |", "|---|---|---|"])
        lines.extend(f"| {r['slot']} | {r['status']} | {r['detail']} |" for r in rows)
    lines.extend(["", "This watchdog never dispatches or reruns trading. It shares GitHub's scheduling "
                  "limitations and cannot guarantee delivery. The last seven calendar days are checked. "
                  "Missing holiday years follow the "
                  "engine's weekday-only fallback."])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    receipt_parser = sub.add_parser("receipt")
    receipt_parser.add_argument("--output", type=Path, required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument('--runtime-url', help='Read-only operational health endpoint; never dispatches trading')
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.command == "receipt":
        args.output.write_text(json.dumps(receipt_document(os.environ, now)), encoding="utf-8")
        return 0
    rows, error, scope = [], None, {}
    try:
        repository = os.environ["GITHUB_REPOSITORY"]
        branch = os.environ["DEFAULT_BRANCH"]
        token = os.environ["GH_TOKEN"]
        rows = check(now, activation_time(), GitHub(repository, token), repository, branch, scope=scope)
    except (EvidenceError, KeyError, ValueError, OSError, subprocess.SubprocessError) as exc:
        error = str(exc) if isinstance(exc, EvidenceError) else "Monitoring prerequisites unavailable"
    report = summary(rows, error, scope)
    runtime = inspect_runtime(args.runtime_url) if args.runtime_url else None
    if runtime:
        report += f"\n## Live execution and account health\n\n**{runtime['status']}**: {runtime['detail']}\n"
    print(report)
    if os.getenv("GITHUB_ACTIONS") == "true":
        failures = ([f"EVIDENCE_UNAVAILABLE: {error}"] if error else [
            f"{row['status']}: {row['slot']}: {row['detail']}"
            for row in rows if row["status"] not in GOOD_STATUSES
        ])
        if runtime and runtime['status'] != 'HEALTHY':
            failures.append(f"LIVE_RUNTIME_{runtime['status']}: {runtime['detail']}")
        for message in failures:
            escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::error title=NSE scheduler health::{escaped}")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(report)
    return int(bool(error) or any(row["status"] not in GOOD_STATUSES for row in rows)
               or bool(runtime and runtime['status'] != 'HEALTHY'))


if __name__ == "__main__":
    raise SystemExit(main())
