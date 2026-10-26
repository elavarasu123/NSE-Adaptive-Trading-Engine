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
cron. It allows 20 minutes for delivery, distinguishes pending runs from failed
or over-45-minute runs, and checks receipts so a late earlier trigger cannot
satisfy the following hour's slot. Only schedule events on the default branch
count; a successful manual run does not prove scheduler health.

Inspect the watchdog's Actions summary for `MISSING`, `FAILED`, `TIMED_OUT`,
`DUPLICATE`, or `EVIDENCE_UNAVAILABLE`. These make the watchdog fail and can use
your existing GitHub Actions failure notifications. If the workflow is disabled,
enable **NSE Paper Engine** in Actions. For unavailable evidence, check token
permissions, artifact availability and network access. It does not create
issues or send messages to external services.

A successful workflow receipt is delivery evidence, not proof of engine
execution: inspect the session-guard result and runtime heartbeat/checkpoint in
the shared state. GitHub can delay/drop both workflows, so this watchdog is not
an independent uptime guarantee. Holiday coverage follows the engine's calendar;
missing holiday years currently fall back to weekdays only.

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

