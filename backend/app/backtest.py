from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .history_cache import (
    load_history,
)
from .universe import (
    load_universe,
)


HORIZONS = (
    5,
    10,
    20,
    30,
)

COST_PER_SIDE = 0.0015


@dataclass
class BacktestConfig:
    rebalance_sessions: int = 5
    min_score: float = 65
    top_n: int = 10
    transaction_cost_per_side: float = (
        COST_PER_SIDE
    )


def rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = (
        -delta.clip(
            upper=0
        )
    )

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    safe_loss = avg_loss.replace(
        0,
        np.nan,
    )

    rs = avg_gain / safe_loss

    result = (
        100
        - 100 / (1 + rs)
    )

    # Wilder RSI edge cases:
    # gains + zero losses => RSI 100
    # zero gains + losses => RSI 0
    # zero gains + zero losses => RSI 50
    result = result.mask(
        (avg_loss == 0)
        & (avg_gain > 0),
        100.0,
    )

    result = result.mask(
        (avg_gain == 0)
        & (avg_loss > 0),
        0.0,
    )

    result = result.mask(
        (avg_gain == 0)
        & (avg_loss == 0),
        50.0,
    )

    return result


def enrich(df):
    out = df.copy()

    close = out["close"]

    out["sma20"] = (
        close.rolling(20).mean()
    )

    out["sma50"] = (
        close.rolling(50).mean()
    )

    out["sma200"] = (
        close.rolling(200).mean()
    )

    out["rsi14"] = rsi(close)

    out["mom1m"] = (
        close.pct_change(21)
    )

    out["mom3m"] = (
        close.pct_change(63)
    )

    out["mom6m"] = (
        close.pct_change(126)
    )

    out["high52"] = (
        close.rolling(252).max()
    )

    out["low52"] = (
        close.rolling(252).min()
    )

    out["vol20"] = (
        close.pct_change()
        .rolling(20)
        .std()
        * np.sqrt(252)
    )

    if "volume" in out:
        out["avgvol20"] = (
            out["volume"]
            .rolling(20)
            .mean()
        )

        out["volume_ratio"] = (
            out["volume"]
            / out["avgvol20"]
        )
    else:
        out["volume_ratio"] = 1.0

    for horizon in HORIZONS:
        out[
            f"forward_{horizon}"
        ] = (
            close.shift(-horizon)
            / close
            - 1
        )

    return out


def feature_score(
    row,
    benchmark_row,
):
    required = [
        "close",
        "sma20",
        "sma50",
        "sma200",
        "mom1m",
        "mom3m",
        "mom6m",
        "rsi14",
        "high52",
        "low52",
    ]

    if any(
        pd.isna(row.get(x))
        for x in required
    ):
        return None

    score = 0.0

    close = row["close"]

    # Trend: 30
    if close > row["sma20"]:
        score += 8

    if close > row["sma50"]:
        score += 10

    if close > row["sma200"]:
        score += 12

    # Absolute momentum: 25
    if row["mom1m"] > 0:
        score += 5

    if row["mom3m"] > 0:
        score += 8

    if row["mom6m"] > 0:
        score += 12

    benchmark_3m = (
        benchmark_row.get(
            "mom3m",
            0,
        )
    )

    benchmark_6m = (
        benchmark_row.get(
            "mom6m",
            0,
        )
    )

    # Relative strength: 25
    rs3 = (
        row["mom3m"]
        - benchmark_3m
    )

    rs6 = (
        row["mom6m"]
        - benchmark_6m
    )

    if rs3 > 0:
        score += 10

    if rs6 > 0:
        score += 15

    # 52-week position: 10
    width = (
        row["high52"]
        - row["low52"]
    )

    if width > 0:
        pos = (
            (close - row["low52"])
            / width
        )

        score += (
            max(
                0,
                min(1, pos),
            )
            * 10
        )

    # Volume: 5
    if (
        row.get(
            "volume_ratio",
            1,
        )
        >= 1
    ):
        score += 5

    # RSI quality: 5
    if (
        45
        <= row["rsi14"]
        <= 70
    ):
        score += 5

    return round(
        min(score, 100),
        2,
    )


def regime_at(
    benchmark_row,
):
    score = 0

    close = benchmark_row[
        "close"
    ]

    if close > benchmark_row["sma20"]:
        score += 1
    else:
        score -= 1

    if close > benchmark_row["sma50"]:
        score += 2
    else:
        score -= 2

    if close > benchmark_row["sma200"]:
        score += 3
    else:
        score -= 3

    if benchmark_row["mom1m"] > 0:
        score += 1
    else:
        score -= 1

    if benchmark_row["mom3m"] > 0:
        score += 2
    else:
        score -= 2

    r = benchmark_row["rsi14"]

    if 50 <= r <= 70:
        score += 1
    elif r < 40:
        score -= 1

    vol = benchmark_row[
        "vol20"
    ]

    if vol >= 0.30:
        score -= 3
    elif vol >= 0.22:
        score -= 1
    elif vol < 0.16:
        score += 1

    if score >= 7:
        return "RISK_ON"

    if score >= 2:
        return "NEUTRAL"

    if score >= -4:
        return "DEFENSIVE"

    return "PANIC"


def max_drawdown(
    returns,
):
    if not returns:
        return 0.0

    curve = (
        pd.Series(returns)
        .fillna(0)
        .add(1)
        .cumprod()
    )

    peak = curve.cummax()

    dd = (
        curve / peak - 1
    )

    return float(
        dd.min()
    )


def profit_factor(
    returns,
):
    wins = sum(
        x
        for x in returns
        if x > 0
    )

    losses = abs(
        sum(
            x
            for x in returns
            if x < 0
        )
    )

    if losses == 0:
        return None

    return wins / losses


def metrics(
    returns,
):
    clean = [
        float(x)
        for x in returns
        if x is not None
        and not np.isnan(x)
    ]

    if not clean:
        return {
            "trades": 0,
            "winRate": None,
            "averageReturn": None,
            "medianReturn": None,
            "expectancy": None,
            "profitFactor": None,
            "maxDrawdownApprox":
                None,
        }

    wins = [
        x
        for x in clean
        if x > 0
    ]

    losses = [
        x
        for x in clean
        if x <= 0
    ]

    avg_win = (
        np.mean(wins)
        if wins
        else 0
    )

    avg_loss = (
        abs(np.mean(losses))
        if losses
        else 0
    )

    win_rate = (
        len(wins)
        / len(clean)
    )

    expectancy = (
        win_rate * avg_win
        - (1 - win_rate)
        * avg_loss
    )

    return {
        "trades": len(clean),
        "winRate": round(
            win_rate,
            4,
        ),
        "averageReturn": round(
            float(np.mean(clean)),
            6,
        ),
        "medianReturn": round(
            float(np.median(clean)),
            6,
        ),
        "expectancy": round(
            float(expectancy),
            6,
        ),
        "profitFactor": (
            round(
                profit_factor(
                    clean
                ),
                4,
            )
            if profit_factor(
                clean
            ) is not None
            else None
        ),
        "maxDrawdownApprox":
            round(
                max_drawdown(
                    clean
                ),
                6,
            ),
    }


def run_backtest(
    start=None,
    end=None,
    config=None,
):
    config = (
        config
        or BacktestConfig()
    )

    benchmark = load_history(
        "^NSEI"
    )

    if (
        benchmark is None
        or len(benchmark) < 300
    ):
        raise RuntimeError(
            "Nifty history missing. "
            "Run cache_history.py first."
        )

    benchmark = enrich(
        benchmark
    )

    if start:
        benchmark = benchmark[
            benchmark.index
            >= pd.Timestamp(start)
        ]

    if end:
        benchmark = benchmark[
            benchmark.index
            <= pd.Timestamp(end)
        ]

    dates = list(
        benchmark.index[
            252:
            :config.rebalance_sessions
        ]
    )

    universe = load_universe()

    stock_frames = {}

    for stock in universe:
        frame = load_history(
            stock.symbol
        )

        if (
            frame is None
            or len(frame) < 300
        ):
            continue

        stock_frames[
            stock.symbol
        ] = (
            enrich(frame)
        )

    observations = []

    for date in dates:
        try:
            b = benchmark.loc[
                date
            ]
        except KeyError:
            continue

        if (
            pd.isna(
                b["sma200"]
            )
            or pd.isna(
                b["mom6m"]
            )
        ):
            continue

        regime = regime_at(b)

        ranked = []

        for stock in universe:
            df = stock_frames.get(
                stock.symbol
            )

            if df is None:
                continue

            if date not in df.index:
                continue

            row = df.loc[date]

            score = feature_score(
                row,
                b,
            )

            if score is None:
                continue

            ranked.append(
                (
                    score,
                    stock,
                    row,
                )
            )

        ranked.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        selected = [
            x
            for x in ranked
            if x[0]
            >= config.min_score
        ][:config.top_n]

        for score, stock, row in selected:
            record = {
                "date":
                    str(date.date()),
                "symbol":
                    stock.symbol,
                "sector":
                    stock.sector,
                "score":
                    score,
                "regime":
                    regime,
            }

            for horizon in HORIZONS:
                raw = row.get(
                    f"forward_{horizon}"
                )

                if pd.isna(raw):
                    record[
                        f"return{horizon}D"
                    ] = None
                else:
                    cost = (
                        config
                        .transaction_cost_per_side
                        * 2
                    )

                    record[
                        f"return{horizon}D"
                    ] = round(
                        float(raw)
                        - cost,
                        6,
                    )

            observations.append(
                record
            )

    report = {
        "status": "EXPLORATORY",
        "warning": (
            "Uses the current Nifty 500 "
            "constituent snapshot across "
            "historical dates and therefore "
            "contains survivorship bias. "
            "Do not interpret this as "
            "production-grade evidence."
        ),
        "config": {
            "rebalanceSessions":
                config.rebalance_sessions,
            "minimumScore":
                config.min_score,
            "topN":
                config.top_n,
            "roundTripCost":
                config
                .transaction_cost_per_side
                * 2,
        },
        "universeLoaded":
            len(universe),
        "symbolsWithHistory":
            len(stock_frames),
        "observations":
            len(observations),
        "horizons": {},
        "scoreBuckets": {},
        "regimes": {},
    }

    for horizon in HORIZONS:
        values = [
            row[
                f"return{horizon}D"
            ]
            for row in observations
            if row[
                f"return{horizon}D"
            ] is not None
        ]

        report["horizons"][
            f"{horizon}D"
        ] = metrics(values)

    buckets = [
        ("65-74", 65, 75),
        ("75-84", 75, 85),
        ("85-100", 85, 101),
    ]

    for name, low, high in buckets:
        subset = [
            row
            for row in observations
            if low
            <= row["score"]
            < high
        ]

        report["scoreBuckets"][
            name
        ] = {}

        for horizon in HORIZONS:
            values = [
                row[
                    f"return{horizon}D"
                ]
                for row in subset
                if row[
                    f"return{horizon}D"
                ] is not None
            ]

            report[
                "scoreBuckets"
            ][name][
                f"{horizon}D"
            ] = metrics(values)

    for regime in [
        "RISK_ON",
        "NEUTRAL",
        "DEFENSIVE",
        "PANIC",
    ]:
        subset = [
            row
            for row in observations
            if row["regime"]
            == regime
        ]

        report["regimes"][
            regime
        ] = {}

        for horizon in HORIZONS:
            values = [
                row[
                    f"return{horizon}D"
                ]
                for row in subset
                if row[
                    f"return{horizon}D"
                ] is not None
            ]

            report[
                "regimes"
            ][regime][
                f"{horizon}D"
            ] = metrics(values)

    report[
        "sampleObservations"
    ] = observations[-50:]

    return report
