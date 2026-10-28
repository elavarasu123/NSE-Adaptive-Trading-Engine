"""Execution-side real market analysis, persisted for the read-only dashboard."""
from __future__ import annotations
from datetime import datetime, timezone, date
import copy
import math
import os

from .adaptive_policy import BASE_THRESHOLDS, entry_threshold
from .shared_state import shared_state_enabled, latest_activity_of_type


def refresh_evidence(as_of):
    import json
    from .history_cache import CACHE_DIR
    try:
        report = json.loads((CACHE_DIR / 'refresh_report.json').read_text())
        if report.get('expectedSession') == as_of:
            return {key: report.get(key) for key in ['counts', 'recentRepair', 'downloadFailures']}
    except (OSError, ValueError, TypeError):
        pass
    return None


def build_market_analysis(context, adaptive, provider=None):
    candidates = context.candidates()
    row = context.benchmark_row
    regime = context.regime
    threshold = entry_threshold(adaptive, regime, BASE_THRESHOLDS[regime])
    reasons = [f"Nifty {'above' if row['close'] > row[key] else 'below'} {label}"
               for key, label in [('sma20', '20DMA'), ('sma50', '50DMA'), ('sma200', '200DMA')]]
    reasons += [f"1M momentum {row['mom1m']:.2%}; 3M momentum {row['mom3m']:.2%}",
                f"Realized volatility {row['vol20']:.2%}; RSI {row['rsi14']:.1f}"]
    quote = {"status": "UNAVAILABLE", "dataLive": False}
    if provider is not None:
        try:
            tick = provider.quote('^NSEI')
            price = float(tick.price)
            if not math.isfinite(price) or price <= 0:
                raise ValueError('Invalid benchmark quote')
            timestamp = tick.timestamp
            if timestamp.tzinfo is None:
                raise ValueError('Quote timestamp must include timezone')
            quote = {"status": "AVAILABLE", "price": price, "observedAt": timestamp.isoformat(),
                     "source": tick.source, "dataLive": False,
                     "changeFromSettledClose": round(price / float(row['close']) - 1, 6)}
        except Exception:
            # Lack of an intraday quote never becomes a fabricated daily update.
            quote['reason'] = 'A reliable delayed benchmark quote is unavailable.'
    results = []
    for candidate in candidates[:50]:
        score = candidate['score']
        decision = 'REJECT' if regime == 'PANIC' else ('BUY' if score >= threshold else 'WATCH' if score >= 65 else 'REJECT')
        results.append({**candidate, 'price': candidate['entryPrice'], 'decision': decision,
                        'source': 'EXECUTION_DAILY_CACHE', 'dataLive': False,
                        'asOf': str(context.market_date.date()), 'minimumScore': threshold,
                        'probabilityCalibrated': False})
    return {'schemaVersion': 1, 'status': 'AVAILABLE', 'asOf': str(context.market_date.date()),
            'generatedAt': datetime.now(timezone.utc).isoformat(), 'source': 'EXECUTION_DAILY_ANALYSIS',
            'executionSource': os.getenv('RUNTIME_SOURCE', 'LOCAL'),
            'dataLive': False, 'modelVersion': 'champion-v0.2-frozen', 'benchmark': '^NSEI',
            'universeSize': len(context.universe), 'successful': len(candidates),
            'failed': sum(context.coverage.values()), 'coverage': dict(context.coverage),
            'dataQuality': {'status': 'PARTIAL' if context.coverage.get('missing', 0) or context.coverage.get('unaligned', 0) else 'COMPLETE',
                            'refreshEvidence': refresh_evidence(str(context.market_date.date())),
                            'exclusions': getattr(context, 'exclusions', [])},
            'regime': {'name': regime, 'buyThreshold': threshold, 'baselineThreshold': BASE_THRESHOLDS[regime],
                       'entriesAllowed': regime != 'PANIC', 'reasons': reasons},
            'indicators': {key: round(float(row[key]), 6) for key in
                           ['close', 'sma20', 'sma50', 'sma200', 'rsi14', 'mom1m', 'mom3m', 'vol20']},
            'benchmarkQuote': quote, 'adaptivePolicy': adaptive, 'results': results,
            'warnings': ['Daily signals use settled sessions. Delayed quotes are separate from the daily model.',
                         'Scores are rankings, not calibrated probabilities.']}


def load_market_analysis(now=None):
    from .reliability import expected_closed_session
    expected = str(expected_closed_session(now))
    if shared_state_enabled():
        record = latest_activity_of_type('MARKET_ANALYSIS')
    else:
        from .runtime import read_jsonl, ACTIVITY_PATH
        record = next((x for x in reversed(read_jsonl(ACTIVITY_PATH))
                       if x.get('eventType') == 'MARKET_ANALYSIS'), None)
    saved = (record or {}).get('data', {}).get('analysis')
    unavailable = {'status': 'UNAVAILABLE', 'asOf': None, 'expectedSession': expected,
                   'source': 'EXECUTION_ANALYSIS', 'dataLive': False, 'results': [],
                   'regime': {'name': 'UNKNOWN', 'entriesAllowed': False},
                   'warnings': ['No execution-side market analysis has been recorded yet.']}
    if (not isinstance(saved, dict) or saved.get('schemaVersion') != 1
            or not isinstance(saved.get('regime'), dict)
            or not isinstance(saved.get('results'), list)
            or saved['regime'].get('name') not in BASE_THRESHOLDS):
        return unavailable
    report = copy.deepcopy(saved)
    try:
        actual = str(date.fromisoformat(report['asOf']))
    except (KeyError, TypeError, ValueError):
        return unavailable
    report['expectedSession'] = expected
    if actual != expected:
        report['status'] = 'STALE' if actual < expected else 'INVALID'
        report['regime']['entriesAllowed'] = False
        for candidate in report['results']:
            candidate.update(decision='WAIT', reason='Analysis is not from the expected settled session.')
    quote = report.get('benchmarkQuote', {})
    if quote.get('status') == 'AVAILABLE':
        try:
            observed = datetime.fromisoformat(quote['observedAt'])
            checked = now or datetime.now(timezone.utc)
            if checked.tzinfo is None:
                from .reliability import IST
                checked = checked.replace(tzinfo=IST)
            age = (checked - observed).total_seconds() / 60
            quote['ageMinutes'] = round(age, 1)
            if age < 0 or age > 20:
                quote['status'] = 'STALE'
        except (KeyError, ValueError, TypeError):
            quote['status'] = 'UNAVAILABLE'
    return report
