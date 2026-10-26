from datetime import datetime, timezone
import pandas as pd
import pytest
from app.market import YahooProvider
import app.market as market


class FixedTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 26, 8, 30, tzinfo=timezone.utc)


def source(monkeypatch, timestamp='2026-10-26 13:55:00+05:30', price=123.):
    monkeypatch.setattr(market, 'datetime', FixedTime)
    provider = object.__new__(YahooProvider)
    calls = []
    provider.history = lambda symbol, **kwargs: calls.append(kwargs) or pd.DataFrame(
        {'close': [price]}, index=pd.DatetimeIndex([timestamp]))
    return provider, calls


def test_quote_retains_actual_observation_time_and_uses_intraday_bars(monkeypatch):
    provider, calls = source(monkeypatch)
    quote = provider.quote('TEST')
    assert quote.timestamp == datetime(2026, 10, 26, 8, 25, tzinfo=timezone.utc)
    assert quote.source == 'YAHOO_DELAYED_5M' and quote.is_live is False
    assert calls == [{'period': '5d', 'interval': '5m'}]


@pytest.mark.parametrize('timestamp,price', [
    ('2026-10-23 15:25:00+05:30', 100.),
    ('2026-10-26 12:00:00+05:30', 100.),
    ('2026-10-26 15:00:00+05:30', 100.),
    ('2026-10-26 13:55:00+05:30', float('inf')),
    ('2026-10-26 13:55:00+05:30', -1.),
])
def test_stale_future_or_invalid_quotes_are_rejected(monkeypatch, timestamp, price):
    provider, _ = source(monkeypatch, timestamp, price)
    with pytest.raises(RuntimeError):
        provider.quote('TEST')
