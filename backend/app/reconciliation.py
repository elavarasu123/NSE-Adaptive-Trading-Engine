"""Read-only reconciliation: never repairs or resets account records."""
from collections import Counter
import math
from .models import Portfolio, Position, PaperTrade, PaperOrder


def reconcile_account(db):
    portfolios = db.query(Portfolio).all()
    if len(portfolios) != 1:
        return {'status': 'BROKEN', 'blocking': True, 'issues': ['Expected one paper portfolio.']}
    portfolio = portfolios[0]
    trades = db.query(PaperTrade).order_by(PaperTrade.id).all()
    orders = db.query(PaperOrder).all()
    positions = db.query(Position).filter_by(status='OPEN').all()
    issues, quantities, open_quantities = [], Counter(), Counter()
    cash, realized = float("nan"), 0.
    automatic_buys, order_buys, sells, order_sells = Counter(), Counter(), Counter(), Counter()
    try:
        cash = float(portfolio.initial_capital)
        for trade in trades:
            if trade.side not in {'BUY', 'SELL'} or trade.quantity <= 0 or trade.price <= 0 or trade.value < 0 or abs(trade.value - round(trade.quantity * trade.price, 2)) > .02 or not all(
                math.isfinite(float(value)) for value in [trade.price, trade.value, trade.realized_pnl]):
                raise ValueError('Invalid trade accounting fields')
            sign = 1 if trade.side == 'BUY' else -1
            quantities[trade.symbol] += sign * trade.quantity
            cash -= sign * trade.value
            realized += trade.realized_pnl
            key = (trade.symbol, trade.quantity, round(trade.price, 2))
            if trade.side == 'BUY' and trade.reason == 'AUTO_FROZEN_PREDICTION':
                automatic_buys[key] += 1
            if trade.side == 'SELL':
                sells[key] += 1
        for order in orders:
            if order.status not in {'FILLED', 'CLOSED'}:
                continue
            if order.quantity <= 0 or float(order.fill_price) <= 0 or not math.isfinite(float(order.fill_price)) or any(not math.isfinite(float(fee or 0)) or float(fee or 0) < 0 for fee in [order.entry_fee, order.exit_fee]):
                raise ValueError('Invalid filled order accounting fields')
            order_buys[(order.symbol, order.quantity, round(order.fill_price, 2))] += 1
            cash -= float(order.entry_fee or 0)
            if order.status == 'CLOSED':
                cash -= float(order.exit_fee or 0)
                order_sells[(order.symbol, order.quantity, round(float(order.exit_price), 2))] += 1
            elif not any(p.symbol == order.symbol and p.quantity == order.quantity for p in positions):
                issues.append('Filled order has no matching open position: ' + order.symbol)
        for position in positions:
            open_quantities[position.symbol] += position.quantity
        if {s: q for s, q in quantities.items() if q} != dict(open_quantities):
            issues.append('Trade quantities do not reconcile with open positions.')
        if automatic_buys != order_buys:
            issues.append('Automatic buy fills do not reconcile with paper orders.')
        if order_sells - sells:
            issues.append('Closed orders have missing sell fills.')
        if not all(math.isfinite(float(x)) for x in [cash, portfolio.cash, portfolio.realized_pnl, realized]):
            raise ValueError('Non-finite account balance')
        if abs(round(cash, 2) - portfolio.cash) > .02:
            issues.append('Cash does not reconcile with trade values and recorded order fees.')
        if abs(round(realized, 2) - portfolio.realized_pnl) > .02:
            issues.append('Realized P&L does not reconcile with sell fills.')
    except (TypeError, ValueError):
        issues.append('Invalid or incomplete accounting data; manual review required.')
    return {'status': 'BROKEN' if issues else 'OK', 'blocking': bool(issues), 'issues': issues,
            'expectedCash': round(cash, 2) if math.isfinite(cash) else None,
            'actualCash': portfolio.cash if portfolio.cash is not None and math.isfinite(portfolio.cash) else None, 'trades': len(trades), 'orders': len(orders)}
