from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class TechnicalSnapshot:
    close: float
    sma20: Optional[float]
    sma50: Optional[float]
    sma200: Optional[float]
    rsi14: Optional[float]
    momentum_1m: Optional[float]
    momentum_3m: Optional[float]
    momentum_6m: Optional[float]
    volatility_20d: Optional[float]
    trend_score: float


def _safe(value):
    if value is None:
        return None

    try:
        if np.isnan(value):
            return None
    except TypeError:
        pass

    return round(float(value), 4)


def rsi(series: pd.Series, period: int = 14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    result = 100 - (100 / (1 + rs))

    return result


def build_snapshot(df: pd.DataFrame) -> TechnicalSnapshot:
    if df is None or df.empty:
        raise ValueError("No historical market data supplied")

    data = df.copy()

    data.columns = [str(c).lower() for c in data.columns]

    if "close" not in data.columns:
        raise ValueError("Historical data does not contain close prices")

    close = pd.to_numeric(data["close"], errors="coerce").dropna()

    if len(close) < 20:
        raise ValueError("At least 20 valid sessions are required")

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    rsi14 = rsi(close, 14)

    returns = close.pct_change()

    volatility20 = returns.rolling(20).std() * np.sqrt(252)

    def momentum(days):
        if len(close) <= days:
            return None

        previous = close.iloc[-days - 1]

        if previous == 0:
            return None

        return (close.iloc[-1] / previous) - 1

    latest = float(close.iloc[-1])

    score = 0.0

    # Simple transparent V0.2 scoring scaffold.
    # These weights are hypotheses to validate, not claims of alpha.

    if len(sma20.dropna()) and latest > sma20.iloc[-1]:
        score += 20

    if len(sma50.dropna()) and latest > sma50.iloc[-1]:
        score += 20

    if len(sma200.dropna()) and latest > sma200.iloc[-1]:
        score += 20

    m1 = momentum(21)
    m3 = momentum(63)
    m6 = momentum(126)

    if m1 is not None and m1 > 0:
        score += 10

    if m3 is not None and m3 > 0:
        score += 15

    if m6 is not None and m6 > 0:
        score += 15

    return TechnicalSnapshot(
        close=round(latest, 2),
        sma20=_safe(sma20.iloc[-1]),
        sma50=_safe(sma50.iloc[-1]) if len(close) >= 50 else None,
        sma200=_safe(sma200.iloc[-1]) if len(close) >= 200 else None,
        rsi14=_safe(rsi14.iloc[-1]),
        momentum_1m=_safe(m1),
        momentum_3m=_safe(m3),
        momentum_6m=_safe(m6),
        volatility_20d=_safe(volatility20.iloc[-1]),
        trend_score=round(score, 2),
    )
