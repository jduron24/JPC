"""Runs the scoring pipeline against known historical repurposing cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scoring import get_candidates, load_cache

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"


def load_ground_truth(path: str | Path = GROUND_TRUTH_PATH) -> list[dict]:
    with Path(path).open() as f:
        return json.load(f)


def evaluate(cases: list[dict], cache: dict, top_k: int = 10) -> dict:
    results = []
    for case in cases:
        candidates = get_candidates(case["drug"], cache, top_k=top_k)
        ranked_indications = [c.indication.lower() for c in candidates]
        known_indications = [i.lower() for i in case["known_new_indications"]]

        hit_rank = next(
            (
                rank
                for rank, indication in enumerate(ranked_indications, start=1)
                if indication in known_indications
            ),
            None,
        )
        results.append(
            {
                "drug": case["drug"],
                "known_new_indications": case["known_new_indications"],
                "hit": hit_rank is not None,
                "rank": hit_rank,
            }
        )

    hits = sum(1 for result in results if result["hit"])
    return {"cases": results, "hit_rate": hits / len(results) if results else 0.0}


def main() -> int:
    cache = load_cache()
    cases = load_ground_truth()
    report = evaluate(cases, cache)

    for case in report["cases"]:
        outcome = f"HIT (rank {case['rank']})" if case["hit"] else "MISS"
        print(f"{case['drug']:<20} known={case['known_new_indications']!r:<40} {outcome}")

    hits = sum(case["hit"] for case in report["cases"])
    print(f"\nHit rate: {report['hit_rate']:.0%} ({hits}/{len(report['cases'])})")
    return 0 if report["hit_rate"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
