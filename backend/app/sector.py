from collections import defaultdict


def sector_strength(
    results,
    sector_map,
):
    grouped = defaultdict(list)

    for row in results:
        sector = sector_map.get(
            row["symbol"],
            "UNKNOWN",
        )

        grouped[sector].append(
            float(row.get("score", 0))
        )

    strengths = {}

    for sector, scores in grouped.items():
        strengths[sector] = round(
            sum(scores) / len(scores),
            2,
        )

    return strengths


def apply_sector_strength(
    results,
    sector_map,
):
    strengths = sector_strength(
        results,
        sector_map,
    )

    for row in results:
        sector = sector_map.get(
            row["symbol"],
            "UNKNOWN",
        )

        row["sector"] = sector
        row["sectorStrength"] = (
            strengths.get(sector)
        )

    return results, strengths
