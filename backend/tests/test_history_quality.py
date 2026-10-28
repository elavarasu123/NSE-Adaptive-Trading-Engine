import runpy
from pathlib import Path
import pandas as pd
import pytest
import app.history_cache as cache
import app.history_quality as quality


def frame(end="2026-10-27", rows=400, price=100.):
    return pd.DataFrame({"open": price, "high": price + 1, "low": price - 1,
                         "close": price, "volume": 1000.}, index=pd.bdate_range(end=end, periods=rows))


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    import app.reliability as reliability
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(reliability, "expected_closed_session", lambda: pd.Timestamp("2026-10-27").date())
    monkeypatch.setattr("time.sleep", lambda *_: None)
    import app.history_official as official
    monkeypatch.setattr(official, 'repair_from_nse', lambda symbols, expected: {'recovered': [], 'status': 'TEST_UNAVAILABLE'})
    path = Path(__file__).resolve().parents[1] / "scripts/cache_history.py"
    return runpy.run_path(str(path))["refresh"]


def test_stale_and_insufficient_are_distinct(pipeline):
    cache.save_history("OLD", frame("2026-10-26"))
    cache.save_history("NEW", frame(rows=150))
    report = quality.history_quality(["OLD", "NEW", "ABSENT"])
    assert report["counts"] == {"STALE": 1, "INSUFFICIENT": 1, "MISSING": 1}


def test_partial_batch_retried_without_overwriting_good_data(pipeline, monkeypatch):
    import yfinance
    cache.save_history("^NSEI", frame())
    cache.save_history("OLD", frame("2026-10-26"))
    cache.save_history("NEW", frame(rows=150))
    calls = []
    def download(**kwargs):
        calls.append(kwargs)
        # First response is truncated; retry returns the full current history.
        return frame(rows=50 if len(calls) == 1 else 400)
    monkeypatch.setattr(yfinance, "download", download)
    report = pipeline(["OLD", "NEW"], repair_only=True)
    assert len(calls) == 2
    assert all(call["tickers"] == ["OLD.NS"] for call in calls)
    assert report["counts"] == {"READY": 2, "INSUFFICIENT": 1}
    assert len(cache.load_history("NEW")) == 150


def test_failed_download_preserves_previous_cache_and_reports_exclusion(pipeline, monkeypatch):
    import yfinance
    cache.save_history("^NSEI", frame())
    cache.save_history("OLD", frame("2026-10-26"))
    monkeypatch.setattr(yfinance, "download", lambda **_: frame("2026-10-20"))
    report = pipeline(["OLD"], repair_only=True)
    assert report["counts"]["STALE"] == 1
    assert cache.load_history("OLD").index.max() == pd.Timestamp("2026-10-26")


def test_unsettled_rows_never_saved_as_validated_history(pipeline, monkeypatch):
    import yfinance
    monkeypatch.setattr(yfinance, "download", lambda **_: frame("2026-10-28"))
    pipeline([], repair_only=True)
    assert cache.load_history("^NSEI").index.max() == pd.Timestamp("2026-10-27")


def test_new_listing_with_fewer_than_100_sessions_is_insufficient_not_missing(pipeline, monkeypatch):
    import yfinance
    cache.save_history("^NSEI", frame())
    monkeypatch.setattr(yfinance, "download", lambda **_: frame(rows=25))
    report = pipeline(["NEW"], repair_only=True)
    assert report["counts"] == {"INSUFFICIENT": 1, "READY": 1}
    assert len(cache.load_history("NEW")) == 25


def test_short_range_repairs_stale_long_range_only_with_matching_overlap(pipeline, monkeypatch):
    import yfinance
    cache.save_history("^NSEI", frame())
    cache.save_history("OLD", frame("2026-10-26"))
    monkeypatch.setattr(yfinance, "download", lambda **kwargs:
                        frame(rows=20) if kwargs['period'] == '1mo' else frame('2026-10-26'))
    report = pipeline(["OLD"], repair_only=True)
    assert report['recentRepair'] == {'attempted': 1, 'recovered': 1}
    assert cache.load_history('OLD').index.max() == pd.Timestamp('2026-10-27')


def test_adjusted_price_disagreement_cannot_be_spliced(pipeline):
    previous = frame('2026-10-26')
    recent = frame(rows=20, price=50.)
    assert quality.merge_recent_history(previous, recent, pd.Timestamp('2026-10-27').date()) is None


def test_atomic_write_failure_preserves_original(pipeline, monkeypatch):
    cache.save_history("OLD", frame())
    def failed(*args, **kwargs):
        raise OSError("disk failure")
    monkeypatch.setattr(pd.DataFrame, "to_csv", failed)
    with pytest.raises(OSError):
        cache.save_history("OLD", frame(price=200))
    assert cache.load_history("OLD")["close"].iloc[-1] == 100.
