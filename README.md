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

- 09:15 IST
- 10:15 IST
- 11:15 IST
- 12:15 IST
- 13:15 IST
- 14:15 IST
- 15:15 IST

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

- 09:15 IST
- 10:15 IST
- 11:15 IST
- 12:15 IST
- 13:15 IST
- 14:15 IST
- 15:15 IST

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

- 09:15 IST
- 10:15 IST
- 11:15 IST
- 12:15 IST
- 13:15 IST
- 14:15 IST
- 15:15 IST

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

- 09:15 IST
- 10:15 IST
- 11:15 IST
- 12:15 IST
- 13:15 IST
- 14:15 IST
- 15:15 IST

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

The cloud workflow now performs settled daily-history refresh after the regular NSE session rather than treating the 15:15 observation cycle as end-of-day data.

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

