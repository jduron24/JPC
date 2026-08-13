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


def _restrict_to_original_indication(cache: dict, drug: str, original_indication: str | None) -> dict:
    """Freeze a case's query drug back to its pre-repurposing indication(s).

    Without this, get_candidates() filters out any indication already present
    in the query drug's *current* (present-day) drug_indications entry -- so
    a drug's own later, real-world repurposing indications get excluded as
    "already covered" before the algorithm ever gets a chance to predict
    them, and the eval can never score a hit. This simulates evaluating the
    pipeline as of the drug's original indication only, leaving every other
    drug's data untouched.
    """
    if not original_indication:
        return cache
    restricted = dict(cache)
    restricted_indications = dict(cache.get("drug_indications", {}))
    restricted_indications[drug] = [
        {"indication": original_indication, "phase": "Approved", "status": "active"}
    ]
    restricted["drug_indications"] = restricted_indications
    return restricted


def evaluate(cases: list[dict], cache: dict, top_k: int = 10) -> dict:
    results = []
    for case in cases:
        case_cache = _restrict_to_original_indication(
            cache, case["drug"], case.get("original_indication")
        )
        candidates = get_candidates(case["drug"], case_cache, top_k=top_k)
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
