"""Wrapper functions over Convoke Program Tracker data.

These operate on raw MCP response JSON already fetched and saved under
data/raw/ (see build_cache.py for how it was pulled). They do not call the
MCP server themselves -- the live query_program_tracker calls were made
directly against the Convoke MCP server during this session to keep the
hackathon's 10-credit budget under control (2 calls to page through all
curated-drug programs, 1 scoped call for the GLP-1R/GIPR/GCGR shared-target
set). Rerun the queries yourself and drop new JSON into data/raw/ if you need
fresher or broader data -- these functions don't care where the JSON came
from as long as the shape matches what query_program_tracker returns.
"""

import json
from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"

# Convoke's entity resolution grouped these drug_name variants under one
# input query (they share the same entity_ids set in entity_resolution).
# Curated list name -> drug_name strings that appear in the raw rows.
DRUG_ALIASES = {
    "Brenipatide": ["Brenipatide", "LY3537031"],
    "Semaglutide": ["Semaglutide", "SYH9017", "Semaglutide Injection (HD1916)"],
    "Tirzepatide": ["Tirzepatide"],
    "Liraglutide": ["Liraglutide"],
    "Dulaglutide": ["Dulaglutide"],
    "Retatrutide": ["LY3437943"],  # Convoke's canonical name for retatrutide
    "Sildenafil": ["Sildenafil", "Sildenafil Citrate"],
    "Minoxidil": ["Minoxidil", "VDPHL01"],
}


def load_items(*filenames):
    items = []
    for filename in filenames:
        with open(RAW_DIR / filename) as f:
            items.extend(json.load(f)["items"])
    return items


def get_target(drug_name, drug_rows):
    """Unique targets for a curated drug, from Program Tracker rows."""
    names = DRUG_ALIASES.get(drug_name, [drug_name])
    targets = set()
    for row in drug_rows:
        if row["drug_name"] in names:
            targets.update(row.get("targets", []))
    return sorted(targets)


def get_indications_for_drug(drug_name, drug_rows):
    """Current indications + phase + status for a curated drug."""
    names = DRUG_ALIASES.get(drug_name, [drug_name])
    return [
        {
            "indication": row["indication_name"],
            "phase": row["development_stage"],
            "status": row["program_status"],
        }
        for row in drug_rows
        if row["drug_name"] in names
    ]


def get_drugs_sharing_target(drug_name, drug_rows, target_rows):
    """Other drugs hitting drug_name's target(s), with indication/phase/org/trials.

    shared_target is the intersection of drug_name's own targets with the
    target set the shared-target query was scoped to (GLP-1R/GIPR/GCGR).
    target_rows doesn't carry a per-row target field (skipped to shrink the
    payload), so a candidate hitting multiple targets can't be attributed to
    exactly one -- this is an approximation, not a precise per-row match.
    """
    own_targets = set(get_target(drug_name, drug_rows))
    exclude_names = set(DRUG_ALIASES.get(drug_name, [drug_name]))
    shared_target = ", ".join(sorted(own_targets)) or None
    return [
        {
            "candidate_drug": row["drug_name"],
            "shared_target": shared_target,
            "candidate_indication": row["indication_name"],
            "phase": row["development_stage"],
            "organization": ", ".join(row.get("organizations", [])) or None,
            "trial_ids": [t["nct_id"] for t in row.get("trials", [])],
        }
        for row in target_rows
        if row["drug_name"] not in exclude_names
    ]


def get_catalysts_for_drug(drug_name, catalyst_rows=None):
    """Upcoming readouts/events for a drug.

    Not pulled this round -- skipped to conserve MCP credits. Pass rows from
    a query_catalyst_calendar(drug=drug_name, task_relevant_fields=["drugs",
    "sort_date"]) call to populate.
    """
    if not catalyst_rows:
        return []
    names = DRUG_ALIASES.get(drug_name, [drug_name])
    return [
        {
            "event_name": row.get("event_name"),
            "reported_date": row.get("reported_date"),
            "is_congress": row.get("is_congress"),
        }
        for row in catalyst_rows
        if any(d in names for d in row.get("drugs", []))
    ]
