# data/cache.json schema

This is the contract for the file Person 1's MCP wrapper writes. It mirrors the four
query functions 1:1, so `scoring.py` can index straight into it without any adapter
code.

```json
{
  "drug_targets": {
    "<drug>": ["<target>", "..."]
  },
  "target_drugs": {
    "<target>": ["<drug>", "..."]
  },
  "drug_indications": {
    "<drug>": [
      {
        "indication": "<free-text indication name>",
        "phase": "Preclinical | Phase 1 | Phase 2 | Phase 3 | Approved",
        "status": "active | discontinued | terminated | withdrawn",
        "trial_id": "<optional NCT id of one representative trial for this indication>"
      }
    ]
  },
  "catalyst_events": {
    "<drug>": [
      {
        "date": "YYYY-MM-DD",
        "event": "<free-text event description>",
        "indication": "<must match an indication name in drug_indications for the same drug>",
        "link": "<url back to the source trial/catalyst data>"
      }
    ]
  },
  "target_mechanisms": {
    "<target>": "<one-line, source-backed description of the shared downstream pathway/mechanism>"
  }
}
```

`target_mechanisms` is optional and owned by Person 3 (domain curation), not by the MCP wrapper —
it's a one-line, literature-backed statement of *why* a shared target plausibly bridges the old and
new indication (e.g. "GLP-1R agonism modulates dopaminergic reward-pathway signaling in addition to
metabolic control"). When a target has an entry here, `scoring.py` upgrades the rationale to the
"strong evidence" tier; when it doesn't, candidates still surface but with the generic "moderate"
tier. Only add an entry once the mechanism claim is actually sourced — an invented-sounding but
unsourced note is worse than no note, since it would misrepresent confidence to judges.

## Notes for Person 1

- `drug` and `target` strings are matched case-sensitively by `scoring.py`. Keep
  naming consistent across `drug_targets`, `target_drugs`, `drug_indications`, and
  `catalyst_events` (e.g. always `"Semaglutide"`, never `"semaglutide"`).
- `target_drugs[t]` should be the full symmetric list of drugs sharing target `t`,
  including the drug the target came from — `scoring.py` excludes the query drug
  itself when generating candidates.
- Every drug referenced in `target_drugs` should have an entry in `drug_indications`
  (even an empty list) so lookups don't need defensive fallback.
- `catalyst_events` is optional per drug — only used for a small recency bonus in
  scoring, not required for a candidate to appear.
- `trial_id` on an indication entry is optional and, when present, is used as a
  fallback link (`https://clinicaltrials.gov/study/<id>`) when no `catalyst_events`
  link matches. It's meant to be one representative trial for that indication, not
  an exhaustive list — don't invent one if the source data doesn't provide it.
- Save the file to `data/cache.json`. Until it exists, `scoring.load_cache()` falls
  back to `data/cache.sample.json` (a small hand-labeled mock) so downstream code
  isn't blocked.
