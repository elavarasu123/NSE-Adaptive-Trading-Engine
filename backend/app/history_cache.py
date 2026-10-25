from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "history"

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def cache_path(symbol):
    clean = (
        symbol
        .replace("^", "INDEX_")
        .replace("/", "_")
    )

    return (
        CACHE_DIR
        / f"{clean}.csv"
    )


def save_history(
    symbol,
    frame,
):
    path = cache_path(symbol)

    output = frame.copy()

    output.index.name = "Date"

    output.to_csv(path)

    return path


def load_history(symbol):
    path = cache_path(symbol)

    if not path.exists():
        return None

    df = pd.read_csv(
        path,
        index_col="Date",
        parse_dates=True,
    )

    df.columns = [
        str(c).lower()
        for c in df.columns
    ]

    return df.sort_index()


def cache_stats():
    files = list(
        CACHE_DIR.glob("*.csv")
    )

    size = sum(
        f.stat().st_size
        for f in files
    )

    return {
        "files": len(files),
        "bytes": size,
        "megabytes": round(
            size / 1024 / 1024,
            2,
        ),
    }
