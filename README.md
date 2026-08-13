# Target-Bridge: Drug Repurposing Explorer

A tool that helps you spot new uses for existing drugs — and shows you the receipts.

## What this does for you

Pick a drug you care about, and this tool finds other drugs that act on the same
biological target in the body. If one of those other drugs is already being tested
for a disease yours isn't, that's a real, sourced lead — not a guess. Every result
traces back to an actual clinical trial, so you can hand this straight to a domain
expert or a judge and defend where every row came from.

Concretely, when you pick a drug you get:

- **What it's already known/approved for**, so you're not shown ideas it's already
  doing.
- **A ranked list of "potential new uses"** — diseases other drugs on the same target
  are being tested for, sorted by how strong the evidence is.
- **An Evidence Strength rating** on every result — 🟢 High means 2+ independent
  drugs on that target already have this indication (a real pattern, not a fluke),
  🟡 Moderate means one drug but at a late clinical stage, 🔴 Low means an early-stage
  or procedural-only match. Nothing is presented as more certain than it actually is.
- **A link to the real trial** behind every result, and a plain-English explanation
  of the reasoning underneath it.
- **Automatic noise filtering** — some "shared target" matches are actually
  procedural or diagnostic uses (e.g. a drug used to relax gut muscle during an
  imaging scan) rather than real disease treatment. Those get filtered out by
  default so you're not distracted by technicalities that share a target on paper
  but mean nothing biologically.

## How it works, briefly

1. Real drug/trial data comes from Convoke's biopharma knowledge graph, pulled via
   MCP.
2. A build script (`data/build_cache.py`) turns that raw data into one clean file
   (`data/cache.json`) the app reads from.
3. The matching logic (`scoring.py`) does the actual thinking — finds shared
   targets, filters out anything already known or discontinued, scores what's left
   by trial phase, and tiers it by how much independent evidence backs it up.
4. `app.py` is the app you interact with.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

This opens in your browser. To rebuild the dataset from raw data, or check the logic
against a handful of known, real drug-repurposing stories:

```bash
.venv/bin/python data/build_cache.py   # rebuild data/cache.json
.venv/bin/python eval.py               # sanity-check against known cases
```

## Good to know

- **This covers a curated set of 10 drugs** (plus everything else in the dataset
  that shares a target with them) — not the full universe of pharmaceuticals.
- **A "Priority Score" reflects how far along a drug's evidence is** (early trial vs.
  approved), not how likely it is to actually succeed for the new use. It's a
  ranking signal, not a prediction.
- **Evidence Strength is computed from real cross-drug data**, not assigned by hand —
  so it updates honestly as more trial data comes in, with no manual curation
  required to trust it.
