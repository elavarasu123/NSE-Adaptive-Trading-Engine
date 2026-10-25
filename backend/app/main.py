from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal, get_db
from .models import (
    Portfolio,
    Position,
    Prediction,
    Journal,
    PaperTrade,
)
from .engine import scan, provider
from .trading import (
    paper_buy,
    paper_sell,
    monitor_positions,
)


Base.metadata.create_all(engine)

app = FastAPI(
    title="NSE Adaptive Trading Engine",
    version="0.2",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def initialize():
    db = SessionLocal()

    try:
        if not db.query(Portfolio).first():
            db.add(
                Portfolio(
                    initial_capital=100000,
                    cash=100000,
                    realized_pnl=0,
                )
            )

            db.add(
                Journal(
                    kind="SYSTEM",
                    message=(
                        "Initialized one-time ₹1,00,000 "
                        "paper capital."
                    ),
                )
            )

            db.commit()
    finally:
        db.close()


initialize()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "PAPER",
        "provider": provider.__class__.__name__,
        "tickByTick": False,
        "version": "0.2",
    }


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    portfolio = db.query(Portfolio).first()

    positions = (
        db.query(Position)
        .filter(Position.status == "OPEN")
        .all()
    )

    market_value = sum(
        p.quantity * p.current_price
        for p in positions
    )

    cost = sum(
        p.quantity * p.avg_price
        for p in positions
    )

    unrealized = market_value - cost

    return {
        "portfolio": {
            "initialCapital": portfolio.initial_capital,
            "cash": round(portfolio.cash, 2),
            "invested": round(market_value, 2),
            "value": round(
                portfolio.cash + market_value,
                2,
            ),
            "realizedPnl": round(
                portfolio.realized_pnl,
                2,
            ),
            "unrealizedPnl": round(
                unrealized,
                2,
            ),
            "totalPnl": round(
                portfolio.realized_pnl + unrealized,
                2,
            ),
        },
        "engine": {
            "status": "ONLINE",
            "strategy": "champion-v1",
            "regime": "NEUTRAL",
            "mode": "PAPER",
        },
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry": p.avg_price,
                "current": p.current_price,
                "stop": p.stop_price,
                "target": p.target_price,
                "status": p.status,
            }
            for p in positions
        ],
    }


@app.get("/api/candidates")
def candidates():
    return scan()


@app.post("/api/engine/run")
def run_engine(db: Session = Depends(get_db)):
    rows = scan()

    for candidate in rows:
        db.add(
            Prediction(
                symbol=candidate["symbol"],
                up=candidate["up"] / 100,
                sideways=candidate["sideways"] / 100,
                down=candidate["down"] / 100,
                confidence=candidate["score"] / 100,
                decision=candidate["decision"],
                evidence="V0.2 feature stack",
            )
        )

    db.add(
        Journal(
            kind="SCAN",
            message=f"Frozen {len(rows)} predictions.",
        )
    )

    db.commit()

    return {
        "status": "complete",
        "predictionsFrozen": len(rows),
    }


@app.get("/api/predictions")
def predictions(db: Session = Depends(get_db)):
    rows = (
        db.query(Prediction)
        .order_by(Prediction.created_at.desc())
        .limit(100)
        .all()
    )

    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "createdAt": row.created_at,
            "horizon": row.horizon,
            "up": row.up,
            "sideways": row.sideways,
            "down": row.down,
            "confidence": row.confidence,
            "decision": row.decision,
            "status": row.status,
            "version": row.version,
        }
        for row in rows
    ]


@app.post("/api/paper/buy/{symbol}")
def buy(
    symbol: str,
    db: Session = Depends(get_db),
):
    position = paper_buy(
        db,
        provider,
        symbol,
    )

    return {
        "symbol": position.symbol,
        "quantity": position.quantity,
        "entry": position.avg_price,
        "stop": position.stop_price,
        "target": position.target_price,
        "status": position.status,
    }


@app.post("/api/paper/sell/{symbol}")
def sell(
    symbol: str,
    db: Session = Depends(get_db),
):
    return paper_sell(
        db,
        provider,
        symbol,
        reason="MANUAL",
    )


@app.post("/api/paper/monitor")
def monitor(db: Session = Depends(get_db)):
    return {
        "events": monitor_positions(
            db,
            provider,
        )
    }


@app.get("/api/trades")
def trades(db: Session = Depends(get_db)):
    rows = (
        db.query(PaperTrade)
        .order_by(PaperTrade.created_at.desc())
        .limit(200)
        .all()
    )

    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "side": row.side,
            "quantity": row.quantity,
            "price": row.price,
            "value": row.value,
            "realizedPnl": row.realized_pnl,
            "reason": row.reason,
            "createdAt": row.created_at,
        }
        for row in rows
    ]
