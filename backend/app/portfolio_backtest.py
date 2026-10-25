from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from .backtest import (
    enrich,
    feature_score,
    regime_at,
)
from .history_cache import load_history
from .universe import load_universe


INITIAL_CAPITAL = 100000.0


@dataclass
class SimulationConfig:
    name: str
    min_score: float
    holding_sessions: int
    max_positions: int = 6
    max_position_pct: float = 0.15
    round_trip_cost: float = 0.003
    allowed_regimes: tuple = (
        "RISK_ON",
        "NEUTRAL",
        "DEFENSIVE",
    )


CHAMPION = SimulationConfig(
    name="champion-v0.2",
    min_score=65,
    holding_sessions=20,
)


CHALLENGER = SimulationConfig(
    name="challenger-30d-v0.1",
    min_score=75,
    holding_sessions=30,
    allowed_regimes=(
        "RISK_ON",
        "NEUTRAL",
    ),
)


def annualized_metrics(
    equity,
):
    if len(equity) < 2:
        return {
            "totalReturn": None,
            "cagr": None,
            "sharpe": None,
            "sortino": None,
            "maxDrawdown": None,
        }

    series = pd.Series(
        {
            pd.Timestamp(x["date"]):
                float(x["equity"])
            for x in equity
        }
    ).sort_index()

    daily = (
        series.pct_change()
        .dropna()
    )

    total_return = (
        series.iloc[-1]
        / series.iloc[0]
        - 1
    )

    calendar_days = max(
        (
            series.index[-1]
            - series.index[0]
        ).days,
        1,
    )

    years = (
        calendar_days / 365.25
    )

    cagr = (
        (
            series.iloc[-1]
            / series.iloc[0]
        ) ** (1 / years)
        - 1
    )

    volatility = daily.std()

    sharpe = (
        daily.mean()
        / volatility
        * sqrt(252)
        if volatility
        and not np.isnan(volatility)
        else None
    )

    downside = daily[
        daily < 0
    ].std()

    sortino = (
        daily.mean()
        / downside
        * sqrt(252)
        if downside
        and not np.isnan(downside)
        else None
    )

    peak = series.cummax()

    drawdown = (
        series / peak - 1
    )

    return {
        "totalReturn": round(
            float(total_return),
            6,
        ),
        "cagr": round(
            float(cagr),
            6,
        ),
        "sharpe": (
            round(
                float(sharpe),
                4,
            )
            if sharpe is not None
            else None
        ),
        "sortino": (
            round(
                float(sortino),
                4,
            )
            if sortino is not None
            else None
        ),
        "maxDrawdown": round(
            float(drawdown.min()),
            6,
        ),
    }


def benchmark_metrics(
    benchmark,
    start,
    end,
    initial_capital,
):
    data = benchmark.loc[
        (benchmark.index >= start)
        & (benchmark.index <= end)
    ].copy()

    if len(data) < 2:
        return None

    first = float(
        data["close"].iloc[0]
    )

    equity = []

    for date, row in data.iterrows():
        value = (
            initial_capital
            * float(row["close"])
            / first
        )

        equity.append(
            {
                "date":
                    str(date.date()),
                "equity": value,
            }
        )

    return {
        "metrics":
            annualized_metrics(
                equity
            ),
        "equityCurve":
            equity,
    }


def simulate(
    start,
    end,
    config,
):
    universe = load_universe()

    benchmark = load_history(
        "^NSEI"
    )

    if (
        benchmark is None
        or len(benchmark) < 300
    ):
        raise RuntimeError(
            "Nifty history unavailable."
        )

    benchmark = enrich(
        benchmark
    )

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
        ] = enrich(frame)

    dates = benchmark.index[
        (benchmark.index
         >= pd.Timestamp(start))
        & (
            benchmark.index
            <= pd.Timestamp(end)
            if end
            else True
        )
    ]

    if len(dates) < 2:
        raise RuntimeError(
            "No sessions in simulation period."
        )

    cash = INITIAL_CAPITAL
    positions = []
    trades = []
    equity_curve = []

    for session_index, date in enumerate(
        dates
    ):
        # ------------------------------------
        # EXIT MATURE POSITIONS
        # ------------------------------------

        still_open = []

        for position in positions:
            df = stock_frames.get(
                position["symbol"]
            )

            if (
                df is None
                or date not in df.index
            ):
                still_open.append(
                    position
                )
                continue

            held = (
                session_index
                - position[
                    "entrySession"
                ]
            )

            if (
                held
                < config.holding_sessions
            ):
                still_open.append(
                    position
                )
                continue

            exit_price = float(
                df.loc[
                    date,
                    "close",
                ]
            )

            gross_value = (
                position["quantity"]
                * exit_price
            )

            exit_cost = (
                gross_value
                * config.round_trip_cost
                / 2
            )

            proceeds = (
                gross_value
                - exit_cost
            )

            cash += proceeds

            pnl = (
                proceeds
                - position[
                    "entryValue"
                ]
                - position[
                    "entryCost"
                ]
            )

            return_pct = (
                pnl
                / (
                    position[
                        "entryValue"
                    ]
                    + position[
                        "entryCost"
                    ]
                )
            )

            trades.append(
                {
                    **position,
                    "exitDate":
                        str(
                            date.date()
                        ),
                    "exitPrice":
                        exit_price,
                    "pnl":
                        round(
                            pnl,
                            2,
                        ),
                    "return":
                        round(
                            return_pct,
                            6,
                        ),
                }
            )

        positions = still_open

        # ------------------------------------
        # MARK TO MARKET
        # ------------------------------------

        market_value = 0.0

        for position in positions:
            df = stock_frames.get(
                position["symbol"]
            )

            if (
                df is None
                or date not in df.index
            ):
                continue

            market_value += (
                position["quantity"]
                * float(
                    df.loc[
                        date,
                        "close",
                    ]
                )
            )

        equity_before_entries = (
            cash + market_value
        )

        # ------------------------------------
        # ENTRY SELECTION
        # ------------------------------------

        benchmark_row = (
            benchmark.loc[
                date
            ]
        )

        required = [
            "sma200",
            "mom6m",
            "rsi14",
            "vol20",
        ]

        benchmark_ready = all(
            not pd.isna(
                benchmark_row.get(x)
            )
            for x in required
        )

        if benchmark_ready:
            regime = regime_at(
                benchmark_row
            )
        else:
            regime = "UNKNOWN"

        slots = (
            config.max_positions
            - len(positions)
        )

        if (
            slots > 0
            and regime
            in config.allowed_regimes
        ):
            existing = {
                x["symbol"]
                for x in positions
            }

            ranked = []

            for stock in universe:
                if stock.symbol in existing:
                    continue

                df = stock_frames.get(
                    stock.symbol
                )

                if (
                    df is None
                    or date not in df.index
                ):
                    continue

                row = df.loc[date]

                score = feature_score(
                    row,
                    benchmark_row,
                )

                if (
                    score is None
                    or score
                    < config.min_score
                ):
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

            for (
                score,
                stock,
                row,
            ) in ranked[:slots]:
                price = float(
                    row["close"]
                )

                max_value = (
                    equity_before_entries
                    * config.max_position_pct
                )

                allocation = min(
                    max_value,
                    cash,
                )

                entry_cost_rate = (
                    config.round_trip_cost
                    / 2
                )

                quantity = int(
                    allocation
                    / (
                        price
                        * (
                            1
                            + entry_cost_rate
                        )
                    )
                )

                if quantity <= 0:
                    continue

                entry_value = (
                    quantity
                    * price
                )

                entry_cost = (
                    entry_value
                    * entry_cost_rate
                )

                total = (
                    entry_value
                    + entry_cost
                )

                if total > cash:
                    continue

                cash -= total

                positions.append(
                    {
                        "symbol":
                            stock.symbol,
                        "sector":
                            stock.sector,
                        "score":
                            score,
                        "regime":
                            regime,
                        "entryDate":
                            str(
                                date.date()
                            ),
                        "entrySession":
                            session_index,
                        "entryPrice":
                            price,
                        "quantity":
                            quantity,
                        "entryValue":
                            entry_value,
                        "entryCost":
                            entry_cost,
                    }
                )

        # ------------------------------------
        # END-OF-DAY EQUITY
        # ------------------------------------

        market_value = 0.0

        for position in positions:
            df = stock_frames.get(
                position["symbol"]
            )

            if (
                df is None
                or date not in df.index
            ):
                continue

            market_value += (
                position["quantity"]
                * float(
                    df.loc[
                        date,
                        "close",
                    ]
                )
            )

        equity_curve.append(
            {
                "date":
                    str(date.date()),
                "equity":
                    round(
                        cash
                        + market_value,
                        2,
                    ),
                "cash":
                    round(
                        cash,
                        2,
                    ),
                "positions":
                    len(positions),
                "regime":
                    regime,
            }
        )

    # Liquidate remaining positions on
    # the final available session.
    final_date = dates[-1]

    for position in positions:
        df = stock_frames.get(
            position["symbol"]
        )

        if (
            df is None
            or final_date
            not in df.index
        ):
            continue

        exit_price = float(
            df.loc[
                final_date,
                "close",
            ]
        )

        gross = (
            position["quantity"]
            * exit_price
        )

        exit_cost = (
            gross
            * config.round_trip_cost
            / 2
        )

        proceeds = (
            gross
            - exit_cost
        )

        cash += proceeds

        pnl = (
            proceeds
            - position[
                "entryValue"
            ]
            - position[
                "entryCost"
            ]
        )

        trades.append(
            {
                **position,
                "exitDate":
                    str(
                        final_date.date()
                    ),
                "exitPrice":
                    exit_price,
                "pnl":
                    round(
                        pnl,
                        2,
                    ),
                "return":
                    round(
                        pnl
                        / (
                            position[
                                "entryValue"
                            ]
                            + position[
                                "entryCost"
                            ]
                        ),
                        6,
                    ),
                "forcedExit":
                    True,
            }
        )

    if equity_curve:
        equity_curve[-1][
            "equity"
        ] = round(
            cash,
            2,
        )

        equity_curve[-1][
            "cash"
        ] = round(
            cash,
            2,
        )

        equity_curve[-1][
            "positions"
        ] = 0

    strategy_metrics = (
        annualized_metrics(
            equity_curve
        )
    )

    trade_returns = [
        x["return"]
        for x in trades
    ]

    wins = [
        x
        for x in trade_returns
        if x > 0
    ]

    losses = [
        x
        for x in trade_returns
        if x <= 0
    ]

    strategy_metrics.update(
        {
            "trades":
                len(trades),
            "winRate": (
                round(
                    len(wins)
                    / len(trades),
                    4,
                )
                if trades
                else None
            ),
            "avgTrade": (
                round(
                    float(
                        np.mean(
                            trade_returns
                        )
                    ),
                    6,
                )
                if trades
                else None
            ),
            "profitFactor": (
                round(
                    sum(wins)
                    / abs(
                        sum(losses)
                    ),
                    4,
                )
                if losses
                and abs(
                    sum(losses)
                ) > 0
                else None
            ),
            "endingCapital":
                round(
                    cash,
                    2,
                ),
        }
    )

    benchmark_result = (
        benchmark_metrics(
            benchmark,
            dates[0],
            dates[-1],
            INITIAL_CAPITAL,
        )
    )

    benchmark_cagr = (
        benchmark_result[
            "metrics"
        ]["cagr"]
        if benchmark_result
        else None
    )

    strategy_metrics[
        "excessCagrVsNifty"
    ] = (
        round(
            strategy_metrics[
                "cagr"
            ]
            - benchmark_cagr,
            6,
        )
        if benchmark_cagr
        is not None
        and strategy_metrics[
            "cagr"
        ] is not None
        else None
    )

    return {
        "strategy":
            config.name,
        "start":
            str(
                dates[0].date()
            ),
        "end":
            str(
                dates[-1].date()
            ),
        "initialCapital":
            INITIAL_CAPITAL,
        "configuration": {
            "minimumScore":
                config.min_score,
            "holdingSessions":
                config
                .holding_sessions,
            "maxPositions":
                config.max_positions,
            "maxPositionPct":
                config
                .max_position_pct,
            "roundTripCost":
                config
                .round_trip_cost,
            "allowedRegimes":
                list(
                    config
                    .allowed_regimes
                ),
        },
        "metrics":
            strategy_metrics,
        "benchmark":
            benchmark_result[
                "metrics"
            ]
            if benchmark_result
            else None,
        "equityCurve":
            equity_curve,
        "benchmarkCurve":
            benchmark_result[
                "equityCurve"
            ]
            if benchmark_result
            else [],
        "trades":
            trades,
        "researchWarnings": [
            (
                "Current Nifty 500 "
                "membership is projected "
                "backward, so historical "
                "results contain "
                "survivorship bias."
            ),
            (
                "Yahoo adjusted daily "
                "prices are research data, "
                "not execution-grade data."
            ),
            (
                "Costs are simplified and "
                "do not model every Indian "
                "tax/fee/slippage component."
            ),
        ],
    }
