"""Assemble data/cache.json from the raw Convoke Program Tracker pulls.

Run: python3 data/build_cache.py

Reads data/raw/*.json (already fetched from the live MCP server -- see
convoke_client.py's module docstring for how/why) and writes data/cache.json
in the shape Person 2 (scoring/eval/app) and Person 3 (historical cases)
build against. No MCP calls happen here; this only reshapes JSON already on
disk, so it's free to rerun.
"""

import json
from pathlib import Path

from convoke_client import (
    get_drugs_sharing_target,
    get_indications_for_drug,
    get_target,
    load_items,
)

CACHE_PATH = Path(__file__).parent / "cache.json"

CURATED_DRUGS = [
    "Brenipatide",
    "Semaglutide",
    "Tirzepatide",
    "Liraglutide",
    "Dulaglutide",
    "Retatrutide",
    "Sildenafil",
    "Minoxidil",
]

# Shared-target candidate pools we pulled, keyed by the target(s) each pool's
# query was scoped to. A drug only draws candidates from the pool matching
# its own target(s) -- pools aren't merged, or e.g. Tadalafil (PDE5) would
# leak into Semaglutide's (GLP-1R) candidate list.
#
# AR (Minoxidil's tagged target) was deliberately skipped: the AR target
# query returned mostly unrelated prostate cancer drugs (Abiraterone,
# Apalutamide, ...), which looks like a knowledge-graph tagging quirk rather
# than real shared mechanism with Minoxidil's actual target (a KATP channel
# opener).
TARGET_POOLS = {
    frozenset({"GLP-1R", "GIPR", "GCGR"}): "program_tracker_targets_glp1_gipr_gcgr.json",
    frozenset({"PDE5"}): "program_tracker_targets_pde5.json",
}


def pool_for_targets(targets):
    target_set = set(targets)
    for pool_targets, filename in TARGET_POOLS.items():
        if target_set & pool_targets:
            return filename
    return None

_PHASE_RANK = {
    "regulatory approval": 6,
    "phase 4": 5.5,
    "phase 3": 5,
    "phase 2, 3": 4.5,
    "phase 2": 4,
    "phase 1, 2": 3.5,
    "phase 1": 3,
    "phase 0": 2,
    "early phase 1": 1,
    "unspecified": 0,
    "preclinical": -1,
}


def phase_rank(phase):
    return _PHASE_RANK.get((phase or "").strip().lower(), -2)


def build_entry(drug_name, drug_rows, target_pools):
    targets = get_target(drug_name, drug_rows)
    current_indications = get_indications_for_drug(drug_name, drug_rows)
    pool_filename = pool_for_targets(targets)

    candidates = []
    if pool_filename:
        target_rows = target_pools[pool_filename]
        already_trialed = {c["indication"].strip().lower() for c in current_indications}
        raw_candidates = get_drugs_sharing_target(drug_name, drug_rows, target_rows)
        seen = set()
        for c in raw_candidates:
            key = (c["candidate_drug"], c["candidate_indication"].strip().lower())
            if c["candidate_indication"].strip().lower() in already_trialed:
                continue
            if key in seen:
                continue
            seen.add(key)
            candidates.append(c)
        candidates.sort(key=lambda c: phase_rank(c["phase"]), reverse=True)

    return {
        "drug": drug_name,
        "targets": targets,
        "current_indications": current_indications,
        "candidates": candidates,
        "candidate_pool_note": (
            None
            if pool_filename
            else f"No shared-target candidate pool pulled for target(s) {targets} this round "
            "(skipped for credit budget / data-quality reasons -- see build_cache.py)."
        ),
    }


def main():
    drug_rows = load_items("program_tracker_drugs_p1.json", "program_tracker_drugs_p2.json")
    target_pools = {filename: load_items(filename) for filename in TARGET_POOLS.values()}

    cache = {
        "generated_from": [
            "data/raw/program_tracker_drugs_p1.json",
            "data/raw/program_tracker_drugs_p2.json",
            *(f"data/raw/{filename}" for filename in TARGET_POOLS.values()),
        ],
        "drugs": [build_entry(name, drug_rows, target_pools) for name in CURATED_DRUGS],
    }

    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"Wrote {CACHE_PATH} with {len(cache['drugs'])} drugs.")
    for entry in cache["drugs"]:
        print(f"  {entry['drug']}: targets={entry['targets']}, "
              f"{len(entry['current_indications'])} current indications, "
              f"{len(entry['candidates'])} candidates")


if __name__ == "__main__":
    main()
