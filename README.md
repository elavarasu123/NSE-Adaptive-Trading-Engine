# NSE Adaptive Trading Engine

V0.1 paper-trading foundation for Indian cash equities.

- Persistent one-time ₹1,00,000 paper portfolio
- FastAPI + SQLite backend
- Frozen prediction ledger
- 5D/10D/20D/30D evaluation model
- Deterministic risk sizing
- Replaceable market-data provider
- Responsive React dashboard

Research/paper trading only. Demo prices are not live NSE data.

## Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Frontend
```bash
cd frontend
npm install
npm run dev
```

## Paper trades on the dashboard

Open **Trades & orders** below the Paper Account cards, or use the **Portfolio
and trades** navigation button. Tap **Recent trade fills**, **Order decisions**,
or **Open positions** to inspect the account.

Trade history uses the existing read-only `/api/trades` endpoint (up to 200
recent buy/sell fills). Automatic order decisions use `/api/execution/status`
(up to 100, including rejections). Open positions use `/api/dashboard`.
Predictions are observations; rejected orders, including PANIC blocks, are not
trade fills. A zero-fill account can therefore be correct. Loading failures are
shown as unavailable evidence rather than an empty account; use **Refresh
activity** to retry. Data refreshes approximately every 30 seconds.

Frontend rendering checks run with `cd frontend && npm test`; the build remains
`npm run build`. The dashboard only reads account state; it cannot place orders.

## Scheduler delivery and health

The engine requests GitHub schedule events at **09:20, 10:20, 11:20,
12:20, 13:20, 14:20, 15:20 and 16:05 IST**, Monday–Friday. The existing
NSE session guard still decides whether execution is permitted. Post-close
history refresh remains at 16:05 IST. Changing cron re-registers the schedule;
it does not guarantee delivery or fix a confirmed GitHub platform cause.

`NSE Scheduler Watchdog` checks at **09:47–15:47 IST hourly and 16:37 IST**.
It uses only the built-in GitHub token (`contents: read`, `actions: read`),
never database credentials. It cannot dispatch, rerun, or execute trading.
It can also be run manually without triggering the engine.

Each engine run uploads a small `scheduler-receipt-<run>-<attempt>` artifact
before dependency installation. It contains event/cron, commit, run identity,
repository/ref and receipt time, never secrets or portfolio contents. Receipt
collection/upload failures do not stop the engine; the watchdog reports missing
evidence instead. Artifacts are retained for seven days.

The watchdog checks the last seven calendar days, excluding configured NSE
holidays/weekends and slots before the default-branch commit that changed the
cron or the workflow's more recent registration update (for example re-enabling).
Earlier failed checks remain in Actions history. It allows 20 minutes for delivery, distinguishes pending runs from failed
or over-45-minute runs, and checks receipts so a late earlier trigger cannot
satisfy the following hour's slot. Only schedule events on the default branch
count; a successful manual run does not prove scheduler health.

Inspect the watchdog's Actions summary for `MISSING`, `FAILED`, `TIMED_OUT`,
`DUPLICATE`, or `EVIDENCE_UNAVAILABLE`. These make the watchdog fail and can use
your existing GitHub Actions failure notifications. The reason is also emitted
as a GitHub annotation, so it can be read without downloading the raw log. If the workflow is disabled,
enable **NSE Paper Engine** in Actions. For unavailable evidence, check token
permissions, artifact availability and network access. It does not create
issues or send messages to external services.

A successful workflow receipt is delivery evidence, not proof of engine
execution: inspect the session-guard result and runtime heartbeat/checkpoint in
the shared state. GitHub can delay/drop both workflows, so this watchdog is not
an independent uptime guarantee. Holiday coverage follows the engine's calendar;
missing holiday years currently fall back to weekdays only.

## Shared dashboard reliability

In shared-DB, public read-only mode, `/api/reliability/status` uses the execution
checkpoint stored in Neon for market-data evidence. Render deliberately excludes
the history cache from its Docker image. Freshness is recomputed against the
currently expected settled NSE session; a missing, stale or future-dated
checkpoint is blocking. Portfolio, ledger and checkpoint integrity are still
checked against shared state. The response identifies `evidenceSource`,
`checkpointCreatedAt` and `executionSource` and marks itself `displayOnly`.

The actual trading runtime still validates its own local market history before
execution. A fresh data checkpoint does not prove an on-time scheduler heartbeat;
the watchdog checks delivery separately. `/api/runtime/activity` and
`/api/runtime/equity` use the same configured backend as `/api/runtime/status`,
preserving newest-first activity and chronological equity.

## V0.8 Runtime

The V0.8 runtime adds scheduled paper-engine execution and observability.

Safety properties:

- Paper trading only.
- No broker order API is connected.
- The original ₹1,00,000 portfolio is not recreated on each cycle.
- Prediction generation is idempotent.
- Frozen predictions are evaluated only after their forward horizons mature.
- Runtime cycles cannot automatically promote a challenger model.
- GitHub Actions is an orchestration layer, not a tick-by-tick trading server.
- GitHub Actions schedule timing may be delayed by the platform.
- Exchange-holiday validation and production-grade market data remain future work.

The scheduled workflow currently targets approximately:

- 09:20 IST
- 10:20 IST
- 11:20 IST
- 12:20 IST
- 13:20 IST
- 14:20 IST
- 15:20 IST

These cycles are research/paper observations, not live trading instructions.

## V0.8 Runtime

The V0.8 runtime adds scheduled paper-engine execution and observability.

Safety properties:

- Paper trading only.
- No broker order API is connected.
- The original ₹1,00,000 portfolio is not recreated on each cycle.
- Prediction generation is idempotent.
- Frozen predictions are evaluated only after their forward horizons mature.
- Runtime cycles cannot automatically promote a challenger model.
- GitHub Actions is an orchestration layer, not a tick-by-tick trading server.
- GitHub Actions schedule timing may be delayed by the platform.
- Exchange-holiday validation and production-grade market data remain future work.

The scheduled workflow currently targets approximately:

- 09:20 IST
- 10:20 IST
- 11:20 IST
- 12:20 IST
- 13:20 IST
- 14:20 IST
- 15:20 IST

These cycles are research/paper observations, not live trading instructions.

## V0.8 Runtime

The V0.8 runtime adds scheduled paper-engine execution and observability.

Safety properties:

- Paper trading only.
- No broker order API is connected.
- The original ₹1,00,000 portfolio is not recreated on each cycle.
- Prediction generation is idempotent.
- Frozen predictions are evaluated only after their forward horizons mature.
- Runtime cycles cannot automatically promote a challenger model.
- GitHub Actions is an orchestration layer, not a tick-by-tick trading server.
- GitHub Actions schedule timing may be delayed by the platform.
- Exchange-holiday validation and production-grade market data remain future work.

The scheduled workflow currently targets approximately:

- 09:20 IST
- 10:20 IST
- 11:20 IST
- 12:20 IST
- 13:20 IST
- 14:20 IST
- 15:20 IST

These cycles are research/paper observations, not live trading instructions.

## V0.8 Runtime

The V0.8 runtime adds scheduled paper-engine execution and observability.

Safety properties:

- Paper trading only.
- No broker order API is connected.
- The original ₹1,00,000 portfolio is not recreated on each cycle.
- Prediction generation is idempotent.
- Frozen predictions are evaluated only after their forward horizons mature.
- Runtime cycles cannot automatically promote a challenger model.
- GitHub Actions is an orchestration layer, not a tick-by-tick trading server.
- GitHub Actions schedule timing may be delayed by the platform.
- Exchange-holiday validation and production-grade market data remain future work.

The scheduled workflow currently targets approximately:

- 09:20 IST
- 10:20 IST
- 11:20 IST
- 12:20 IST
- 13:20 IST
- 14:20 IST
- 15:20 IST

These cycles are research/paper observations, not live trading instructions.

## V0.9 Reliability

V0.9 adds a fail-closed reliability layer around the paper engine.

Before a runtime cycle can generate or mature predictions, the engine checks:

- benchmark data freshness,
- one-time portfolio integrity,
- append-only forward-ledger integrity,
- previous successful runtime checkpoint fingerprints.

A normal interrupted/failed cycle can enter recovery mode and rebuild a clean checkpoint after the next successful cycle.

The dashboard labels whether the visible runtime state came from a LOCAL process or GITHUB_ACTIONS.

The cloud workflow now performs settled daily-history refresh after the regular NSE session rather than treating the 15:20 observation cycle as end-of-day data.

GitHub Actions remains a paper/research orchestrator. It is not a tick-by-tick execution service and is not connected to a live broker.

## V1.0 Automatic Paper Execution

V1.0 converts eligible frozen forward predictions into simulated paper positions.

Execution pipeline:

1. Read the latest immutable forward prediction batch.
2. Verify the frozen champion model version.
3. Apply the prediction-time regime gate.
4. Apply the existing regime-specific score threshold.
5. Build the existing ATR/structure stop and 2R target.
6. Size using original capital, cash and regime exposure.
7. Apply portfolio-wide risk/exposure limits.
8. Simulate adverse fill slippage and configurable paper transaction costs.
9. Persist the PaperOrder lifecycle.
10. Monitor stop/target exits on future runtime cycles.

Default paper assumptions:

- buy slippage: 5 bps,
- sell slippage: 5 bps,
- generic execution cost: 10 bps per side,
- maximum two new positions from one prediction batch.

These are conservative configurable simulation assumptions and are NOT representations of exact broker charges.

PANIC regime remains a complete automatic-entry block.

No live broker API is connected.

## V1.1 Shared Cloud State

V1.1 introduces a canonical PostgreSQL state store.

When `DATABASE_URL` points to PostgreSQL and
`SHARED_STATE_BACKEND=db`, the following state is shared:

- the one-time ₹1,00,000 paper portfolio,
- positions and paper trades,
- automatic PaperOrder lifecycle,
- immutable forward prediction/outcome events,
- runtime heartbeat,
- activity journal,
- equity snapshots,
- integrity checkpoint.

SQLite and JSONL remain available as a local-development fallback.

GitHub Actions no longer treats its paper-state cache as the canonical trading account. The old cache is restored only to perform the one-time migration into PostgreSQL.

## V1.2 Permanent Cloud Dashboard

V1.2 deploys the existing React dashboard and FastAPI API
as one cloud web service.

Production architecture:

GitHub Actions
    -> scheduled paper engine
    -> Neon PostgreSQL
    -> FastAPI API
    -> React dashboard
    -> permanent HTTPS dashboard

GitHub Actions and the dashboard use the same Neon
PostgreSQL database introduced in V1.1.

Safety constraints remain enforced:

- paper trading only
- one-time INR 100,000 paper capital
- no daily capital reset
- no live broker orders
- no automatic real-money execution
- no automatic model promotion

DATABASE_URL is supplied through deployment secrets and
must never be committed to Git.



## Market analysis and automatic paper adaptation

The execution cycle records real daily analysis in shared runtime activity.
`GET /api/market/analysis` supplies the dashboard with the settled data date,
benchmark indicators, actual execution regime, universe coverage, delayed Nifty
observation and learning decision. In public read-only mode, scanner, candidates,
regime and dashboard metadata use this persisted report. Missing reports return
UNAVAILABLE; stale reports suppress BUY decisions. Production never substitutes
DEMO candidates. Render neither downloads market history nor trains the policy.

One cycle shares its settled, date-bounded history/features and observed quotes
across learning, analysis, execution and marking. Partial/future daily bars are
excluded. Paper entries size against an observed five-minute delayed quote;
quote timestamps come from the actual bar, not the fetch clock. Stale/future or
invalid quotes are rejected. Yahoo remains a delayed research feed, not tick-grade
execution data. Daily signals update after settled history refresh; an intraday
quote is displayed separately and does not masquerade as a new settled signal.

The user has authorized **automatic validated paper-policy updates**. The original
score model and immutable predictions remain comparison controls. Adaptive entry
v1 can automatically tighten each non-PANIC regime's score threshold by 5 or 10
points; it never expands exposure, removes the PANIC gate, resets capital or
promotes a different score model. Existing order decisions are not retried.

Learning uses only baseline 20-session outcomes that matured strictly before the
signal date, with at least 30 training dates and 40 later validation dates and
100 outcomes in each split. Training labels crossing validation start are purged.
Two threshold candidates are compared on training data; only the chosen candidate
is evaluated on validation. Activation requires positive held-out return uplift,
positive net benchmark excess (both 95% lower bounds using 20-date block
bootstrap), and entries on at least half of validation dates. Paper slippage and
fees are deducted. This evaluates a top-two equal-weight forward-return proxy,
not a capital-constrained portfolio backtest or proof of future accuracy.

Every cycle recomputes its policy from available immutable evidence and records
its revision, thresholds and validation result before paper execution. If any
gate fails, the baseline threshold is used. With the currently unmatured forward
ledger, the correct initial status is BASELINE_RETAINED / WAITING_FOR_EVIDENCE.
The dashboard shows that explicitly rather than inventing a learned improvement.
GitHub Actions remains the sole execution scheduler and Neon the shared source.

## Operational health and atomic paper execution

`GET /api/runtime/status` now includes `operational`: execution freshness,
last successful completion, latest slot whose grace expired, next slot,
schedule provenance and independent-monitor configuration. Stored runtime
HEALTHY is a historical result; it no longer means a current cycle exists.
Manual fallback can make execution CURRENT without proving automatic delivery.
Scheduled proof is limited to the latest due slot and requires verified original
GitHub run metadata, matching cron/date, a successful completion, and attempt1.
Re-runs and prior-day jobs do not attest a new scheduled delivery. Failure to
retrieve optional provenance never stops paper trading, but stays UNVERIFIED.

`GET/HEAD /api/operations/health` is a public, read-only observer endpoint.
Unknown `/api` paths return JSON404 instead of successful dashboard HTML.
Verify the deployed JSON response when configuring a monitor. It returns
200 only when unattended execution readiness is supported by fresh execution,
data/integrity checks and current scheduled-run evidence; otherwise it returns
503 with a structured BLOCKED/DEGRADED report. A current manual run can therefore
coexist with HTTP503 for unverified automation. `/health` remains the web-service
availability endpoint used by Render; do not substitute operational readiness
as Render's startup probe. Normal in-progress checkpoint changes are UPDATING
when other integrity checks pass and the prior due slot has verified success.

The dashboard displays execution, data, integrity, scheduling and alert setup
separately. Independent alerts remain UNCONFIGURED. To add them, configure an
observer outside GitHub to check the operations endpoint, choose a notification
destination and test actual delivery. A five-minute poll adds up to five minutes
beyond the20-minute schedule grace. A watchdog using the same GitHub scheduling
service is not an independent observer. No notification is sent by this change.

Paper entry/exit helpers now share atomic transactions with their automatic
order/journal updates. Failed order persistence rolls back associated cash,
position and fill changes. A PostgreSQL transaction-scoped advisory lock on a
dedicated connection protects execution across processes (compatible with Neon
transaction pooling); losing that connection prevents subsequent Session
commits. SQLite uses a local process lock for development. These controls
supplement, rather than replace, the GitHub concurrency group.

Account reconciliation checks cash, recorded fees, trade quantities, open
positions, realized P&L and automatic-order/fill correspondence. Unexplained
changes block preflight; no balance is reset or repaired automatically. Open
positions with missing/invalid quotes retain their prior valuation, pause new
entries, and allow other valid exit checks. Incomplete risk checks yield
DEGRADED, preserve the prior last-success timestamp, and make the Actions CLI
fail visibly after recording the completed cycle/checkpoint.

Logical frozen-prediction and outcome indexes are created for new databases;
existing databases get an audited, idempotent index migration before runtime.
Duplicate/incomplete identities require manual review: migration never deletes
or overwrites evidence. Valid new forward events must include their logical
identity. Existing order prediction-ID uniqueness remains enforced.

A process failure can leave earlier forward-learning/activity stages committed
while its atomic trading stage rolled back. The existing RECOVERY_REQUIRED path
permits retry from ERROR/interrupted RUNNING only when the exclusive runtime
lock is acquired and data, ledger and account reconciliation pass. Recovery is
recorded at runtime start. Unexplained changes under a healthy saved state or
failed logical/account checks remain blocked for review. Never blindly reset
cash, delete ledger rows, or re-sign an unexplained change.

The validation workflow uses an isolated PostgreSQL16 service and temporary
SQLite state, with no Neon credentials. Run equivalent integration tests locally
with TEST_POSTGRES_URL pointing only to an explicitly disposable localhost
integrity/test_engine database. Tests create/drop isolated schemas; never supply
a production database. CI covers atomic entry/exit failure, lock contention and
loss, logical uniqueness, migration audits, degraded feeds and status semantics.
