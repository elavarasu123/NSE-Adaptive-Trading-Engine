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
