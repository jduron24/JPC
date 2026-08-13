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
    return PHASE_WEIGHTS.get(phase, 0) + _recency_bonus(catalyst_events, indication)


def generate_rationale(
    query_drug: str,
    shared_target: str,
    source_drug: str,
    indication: str,
    phase: str,
    mechanism_note: str | None = None,
) -> tuple[str, str]:
    """Returns (rationale, evidence_tier). Tier is "strong" only when a curated
    mechanism_note backs the shared target — never inferred from phase/score alone,
    since that would overstate mechanistic confidence we don't actually have."""
    if mechanism_note:
        rationale = (
            f"{source_drug} and {query_drug} both act on {shared_target}. {mechanism_note} "
            f"{source_drug}'s Phase {phase} activity in {indication} suggests a "
            f"mechanistically grounded repurposing opportunity for {query_drug}."
        )
        return rationale, "strong"

    rationale = (
        f"{source_drug} shares target {shared_target} with {query_drug}, "
        f"active in {phase} for {indication}."
    )
    return rationale, "moderate"


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

    candidates = []
    for source_drug, shared_target in shared_target_by_source.items():
        catalyst_events = cache.get("catalyst_events", {}).get(source_drug, [])
        mechanism_note = target_mechanisms.get(shared_target)
        for entry in cache.get("drug_indications", {}).get(source_drug, []):
            indication = entry["indication"]
            phase = entry["phase"]
            if _is_already_covered(indication, original_indications):
                continue
            if _is_excluded_status(entry.get("status", "active")):
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
            rationale, evidence_tier = generate_rationale(
                query_drug, shared_target, source_drug, indication, phase, mechanism_note
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
                    trial_id=trial_id,
                    source_link=link,
                )
            )

    candidates.sort(key=lambda c: c.score, reverse=True)
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
