from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Portfolio, Position, PaperTrade, Journal
from .risk import position_size


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
    stop_pct: float = 0.06,
    target_pct: float = 0.10,
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
        raise HTTPException(400, "Position already open")

    portfolio = get_portfolio(db)
    quote = provider.quote(symbol)

    if quote.price <= 0:
        raise HTTPException(400, "Invalid market price")

    stop = round(quote.price * (1 - stop_pct), 2)
    target = round(quote.price * (1 + target_pct), 2)

    qty = position_size(
        portfolio.cash,
        quote.price,
        stop,
    )

    if qty < 1:
        raise HTTPException(400, "Risk gate rejected trade")

    cost = round(qty * quote.price, 2)

    if cost > portfolio.cash:
        raise HTTPException(400, "Insufficient paper cash")

    portfolio.cash = round(portfolio.cash - cost, 2)

    position = Position(
        symbol=symbol,
        quantity=qty,
        avg_price=quote.price,
        current_price=quote.price,
        stop_price=stop,
        target_price=target,
        status="OPEN",
    )

    db.add(position)

    db.add(
        PaperTrade(
            symbol=symbol,
            side="BUY",
            quantity=qty,
            price=quote.price,
            value=cost,
            realized_pnl=0,
            reason="ENTRY",
        )
    )

    db.add(
        Journal(
            kind="PAPER_BUY",
            message=(
                f"{symbol}: BUY {qty} @ ₹{quote.price}; "
                f"stop ₹{stop}; target ₹{target}"
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
