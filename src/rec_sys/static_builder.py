from pathlib import Path
import json

from rec_sys.data_loader import WelfareDataLoader
from rec_sys.recommender import generate_recommendation


def build_recommendation_data(output_dir: str | Path) -> dict:
    """Build static JSON payloads for the recommendation web UI."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    loader = WelfareDataLoader()
    complexes = loader.get_all_complexes()
    details = {}
    recommendations = {}

    for item in complexes:
        detail = loader.get_complex_detail(item["id"])
        if not detail:
            continue
        details[item["id"]] = detail
        recommendations[item["id"]] = generate_recommendation(
            detail=detail,
            api_key="",
            model="static-precomputed",
            use_cache=False,
        )

    stats = {
        "total_complexes": len(complexes),
        "blindspot_count": sum(1 for c in complexes if c.get("is_blindspot")),
        "robust_highrisk_count": sum(1 for c in complexes if c.get("is_robust_highrisk")),
    }

    payloads = {
        "complexes.json": complexes,
        "details.json": details,
        "recommendations.json": recommendations,
        "stats.json": stats,
    }
    for filename, payload in payloads.items():
        indent = 2 if filename == "stats.json" else None
        separators = None if indent else (",", ":")
        (out_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=indent, separators=separators),
            encoding="utf-8",
        )

    return stats
