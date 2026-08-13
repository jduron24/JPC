# Drug Repurposing Candidate Finder

A tool that helps spot new uses for existing drugs.

## What it does

Many drugs already on the market, or already in clinical trials, could potentially treat
diseases beyond what they were originally designed for. This happens because different
drugs can act on the same biological "target" in the body — and if one drug on that target
is showing promise for a disease, others that share the target might work too.

This tool searches two ways:

- **Search by drug** — pick a drug, and see what other diseases it might be worth testing,
  based on what other drugs sharing its target are already being tried for.
- **Search by disease** — pick a disease, and see every drug currently being tested or
  already approved for it.

Every result links back to a real clinical trial, so nothing shown is a guess made up out
of thin air — it's either a documented trial or an explicit "we don't have a source for
this yet."

## How it works, in short

1. **Raw data** comes from Convoke's drug program tracker — real records of which drugs
   target what, and what diseases they've been tested for.
2. **A build script** (`data/build_cache.py`) cleans that raw data into one simple file
   (`data/cache.json`) the rest of the app reads from.
3. **The matching logic** (`scoring.py`) does the actual thinking: find shared targets,
   find other drugs on those targets, filter out anything already covered or discontinued,
   and rank what's left by how far along the evidence is.
4. **The app** (`app.py`) is what you actually see and click around in.

## What's in this repo

| File / folder | What it's for |
|---|---|
| `app.py` | The web app you interact with (built with Streamlit) |
| `scoring.py` | The core logic — finds and ranks candidates |
| `eval.py` | Checks the logic against a few real, known drug-repurposing stories |
| `ground_truth.json` | Those known real stories, used by `eval.py` |
| `data/build_cache.py` | Turns raw data into the file the app actually reads |
| `data/cache.json` | The cleaned, ready-to-use dataset |
| `data/raw/` | The original data pulled from Convoke |
| `data/SCHEMA.md` | A technical reference for how the data is shaped (for contributors) |

## Running it yourself

You'll need Python installed. Then, from this folder:

```bash
# one-time setup
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# start the app
.venv/bin/streamlit run app.py
```

This opens in your browser automatically. If you ever want to rebuild the dataset from the
raw data, or double-check the logic against known cases:

```bash
.venv/bin/python data/build_cache.py   # rebuild data/cache.json
.venv/bin/python eval.py               # sanity-check against known cases
```

## Good to know before you demo this

- **This is a small, curated dataset**, not the full universe of drugs — it currently
  covers 8 main drugs plus everything else that shares a target with them.
- **A "Target match only" tag means exactly that** — the tool found a real shared target,
  but no one has written up the biological reasoning behind it yet. It's not a weaker or
  wrong result, just an honest label for "not yet reviewed by a person."
- **A score reflects how far along a drug's evidence is** (early trial vs. approved), not
  how likely it is to actually work for the new disease. It's a ranking signal, not a
  prediction.
