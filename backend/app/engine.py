import os

from .market import (
    DemoProvider,
    YahooProvider,
)
from .scanner import scan_market


PROVIDER_NAME = os.getenv(
    "MARKET_PROVIDER",
    "demo",
).lower()

if PROVIDER_NAME == "yahoo":
    provider = YahooProvider()
else:
    provider = DemoProvider()


DEMO_SEEDS = [
    ("TCS", 84, 68, 21, 11, "BUY"),
    ("ICICIBANK", 80, 63, 24, 13, "WATCH"),
    ("LT", 76, 59, 27, 14, "WATCH"),
    ("RELIANCE", 71, 54, 29, 17, "WAIT"),
    ("SBIN", 65, 47, 31, 22, "REJECT"),
]


def demo_scan():
    output = []

    for (
        symbol,
        score,
        up,
        sideways,
        down,
        decision,
    ) in DEMO_SEEDS:

        quote = provider.quote(symbol)

        output.append(
            {
                "symbol": symbol,
                "price": quote.price,
                "score": score,
                "up": up,
                "sideways": sideways,
                "down": down,
                "decision": decision,
                "stop": round(
                    quote.price * 0.94,
                    2,
                ),
                "target": round(
                    quote.price * 1.10,
                    2,
                ),
                "source": "DEMO",
                "dataLive": False,
            }
        )

    return output


def scan():
    if PROVIDER_NAME == "yahoo":
        report = scan_market(provider)
        return report["results"]

    return demo_scan()


def scan_report():
    if PROVIDER_NAME == "yahoo":
        return scan_market(provider)

    rows = demo_scan()

    return {
        "universeSize": len(rows),
        "successful": len(rows),
        "failed": 0,
        "benchmark": "DEMO",
        "results": rows,
        "warnings": [],
    }
