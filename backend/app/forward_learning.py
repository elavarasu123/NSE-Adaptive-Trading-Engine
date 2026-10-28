from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import json
import math
import uuid

import numpy as np
import pandas as pd

from .backtest import enrich, feature_score, regime_at
from .history_cache import load_history
from .universe import load_universe

from .shared_state import (
    append_forward_event,
    read_forward_events,
    shared_state_enabled,
)


MODEL_VERSION = "champion-v0.2-frozen"
HORIZONS = (5, 10, 20, 30)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "forward"
LEDGER_PATH = DATA_DIR / "prediction_ledger.jsonl"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def _safe_float(value):
    if value is None:
        return None

    try:
        value = float(value)

        if not math.isfinite(value):
            return None

        return value
    except (TypeError, ValueError):
        return None


def read_ledger():
    if shared_state_enabled():
        return read_forward_events()

    if not LEDGER_PATH.exists():
        return []

    rows = []

    with LEDGER_PATH.open() as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            rows.append(
                json.loads(line)
            )

    return rows


def append_event(event):
    if shared_state_enabled():
        return append_forward_event(
            event
        )

    event = {
        **event,
        "recordedAt": utc_now(),
    }

    with LEDGER_PATH.open("a") as f:
        f.write(
            json.dumps(
                event,
                separators=(",", ":"),
            )
            + "\n"
        )

    return event


def latest_predictions():
    """
    Reconstruct immutable prediction records plus
    any outcome events appended later.
    """
    predictions = {}
    outcomes = {}

    for event in read_ledger():
        event_type = event.get(
            "eventType"
        )

        if event_type == "PREDICTION":
            predictions[
                event["predictionId"]
            ] = event

        elif event_type == "OUTCOME":
            key = (
                event["predictionId"],
                event["horizon"],
            )

            outcomes[key] = event

    result = []

    for prediction_id, row in (
        predictions.items()
    ):
        item = dict(row)

        item["outcomes"] = {}

        for horizon in HORIZONS:
            outcome = outcomes.get(
                (
                    prediction_id,
                    horizon,
                )
            )

            if outcome:
                item["outcomes"][
                    f"{horizon}D"
                ] = outcome

        result.append(item)

    result.sort(
        key=lambda x:
            x["predictionDate"],
        reverse=True,
    )

    return result


def _trading_dates_after(
    benchmark,
    prediction_date,
):
    timestamp = pd.Timestamp(
        prediction_date
    )

    return benchmark.index[
        benchmark.index > timestamp
    ]


def _maturity_date(
    benchmark,
    prediction_date,
    horizon,
):
    future_dates = (
        _trading_dates_after(
            benchmark,
            prediction_date,
        )
    )

    if len(future_dates) < horizon:
        return None

    return future_dates[
        horizon - 1
    ]


def _price_on_or_before(
    frame,
    timestamp,
):
    eligible = frame.loc[
        frame.index <= timestamp
    ]

    if eligible.empty:
        return None

    return float(
        eligible["close"].iloc[-1]
    )


class LearningContext:
    """One settled, point-in-time view per cycle; load/enrich each symbol once."""
    def __init__(self, as_of=None):
        from .reliability import expected_closed_session
        self.as_of = as_of or expected_closed_session()
        self.frames = {}
        self.coverage = {"missing": 0, "insufficient": 0, "unaligned": 0}
        self.exclusions = []
        self._candidates = None

    def frame(self, symbol):
        if symbol not in self.frames:
            raw = load_history(symbol)
            if raw is None or raw.empty:
                self.frames[symbol] = None
            else:
                raw = raw.copy()
                for column in ["open", "high", "low", "close", "volume"]:
                    if column in raw:
                        raw[column] = pd.to_numeric(raw[column], errors="coerce")
                index = pd.to_datetime(raw.index)
                if index.tz is not None:
                    index = index.tz_convert("Asia/Kolkata").tz_localize(None)
                raw.index = index.normalize()
                raw = raw.loc[~raw.index.duplicated(keep="last")].sort_index()
                raw = raw.loc[raw.index <= pd.Timestamp(self.as_of)]
                # Partial/future daily bars must never enter labels or features.
                raw = raw.loc[np.isfinite(raw["close"]) & (raw["close"] > 0)]
                self.frames[symbol] = enrich(raw) if not raw.empty else None
        return self.frames[symbol]

    def candidates(self):
        if self._candidates is not None:
            return self._candidates
        benchmark = self.frame("^NSEI")
        if benchmark is None or len(benchmark) < 300:
            raise RuntimeError("Nifty history unavailable.")
        self.market_date = benchmark.index[-1]
        if self.market_date.date() != self.as_of:
            raise RuntimeError("Benchmark does not contain the expected settled session.")
        self.benchmark_row = benchmark.iloc[-1]
        self.regime = regime_at(self.benchmark_row)
        self.universe = load_universe()
        candidates = []
        for stock in self.universe:
            frame = self.frame(stock.symbol)
            if frame is None:
                self.coverage["missing"] += 1
                self.exclusions.append({"symbol": stock.symbol, "reason": "MISSING"})
                continue
            if len(frame) < 300:
                self.coverage["insufficient"] += 1
                self.exclusions.append({"symbol": stock.symbol, "reason": "INSUFFICIENT_HISTORY", "rows": len(frame)})
                continue
            if self.market_date not in frame.index:
                self.coverage["unaligned"] += 1
                self.exclusions.append({"symbol": stock.symbol, "reason": "STALE", "latestSession": str(frame.index[-1].date())})
                continue
            row = frame.loc[self.market_date]
            score = feature_score(row, self.benchmark_row)
            price = _safe_float(row.get("close"))
            if score is None or not math.isfinite(score) or price is None:
                self.coverage["insufficient"] += 1
                self.exclusions.append({"symbol": stock.symbol, "reason": "INVALID_FEATURES"})
                continue
            candidates.append({"symbol": stock.symbol, "sector": stock.sector,
                               "score": float(score), "entryPrice": price, "regime": self.regime})
        candidates.sort(key=lambda x: x["score"], reverse=True)
        self._candidates = candidates
        return candidates


def generate_predictions(
    minimum_score=65,
    top_n=10,
    context=None,
):
    """
    Generate one frozen prediction batch for the
    latest common market date.

    Re-running on the same date/model/symbol is
    idempotent: duplicate predictions are skipped.
    """
    context = context or LearningContext()
    candidates = [x for x in context.candidates() if x["score"] >= minimum_score]
    benchmark = context.frame("^NSEI")
    market_date, regime = context.market_date, context.regime
    existing = latest_predictions()
    duplicate_keys = {(x["modelVersion"], x["predictionDate"], x["symbol"]) for x in existing}

    created = []
    skipped = []

    for candidate in candidates[
        :top_n
    ]:
        prediction_date = str(
            market_date.date()
        )

        key = (
            MODEL_VERSION,
            prediction_date,
            candidate["symbol"],
        )

        if key in duplicate_keys:
            skipped.append(
                candidate["symbol"]
            )
            continue

        maturity = {}

        for horizon in HORIZONS:
            timestamp = _maturity_date(
                benchmark,
                market_date,
                horizon,
            )

            maturity[
                f"{horizon}D"
            ] = (
                str(timestamp.date())
                if timestamp is not None
                else None
            )

        event = append_event(
            {
                "eventType":
                    "PREDICTION",
                "predictionId":
                    str(uuid.uuid4()),
                "modelVersion":
                    MODEL_VERSION,
                "predictionDate":
                    prediction_date,
                "symbol":
                    candidate["symbol"],
                "sector":
                    candidate["sector"],
                "score":
                    round(
                        candidate["score"],
                        4,
                    ),
                "entryPrice":
                    round(
                        candidate[
                            "entryPrice"
                        ],
                        4,
                    ),
                "regime":
                    candidate["regime"],
                "minimumScore":
                    minimum_score,
                "rankUniverse":
                    len(candidates),
                "maturityDates":
                    maturity,
                "researchOnly":
                    True,
            }
        )

        created.append(event)

    return {
        "modelVersion":
            MODEL_VERSION,
        "predictionDate":
            str(market_date.date()),
        "regime":
            regime,
        "created":
            len(created),
        "skippedDuplicates":
            skipped,
        "predictions":
            created,
    }


def mature_outcomes(context=None):
    """
    Append outcomes ONLY when the required number
    of subsequent trading sessions exists.

    Prediction records themselves are never edited.
    """
    context = context or LearningContext()
    benchmark = context.frame("^NSEI")
    if benchmark is None:
        raise RuntimeError("Nifty history unavailable.")

    predictions = (
        latest_predictions()
    )

    created = []

    for prediction in predictions:
        symbol = prediction[
            "symbol"
        ]

        frame = context.frame(symbol)
        if frame is None:
            continue

        prediction_date = (
            pd.Timestamp(
                prediction[
                    "predictionDate"
                ]
            )
        )

        entry_price = float(
            prediction[
                "entryPrice"
            ]
        )

        benchmark_entry = (
            _price_on_or_before(
                benchmark,
                prediction_date,
            )
        )

        if benchmark_entry is None:
            continue

        for horizon in HORIZONS:
            key = f"{horizon}D"

            if key in prediction[
                "outcomes"
            ]:
                continue

            maturity_date = (
                _maturity_date(
                    benchmark,
                    prediction_date,
                    horizon,
                )
            )

            if maturity_date is None:
                continue

            # Never use a maturity date that is
            # beyond currently cached market data.
            if (
                maturity_date
                > benchmark.index[-1]
            ):
                continue

            if maturity_date not in frame.index:
                continue

            exit_price = float(
                frame.loc[
                    maturity_date,
                    "close",
                ]
            )

            benchmark_exit = float(
                benchmark.loc[
                    maturity_date,
                    "close",
                ]
            )

            stock_return = (
                exit_price
                / entry_price
                - 1
            )

            nifty_return = (
                benchmark_exit
                / benchmark_entry
                - 1
            )

            excess_return = (
                stock_return
                - nifty_return
            )

            event = append_event(
                {
                    "eventType":
                        "OUTCOME",
                    "predictionId":
                        prediction[
                            "predictionId"
                        ],
                    "modelVersion":
                        prediction[
                            "modelVersion"
                        ],
                    "symbol":
                        symbol,
                    "predictionDate":
                        prediction[
                            "predictionDate"
                        ],
                    "horizon":
                        horizon,
                    "maturityDate":
                        str(
                            maturity_date.date()
                        ),
                    "entryPrice":
                        round(
                            entry_price,
                            4,
                        ),
                    "exitPrice":
                        round(
                            exit_price,
                            4,
                        ),
                    "stockReturn":
                        round(
                            stock_return,
                            6,
                        ),
                    "niftyReturn":
                        round(
                            nifty_return,
                            6,
                        ),
                    "excessReturn":
                        round(
                            excess_return,
                            6,
                        ),
                }
            )

            created.append(event)

    return {
        "outcomesCreated":
            len(created),
        "outcomes":
            created,
    }


def forward_metrics(predictions=None):
    predictions = latest_predictions() if predictions is None else predictions

    result = {
        "modelVersion":
            MODEL_VERSION,
        "predictions":
            len(predictions),
        "horizons": {},
    }

    for horizon in HORIZONS:
        key = f"{horizon}D"

        matured = []

        for prediction in predictions:
            outcome = prediction[
                "outcomes"
            ].get(key)

            if outcome:
                matured.append(
                    {
                        "score":
                            float(
                                prediction[
                                    "score"
                                ]
                            ),
                        "return":
                            float(
                                outcome[
                                    "stockReturn"
                                ]
                            ),
                        "excess":
                            float(
                                outcome[
                                    "excessReturn"
                                ]
                            ),
                    }
                )

        if not matured:
            result["horizons"][
                key
            ] = {
                "matured": 0,
                "meanReturn": None,
                "meanExcess": None,
                "winRate": None,
                "excessWinRate": None,
                "ic": None,
            }

            continue

        returns = np.asarray(
            [
                x["return"]
                for x in matured
            ]
        )

        excess = np.asarray(
            [
                x["excess"]
                for x in matured
            ]
        )

        scores = pd.Series(
            [
                x["score"]
                for x in matured
            ],
            dtype=float,
        )

        excess_series = pd.Series(
            excess,
            dtype=float,
        )

        ic = None

        if (
            len(matured) >= 10
            and scores.nunique() > 1
            and excess_series.nunique()
            > 1
        ):
            ic_value = (
                scores.rank()
                .corr(
                    excess_series.rank()
                )
            )

            if pd.notna(ic_value):
                ic = round(
                    float(ic_value),
                    6,
                )

        result["horizons"][
            key
        ] = {
            "matured":
                len(matured),
            "meanReturn":
                round(
                    float(
                        returns.mean()
                    ),
                    6,
                ),
            "meanExcess":
                round(
                    float(
                        excess.mean()
                    ),
                    6,
                ),
            "winRate":
                round(
                    float(
                        np.mean(
                            returns > 0
                        )
                    ),
                    4,
                ),
            "excessWinRate":
                round(
                    float(
                        np.mean(
                            excess > 0
                        )
                    ),
                    4,
                ),
            "ic": ic,
        }

    return result


def learning_status():
    predictions = (
        latest_predictions()
    )

    metrics = forward_metrics(predictions)

    today = date.today()

    pending = {
        f"{h}D": 0
        for h in HORIZONS
    }

    matured = {
        f"{h}D": 0
        for h in HORIZONS
    }

    for prediction in predictions:
        for horizon in HORIZONS:
            key = f"{horizon}D"

            if key in prediction[
                "outcomes"
            ]:
                matured[key] += 1
            else:
                pending[key] += 1

    from .market_analysis import load_market_analysis
    analysis = load_market_analysis()
    return {
        "adaptivePolicy": analysis.get("adaptivePolicy"),
        "automaticPaperPolicyUpdates": True,
        "engine":
            "FORWARD_PAPER_LEARNING",
        "modelVersion":
            MODEL_VERSION,
        "modelFrozen":
            True,
        "researchOnly":
            True,
        "liveTradingAllowed":
            False,
        "today":
            str(today),
        "totalPredictions":
            len(predictions),
        "matured":
            matured,
        "pending":
            pending,
        "metrics":
            metrics,
        "promotionPolicy": (
            "Baseline scores and recorded predictions remain immutable. "
            "Paper entry thresholds adapt automatically after purged chronological "
            "validation on matured outcomes. No automatic score-model promotion."
        ),
    }
