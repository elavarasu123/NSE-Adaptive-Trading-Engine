# Execution recovery and external monitoring

The read-only GitHub watchdog checks two independent things: verified delivery
within the 20-minute grace (including runner receipt time), and current live
execution/data/account health. Successful workflows delivered hours late are
reported as `LATE_DELIVERY`, and a current checkpoint cannot mask an overdue
runtime. A manual recovery can restore live health while historical late
deliveries remain visible failures. The watchdog fetches the public operational
health endpoint without credentials and never dispatches trading or reads Neon.

The nominal cycles remain 09:20–15:20 IST hourly and 16:05 IST post-close.
Additional GitHub Actions schedule deliveries at 09:27 and every 20 minutes from
09:37 through 16:17 recover the latest slot if no healthy completion covers it.
Completed slots skip data downloads and execution. The same concurrency group
serializes all requests, with a second due check before execution. Manual runs
retain explicit validation behavior. Recovery never replays historical fills or
forces after-hours execution. A degraded/error cycle remains eligible to retry.

Recovered slots are reported separately from original scheduled deliveries.
GitHub can delay **all** its schedule events; these recovery triggers cannot
provide an independent scheduling guarantee. Actions remains the only engine
execution scheduler. The read-only watchdog never dispatches trading.

The active engine definition is `.github/workflows/nse-paper-engine.yml`.
It replaces the earlier `paper-engine.yml` registration after GitHub again
reported an orphaned queued run with zero jobs and rejected both cancellation
endpoints with HTTP 409. The same concurrency group and database lock protect
execution across registrations. Retain the old run as diagnostic evidence;
disable its old registration once the replacement is active. A replacement
manual run must be verified independently; file renaming is not proof that
scheduled delivery is fixed.

The history refresher retries missing/stale symbols in smaller batches, retains
usable cache files if a response is older or truncated, excludes partial daily
candles, and writes CSV files atomically. A stock with fewer than 300 settled
sessions is reported as insufficient history, distinct from stale data. Symbols
still unavailable after retries remain excluded; data is never invented.

If a long-range response is stale, a recent-range request is also tried. Recent
bars are appended only if adjusted OHLC matches the existing cache across at
least three overlapping sessions. Split/restatement mismatches are rejected;
the model's historical price basis is never silently mixed.

If Yahoo remains stale, an optional official NSE cash bhavcopy fallback checks
the expected session plus three preceding NSE sessions. Only EQ-series records
with all four sessions and matching historical OHLC may extend an existing
cache. Files use the official archive schema, exact session validation, and size
limits. A verified NSE corporate-action manifest is mandatory; ex-date symbols
are excluded until a full adjusted history is available. Source failures,
missing records and adjustment mismatches stay visible
in persisted repair evidence and leave cached prices untouched. This supplies
settled research bars, never live execution quotes.

A different constant adjusted price basis may be reconciled only when all 12
OHLC values across three overlapping sessions match the same positive factor.
Only incoming bars are converted; existing cached history is preserved. The
factor is recorded for audit. Changing/nonconstant factors and ex-date symbols
remain excluded, and volume is never scaled.

## Independent observer configuration

Create an HTTPS monitor in a service **outside GitHub Actions**:

* URL: `https://nse-adaptive-trading-engine.onrender.com/api/operations/execution-health`
* Method: GET (HEAD is also supported).
* Expected HTTP status: 200. HTTP 503 indicates unproven execution/delivery or
  failed data/account checks. The response includes the specific reason.
* Suggested check interval: 5 minutes; notify after two consecutive failures.
* Configure an explicit notification destination and test both failure and
  recovery delivery before calling alerts verified.
* Do not use `/health`: that proves the web process responds, not paper execution.
* Do not use the observer to dispatch/rerun trading or modify shared state.

`/api/operations/health` additionally requires independent monitoring verification
for unattended readiness. It cannot become READY merely because schedule
recovery works. Monitoring remains UNCONFIGURED until an actual service/account
and destination are supplied and integration is verified. No external account
or alert has been created by this change.

If GitHub still delivers all events late, resolving guaranteed execution timing
requires changing the GitHub-only scheduling constraint or GitHub-side recovery.
Neither a green manual run nor a changed status label proves that guarantee.
