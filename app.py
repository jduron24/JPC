"""Streamlit UI for browsing ranked drug repurposing candidates.

Written for a non-technical, biology-literate audience: plain-language labels,
a short explanation of what "shared target" means, and receptor descriptions
for anyone who doesn't have GLP-1R/PDE5/etc memorized.
"""

import pandas as pd
import streamlit as st

from scoring import get_candidates, load_cache

st.set_page_config(page_title="Target-Bridge — Drug Repurposing Explorer", layout="wide", page_icon="🧬")

# Plain-language descriptions of the biological targets in our dataset, so a
# viewer doesn't need to already know what "GLP-1R" means to follow the logic.
TARGET_DESCRIPTIONS = {
    "GLP-1R": "Glucagon-like peptide-1 receptor — regulates blood sugar, appetite, and insulin release.",
    "GIPR": "Glucose-dependent insulinotropic polypeptide receptor — works alongside GLP-1R in metabolism.",
    "GCGR": "Glucagon receptor — raises blood sugar; opposite effect to GLP-1R.",
    "PDE5": "Phosphodiesterase type 5 — regulates blood vessel relaxation (erectile dysfunction, pulmonary hypertension).",
    "AR": "Androgen receptor — mediates testosterone/DHT signaling (hair growth, prostate).",
    "MC4R": "Melanocortin 4 receptor — regulates appetite and energy balance in the brain.",
    "SSTR2": "Somatostatin receptor 2 — suppresses hormone secretion (growth hormone, insulin, glucagon).",
}

PHASE_ORDER = ["Approved", "Phase 3", "Phase 2", "Phase 1", "Preclinical"]
PHASE_LABEL = {
    "Approved": "✅ Approved",
    "Phase 3": "🔵 Phase 3",
    "Phase 2": "🟡 Phase 2",
    "Phase 1": "⚪ Phase 1",
    "Preclinical": "⚫ Preclinical",
}
EVIDENCE_ICON = {"high": "🟢", "moderate": "🟡", "low": "🔴"}

st.title("🧬 Target-Bridge: Drug Repurposing Explorer")
st.markdown(
    "**How this works:** pick a drug, and we find its biological target, find "
    "every *other* drug that acts on that same target, and show you the "
    "diseases those other drugs are being tested for that **your drug isn't "
    "being tested for yet.** Every row traces back to a real clinical trial."
)


@st.cache_data
def get_cache() -> dict:
    return load_cache()


cache = get_cache()
drug_options = sorted(cache.get("drug_targets", {}).keys())

with st.sidebar:
    st.header("Search")
    query_drug = st.selectbox("Choose a drug to explore", drug_options)
    top_k = st.slider("Number of candidates to show", min_value=1, max_value=30, value=10)
    hide_procedural = st.checkbox(
        "Hide procedural/diagnostic-only uses",
        value=True,
        help=(
            "Some 'shared target' matches are procedural (e.g. a drug used to relax "
            "gut muscle during an imaging scan), not a real disease-treatment "
            "indication. On by default so the list stays focused on genuine "
            "repurposing signal."
        ),
    )

targets = cache.get("drug_targets", {}).get(query_drug, [])
current_indications = cache.get("drug_indications", {}).get(query_drug, [])

st.subheader(f"About {query_drug}")
col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("**Biological target(s):**")
    for t in targets:
        description = TARGET_DESCRIPTIONS.get(t)
        st.markdown(f"- **{t}**" + (f" — {description}" if description else ""))
with col2:
    st.markdown("**Already known/approved/in trials for:**")
    if current_indications:
        st.markdown(", ".join(sorted({e["indication"] for e in current_indications})))
    else:
        st.markdown("_No indications on file for this drug._")

st.divider()

# top_k is a display cap on the *shown* list; we always fetch enough extra
# rows to backfill anything hidden by the procedural filter, otherwise
# hiding procedural rows would silently shrink the list below what the user
# asked for.
raw_candidates = get_candidates(query_drug, cache, top_k=top_k * 3)
candidates = [c for c in raw_candidates if not (hide_procedural and c.is_procedural)]
hidden_count = len(raw_candidates) - len(candidates)
candidates = candidates[:top_k]

st.subheader(f"Potential repurposing candidates for {query_drug}")

if not candidates:
    st.info(f"No repurposing candidates found for {query_drug} in the current dataset.")
else:
    if hidden_count:
        st.caption(f"({hidden_count} procedural/diagnostic-use row(s) hidden — toggle in the sidebar to show)")

    table = pd.DataFrame(
        [
            {
                "Potential New Use": c.indication,
                "Stage of Evidence": PHASE_LABEL.get(c.phase, c.phase),
                "Seen In (Drug)": c.source_drug,
                "Shared Target": c.shared_target,
                "Evidence Strength": f"{EVIDENCE_ICON.get(c.evidence_tier, '')} {c.evidence_label}",
                "Clinical Trial": c.source_link,
                "Priority Score": round(c.score, 2),
            }
            for c in candidates
        ]
    )
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Clinical Trial": st.column_config.LinkColumn(
                "Clinical Trial", display_text="View on ClinicalTrials.gov"
            ),
        },
    )

    st.markdown("#### Details & rationale")
    for c in candidates:
        with st.expander(f"{c.indication} — seen in {c.source_drug}"):
            st.write(c.rationale)
            if c.source_link:
                st.markdown(f"🔗 [View source trial on ClinicalTrials.gov]({c.source_link})")
            else:
                st.caption("No linked trial in dataset for this specific row.")

st.divider()
st.caption(
    "Data source: Convoke Program Tracker (biopharma knowledge graph), pulled live via MCP. "
    "Scores: Approved=5, Phase 3=4, Phase 2=3, Phase 1=2, Preclinical=1, plus a recency bonus "
    "for recent catalyst events. Procedural/diagnostic-use indications are capped at the "
    "Preclinical score regardless of their real phase, since they reflect a technical target "
    "overlap rather than a genuine disease-treatment signal. "
    "Evidence Strength: 🟢 High = 2+ independent drugs on the same target already have this "
    "indication; 🟡 Moderate = one drug, but at Approved/Phase 3; 🔴 Low = one drug at an "
    "earlier phase, or a procedural/diagnostic match."
)
