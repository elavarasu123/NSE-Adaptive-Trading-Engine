from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Portfolio, Position, PaperTrade, Journal
from .risk import build_trade_plan
from .portfolio_risk import validate_new_trade


def get_portfolio(db: Session):
    portfolio = db.query(Portfolio).first()

    if not portfolio:
        portfolio = Portfolio(
            initial_capital=100000,
            cash=100000,
            realized_pnl=0,
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)

    return portfolio


def paper_buy(
    db: Session,
    provider,
    symbol: str,
    exposure_multiplier: float = 1.0,
):
    symbol = symbol.upper().replace(".NS", "")

    existing = (
        db.query(Position)
        .filter(
            Position.symbol == symbol,
            Position.status == "OPEN",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            400,
            "Position already open",
        )

    portfolio = get_portfolio(db)

    try:
        history = provider.history(
            symbol,
            period="1y",
        )

        plan = build_trade_plan(
            history,
            cash=portfolio.cash,
            capital=portfolio.initial_capital,
            exposure_multiplier=
                exposure_multiplier,
        )

    except Exception as exc:
        raise HTTPException(
            400,
            f"Risk plan unavailable: {exc}",
        )

    if not plan.valid:
        raise HTTPException(
            400,
            plan.reason,
        )

    portfolio_gate = validate_new_trade(
        db=db,
        capital=portfolio.initial_capital,
        proposed_value=plan.position_value,
        proposed_risk=plan.capital_risk,
    )

    if not portfolio_gate.approved:
        raise HTTPException(
            400,
            portfolio_gate.reason,
        )

    cost = round(
        plan.quantity * plan.entry,
        2,
    )

    if cost > portfolio.cash:
        raise HTTPException(
            400,
            "Insufficient paper cash",
        )

    portfolio.cash = round(
        portfolio.cash - cost,
        2,
    )

    position = Position(
        symbol=symbol,
        quantity=plan.quantity,
        avg_price=plan.entry,
        current_price=plan.entry,
        stop_price=plan.stop,
        target_price=plan.target,
        status="OPEN",
    )

    db.add(position)

    db.add(
        PaperTrade(
            symbol=symbol,
            side="BUY",
            quantity=plan.quantity,
            price=plan.entry,
            value=cost,
            realized_pnl=0,
            reason="ATR_RISK_ENTRY",
        )
    )

    db.add(
        Journal(
            kind="PAPER_BUY",
            message=(
                f"{symbol}: BUY "
                f"{plan.quantity} @ "
                f"₹{plan.entry}; "
                f"stop ₹{plan.stop}; "
                f"target ₹{plan.target}; "
                f"risk ₹{plan.capital_risk}; "
                f"RR {plan.reward_risk}"
            ),
        )
    )

    db.commit()
    db.refresh(position)

    return position


def paper_sell(
    db: Session,
    provider,
    symbol: str,
    reason: str = "MANUAL",
):
    symbol = symbol.upper().replace(".NS", "")

    position = (
        db.query(Position)
        .filter(
            Position.symbol == symbol,
            Position.status == "OPEN",
        )
        .first()
    )

    if not position:
        raise HTTPException(404, "No open position")

    portfolio = get_portfolio(db)
    quote = provider.quote(symbol)

    proceeds = round(position.quantity * quote.price, 2)

    pnl = round(
        (quote.price - position.avg_price) * position.quantity,
        2,
    )

    portfolio.cash = round(portfolio.cash + proceeds, 2)
    portfolio.realized_pnl = round(
        portfolio.realized_pnl + pnl,
        2,
    )

    position.current_price = quote.price
    position.status = "CLOSED"
    position.closed_at = datetime.utcnow()

    db.add(
        PaperTrade(
            symbol=symbol,
            side="SELL",
            quantity=position.quantity,
            price=quote.price,
            value=proceeds,
            realized_pnl=pnl,
            reason=reason,
        )
    )

    db.add(
        Journal(
            kind="PAPER_SELL",
            message=(
                f"{symbol}: SELL {position.quantity} @ ₹{quote.price}; "
                f"PnL ₹{pnl}; reason={reason}"
            ),
        )
    )

    db.commit()

    return {
        "symbol": symbol,
        "quantity": position.quantity,
        "exit": quote.price,
        "realizedPnl": pnl,
        "reason": reason,
    }


def monitor_positions(db: Session, provider):
    positions = (
        db.query(Position)
        .filter(Position.status == "OPEN")
        .all()
    )

    events = []

    for position in positions:
        try:
            quote = provider.quote(position.symbol)
        except Exception as exc:
            events.append(
                {
                    "symbol": position.symbol,
                    "action": "DATA_ERROR",
                    "message": str(exc),
                }
            )
            continue

        position.current_price = quote.price

        if quote.price <= position.stop_price:
            result = paper_sell(
                db,
                provider,
                position.symbol,
                reason="STOP_LOSS",
            )

            events.append(
                {
                    "symbol": position.symbol,
                    "action": "SELL",
                    "reason": "STOP_LOSS",
                    "result": result,
                }
            )

        elif quote.price >= position.target_price:
            result = paper_sell(
                db,
                provider,
                position.symbol,
                reason="TARGET",
            )

            events.append(
                {
                    "symbol": position.symbol,
                    "action": "SELL",
                    "reason": "TARGET",
                    "result": result,
                }
            )

        else:
            events.append(
                {
                    "symbol": position.symbol,
                    "action": "HOLD",
                    "price": quote.price,
                }
            )

    db.commit()

    return events
