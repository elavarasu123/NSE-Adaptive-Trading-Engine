from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from .database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    initial_capital = Column(Float, default=100000)
    cash = Column(Float, default=100000)
    realized_pnl = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


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
    created_at = Column(DateTime, default=datetime.utcnow)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    horizon = Column(String, default="5D/10D")
    up = Column(Float)
    sideways = Column(Float)
    down = Column(Float)
    confidence = Column(Float)
    decision = Column(String)
    version = Column(String, default="champion-v1")
    evidence = Column(Text)
    frozen = Column(Boolean, default=True)
    status = Column(String, default="PENDING")


class Journal(Base):
    __tablename__ = "journal"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    kind = Column(String)
    message = Column(Text)
