from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    initial_capital = Column(Float, default=100000)
    cash = Column(Float, default=100000)
    realized_pnl = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    quantity = Column(Integer)
    avg_price = Column(Float)
    current_price = Column(Float)
    stop_price = Column(Float)
    target_price = Column(Float)
    status = Column(String, default="OPEN")
    opened_at = Column(DateTime(timezone=True), default=utc_now)
    closed_at = Column(DateTime(timezone=True), nullable=True)


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    side = Column(String)
    quantity = Column(Integer)
    price = Column(Float)
    value = Column(Float)
    realized_pnl = Column(Float, default=0)
    reason = Column(String)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    entry_price = Column(Float)
    horizon = Column(String, default="5D/10D/20D/30D")

    up = Column(Float)
    sideways = Column(Float)
    down = Column(Float)
    confidence = Column(Float)

    decision = Column(String)
    raw_decision = Column(String)

    regime = Column(String)
    strategy_version = Column(
        String,
        default="champion-v0.2",
    )

    evidence = Column(Text)

    frozen = Column(Boolean, default=True)
    status = Column(String, default="PENDING")


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"

    id = Column(Integer, primary_key=True)

    prediction_id = Column(
        Integer,
        index=True,
        nullable=False,
    )

    symbol = Column(String, index=True)

    horizon_days = Column(Integer)

    due_at = Column(DateTime(timezone=True))
    evaluated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    entry_price = Column(Float)
    outcome_price = Column(Float, nullable=True)

    forward_return = Column(Float, nullable=True)

    predicted_class = Column(String)
    actual_class = Column(String, nullable=True)

    correct = Column(Boolean, nullable=True)

    brier_score = Column(Float, nullable=True)

    status = Column(String, default="PENDING")


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    id = Column(Integer, primary_key=True)

    name = Column(
        String,
        unique=True,
        index=True,
    )

    role = Column(String, default="CHAMPION")

    description = Column(Text)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )

    active = Column(Boolean, default=True)


class Journal(Base):
    __tablename__ = "journal"

    id = Column(Integer, primary_key=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )

    kind = Column(String)
    message = Column(Text)



class PaperOrder(Base):
    """
    V1.0 automatic paper-execution lifecycle.

    One frozen prediction can create at most
    one PaperOrder.
    """
    __tablename__ = "paper_orders"

    id = Column(Integer, primary_key=True)

    prediction_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    prediction_date = Column(String)

    model_version = Column(String)

    symbol = Column(
        String,
        index=True,
        nullable=False,
    )

    score = Column(Float)

    regime = Column(String)

    status = Column(
        String,
        default="PENDING",
        index=True,
    )

    quantity = Column(
        Integer,
        default=0,
    )

    signal_price = Column(Float)

    fill_price = Column(Float)

    stop_price = Column(Float)

    target_price = Column(Float)

    entry_fee = Column(
        Float,
        default=0,
    )

    exit_price = Column(
        Float,
        nullable=True,
    )

    exit_fee = Column(
        Float,
        default=0,
    )

    realized_pnl = Column(
        Float,
        default=0,
    )

    reason = Column(String)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )

    closed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
