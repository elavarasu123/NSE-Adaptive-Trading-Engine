# Proposed independent paper-worker cutover

This proposal is **inactive**. The existing GitHub-only scheduling requirement
remains in effect until the user approves a different scheduler. The separate
file `deploy/render-paper-worker.proposed.yaml` is not applied by the current
root Render Blueprint. No service has been created and no worker enabled.

## Concrete worker behavior

The proposed Render cron checks every five minutes from 03:00–10:55 UTC on
weekdays. The existing NSE calendar and market/post-close guard still apply.
Only the latest nominal slot (09:20–15:20 IST hourly, then 16:05) can execute;
completed slots skip data downloads. No old fills are replayed. The worker
refreshes settled history, then rechecks the clock and slot under the existing
PostgreSQL advisory lock before invoking the unchanged paper engine.

The worker has no HTTP listener and no broker adapter. It requires the existing
Neon account and portfolio ID 1. It cannot initialize/fund a new portfolio,
reset capital, accept force mode or run against SQLite/demo data. The Render
dashboard retains its read-only web role. Failure or incomplete risk data exits
nonzero; existing prices, signals, positions, cash and fill controls remain.

Hosting charges must be reviewed in Render before creating this service.
Cron filesystem changes may be ephemeral: each invocation validates/refetches
history rather than assuming a persistent local cache. Source availability and
execution time therefore still require monitoring; this is not a timing SLA.

## Activation sequence after approval

1. Create the proposed separate cron service with execution **disabled**. Set
   its `DATABASE_URL` privately in Render to the same existing Neon URL used by
   the engine. Do not send credentials in chat or create a new database.
2. Keep the dashboard read-only and verify the inactive worker exits DISABLED.
3. Disable the GitHub engine workflow and delivery watchdog, confirm that no
   engine job is running, then set `WORKER_EXECUTION_ENABLED=true` on the worker.
   The shared lock and final due check protect overlap during cutover, but two
   independent execution schedulers are not the intended steady state.
4. Verify a real scheduled execution: source SCHEDULED_PAPER_WORKER, expected
   settled session, current completion, matching checkpoint and reconciled
   account. Confirm later five-minute checks do not repeat the completed slot.
5. Connect an independent observer/notification destination and verify failure
   and recovery alerts. Read-only `app.scheduler_health.inspect_runtime` can
   check public JSON freshness/data/integrity without triggering execution.

The current schedule-proof fields specifically attest GitHub events. Worker
execution must not be mislabeled as verified GitHub delivery. Independent worker
provenance/alert verification remains a deployment acceptance requirement;
unattended readiness stays unverified until it is established. Do not use a
green manual run or the web `/health` route as proof of automatic execution.

Rollback: disable worker execution, wait for its active job to finish, and
re-enable the GitHub engine only. Keep the same Neon state and capital.
