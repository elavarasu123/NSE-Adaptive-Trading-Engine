from dataclasses import dataclass, asdict

from sqlalchemy.orm import Session

from .models import Position


@dataclass
class PortfolioRisk:
    open_positions: int
    market_value: float
    exposure_pct: float
    capital_at_risk: float
    risk_pct: float
    remaining_risk: float
    remaining_exposure: float


@dataclass
class RiskGate:
    approved: bool
    reason: str
    proposed_risk: float
    total_risk_after: float
    proposed_value: float
    total_exposure_after: float


def portfolio_risk(
    db: Session,
    capital: float,
):
    positions = (
        db.query(Position)
        .filter(Position.status == "OPEN")
        .all()
    )

    market_value = 0.0
    capital_at_risk = 0.0

    for p in positions:
        market_value += (
            p.quantity * p.current_price
        )

        risk_per_share = max(
            p.avg_price - p.stop_price,
            0,
        )

        capital_at_risk += (
            p.quantity * risk_per_share
        )

    exposure_pct = (
        market_value / capital * 100
        if capital > 0
        else 0
    )

    risk_pct = (
        capital_at_risk / capital * 100
        if capital > 0
        else 0
    )

    return PortfolioRisk(
        open_positions=len(positions),
        market_value=round(
            market_value,
            2,
        ),
        exposure_pct=round(
            exposure_pct,
            2,
        ),
        capital_at_risk=round(
            capital_at_risk,
            2,
        ),
        risk_pct=round(
            risk_pct,
            3,
        ),
        remaining_risk=0,
        remaining_exposure=0,
    )


def validate_new_trade(
    db: Session,
    capital: float,
    proposed_value: float,
    proposed_risk: float,
    max_positions: int = 6,
    max_total_risk_pct: float = 0.04,
    max_total_exposure_pct: float = 0.70,
):
    current = portfolio_risk(
        db,
        capital,
    )

    max_risk = (
        capital * max_total_risk_pct
    )

    max_exposure = (
        capital
        * max_total_exposure_pct
    )

    risk_after = (
        current.capital_at_risk
        + proposed_risk
    )

    exposure_after = (
        current.market_value
        + proposed_value
    )

    if current.open_positions >= max_positions:
        return RiskGate(
            False,
            "Maximum open positions reached",
            proposed_risk,
            risk_after,
            proposed_value,
            exposure_after,
        )

    if risk_after > max_risk:
        return RiskGate(
            False,
            "Portfolio risk limit exceeded",
            proposed_risk,
            risk_after,
            proposed_value,
            exposure_after,
        )

    if exposure_after > max_exposure:
        return RiskGate(
            False,
            "Portfolio exposure limit exceeded",
            proposed_risk,
            risk_after,
            proposed_value,
            exposure_after,
        )

    return RiskGate(
        True,
        "PASS",
        proposed_risk,
        risk_after,
        proposed_value,
        exposure_after,
    )


def portfolio_risk_dict(
    db: Session,
    capital: float,
):
    result = portfolio_risk(
        db,
        capital,
    )

    max_risk = capital * 0.04
    max_exposure = capital * 0.70

    result.remaining_risk = round(
        max(
            max_risk
            - result.capital_at_risk,
            0,
        ),
        2,
    )

    result.remaining_exposure = round(
        max(
            max_exposure
            - result.market_value,
            0,
        ),
        2,
    )

    return asdict(result)
