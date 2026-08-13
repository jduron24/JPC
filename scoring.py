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


@dataclass
class Candidate:
    query_drug: str
    shared_target: str
    source_drug: str
    indication: str
    phase: str
    score: float
    rationale: str
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
    query_drug: str, shared_target: str, source_drug: str, indication: str, phase: str
) -> str:
    return (
        f"{source_drug} shares target {shared_target} with {query_drug}, "
        f"active in {phase} for {indication}."
    )


def get_candidates(query_drug: str, cache: dict, top_k: int = 10) -> list[Candidate]:
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

    candidates = []
    for source_drug, shared_target in shared_target_by_source.items():
        catalyst_events = cache.get("catalyst_events", {}).get(source_drug, [])
        for entry in cache.get("drug_indications", {}).get(source_drug, []):
            indication = entry["indication"]
            phase = entry["phase"]
            if _is_already_covered(indication, original_indications):
                continue
            if _is_excluded_status(entry.get("status", "active")):
                continue

            link = next(
                (
                    event["link"]
                    for event in catalyst_events
                    if event.get("indication", "").lower() == indication.lower()
                ),
                None,
            )
            candidates.append(
                Candidate(
                    query_drug=query_drug,
                    shared_target=shared_target,
                    source_drug=source_drug,
                    indication=indication,
                    phase=phase,
                    score=score_candidate(phase, indication, catalyst_events),
                    rationale=generate_rationale(
                        query_drug, shared_target, source_drug, indication, phase
                    ),
                    source_link=link,
                )
            )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_k]
