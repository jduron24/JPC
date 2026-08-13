"""Transforms raw Convoke Program Tracker JSON (data/raw/*.json) into data/cache.json,
matching the contract in data/SCHEMA.md.

Replaces Person 1's build_cache.py, which targeted a different schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"
CACHE_PATH = Path(__file__).parent / "cache.json"

# Convoke's raw drug_name -> our canonical drug name. Only these 8 are in scope;
# every other drug_name in data/raw/*.json is either a candidate-pool entry (handled
# separately) or noise from a broader MCP query and gets dropped.
CURATED_DRUGS = {
    "Brenipatide": "Brenipatide",
    "Semaglutide": "Semaglutide",
    "Tirzepatide": "Tirzepatide",
    "Liraglutide": "Liraglutide",
    "Dulaglutide": "Dulaglutide",
    "LY3437943": "Retatrutide",
    "Sildenafil": "Sildenafil",
    "Minoxidil": "Minoxidil",
    "Bremelanotide": "Bremelanotide",
    "Octreotide": "Octreotide",
}

# Bremelanotide/Octreotide were added to ground_truth.json as extra validation
# cases but never had their own drug-specific pull or target-sharing pool.
# Convoke tags Bremelanotide's own target generically as "MCR" (not "MC4R"
# specifically) and Octreotide's as {SSTR2, SSTR3, SSTR5} -- both correct per
# real pharmacology (PT-141 is a known MC3R/MC4R agonist; octreotide is a
# broad-spectrum somatostatin analog). We normalize to the single target each
# was queried under (MC4R / SSTR2) so they bucket with their real candidate
# pools instead of sitting in a target key nothing else uses.
TARGET_OVERRIDES = {
    "Bremelanotide": ["MC4R"],
    "Octreotide": ["SSTR2"],
}

STATUS_MAP = {
    "Active": "active",
    "Probable Inactive": "withdrawn",
    "Discontinued": "discontinued",
    "Terminated": "terminated",
    "Withdrawn": "withdrawn",
}


def map_status(program_status: str) -> str:
    try:
        return STATUS_MAP[program_status]
    except KeyError:
        raise ValueError(f"Unrecognized program_status from Convoke data: {program_status!r}")


def map_phase(development_stage: str) -> str:
    if development_stage == "Regulatory Approval":
        return "Approved"
    if development_stage in {"Unspecified", "Phase 0"}:
        return "Preclinical"
    numbers = [int(n) for n in re.findall(r"\d+", development_stage)]
    if numbers:
        return f"Phase {max(numbers)}"
    raise ValueError(f"Unrecognized development_stage from Convoke data: {development_stage!r}")


def load_items(filename: str) -> list[dict]:
    with (RAW_DIR / filename).open() as f:
        return json.load(f)["items"]


def build_indication_entry(item: dict) -> dict:
    entry = {
        "indication": item["indication_name"],
        "phase": map_phase(item["development_stage"]),
        "status": map_status(item["program_status"]),
    }
    trials = item.get("trials") or []
    if trials:
        entry["trial_id"] = trials[0]["nct_id"]
    return entry


def build_curated(drug_items: list[dict]) -> tuple[dict, dict]:
    drug_targets: dict[str, list[str]] = {}
    drug_indications: dict[str, list[dict]] = {}
    for item in drug_items:
        canonical = CURATED_DRUGS.get(item["drug_name"])
        if canonical is None:
            continue
        drug_targets.setdefault(canonical, TARGET_OVERRIDES.get(canonical, item["targets"]))
        drug_indications.setdefault(canonical, []).append(build_indication_entry(item))
    return drug_targets, drug_indications


def add_pool_to_target_drugs(target_drugs: dict[str, list[str]], pool_items: list[dict], targets: list[str]) -> None:
    for item in pool_items:
        drug = item["drug_name"]
        for target in targets:
            bucket = target_drugs.setdefault(target, [])
            if drug not in bucket:
                bucket.append(drug)


def add_pool_indications(drug_indications: dict[str, list[dict]], pool_items: list[dict]) -> None:
    curated_names = set(CURATED_DRUGS.values())
    for item in pool_items:
        drug = item["drug_name"]
        if drug in curated_names:
            continue  # curated file already has the fuller (all-phase, all-status) picture
        drug_indications.setdefault(drug, []).append(build_indication_entry(item))


def build_cache() -> dict:
    drug_items = (
        load_items("program_tracker_drugs_p1.json")
        + load_items("program_tracker_drugs_p2.json")
        + load_items("program_tracker_drugs_bremelanotide_octreotide.json")
    )
    glp1_gipr_gcgr_pool = load_items("program_tracker_targets_glp1_gipr_gcgr.json")
    pde5_pool = load_items("program_tracker_targets_pde5.json")
    mc4r_pool = load_items("program_tracker_targets_mc4r.json")
    sstr2_pool = load_items("program_tracker_targets_sstr2.json")

    drug_targets, drug_indications = build_curated(drug_items)

    target_drugs: dict[str, list[str]] = {}
    # Queried with all three targets at once, so we don't know which specific one each
    # row hit -- every drug in this pool goes under all three keys. Never a false
    # candidate (each row genuinely hit at least one), just an imprecise rationale
    # target for multi-target source drugs.
    add_pool_to_target_drugs(target_drugs, glp1_gipr_gcgr_pool, ["GLP-1R", "GIPR", "GCGR"])
    add_pool_to_target_drugs(target_drugs, pde5_pool, ["PDE5"])
    add_pool_to_target_drugs(target_drugs, mc4r_pool, ["MC4R"])
    add_pool_to_target_drugs(target_drugs, sstr2_pool, ["SSTR2"])

    # Curated drugs' own real targets are precise (unlike the ambiguous pool above),
    # so make sure they're bucketed correctly even if a drug is missing from its pool.
    for drug, targets in drug_targets.items():
        for target in targets:
            bucket = target_drugs.setdefault(target, [])
            if drug not in bucket:
                bucket.append(drug)

    add_pool_indications(drug_indications, glp1_gipr_gcgr_pool)
    add_pool_indications(drug_indications, pde5_pool)
    add_pool_indications(drug_indications, mc4r_pool)
    add_pool_indications(drug_indications, sstr2_pool)

    # Minoxidil's AR target query returned unrelated prostate-cancer drugs -- a
    # knowledge-graph tagging artifact, not real shared biology with minoxidil's
    # actual mechanism (a KATP channel opener). Self-only entry, no pool.
    target_drugs["AR"] = ["Minoxidil"]

    return {
        "drug_targets": drug_targets,
        "target_drugs": target_drugs,
        "drug_indications": drug_indications,
    }


def main() -> None:
    cache = build_cache()
    with CACHE_PATH.open("w") as f:
        json.dump(cache, f, indent=2)
    print(f"Wrote {CACHE_PATH} ({len(cache['drug_indications'])} drugs, {len(cache['target_drugs'])} targets)")


if __name__ == "__main__":
    main()
