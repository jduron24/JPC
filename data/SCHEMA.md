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
        "status": "active | discontinued | terminated | withdrawn"
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
  }
}
```

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
- Save the file to `data/cache.json`. Until it exists, `scoring.load_cache()` falls
  back to `data/cache.sample.json` (a small hand-labeled mock) so downstream code
  isn't blocked.
