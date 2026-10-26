# Scheduler maintenance handoff

This focused note records scheduler maintenance, supplementing the separately
supplied ChatGPT project handoff. See README for operational steps. This note
does not establish current deployed state. Runtime state remains canonical in Neon.

## Intended schedule after this change reaches main

- GitHub Actions remains the only paper-engine execution scheduler.
- Intraday requests: 09:20, 10:20, 11:20, 12:20, 13:20, 14:20, 15:20 IST.
- Post-close request/history refresh: 16:05 IST, unchanged.
- Read-only watchdog: 09:47–15:47 IST hourly, plus 16:37 IST.
- ChatGPT explanation/coach automations are independent and have not been edited.

The cron adjustment is a re-registration/mitigation, not proof of the reason
earlier schedule events were absent. `:45` UTC was already away from the top
of the hour. GitHub scheduling can delay/drop both engine and watchdog events.

## Monitoring

The engine writes a credential-free scheduler receipt artifact per run/attempt.
Telemetry failures do not stop paper execution. The watchdog uses the built-in
GitHub token with read-only permissions, checks seven calendar days, allows
20-minute delivery grace, and identifies failed or over-45-minute runs.
Slots before cron activation on the default branch are excluded. Manual engine
runs do not satisfy scheduled slots. Unknown evidence is not reported healthy.

Health summaries describe GitHub delivery/workflow state. A successful run can
legitimately skip execution at the NSE session guard; inspect runtime evidence
before claiming execution. No automatic dispatch, rerun, issue creation, or
external messaging is implemented by the watchdog.

## Unchanged invariants

Paper/research only; one-time INR 100,000 capital; no resets; no live broker;
frozen predictions and champion; no automatic promotion; GitHub executes,
Neon stores, Render displays read-only, ChatGPT explains/alerts/teaches.

## Rollout evidence

Local tests/build and GitHub publication status are reported in the change's
handoff. The schedules become effective only after merge into the default
branch. A real schedule-event run and its runtime evidence must be checked
after rollout; a manual engine run must not be used as substitute proof.
