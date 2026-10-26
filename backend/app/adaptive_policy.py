"""Validated paper threshold adaptation, retaining the original score benchmark.

The evaluation is a top-two equal-weight 20D return proxy, not a portfolio
backtest. Correlated labels use a 20-date block bootstrap. Risk never expands.
"""
from __future__ import annotations
from datetime import date
import hashlib
import json
import math
import numpy as np

BASE_THRESHOLDS = {"RISK_ON": 75., "NEUTRAL": 80., "DEFENSIVE": 88., "PANIC": 101.}
MIN_TRAIN_DATES = 30
MIN_VALIDATION_DATES = 40
MIN_OBSERVATIONS = 100
BLOCK_DATES = 20


def _daily(rows, threshold, cost):
    groups = {}
    for row in rows:
        groups.setdefault(row["date"], []).append(row)
    result = []
    for day, group in sorted(groups.items()):
        picks = sorted((x for x in group if x["score"] >= threshold),
                       key=lambda x: -x["score"])[:2]
        benchmark = float(np.mean([x["benchmark"] for x in group]))
        net = float(np.mean([x["return"] - cost for x in picks])) if picks else 0.
        result.append({"date": day, "net": net, "excess": net - benchmark, "selected": bool(picks)})
    return result


def _lower_bound(values):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(1701)
    count = len(values)
    starts = rng.integers(0, count - BLOCK_DATES + 1,
                          size=(1000, math.ceil(count / BLOCK_DATES)))
    indices = (starts[..., None] + np.arange(BLOCK_DATES)).reshape(1000, -1)[:, :count]
    return float(np.quantile(values[indices].mean(axis=1), .025))


def learn_entry_policy(predictions, as_of, round_trip_cost=.003):
    """Fit earlier dates, validate later, purge labels crossing the split.

    Only baseline 20D outcomes strictly before as_of are eligible. Malformed,
    future, duplicate and insufficient evidence cannot activate a revision.
    """
    date.fromisoformat(as_of)
    if not math.isfinite(round_trip_cost) or not 0 <= round_trip_cost <= .1:
        raise ValueError("Invalid paper friction assumption")
    rows, seen = [], set()
    for prediction in predictions:
        outcome = prediction.get("outcomes", {}).get("20D")
        if not outcome or prediction.get("modelVersion") != "champion-v0.2-frozen":
            continue
        try:
            day = str(date.fromisoformat(prediction["predictionDate"]))
            maturity = str(date.fromisoformat(outcome["maturityDate"]))
            if not day < maturity < as_of:
                continue
            key = (day, prediction["symbol"])
            if key in seen:
                continue
            row = {"date": day, "maturity": maturity, "symbol": prediction["symbol"],
                   "regime": prediction["regime"], "score": float(prediction["score"]),
                   "return": float(outcome["stockReturn"]), "benchmark": float(outcome["niftyReturn"])}
            if not all(math.isfinite(row[k]) for k in ["score", "return", "benchmark"]):
                continue
            seen.add(key)
            rows.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    regimes = {}
    for regime, baseline in BASE_THRESHOLDS.items():
        report = {"status": "WAITING_FOR_EVIDENCE", "baselineThreshold": baseline,
                  "effectiveThreshold": baseline, "trainingDates": 0, "validationDates": 0,
                  "reason": "Need 30 training dates and 40 later validation dates, 100 outcomes in each; crossing labels are purged."}
        regimes[regime] = report
        if regime == "PANIC":
            report.update(status="BLOCKED", reason="PANIC entry protection is never relaxed.")
            continue
        eligible = [x for x in rows if x["regime"] == regime and x["score"] >= baseline]
        days = sorted({x["date"] for x in eligible})
        if len(days) < MIN_TRAIN_DATES + MIN_VALIDATION_DATES:
            continue
        split = days[-MIN_VALIDATION_DATES]
        train = [x for x in eligible if x["date"] < split and x["maturity"] < split]
        validation = [x for x in eligible if x["date"] >= split]
        train_days = len({x["date"] for x in train})
        report.update(trainingDates=train_days, validationDates=len({x["date"] for x in validation}),
                      trainingOutcomes=len(train), validationOutcomes=len(validation), validationStart=split)
        if train_days < MIN_TRAIN_DATES or min(len(train), len(validation)) < MIN_OBSERVATIONS:
            continue
        train_base = _daily(train, baseline, round_trip_cost)
        base_return = np.mean([x["net"] for x in train_base])
        candidates = []
        for threshold in sorted({min(baseline + 5, 100), min(baseline + 10, 100)}):
            daily = _daily(train, threshold, round_trip_cost)
            if np.mean([x["selected"] for x in daily]) >= .5:
                candidates.append((float(np.mean([x["net"] for x in daily]) - base_return), threshold))
        if not candidates or max(candidates)[0] <= 0:
            report.update(status="BASELINE_RETAINED", reason="No threshold improved training returns after paper costs.")
            continue
        # Choose once on training data; no threshold search on the holdout.
        _, threshold = max(candidates, key=lambda x: (x[0], -x[1]))
        baseline_daily = _daily(validation, baseline, round_trip_cost)
        candidate_daily = _daily(validation, threshold, round_trip_cost)
        uplift = [new["net"] - old["net"] for old, new in zip(baseline_daily, candidate_daily)]
        excess = [x["excess"] for x in candidate_daily]
        lower_uplift, lower_excess = _lower_bound(uplift), _lower_bound(excess)
        coverage = float(np.mean([x["selected"] for x in candidate_daily]))
        report.update(candidateThreshold=threshold, validationMeanUplift=round(float(np.mean(uplift)), 6),
                      validationMeanNetExcess=round(float(np.mean(excess)), 6),
                      upliftLowerBound=round(lower_uplift, 6), netExcessLowerBound=round(lower_excess, 6),
                      validationCoverage=round(coverage, 4), status="VALIDATION_FAILED",
                      reason="Held-out uplift, positive net excess and coverage must all pass.")
        if lower_uplift > 0 and lower_excess > 0 and coverage >= .5:
            report.update(status="ACTIVE", effectiveThreshold=threshold,
                          reason="Purged chronological holdout passed paper entry-policy gates.")
    revision = hashlib.sha256(json.dumps({"regimes": regimes, "cost": round_trip_cost}, sort_keys=True).encode()).hexdigest()[:12]
    return {"version": "adaptive-entry-v1", "revision": revision, "asOf": as_of,
            "status": "ACTIVE" if any(x["status"] == "ACTIVE" for x in regimes.values()) else "BASELINE_RETAINED",
            "matured20D": len(rows), "roundTripCost": round_trip_cost, "regimes": regimes,
            "automaticPaperPolicyUpdates": True, "automaticModelPromotion": False,
            "evaluation": "Top-two equal-weight 20D forward-return proxy; not a portfolio backtest or proof of future accuracy."}


def entry_threshold(policy, regime, baseline):
    row = (policy or {}).get("regimes", {}).get(regime, {})
    value = row.get("effectiveThreshold", baseline)
    if row.get("status") != "ACTIVE" or not isinstance(value, (int, float)) or not math.isfinite(value):
        return baseline
    return max(baseline, min(float(value), baseline + 10, 100)) if regime != "PANIC" else baseline
