"""Streamlit UI for browsing ranked drug repurposing candidates."""

import pandas as pd
import streamlit as st

from scoring import get_candidates, load_cache

st.set_page_config(page_title="Drug Repurposing Candidate Finder", layout="wide")
st.title("Drug Repurposing Candidate Finder")


@st.cache_data
def get_cache() -> dict:
    return load_cache()


cache = get_cache()
drug_options = sorted(cache.get("drug_targets", {}).keys())

query_drug = st.selectbox("Search for a drug", drug_options)
top_k = st.slider("Number of candidates to show", min_value=1, max_value=20, value=10)

candidates = get_candidates(query_drug, cache, top_k=top_k)

if not candidates:
    st.info(f"No repurposing candidates found for {query_drug} in the current dataset.")
else:
    table = pd.DataFrame(
        [
            {
                "Indication": c.indication,
                "Phase": c.phase,
                "Source Drug": c.source_drug,
                "Shared Target": c.shared_target,
                "Score": round(c.score, 2),
            }
            for c in candidates
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    for c in candidates:
        with st.expander(f"{c.indication} — via {c.source_drug}"):
            st.write(c.rationale)
            if c.source_link:
                st.markdown(f"[Source trial data]({c.source_link})")
