from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

from .indicators import build_snapshot


@dataclass
class MarketRegime:
    name: str
    score: int
    confidence: float
    nifty_close: float
    rsi14: Optional[float]
    momentum_1m: Optional[float]
    momentum_3m: Optional[float]
    volatility_20d: Optional[float]
    above_sma20: bool
    above_sma50: bool
    above_sma200: bool
    exposure_multiplier: float
    buy_threshold: float
    reasons: list


def detect_regime(provider) -> MarketRegime:
    df = provider.history("^NSEI", period="2y")

    if df is None or df.empty:
        raise ValueError("Nifty history unavailable")

    df = df.copy()
    df.columns = [
        str(c).lower()
        for c in df.columns
    ]

    snapshot = build_snapshot(df)

    close = snapshot.close

    above20 = (
        snapshot.sma20 is not None
        and close > snapshot.sma20
    )

    above50 = (
        snapshot.sma50 is not None
        and close > snapshot.sma50
    )

    above200 = (
        snapshot.sma200 is not None
        and close > snapshot.sma200
    )

    score = 0
    reasons = []

    if above20:
        score += 1
        reasons.append("Nifty above 20DMA")
    else:
        score -= 1
        reasons.append("Nifty below 20DMA")

    if above50:
        score += 2
        reasons.append("Nifty above 50DMA")
    else:
        score -= 2
        reasons.append("Nifty below 50DMA")

    if above200:
        score += 3
        reasons.append("Nifty above 200DMA")
    else:
        score -= 3
        reasons.append("Nifty below 200DMA")

    if (
        snapshot.momentum_1m is not None
        and snapshot.momentum_1m > 0
    ):
        score += 1
        reasons.append("1M momentum positive")
    else:
        score -= 1
        reasons.append("1M momentum non-positive")

    if (
        snapshot.momentum_3m is not None
        and snapshot.momentum_3m > 0
    ):
        score += 2
        reasons.append("3M momentum positive")
    else:
        score -= 2
        reasons.append("3M momentum non-positive")

    if snapshot.rsi14 is not None:
        if 50 <= snapshot.rsi14 <= 70:
            score += 1
            reasons.append("RSI supports trend")
        elif snapshot.rsi14 < 40:
            score -= 1
            reasons.append("RSI weak")

    vol = snapshot.volatility_20d

    if vol is not None:
        if vol >= 0.30:
            score -= 3
            reasons.append("High realized volatility")
        elif vol >= 0.22:
            score -= 1
            reasons.append("Elevated realized volatility")
        elif vol < 0.16:
            score += 1
            reasons.append("Realized volatility contained")

    # Deterministic regime mapping.
    if score >= 7:
        name = "RISK_ON"
        exposure = 1.00
        threshold = 75.0

    elif score >= 2:
        name = "NEUTRAL"
        exposure = 0.75
        threshold = 80.0

    elif score >= -4:
        name = "DEFENSIVE"
        exposure = 0.40
        threshold = 88.0

    else:
        name = "PANIC"
        exposure = 0.00
        threshold = 101.0

    confidence = min(
        1.0,
        0.50 + abs(score) * 0.05,
    )

    return MarketRegime(
        name=name,
        score=score,
        confidence=round(confidence, 2),
        nifty_close=close,
        rsi14=snapshot.rsi14,
        momentum_1m=snapshot.momentum_1m,
        momentum_3m=snapshot.momentum_3m,
        volatility_20d=vol,
        above_sma20=above20,
        above_sma50=above50,
        above_sma200=above200,
        exposure_multiplier=exposure,
        buy_threshold=threshold,
        reasons=reasons,
    )


def regime_dict(provider):
    return asdict(detect_regime(provider))


def apply_regime(candidate, regime):
    """
    Keep raw stock score untouched.

    Only the final permission/decision changes.
    This lets us later test whether regime filtering helped.
    """

    result = dict(candidate)

    raw_decision = result.get(
        "decision",
        "REJECT",
    )

    result["rawDecision"] = raw_decision
    result["regime"] = regime.name
    result["regimeScore"] = regime.score
    result["exposureMultiplier"] = (
        regime.exposure_multiplier
    )

    score = float(
        result.get("score", 0)
    )

    if regime.name == "PANIC":
        result["decision"] = "REJECT"
        result["regimeGate"] = (
            "Blocked: PANIC regime"
        )

    elif score >= regime.buy_threshold:
        result["decision"] = "BUY"
        result["regimeGate"] = "PASS"

    elif score >= 65:
        result["decision"] = "WATCH"
        result["regimeGate"] = (
            f"Needs score >= "
            f"{regime.buy_threshold:.0f} "
            f"in {regime.name}"
        )

    else:
        result["decision"] = "REJECT"
        result["regimeGate"] = (
            "Below minimum quality threshold"
        )

    return result
