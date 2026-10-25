import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

OUTPUT = DATA / "nifty500.csv"
META = DATA / "nifty500.meta.json"


# Official Nifty Indices constituent download location.
URLS = [
    "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv",
]


def download():
    last_error = None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "NSE-Adaptive-Trading-Engine/0.3"
        ),
        "Accept": "text/csv,*/*",
    }

    for url in URLS:
        try:
            req = urllib.request.Request(
                url,
                headers=headers,
            )

            with urllib.request.urlopen(
                req,
                timeout=30,
            ) as response:
                raw = response.read()

            text = raw.decode(
                "utf-8-sig"
            )

            reader = csv.DictReader(
                io.StringIO(text)
            )

            rows = []

            for row in reader:
                symbol = (
                    row.get("Symbol")
                    or row.get("SYMBOL")
                    or row.get("symbol")
                    or ""
                ).strip().upper()

                if not symbol:
                    continue

                company = (
                    row.get("Company Name")
                    or row.get("Company")
                    or ""
                ).strip()

                sector = (
                    row.get("Industry")
                    or row.get("Sector")
                    or "UNKNOWN"
                ).strip().upper()

                rows.append(
                    {
                        "symbol": symbol,
                        "company": company,
                        "sector": sector,
                    }
                )

            if len(rows) < 400:
                raise RuntimeError(
                    "Downloaded constituent file "
                    f"contains only {len(rows)} rows."
                )

            DATA.mkdir(
                parents=True,
                exist_ok=True,
            )

            with OUTPUT.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "symbol",
                        "company",
                        "sector",
                    ],
                )

                writer.writeheader()
                writer.writerows(rows)

            META.write_text(
                json.dumps(
                    {
                        "source": url,
                        "downloadedAt":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),
                        "constituents":
                            len(rows),
                        "warning": (
                            "Current constituent "
                            "snapshot. Historical "
                            "backtests using this "
                            "snapshot have "
                            "survivorship bias."
                        ),
                    },
                    indent=2,
                )
            )

            print(
                f"Saved {len(rows)} "
                f"Nifty 500 constituents"
            )

            print(
                f"Source: {url}"
            )

            return

        except Exception as exc:
            last_error = exc

    raise SystemExit(
        "Unable to download Nifty 500 "
        f"constituents: {last_error}"
    )


if __name__ == "__main__":
    download()
