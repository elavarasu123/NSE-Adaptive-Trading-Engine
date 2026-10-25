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
