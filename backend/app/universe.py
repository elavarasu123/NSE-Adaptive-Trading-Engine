import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_FILE = ROOT / "data" / "nifty500.csv"


@dataclass
class UniverseStock:
    symbol: str
    company: str = ""
    sector: str = "UNKNOWN"


FALLBACK = [
    UniverseStock("RELIANCE", "Reliance Industries", "ENERGY"),
    UniverseStock("TCS", "Tata Consultancy Services", "IT"),
    UniverseStock("HDFCBANK", "HDFC Bank", "FINANCIALS"),
    UniverseStock("ICICIBANK", "ICICI Bank", "FINANCIALS"),
    UniverseStock("INFY", "Infosys", "IT"),
    UniverseStock("SBIN", "State Bank of India", "FINANCIALS"),
    UniverseStock("BHARTIARTL", "Bharti Airtel", "TELECOM"),
    UniverseStock("LT", "Larsen & Toubro", "INDUSTRIALS"),
    UniverseStock("ITC", "ITC", "CONSUMER"),
    UniverseStock("AXISBANK", "Axis Bank", "FINANCIALS"),
    UniverseStock("KOTAKBANK", "Kotak Mahindra Bank", "FINANCIALS"),
    UniverseStock("MARUTI", "Maruti Suzuki", "AUTO"),
    UniverseStock("SUNPHARMA", "Sun Pharma", "PHARMA"),
    UniverseStock("TITAN", "Titan", "CONSUMER"),
    UniverseStock("BAJFINANCE", "Bajaj Finance", "FINANCIALS"),
]


def normalize_symbol(symbol: str) -> str:
    return (
        str(symbol)
        .strip()
        .upper()
        .replace(".NS", "")
    )


def load_universe(
    path: Optional[Path] = None,
) -> List[UniverseStock]:
    file_path = path or UNIVERSE_FILE

    if not file_path.exists():
        return FALLBACK.copy()

    rows = []

    with file_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            symbol = normalize_symbol(
                row.get("symbol")
                or row.get("Symbol")
                or row.get("SYMBOL")
                or ""
            )

            if not symbol:
                continue

            company = (
                row.get("company")
                or row.get("Company Name")
                or row.get("COMPANY")
                or ""
            ).strip()

            sector = (
                row.get("sector")
                or row.get("Industry")
                or row.get("SECTOR")
                or "UNKNOWN"
            ).strip().upper()

            rows.append(
                UniverseStock(
                    symbol=symbol,
                    company=company,
                    sector=sector,
                )
            )

    return rows or FALLBACK.copy()


def symbol_sector_map():
    return {
        stock.symbol: stock.sector
        for stock in load_universe()
    }
