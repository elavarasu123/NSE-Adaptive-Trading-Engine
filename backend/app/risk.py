from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class TradePlan:
    entry: float
    stop: float
    target: float
    atr14: float
    risk_per_share: float
    reward_per_share: float
    reward_risk: float
    quantity: int
    position_value: float
    capital_risk: float
    risk_pct_capital: float
    exposure_pct_capital: float
    valid: bool
    reason: str


def atr(df: pd.DataFrame, period: int = 14):
    data = df.copy()
    data.columns = [
        str(c).lower()
        for c in data.columns
    ]

    required = {"high", "low", "close"}

    if not required.issubset(data.columns):
        raise ValueError(
            "ATR requires high, low and close"
        )

    high = pd.to_numeric(
        data["high"],
        errors="coerce",
    )

    low = pd.to_numeric(
        data["low"],
        errors="coerce",
    )

    close = pd.to_numeric(
        data["close"],
        errors="coerce",
    )

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def position_size(
    cash,
    entry,
    stop,
    risk=.01,
    cap=.15,
    capital=None,
    exposure_multiplier=1.0,
):
    """
    Backward-compatible deterministic sizing.

    risk:
        max fraction of original capital at risk.

    cap:
        max fraction of original capital allocated
        to one position.

    exposure_multiplier:
        regime-based exposure control.
    """

    if (
        entry <= 0
        or stop <= 0
        or stop >= entry
        or cash <= 0
    ):
        return 0

    base_capital = (
        float(capital)
        if capital is not None
        else float(cash)
    )

    exposure_multiplier = max(
        0.0,
        min(float(exposure_multiplier), 1.0),
    )

    if exposure_multiplier == 0:
        return 0

    per_share_risk = entry - stop

    risk_budget = (
        base_capital
        * risk
        * exposure_multiplier
    )

    position_cap = (
        base_capital
        * cap
        * exposure_multiplier
    )

    by_risk = int(
        risk_budget // per_share_risk
    )

    by_position_cap = int(
        position_cap // entry
    )

    by_cash = int(
        cash // entry
    )

    return max(
        0,
        min(
            by_risk,
            by_position_cap,
            by_cash,
        ),
    )


def build_trade_plan(
    df,
    cash,
    capital,
    exposure_multiplier=1.0,
    risk_fraction=0.01,
    position_cap=0.15,
    atr_multiple=2.0,
    reward_risk=2.0,
    entry_price=None,
):
    if df is None or df.empty:
        raise ValueError(
            "Historical data unavailable"
        )

    data = df.copy()
    data.columns = [
        str(c).lower()
        for c in data.columns
    ]

    if "close" not in data.columns:
        raise ValueError(
            "Close column unavailable"
        )

    close = pd.to_numeric(
        data["close"],
        errors="coerce",
    ).dropna()

    if len(close) < 20:
        raise ValueError(
            "Insufficient history"
        )

    entry = float(close.iloc[-1] if entry_price is None else entry_price)
    if not np.isfinite(entry) or entry <= 0:
        raise ValueError("Invalid observed entry price")

    atr_series = atr(data, 14)
    atr_values = atr_series.dropna()

    if atr_values.empty:
        raise ValueError(
            "ATR unavailable"
        )

    atr14 = float(
        atr_values.iloc[-1]
    )

    if (
        not np.isfinite(atr14)
        or atr14 <= 0
    ):
        raise ValueError(
            "Invalid ATR"
        )

    # Volatility stop.
    atr_stop = (
        entry
        - atr_multiple * atr14
    )

    # Structure reference:
    # recent 20-session low.
    recent_low = float(
        pd.to_numeric(
            data["low"],
            errors="coerce",
        )
        .tail(20)
        .min()
    )

    # We don't want the stop sitting above
    # obvious recent structure.
    structure_stop = (
        recent_low
        - 0.25 * atr14
    )

    stop = min(
        atr_stop,
        structure_stop,
    )

    # Guard against pathological data / huge stop.
    maximum_stop_distance = (
        entry * 0.12
    )

    stop = max(
        stop,
        entry - maximum_stop_distance,
    )

    stop = round(
        max(stop, 0.01),
        2,
    )

    risk_per_share = (
        entry - stop
    )

    if risk_per_share <= 0:
        raise ValueError(
            "Invalid stop distance"
        )

    target = round(
        entry
        + risk_per_share * reward_risk,
        2,
    )

    quantity = position_size(
        cash=cash,
        entry=entry,
        stop=stop,
        risk=risk_fraction,
        cap=position_cap,
        capital=capital,
        exposure_multiplier=
            exposure_multiplier,
    )

    position_value = round(
        quantity * entry,
        2,
    )

    capital_risk = round(
        quantity * risk_per_share,
        2,
    )

    actual_rr = (
        (target - entry)
        / risk_per_share
    )

    valid = quantity >= 1
    reason = (
        "PASS"
        if valid
        else "Risk budget cannot fund 1 share"
    )

    return TradePlan(
        entry=round(entry, 2),
        stop=stop,
        target=target,
        atr14=round(atr14, 2),
        risk_per_share=round(
            risk_per_share,
            2,
        ),
        reward_per_share=round(
            target - entry,
            2,
        ),
        reward_risk=round(
            actual_rr,
            2,
        ),
        quantity=quantity,
        position_value=position_value,
        capital_risk=capital_risk,
        risk_pct_capital=round(
            (
                capital_risk
                / capital
                * 100
            )
            if capital
            else 0,
            3,
        ),
        exposure_pct_capital=round(
            (
                position_value
                / capital
                * 100
            )
            if capital
            else 0,
            2,
        ),
        valid=valid,
        reason=reason,
    )


def trade_plan_dict(*args, **kwargs):
    return asdict(
        build_trade_plan(
            *args,
            **kwargs,
        )
    )
