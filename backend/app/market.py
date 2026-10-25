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

    def history(self, symbol: str, period: str = "1y"):
        ticker = self.normalize_symbol(symbol)

        df = self.yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
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
        df = self.history(symbol, period="5d")

        if df is None or df.empty or "close" not in df.columns:
            raise RuntimeError(f"No reliable price available for {symbol}")

        close_series = df["close"].dropna()

        if close_series.empty:
            raise RuntimeError(f"No close price available for {symbol}")

        price = float(close_series.iloc[-1])

        return Quote(
            symbol=symbol.upper().replace(".NS", ""),
            price=round(price, 2),
            timestamp=datetime.now(timezone.utc),
            source="YAHOO_DELAYED",
            is_live=False,
        )


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
