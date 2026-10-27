from datetime import (
    datetime,
    timezone,
)

import math

from fastapi import HTTPException
from sqlalchemy.orm import Session
from .transactions import persist, atomic_paper_operation, exclusive_cycle

from .models import (
    Portfolio,
    Position,
    PaperTrade,
    Journal,
)
from .risk import build_trade_plan
from .portfolio_risk import (
    validate_new_trade,
)


def get_portfolio(
    db: Session,
):
    portfolio = (
        db.query(Portfolio)
        .first()
    )

    if not portfolio:
        portfolio = Portfolio(
            id=1,
            initial_capital=100000,
            cash=100000,
            realized_pnl=0,
        )

        db.add(portfolio)
        persist(db)
        db.refresh(portfolio)

    return portfolio


def _bps(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number < 10000:
        raise HTTPException(400, "Invalid paper execution cost assumption")
    return number / 10000.0


@exclusive_cycle
@atomic_paper_operation
def paper_buy(
    db: Session,
    provider,
    symbol: str,
    exposure_multiplier: float = 1.0,
    slippage_bps: float = 0.0,
    fee_bps: float = 0.0,
    reason: str = "ATR_RISK_ENTRY",
):
    symbol = (
        symbol
        .upper()
        .replace(".NS", "")
    )

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

    portfolio = get_portfolio(
        db
    )

    try:
        history = provider.history(
            symbol,
            period="1y",
        )

        quote = provider.quote(symbol)
        plan = build_trade_plan(
            history,
            entry_price=float(quote.price),
            cash=portfolio.cash,
            capital=
                portfolio.initial_capital,
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

    # BUY slippage is adverse.
    fill_price = round(
        plan.entry
        * (
            1
            + _bps(
                slippage_bps
            )
        ),
        2,
    )

    fee_rate = _bps(
        fee_bps
    )

    # Ensure the original quantity still fits
    # after simulated execution friction.
    max_by_cash = int(
        float(portfolio.cash)
        // (
            fill_price
            * (1 + fee_rate)
        )
    )

    quantity = min(
        int(plan.quantity),
        max_by_cash,
    )

    if quantity < 1:
        raise HTTPException(
            400,
            "Insufficient paper cash "
            "after simulated costs",
        )

    gross = round(
        quantity * fill_price,
        2,
    )

    entry_fee = round(
        gross * fee_rate,
        2,
    )

    total_cost = round(
        gross + entry_fee,
        2,
    )

    proposed_risk = round(
        quantity
        * max(
            fill_price
            - plan.stop,
            0,
        ),
        2,
    )

    portfolio_gate = (
        validate_new_trade(
            db=db,
            capital=
                portfolio.initial_capital,
            proposed_value=gross,
            proposed_risk=
                proposed_risk,
        )
    )

    if not portfolio_gate.approved:
        raise HTTPException(
            400,
            portfolio_gate.reason,
        )

    if (
        total_cost
        > portfolio.cash
    ):
        raise HTTPException(
            400,
            "Insufficient paper cash",
        )

    portfolio.cash = round(
        portfolio.cash
        - total_cost,
        2,
    )

    position = Position(
        symbol=symbol,
        quantity=quantity,
        avg_price=fill_price,
        current_price=fill_price,
        stop_price=plan.stop,
        target_price=plan.target,
        status="OPEN",
    )

    db.add(position)

    db.add(
        PaperTrade(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=fill_price,
            value=gross,
            realized_pnl=0,
            reason=reason,
        )
    )

    db.add(
        Journal(
            kind="PAPER_BUY",
            message=(
                f"{symbol}: BUY "
                f"{quantity} @ "
                f"₹{fill_price}; "
                f"signal ₹{plan.entry}; "
                f"stop ₹{plan.stop}; "
                f"target ₹{plan.target}; "
                f"fee ₹{entry_fee}; "
                f"slippage="
                f"{slippage_bps}bps; "
                f"risk ₹{proposed_risk}"
            ),
        )
    )

    persist(db)
    db.refresh(position)

    return position


@exclusive_cycle
@atomic_paper_operation
def paper_sell(
    db: Session,
    provider,
    symbol: str,
    reason: str = "MANUAL",
    slippage_bps: float = 0.0,
    fee_bps: float = 0.0,
    entry_fee: float = 0.0,
    price_override: float | None = None,
):
    symbol = (
        symbol
        .upper()
        .replace(".NS", "")
    )

    position = (
        db.query(Position)
        .filter(
            Position.symbol == symbol,
            Position.status == "OPEN",
        )
        .first()
    )

    if not position:
        raise HTTPException(
            404,
            "No open position",
        )

    portfolio = get_portfolio(
        db
    )

    if price_override is None:
        quote = provider.quote(
            symbol
        )

        market_price = float(
            quote.price
        )
    else:
        market_price = float(
            price_override
        )

    if not math.isfinite(market_price) or market_price <= 0:
        raise HTTPException(400, "Invalid observed exit price")

    # SELL slippage is adverse.
    fill_price = round(
        market_price
        * (
            1
            - _bps(
                slippage_bps
            )
        ),
        2,
    )

    gross = round(
        position.quantity
        * fill_price,
        2,
    )

    exit_fee = round(
        gross
        * _bps(
            fee_bps
        ),
        2,
    )

    proceeds = round(
        gross - exit_fee,
        2,
    )

    gross_pnl = (
        (
            fill_price
            - position.avg_price
        )
        * position.quantity
    )

    net_pnl = round(
        gross_pnl
        - float(entry_fee or 0)
        - exit_fee,
        2,
    )

    portfolio.cash = round(
        portfolio.cash
        + proceeds,
        2,
    )

    portfolio.realized_pnl = (
        round(
            portfolio.realized_pnl
            + net_pnl,
            2,
        )
    )

    position.current_price = (
        fill_price
    )

    position.status = "CLOSED"

    position.closed_at = (
        datetime.now(
            timezone.utc
        )
    )

    db.add(
        PaperTrade(
            symbol=symbol,
            side="SELL",
            quantity=
                position.quantity,
            price=fill_price,
            value=gross,
            realized_pnl=
                net_pnl,
            reason=reason,
        )
    )

    db.add(
        Journal(
            kind="PAPER_SELL",
            message=(
                f"{symbol}: SELL "
                f"{position.quantity} @ "
                f"₹{fill_price}; "
                f"net PnL ₹{net_pnl}; "
                f"entry fee "
                f"₹{entry_fee}; "
                f"exit fee "
                f"₹{exit_fee}; "
                f"reason={reason}"
            ),
        )
    )

    persist(db)

    return {
        "symbol":
            symbol,
        "quantity":
            position.quantity,
        "exit":
            fill_price,
        "grossProceeds":
            gross,
        "exitFee":
            exit_fee,
        "realizedPnl":
            net_pnl,
        "reason":
            reason,
    }


@exclusive_cycle
@atomic_paper_operation
def monitor_positions(
    db: Session,
    provider,
):
    """
    Backward-compatible manual position monitor.

    V1.0 automatic orders use execution.py,
    which tracks entry costs as well.
    """
    positions = (
        db.query(Position)
        .filter(
            Position.status == "OPEN"
        )
        .all()
    )

    events = []

    for position in positions:
        try:
            quote = provider.quote(
                position.symbol
            )

        except Exception as exc:
            events.append(
                {
                    "symbol":
                        position.symbol,
                    "action":
                        "DATA_ERROR",
                    "message":
                        str(exc),
                }
            )

            continue

        position.current_price = (
            quote.price
        )

        if (
            quote.price
            <= position.stop_price
        ):
            result = paper_sell(
                db,
                provider,
                position.symbol,
                reason="STOP_LOSS",
                price_override=
                    quote.price,
            )

            events.append(
                {
                    "symbol":
                        position.symbol,
                    "action":
                        "SELL",
                    "reason":
                        "STOP_LOSS",
                    "result":
                        result,
                }
            )

        elif (
            quote.price
            >= position.target_price
        ):
            result = paper_sell(
                db,
                provider,
                position.symbol,
                reason="TARGET",
                price_override=
                    quote.price,
            )

            events.append(
                {
                    "symbol":
                        position.symbol,
                    "action":
                        "SELL",
                    "reason":
                        "TARGET",
                    "result":
                        result,
                }
            )

        else:
            events.append(
                {
                    "symbol":
                        position.symbol,
                    "action":
                        "HOLD",
                    "price":
                        quote.price,
                }
            )

    persist(db)

    return events
