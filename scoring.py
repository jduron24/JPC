"""Candidate generation, filtering, scoring, and rationale for drug repurposing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CACHE_PATH = DATA_DIR / "cache.json"
FALLBACK_CACHE_PATH = DATA_DIR / "cache.sample.json"

PHASE_WEIGHTS = {
    "Approved": 5,
    "Phase 3": 4,
    "Phase 2": 3,
    "Phase 1": 2,
    "Preclinical": 1,
}
EXCLUDED_STATUSES = {"discontinued", "terminated", "withdrawn"}

RECENCY_WINDOW_DAYS = 365
RECENCY_MAX_BONUS = 1.5

TRIAL_URL_TEMPLATE = "https://clinicaltrials.gov/study/{trial_id}"

# Indications that are procedural/diagnostic/perioperative uses of a drug
# rather than disease-treatment indications (e.g. glucagon relaxing GI smooth
# muscle for a radiology exam). These share the query drug's target on a
# technicality and shouldn't outrank genuine disease indications just because
# the underlying program happens to be Approved/Phase 3.
PROCEDURAL_KEYWORDS = (
    "diagnostic aid",
    "diagnostic imaging",
    "radiologic examination",
    "radiographic",
    "imaging",
    "anesthesia adjunct",
    "anaesthesia adjunct",
    "perioperative",
)

# Capped at the Preclinical weight so a procedural indication never outranks
# a genuine disease indication at any real trial phase (Phase 1+), while
# still surfacing rather than being hard-excluded.
PROCEDURAL_SCORE_CAP = PHASE_WEIGHTS["Preclinical"]


def is_procedural_indication(indication: str) -> bool:
    lowered = indication.lower()
    return any(keyword in lowered for keyword in PROCEDURAL_KEYWORDS)


# Evidence Strength tiers -- how much independent cross-drug support a
# candidate indication has, computed from data we actually have (not a
# hardcoded label). "Confidence" implied we knew whether the candidate is
# CORRECT; what we can actually measure is how much evidence backs it, hence
# the rename.
#   HIGH:     2+ distinct other drugs on the same target already have this
#             indication -- independent cross-drug precedent.
#   MODERATE: exactly 1 other drug has it, at Approved or Phase 3 -- a
#             single but late-stage (de-risked) source.
#   LOW:      exactly 1 other drug has it at Phase 1/2, or it's a
#             procedural/diagnostic-only match (already score-capped).
EVIDENCE_LABELS = {
    "high": "High ({support_count}+ independent drugs)",
    "moderate": "Moderate (single-source, late-phase)",
    "low_procedural": "Low (procedural/diagnostic use)",
    "low_early_phase": "Low (single-source, early-phase)",
}


def compute_evidence(indication: str, phase: str, support_count: int) -> tuple[str, str]:
    """Returns (evidence_tier, evidence_label). support_count is the number of
    distinct OTHER drugs (sharing the query drug's target) that also have this
    exact indication -- computed by aggregating across all matches first, not
    just looking at the one row being scored."""
    if is_procedural_indication(indication):
        return "low", EVIDENCE_LABELS["low_procedural"]
    if support_count >= 2:
        return "high", EVIDENCE_LABELS["high"].format(support_count=support_count)
    if phase in ("Approved", "Phase 3"):
        return "moderate", EVIDENCE_LABELS["moderate"]
    return "low", EVIDENCE_LABELS["low_early_phase"]


@dataclass
class Candidate:
    query_drug: str
    shared_target: str
    source_drug: str
    indication: str
    phase: str
    score: float
    rationale: str
    evidence_tier: str
    evidence_label: str
    is_procedural: bool
    trial_id: str | None
    source_link: str | None


@dataclass
class DrugMatch:
    indication: str
    drug: str
    phase: str
    status: str
    score: float
    trial_id: str | None
    source_link: str | None


def load_cache(path: str | Path | None = None) -> dict:
    cache_path = Path(path) if path else DEFAULT_CACHE_PATH
    if not cache_path.exists():
        cache_path = FALLBACK_CACHE_PATH
    with cache_path.open() as f:
        return json.load(f)


def _is_already_covered(indication: str, original_indications: set[str]) -> bool:
    return indication.lower() in original_indications


def _is_excluded_status(status: str) -> bool:
    return status.lower() in EXCLUDED_STATUSES


def _recency_bonus(events: list[dict], indication: str, today: date | None = None) -> float:
    today = today or date.today()
    matching_dates = [
        datetime.strptime(event["date"], "%Y-%m-%d").date()
        for event in events
        if event.get("indication", "").lower() == indication.lower()
    ]
    if not matching_dates:
        return 0.0
    days_since = (today - max(matching_dates)).days
    if days_since < 0 or days_since > RECENCY_WINDOW_DAYS:
        return 0.0
    return RECENCY_MAX_BONUS * (1 - days_since / RECENCY_WINDOW_DAYS)


def score_candidate(phase: str, indication: str, catalyst_events: list[dict]) -> float:
    score = PHASE_WEIGHTS.get(phase, 0) + _recency_bonus(catalyst_events, indication)
    if is_procedural_indication(indication):
        score = min(score, PROCEDURAL_SCORE_CAP)
    return score


def generate_rationale(
    query_drug: str,
    shared_target: str,
    source_drug: str,
    indication: str,
    phase: str,
    evidence_tier: str,
    support_drugs: set[str],
    mechanism_note: str | None = None,
) -> str:
    if is_procedural_indication(indication):
        return (
            f"{source_drug} shares target {shared_target} with {query_drug}, but its "
            f"{phase} activity in {indication} is a procedural/diagnostic use, not a "
            f"disease-treatment indication -- weak signal for repurposing {query_drug}."
        )

    mechanism_sentence = f" {mechanism_note}" if mechanism_note else ""

    if evidence_tier == "high":
        others = sorted(support_drugs - {source_drug})
        others_text = " and ".join(others) if len(others) <= 2 else f"{len(others)} other drugs"
        return (
            f"{source_drug} shares target {shared_target} with {query_drug}.{mechanism_sentence} "
            f"{indication} isn't just a one-off: {others_text} on the same target ALSO has an "
            f"active program in {indication}, independent cross-drug precedent rather than a "
            f"single coincidental match."
        )

    return (
        f"{source_drug} shares target {shared_target} with {query_drug}.{mechanism_sentence} "
        f"{source_drug}'s {phase} activity in {indication} is currently the only source of this "
        f"signal for {query_drug} -- no other drug on {shared_target} has reached {indication} yet."
    )


def get_candidates(query_drug: str, cache: dict, top_k: int | None = 10) -> list[Candidate]:
    targets = cache.get("drug_targets", {}).get(query_drug, [])
    original_indications = {
        entry["indication"].lower()
        for entry in cache.get("drug_indications", {}).get(query_drug, [])
    }

    shared_target_by_source: dict[str, str] = {}
    for target in targets:
        for drug in cache.get("target_drugs", {}).get(target, []):
            if drug != query_drug:
                shared_target_by_source.setdefault(drug, target)

    target_mechanisms = cache.get("target_mechanisms", {})

    # Pass 1: collect every (source_drug, indication) row that survives the
    # already-covered/excluded-status filters, without scoring yet -- we need
    # the full set first to know how many distinct drugs back each indication.
    raw_rows = []
    for source_drug, shared_target in shared_target_by_source.items():
        catalyst_events = cache.get("catalyst_events", {}).get(source_drug, [])
        for entry in cache.get("drug_indications", {}).get(source_drug, []):
            indication = entry["indication"]
            if _is_already_covered(indication, original_indications):
                continue
            if _is_excluded_status(entry.get("status", "active")):
                continue
            raw_rows.append(
                {
                    "source_drug": source_drug,
                    "shared_target": shared_target,
                    "indication": indication,
                    "phase": entry["phase"],
                    "trial_id": entry.get("trial_id"),
                    "catalyst_events": catalyst_events,
                }
            )

    # Pass 2: aggregate -- for each indication, which distinct drugs support it.
    support_by_indication: dict[str, set[str]] = {}
    for row in raw_rows:
        key = row["indication"].lower()
        support_by_indication.setdefault(key, set()).add(row["source_drug"])

    # Pass 3: score and tier each row using the aggregated support counts.
    candidates = []
    for row in raw_rows:
        indication = row["indication"]
        phase = row["phase"]
        source_drug = row["source_drug"]
        shared_target = row["shared_target"]
        catalyst_events = row["catalyst_events"]
        support_drugs = support_by_indication[indication.lower()]

        trial_id = row["trial_id"]
        link = next(
            (
                event["link"]
                for event in catalyst_events
                if event.get("indication", "").lower() == indication.lower()
            ),
            None,
        )
        if link is None and trial_id:
            link = TRIAL_URL_TEMPLATE.format(trial_id=trial_id)

        evidence_tier, evidence_label = compute_evidence(indication, phase, len(support_drugs))
        rationale = generate_rationale(
            query_drug,
            shared_target,
            source_drug,
            indication,
            phase,
            evidence_tier,
            support_drugs,
            target_mechanisms.get(shared_target),
        )
        candidates.append(
            Candidate(
                query_drug=query_drug,
                shared_target=shared_target,
                source_drug=source_drug,
                indication=indication,
                phase=phase,
                score=score_candidate(phase, indication, catalyst_events),
                rationale=rationale,
                evidence_tier=evidence_tier,
                evidence_label=evidence_label,
                is_procedural=is_procedural_indication(indication),
                trial_id=trial_id,
                source_link=link,
            )
        )

    # Primary: score descending. Secondary: procedural-tagged rows sink below
    # any tie (belt-and-suspenders alongside the score cap in score_candidate).
    # Tertiary: indication name, so ties land in a stable, explainable order
    # instead of whatever order dict iteration happened to produce.
    candidates.sort(key=lambda c: (-c.score, c.is_procedural, c.indication.lower()))
    return candidates[:top_k]


def list_indications(cache: dict) -> list[str]:
    return sorted(
        {
            entry["indication"]
            for entries in cache.get("drug_indications", {}).values()
            for entry in entries
        }
    )


def get_drugs_for_indication(indication: str, cache: dict, top_k: int | None = 10) -> list[DrugMatch]:
    matches = []
    for drug, entries in cache.get("drug_indications", {}).items():
        catalyst_events = cache.get("catalyst_events", {}).get(drug, [])
        for entry in entries:
            if entry["indication"].lower() != indication.lower():
                continue
            status = entry.get("status", "active")
            if _is_excluded_status(status):
                continue

            trial_id = entry.get("trial_id")
            link = next(
                (
                    event["link"]
                    for event in catalyst_events
                    if event.get("indication", "").lower() == indication.lower()
                ),
                None,
            )
            if link is None and trial_id:
                link = TRIAL_URL_TEMPLATE.format(trial_id=trial_id)

            matches.append(
                DrugMatch(
                    indication=entry["indication"],
                    drug=drug,
                    phase=entry["phase"],
                    status=status,
                    score=score_candidate(entry["phase"], indication, catalyst_events),
                    trial_id=trial_id,
                    source_link=link,
                )
            )

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:top_k]
