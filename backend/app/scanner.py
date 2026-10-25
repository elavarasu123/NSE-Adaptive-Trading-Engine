from dataclasses import asdict
from typing import Dict, List

import numpy as np
import pandas as pd

from .indicators import build_snapshot


DEFAULT_UNIVERSE = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "ICICIBANK",
    "INFY",
    "SBIN",
    "BHARTIARTL",
    "LT",
    "ITC",
    "AXISBANK",
    "KOTAKBANK",
    "MARUTI",
    "SUNPHARMA",
    "TITAN",
    "BAJFINANCE",
]


def _number(value, digits=4):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return round(float(value), digits)


def _return(close: pd.Series, sessions: int):
    close = close.dropna()

    if len(close) <= sessions:
        return None

    old = float(close.iloc[-sessions - 1])
    new = float(close.iloc[-1])

    if old <= 0:
        return None

    return (new / old) - 1


def _volume_metrics(df: pd.DataFrame):
    if "volume" not in df.columns:
        return None, None

    volume = pd.to_numeric(
        df["volume"],
        errors="coerce",
    ).dropna()

    if len(volume) < 20:
        return None, None

    avg20 = float(volume.tail(20).mean())

    if avg20 <= 0:
        return None, None

    latest = float(volume.iloc[-1])

    return avg20, latest / avg20


def _position_52w(close: pd.Series):
    values = close.dropna().tail(252)

    if values.empty:
        return None

    low = float(values.min())
    high = float(values.max())
    latest = float(values.iloc[-1])

    if high <= low:
        return None

    return (latest - low) / (high - low)


def _score(
    snapshot,
    rs_3m,
    rs_6m,
    position_52w,
    volume_ratio,
):
    """
    Transparent V0.2 research score.

    This is a hypothesis to test, not a proven alpha model.
    """

    score = 0.0

    # Trend structure: 30 points
    if snapshot.sma20 and snapshot.close > snapshot.sma20:
        score += 8

    if snapshot.sma50 and snapshot.close > snapshot.sma50:
        score += 10

    if snapshot.sma200 and snapshot.close > snapshot.sma200:
        score += 12

    # Absolute momentum: 25 points
    if snapshot.momentum_1m is not None:
        if snapshot.momentum_1m > 0:
            score += 5

    if snapshot.momentum_3m is not None:
        if snapshot.momentum_3m > 0:
            score += 8

    if snapshot.momentum_6m is not None:
        if snapshot.momentum_6m > 0:
            score += 12

    # Relative strength vs Nifty: 25 points
    if rs_3m is not None and rs_3m > 0:
        score += 10

    if rs_6m is not None and rs_6m > 0:
        score += 15

    # 52-week location: 10 points
    if position_52w is not None:
        if position_52w >= 0.80:
            score += 10
        elif position_52w >= 0.60:
            score += 6
        elif position_52w >= 0.40:
            score += 3

    # Volume confirmation: 5 points
    if volume_ratio is not None:
        if volume_ratio >= 1.50:
            score += 5
        elif volume_ratio >= 1.00:
            score += 3

    # RSI quality: 5 points
    # Reward constructive momentum, not extreme overextension.
    if snapshot.rsi14 is not None:
        if 50 <= snapshot.rsi14 <= 68:
            score += 5
        elif 45 <= snapshot.rsi14 < 50:
            score += 2
        elif 68 < snapshot.rsi14 <= 75:
            score += 2

    return round(min(score, 100.0), 2)


def _decision(score):
    if score >= 75:
        return "BUY"

    if score >= 65:
        return "WATCH"

    if score >= 50:
        return "WAIT"

    return "REJECT"


def _probabilities(score):
    """
    Temporary heuristic probabilities.

    These are NOT statistically calibrated yet.
    Calibration comes after enough frozen predictions mature.
    """

    up = 0.35 + (score / 100.0) * 0.40
    down = 0.35 - (score / 100.0) * 0.22

    up = min(max(up, 0.20), 0.75)
    down = min(max(down, 0.08), 0.40)

    sideways = 1.0 - up - down

    if sideways < 0.10:
        sideways = 0.10
        up = 1.0 - sideways - down

    total = up + sideways + down

    return (
        round(up / total * 100, 1),
        round(sideways / total * 100, 1),
        round(down / total * 100, 1),
    )


def scan_market(
    provider,
    universe: List[str] = None,
) -> Dict:
    symbols = universe or DEFAULT_UNIVERSE

    warnings = []
    results = []

    try:
        nifty = provider.history(
            "^NSEI",
            period="2y",
        )

        if nifty is None or nifty.empty:
            raise ValueError("Nifty history unavailable")

        nifty.columns = [
            str(c).lower()
            for c in nifty.columns
        ]

        nifty_close = pd.to_numeric(
            nifty["close"],
            errors="coerce",
        ).dropna()

        nifty_3m = _return(nifty_close, 63)
        nifty_6m = _return(nifty_close, 126)

    except Exception as exc:
        nifty_close = None
        nifty_3m = None
        nifty_6m = None

        warnings.append(
            {
                "symbol": "NIFTY50",
                "error": str(exc),
            }
        )

    for symbol in symbols:
        try:
            df = provider.history(
                symbol,
                period="2y",
            )

            if df is None or df.empty:
                raise ValueError("No historical data")

            df.columns = [
                str(c).lower()
                for c in df.columns
            ]

            snapshot = build_snapshot(df)

            close = pd.to_numeric(
                df["close"],
                errors="coerce",
            ).dropna()

            stock_3m = _return(close, 63)
            stock_6m = _return(close, 126)

            rs_3m = None
            rs_6m = None

            if (
                stock_3m is not None
                and nifty_3m is not None
            ):
                rs_3m = stock_3m - nifty_3m

            if (
                stock_6m is not None
                and nifty_6m is not None
            ):
                rs_6m = stock_6m - nifty_6m

            position52 = _position_52w(close)

            avg_volume20, volume_ratio = (
                _volume_metrics(df)
            )

            score = _score(
                snapshot,
                rs_3m,
                rs_6m,
                position52,
                volume_ratio,
            )

            up, sideways, down = (
                _probabilities(score)
            )

            result = {
                "symbol": symbol,
                "price": snapshot.close,
                "score": score,
                "decision": _decision(score),
                "up": up,
                "sideways": sideways,
                "down": down,
                "rsi14": snapshot.rsi14,
                "sma20": snapshot.sma20,
                "sma50": snapshot.sma50,
                "sma200": snapshot.sma200,
                "momentum1m": snapshot.momentum_1m,
                "momentum3m": snapshot.momentum_3m,
                "momentum6m": snapshot.momentum_6m,
                "relativeStrength3m": _number(rs_3m),
                "relativeStrength6m": _number(rs_6m),
                "position52w": _number(position52),
                "volatility20d": snapshot.volatility_20d,
                "avgVolume20d": _number(
                    avg_volume20,
                    0,
                ),
                "volumeRatio": _number(
                    volume_ratio,
                    2,
                ),
                "source": "YAHOO_RESEARCH",
                "dataLive": False,
            }

            results.append(result)

        except Exception as exc:
            warnings.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                }
            )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return {
        "universeSize": len(symbols),
        "successful": len(results),
        "failed": len(warnings),
        "benchmark": "NIFTY50",
        "results": results,
        "warnings": warnings,
    }
