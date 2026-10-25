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
    PredictionOutcome,
    StrategyVersion,
)
from .engine import scan, scan_report, provider
from .regime import regime_dict, detect_regime
from .portfolio_risk import portfolio_risk_dict
from .evaluation import create_checkpoints, evaluate_due_predictions, accuracy_report
from .trading import (
    paper_buy,
    paper_sell,
    monitor_positions,
)


Base.metadata.create_all(engine)
from .backtest_store import (
    load_report,
    LATEST,
    WALK_FORWARD,
)
from .history_cache import cache_stats


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

        if not db.query(StrategyVersion).filter(
            StrategyVersion.name
            == "champion-v0.2"
        ).first():
            db.add(
                StrategyVersion(
                    name="champion-v0.2",
                    role="CHAMPION",
                    description=(
                        "V0.2 research strategy: "
                        "momentum, relative strength, "
                        "market regime and deterministic "
                        "portfolio risk controls."
                    ),
                    active=True,
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


@app.get("/api/risk")
def risk_status(
    db: Session = Depends(get_db),
):
    portfolio = db.query(
        Portfolio
    ).first()

    return portfolio_risk_dict(
        db,
        portfolio.initial_capital,
    )


@app.get("/api/candidates")
def candidates():
    return scan()


@app.get("/api/scanner/report")
def scanner_report():
    return scan_report()


@app.get("/api/regime")
def market_regime():
    return regime_dict(provider)


@app.post("/api/engine/run")
def run_engine(
    db: Session = Depends(get_db),
):
    rows = scan()

    frozen = 0

    for candidate in rows:
        try:
            entry = float(
                candidate["price"]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        prediction = Prediction(
            symbol=candidate["symbol"],
            entry_price=entry,
            up=(
                candidate["up"]
                / 100
            ),
            sideways=(
                candidate["sideways"]
                / 100
            ),
            down=(
                candidate["down"]
                / 100
            ),
            confidence=(
                candidate["score"]
                / 100
            ),
            decision=candidate[
                "decision"
            ],
            raw_decision=candidate.get(
                "rawDecision",
                candidate["decision"],
            ),
            regime=candidate.get(
                "regime",
                "UNKNOWN",
            ),
            strategy_version=(
                "champion-v0.2"
            ),
            evidence=(
                "Frozen V0.2 research "
                "feature snapshot"
            ),
            frozen=True,
            status="PENDING",
        )

        db.add(prediction)
        db.flush()

        create_checkpoints(
            db,
            prediction,
        )

        frozen += 1

    db.add(
        Journal(
            kind="SCAN",
            message=(
                f"Frozen {frozen} predictions "
                f"with 5D/10D/20D/30D "
                f"checkpoints."
            ),
        )
    )

    db.commit()

    return {
        "status": "complete",
        "predictionsFrozen": frozen,
        "checkpointsCreated":
            frozen * 4,
        "strategyVersion":
            "champion-v0.2",
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
    try:
        regime = detect_regime(provider)
        exposure = regime.exposure_multiplier
    except Exception:
        exposure = 0.0

    position = paper_buy(
        db,
        provider,
        symbol,
        exposure_multiplier=exposure,
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


@app.post("/api/evaluation/run")
def run_evaluation(
    db: Session = Depends(get_db),
):
    return evaluate_due_predictions(
        db,
        provider,
    )


@app.get("/api/accuracy")
def accuracy(
    db: Session = Depends(get_db),
):
    return accuracy_report(db)


@app.get("/api/outcomes")
def outcomes(
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PredictionOutcome)
        .order_by(
            PredictionOutcome.id.desc()
        )
        .limit(500)
        .all()
    )

    return [
        {
            "id": row.id,
            "predictionId":
                row.prediction_id,
            "symbol": row.symbol,
            "horizonDays":
                row.horizon_days,
            "dueAt": row.due_at,
            "evaluatedAt":
                row.evaluated_at,
            "entryPrice":
                row.entry_price,
            "outcomePrice":
                row.outcome_price,
            "forwardReturn":
                row.forward_return,
            "predicted":
                row.predicted_class,
            "actual":
                row.actual_class,
            "correct": row.correct,
            "brierScore":
                row.brier_score,
            "status": row.status,
        }
        for row in rows
    ]


@app.get("/api/activity")
def activity(
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Journal)
        .order_by(
            Journal.created_at.desc()
        )
        .limit(100)
        .all()
    )

    return [
        {
            "id": row.id,
            "createdAt":
                row.created_at,
            "kind": row.kind,
            "message": row.message,
        }
        for row in rows
    ]


@app.get("/api/strategy")
def strategy(
    db: Session = Depends(get_db),
):
    rows = (
        db.query(StrategyVersion)
        .order_by(
            StrategyVersion.id.desc()
        )
        .all()
    )

    return [
        {
            "name": row.name,
            "role": row.role,
            "description":
                row.description,
            "active": row.active,
            "createdAt":
                row.created_at,
        }
        for row in rows
    ]


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


@app.get("/api/backtest/latest")
def backtest_latest():
    report = load_report(
        LATEST
    )

    if report is None:
        return {
            "status": "NOT_RUN",
            "message": (
                "Run scripts/"
                "run_backtest.py first."
            ),
        }

    return report


@app.get("/api/backtest/walk-forward")
def backtest_walk_forward():
    report = load_report(
        WALK_FORWARD
    )

    if report is None:
        return {
            "status": "NOT_RUN",
            "message": (
                "Run backtest with "
                "--walk-forward first."
            ),
        }

    return report


@app.get("/api/data/status")
def data_status():
    from .universe import (
        load_universe,
    )

    universe = (
        load_universe()
    )

    return {
        "universeSize":
            len(universe),
        "historyCache":
            cache_stats(),
        "researchWarning": (
            "Historical tests use "
            "current constituent "
            "membership unless a "
            "point-in-time universe "
            "snapshot is supplied."
        ),
    }


@app.get("/api/research/champion-challenger")
def champion_challenger_report():
    from pathlib import Path
    import json

    path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "data"
        / "backtests"
        / "portfolio_research.json"
    )

    if not path.exists():
        return {
            "status": "NOT_RUN",
            "message": (
                "Run scripts/"
                "run_portfolio_research.py"
            ),
        }

    return json.loads(
        path.read_text()
    )


@app.get("/api/research/signal-validation")
def signal_validation_report():
    from pathlib import Path
    import json

    path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "data"
        / "backtests"
        / "signal_validation.json"
    )

    if not path.exists():
        return {
            "status": "NOT_RUN",
            "message": (
                "Run scripts/"
                "run_signal_validation.py"
            ),
        }

    return json.loads(
        path.read_text()
    )

@app.get("/api/forward/status")
def forward_learning_status():
    from .forward_learning import learning_status

    return learning_status()


@app.get("/api/forward/predictions")
def forward_predictions():
    from .forward_learning import latest_predictions

    return {
        "predictions":
            latest_predictions()
    }


@app.post("/api/forward/run")
def run_forward_learning():
    from .forward_learning import (
        generate_predictions,
        mature_outcomes,
        learning_status,
    )

    outcomes = mature_outcomes()

    predictions = generate_predictions(
        minimum_score=65,
        top_n=10,
    )

    return {
        "outcomes":
            outcomes,
        "predictions":
            predictions,
        "status":
            learning_status(),
    }


@app.get("/api/runtime/status")
def get_runtime_status():
    from .runtime import runtime_status

    return runtime_status()


@app.post("/api/runtime/run")
def run_runtime_cycle():
    from .database import SessionLocal
    from .runtime import run_cycle

    db = SessionLocal()

    try:
        return run_cycle(db)
    finally:
        db.close()


@app.get("/api/runtime/activity")
def get_runtime_activity():
    from .runtime import (
        ACTIVITY_PATH,
        read_jsonl,
    )

    return {
        "activity":
            list(
                reversed(
                    read_jsonl(
                        ACTIVITY_PATH,
                        limit=100,
                    )
                )
            )
    }


@app.get("/api/runtime/equity")
def get_runtime_equity():
    from .runtime import (
        EQUITY_PATH,
        read_jsonl,
    )

    return {
        "equity":
            read_jsonl(
                EQUITY_PATH,
                limit=500,
            )
    }


@app.get("/api/reliability/status")
def reliability_status(
    db: Session = Depends(get_db),
):
    from .reliability import (
        reliability_report,
    )

    return reliability_report(
        db
    )


@app.get("/api/execution/status")
def paper_execution_status(
    db: Session = Depends(get_db),
):
    from .execution import (
        execution_status,
    )

    return execution_status(
        db
    )


@app.post("/api/execution/run")
def run_paper_execution(
    db: Session = Depends(get_db),
):
    from .execution import (
        run_execution_cycle,
    )
    from .market import YahooProvider

    return run_execution_cycle(
        db,
        YahooProvider(),
    )
