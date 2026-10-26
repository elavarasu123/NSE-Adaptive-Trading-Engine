from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import math


@dataclass
class Quote:
    symbol: str
    price: float
    timestamp: datetime
    source: str
    is_live: bool


class MarketDataProvider(ABC):
    """Interface for all market-data providers."""

    @abstractmethod
    def quote(self, symbol: str) -> Quote:
        raise NotImplementedError

    @abstractmethod
    def history(self, symbol: str, period: str = "1y"):
        raise NotImplementedError


class DemoProvider(MarketDataProvider):
    """
    Deterministic development provider.

    IMPORTANT:
    - Not live market data.
    - Never use these prices as actual executions.
    """

    BASE_PRICES = {
        "TCS": 3250.0,
        "ICICIBANK": 1400.0,
        "LT": 3900.0,
        "RELIANCE": 1400.0,
        "SBIN": 900.0,
    }

    def quote(self, symbol: str) -> Quote:
        symbol = symbol.upper().replace(".NS", "")
        base = self.BASE_PRICES.get(symbol, 1000.0)

        now = datetime.now(timezone.utc)

        # Small deterministic movement for UI/testing.
        minute_bucket = int(now.timestamp() // 60)
        drift = math.sin(minute_bucket / 10) * 0.002

        return Quote(
            symbol=symbol,
            price=round(base * (1 + drift), 2),
            timestamp=now,
            source="DEMO",
            is_live=False,
        )

    def history(self, symbol: str, period: str = "1y"):
        return []


class YahooProvider(MarketDataProvider):
    """
    Development/research provider using yfinance.

    This is NOT considered tick-grade execution data.
    Broker WebSocket data will be a separate provider later.
    """

    def __init__(self):
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError(
                "yfinance is not installed. Run: pip install yfinance"
            ) from exc

        self.yf = yf

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        symbol = symbol.upper().strip()

        # Yahoo index symbols such as ^NSEI must not
        # receive the NSE equity suffix.
        if symbol.startswith("^"):
            return symbol

        if symbol.endswith(".NS"):
            return symbol

        return f"{symbol}.NS"

    def history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        ticker = self.normalize_symbol(symbol)

        df = self.yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False,
            timeout=15,
        )

        if df is None or df.empty:
            return df

        # yfinance can return MultiIndex columns.
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = [
                col[0] if isinstance(col, tuple) else col
                for col in df.columns
            ]

        df.columns = [str(c).strip().lower() for c in df.columns]

        return df

    def quote(self, symbol: str) -> Quote:
        from zoneinfo import ZoneInfo
        import pandas as pd
        from .scheduler_guard import session_guard
        from .reliability import expected_closed_session
        df = self.history(symbol, period="5d", interval="5m")
        if df is None or df.empty or "close" not in df.columns:
            raise RuntimeError(f"No reliable delayed price available for {symbol}")
        closes = df["close"].dropna().sort_index()
        if closes.empty:
            raise RuntimeError(f"No delayed price available for {symbol}")
        price = float(closes.iloc[-1])
        observed = pd.Timestamp(closes.index[-1])
        if observed.tzinfo is None:
            observed = observed.tz_localize("Asia/Kolkata")
        timestamp = observed.to_pydatetime().astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        age = (now - timestamp).total_seconds()
        guard = session_guard(now)
        local_day = timestamp.astimezone(ZoneInfo("Asia/Kolkata")).date()
        if (not math.isfinite(price) or price <= 0 or age < -120
                or (guard.in_market_window and (age > 20 * 60 or local_day != now.astimezone(ZoneInfo("Asia/Kolkata")).date()))
                or (guard.in_post_close_window and local_day != now.astimezone(ZoneInfo("Asia/Kolkata")).date())
                or local_day < expected_closed_session(now)):
            raise RuntimeError(f"Stale or invalid delayed price for {symbol}")
        return Quote(symbol=symbol.upper().replace(".NS", ""), price=round(price, 2),
                     timestamp=timestamp, source="YAHOO_DELAYED_5M", is_live=False)


class CycleMarketProvider:
    """Reuse settled histories and one observed quote per symbol within a cycle."""
    def __init__(self, provider, context):
        self.provider, self.context, self.quotes = provider, context, {}

    def history(self, symbol, period="1y"):
        frame = self.context.frame(symbol)
        if frame is None:
            raise RuntimeError(f"Settled history unavailable for {symbol}")
        return frame

    def quote(self, symbol):
        if symbol not in self.quotes:
            self.quotes[symbol] = self.provider.quote(symbol)
        return self.quotes[symbol]



def get_market_provider(name: Optional[str] = None) -> MarketDataProvider:
    """
    Explicit provider selection.

    Defaults to DEMO so an accidental deployment can never silently
    pretend delayed Yahoo data is a live execution feed.
    """

    provider = (name or "demo").lower()

    if provider == "yahoo":
        return YahooProvider()

    return DemoProvider()
