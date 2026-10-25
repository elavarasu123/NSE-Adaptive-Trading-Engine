import os

from .market import (
    DemoProvider,
    YahooProvider,
)
from .scanner import scan_market
from .regime import detect_regime, apply_regime
from .cache import market_cache


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
    return scan_report()["results"]


def scan_report(force=False):
    if PROVIDER_NAME == "yahoo":
        if not force:
            cached = market_cache.get(
                "scanner-report"
            )

            if cached is not None:
                return cached

        report = scan_market(provider)

        try:
            regime = detect_regime(provider)

            report["regime"] = {
                "name": regime.name,
                "score": regime.score,
                "confidence": regime.confidence,
                "exposureMultiplier":
                    regime.exposure_multiplier,
                "buyThreshold":
                    regime.buy_threshold,
                "reasons": regime.reasons,
            }

            report["results"] = [
                apply_regime(row, regime)
                for row in report["results"]
            ]

        except Exception as exc:
            report["regime"] = {
                "name": "UNKNOWN",
                "error": str(exc),
            }

            report["warnings"].append(
                {
                    "symbol": "REGIME",
                    "error": str(exc),
                }
            )

        market_cache.set(
            "scanner-report",
            report,
            ttl_seconds=900,
        )

        return report

    rows = demo_scan()

    return {
        "universeSize": len(rows),
        "successful": len(rows),
        "failed": 0,
        "benchmark": "DEMO",
        "regime": {
            "name": "DEMO",
            "score": 0,
            "confidence": 0,
            "exposureMultiplier": 1,
            "buyThreshold": 75,
            "reasons": [
                "Demo mode has no real regime"
            ],
        },
        "results": rows,
        "warnings": [],
    }
