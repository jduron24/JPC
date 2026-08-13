"""Streamlit UI for browsing ranked drug repurposing candidates.

Layout/visual design ported from a static HTML mock (Repurposing Results.dc.html).
Two modes share one page via a toggle: search by drug (get_candidates, shared-target
inference) or search by disease (get_drugs_for_indication, direct lookup -- no
inference, just "who's already being tested for this"). Interactive controls are real
Streamlit widgets restyled with CSS; everything else is custom-rendered HTML driven
entirely by scoring.py output -- no fields are invented beyond what the dataclasses have.
"""

import html

import streamlit as st

from scoring import (
    Candidate,
    DrugMatch,
    get_candidates,
    get_drugs_for_indication,
    list_indications,
    load_cache,
)

st.set_page_config(page_title="Drug Repurposing Candidate Finder", layout="wide")

PHASES = ["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Approved"]

INK = "oklch(0.24 0.012 250)"
BODY_TEXT = "oklch(0.38 0.012 250)"
MUTED = "oklch(0.5 0.012 250)"
FAINT = "oklch(0.58 0.012 250)"
BORDER = "oklch(0.88 0.008 250)"
BORDER_SOFT = "oklch(0.92 0.008 250)"
PAPER = "oklch(0.983 0.004 95)"
ACCENT = "oklch(0.48 0.075 205)"
ACCENT_BG = "oklch(0.94 0.03 205)"
ACCENT_BORDER = "oklch(0.82 0.05 205)"
ACCENT_TEXT = "oklch(0.38 0.07 205)"
CHIP_BG = "oklch(0.95 0.006 250)"
CHIP_BORDER = "oklch(0.89 0.008 250)"

DRUG_MODE_LABEL = "Drugs"
DISEASE_MODE_LABEL = "Diseases"

DRUG_MODE_DESCRIPTION = (
    "Pick a drug. We find other drugs that hit the same biological target, then surface "
    "the indications those drugs are already being tested for &mdash; and yours isn't. "
    "Each row is a hypothesis with a trial behind it, not a prediction."
)
DRUG_MODE_STEPS = [
    "1 &middot; your drug",
    "2 &middot; shared target",
    "3 &middot; other drugs on that target",
    "4 &middot; their indications, minus yours",
]

DISEASE_MODE_DESCRIPTION = (
    "Pick a disease. We show every drug in the dataset already being tested for it, "
    "ranked by how far along that evidence is. This is a direct match against tracked "
    "programs, not a shared-target inference."
)
DISEASE_MODE_STEPS = [
    "1 &middot; your disease",
    "2 &middot; drugs tracked for it",
    "3 &middot; ranked by clinical stage",
]


def inject_styles() -> None:
    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
        .stApp {{ background: {PAPER}; }}
        .block-container {{
            max-width: 1180px !important; margin: 0 auto; padding-top: 2.5rem !important;
            padding-bottom: 4rem; font-family: 'IBM Plex Sans', system-ui, sans-serif; color: {INK};
        }}
        h1, h2, h3 {{ font-family: 'Newsreader', Georgia, serif; font-weight: 400; }}
        a {{ color: {ACCENT}; }}
        [data-testid="stSelectbox"] label p, [data-testid="stSlider"] label p {{
            font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: {MUTED};
        }}
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
            background: white; border: 1px solid oklch(0.82 0.01 250); border-radius: 6px;
        }}
        [data-testid="stSlider"] div[data-baseweb="slider"] div[role="slider"] {{
            background-color: {ACCENT} !important; border-color: {ACCENT} !important;
        }}
        [data-testid="stSlider"] div[data-testid="stTickBarMin"],
        [data-testid="stSlider"] div[data-testid="stTickBarMax"] {{ color: {FAINT}; }}
        [data-testid="stRadio"] div[role="radiogroup"] {{ gap: 8px; }}
        [data-testid="stRadio"] div[role="radiogroup"] label {{
            background: {CHIP_BG}; border: 1px solid {CHIP_BORDER}; border-radius: 999px;
            padding: 8px 20px;
        }}
        [data-testid="stRadio"] div[role="radiogroup"] label,
        [data-testid="stRadio"] div[role="radiogroup"] label * {{
            font-family: 'IBM Plex Sans', system-ui, sans-serif !important;
            font-size: 14.5px !important; font-weight: 500 !important; letter-spacing: normal !important;
            color: {INK} !important; opacity: 1 !important;
        }}
        [data-testid="stRadio"] div[role="radiogroup"] label input[type="radio"] {{
            position: absolute; opacity: 0; width: 0; height: 0;
        }}
        [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked),
        [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) * {{
            background: {ACCENT}; border-color: {ACCENT}; color: white !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(description: str, steps: list[str]) -> None:
    chips = []
    for i, step in enumerate(steps):
        if i > 0:
            chips.append('<span style="color:oklch(0.7 0.01 250);">&rarr;</span>')
        is_last = i == len(steps) - 1
        style = (
            f"background:{ACCENT};color:oklch(0.98 0.01 205);padding:6px 10px;border-radius:3px;"
            if is_last
            else f"background:{CHIP_BG};padding:6px 10px;border-radius:3px;"
        )
        chips.append(f'<span style="{style}">{step}</span>')
    steps_html = "".join(chips)

    st.markdown(
        f"""
        <div style="display:flex;flex-direction:column;gap:14px;border-bottom:1px solid {BORDER};padding-bottom:22px;margin-bottom:20px;">
          <div style="display:flex;align-items:baseline;justify-content:space-between;gap:24px;flex-wrap:wrap;">
            <h1 style="font-size:40px;line-height:1.05;margin:0;letter-spacing:-0.01em;">Drug Repurposing Candidate Finder</h1>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.09em;text-transform:uppercase;color:{FAINT};border:1px solid {BORDER};border-radius:3px;padding:5px 9px;">Demo build &middot; cached dataset</span>
          </div>
          <p style="margin:0;max-width:74ch;font-size:16.5px;line-height:1.5;color:{BODY_TEXT};">{description}</p>
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:'IBM Plex Mono',monospace;font-size:12px;color:{MUTED};margin-top:2px;">
            {steps_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stats(col, tiles: list[tuple[int, str]]) -> None:
    tiles_html = "".join(
        f'<div style="display:flex;flex-direction:column;gap:3px;">'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:26px;line-height:1;">{value}</span>'
        f'<span style="font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:{FAINT};">{label}</span>'
        f"</div>"
        for value, label in tiles
    )
    with col:
        st.markdown(
            f'<div style="display:flex;gap:26px;justify-content:flex-end;text-align:right;padding-top:30px;">{tiles_html}</div>',
            unsafe_allow_html=True,
        )


def render_section_header(title_html: str, caption: str) -> None:
    st.markdown(
        f"""
        <div style="display:flex;align-items:baseline;justify-content:space-between;gap:20px;flex-wrap:wrap;border-top:1px solid {BORDER};padding-top:18px;margin-top:8px;">
          <h2 style="font-size:22px;margin:0;">{title_html}</h2>
          <span style="font-size:12.5px;color:{MUTED};font-family:'IBM Plex Mono',monospace;">{caption}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _phase_steps_html(phase: str) -> str:
    phase_index = PHASES.index(phase)
    return "".join(
        f'<span style="height:7px;flex:1;border-radius:2px;background:{ACCENT if step <= phase_index else "oklch(0.91 0.008 250)"};"></span>'
        for step in range(len(PHASES))
    )


def _trial_link_html(trial_id: str | None, source_link: str | None) -> str:
    if trial_id and source_link:
        return (
            f'<a href="{html.escape(source_link)}" target="_blank" rel="noopener" '
            f'style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;">{html.escape(trial_id)} &#8599;</a>'
        )
    return (
        '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12.5px;color:oklch(0.62 0.012 250);">'
        "no linked trial record</span>"
    )


# Visual weight per evidence tier -- solid accent for corroborated (high),
# tinted accent for a single late-phase source (moderate), dashed muted for
# a single early-phase or procedural/diagnostic-only source (low). The label
# text itself (c.evidence_label) already distinguishes "low" reasons, so no
# separate procedural tag is needed here.
_EVIDENCE_BADGE_STYLE = {
    "high": f"background:{ACCENT};color:white;border:1px solid {ACCENT};",
    "moderate": f"background:{ACCENT_BG};border:1px solid {ACCENT_BORDER};color:{ACCENT_TEXT};",
    "low": f"color:{MUTED};border:1px dashed oklch(0.78 0.01 250);",
}


def _evidence_badge_html(c: Candidate) -> str:
    style = _EVIDENCE_BADGE_STYLE.get(c.evidence_tier, _EVIDENCE_BADGE_STYLE["low"])
    return (
        f'<span style="display:inline-flex;align-items:center;gap:6px;font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:11.5px;letter-spacing:0.05em;text-transform:uppercase;border-radius:3px;padding:5px 9px;{style}">'
        f"{html.escape(c.evidence_label)}</span>"
    )


def render_candidate_card(rank: int, c: Candidate) -> None:
    st.markdown(
        f"""
        <article style="display:grid;grid-template-columns:44px minmax(0,1fr) 250px;gap:24px;background:white;border:1px solid {BORDER};border-radius:8px;padding:22px 24px;margin-bottom:12px;box-shadow:0 1px 2px oklch(0.2 0.02 250 / 0.04);">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:15px;color:oklch(0.65 0.012 250);padding-top:3px;">{rank:02d}</div>
          <div style="display:flex;flex-direction:column;gap:12px;min-width:0;">
            <h3 style="font-size:25px;line-height:1.15;margin:0;letter-spacing:-0.005em;">{html.escape(c.indication)}</h3>
            <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:13.5px;">
              <span style="font-family:'IBM Plex Mono',monospace;background:{CHIP_BG};border:1px solid {CHIP_BORDER};border-radius:3px;padding:4px 8px;">{html.escape(c.query_drug)}</span>
              <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.05em;text-transform:uppercase;color:{MUTED};">shares</span>
              <span style="font-family:'IBM Plex Mono',monospace;font-weight:500;background:{ACCENT_BG};border:1px solid {ACCENT_BORDER};color:{ACCENT_TEXT};border-radius:3px;padding:4px 8px;">{html.escape(c.shared_target)}</span>
              <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.05em;text-transform:uppercase;color:{MUTED};">with</span>
              <span style="font-family:'IBM Plex Mono',monospace;background:{CHIP_BG};border:1px solid {CHIP_BORDER};border-radius:3px;padding:4px 8px;">{html.escape(c.source_drug)}</span>
            </div>
            <p style="margin:0;font-size:15px;line-height:1.5;color:{BODY_TEXT};max-width:62ch;border-left:2px solid {BORDER_SOFT};padding-left:13px;">{html.escape(c.rationale)}</p>
            <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;font-size:13px;color:{MUTED};">
              {_evidence_badge_html(c)}
              {_trial_link_html(c.trial_id, c.source_link)}
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:14px;border-left:1px solid {BORDER_SOFT};padding-left:22px;">
            <div style="display:flex;flex-direction:column;gap:7px;">
              <span style="font-size:10.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{FAINT};">Stage for {html.escape(c.source_drug)}</span>
              <span style="display:flex;gap:3px;">{_phase_steps_html(c.phase)}</span>
              <span style="font-size:16px;font-weight:600;letter-spacing:-0.005em;">{html.escape(c.phase)}</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:3px;">
              <span style="font-size:10.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{FAINT};">Stage score</span>
              <span style="font-family:'IBM Plex Mono',monospace;font-size:20px;line-height:1.1;">{c.score:.2f}</span>
              <span style="font-size:11.5px;line-height:1.35;color:oklch(0.6 0.012 250);">how far along the evidence is &mdash; not a success probability</span>
            </div>
          </div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def render_drug_match_card(rank: int, m: DrugMatch) -> None:
    st.markdown(
        f"""
        <article style="display:grid;grid-template-columns:44px minmax(0,1fr) 250px;gap:24px;background:white;border:1px solid {BORDER};border-radius:8px;padding:22px 24px;margin-bottom:12px;box-shadow:0 1px 2px oklch(0.2 0.02 250 / 0.04);">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:15px;color:oklch(0.65 0.012 250);padding-top:3px;">{rank:02d}</div>
          <div style="display:flex;flex-direction:column;gap:12px;min-width:0;justify-content:center;">
            <h3 style="font-size:25px;line-height:1.15;margin:0;letter-spacing:-0.005em;">{html.escape(m.drug)}</h3>
            <div style="display:flex;flex-direction:column;gap:4px;">
              <span style="font-size:10.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{FAINT};">Source</span>
              <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;font-size:13px;color:{MUTED};">
                {_trial_link_html(m.trial_id, m.source_link)}
              </div>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:14px;border-left:1px solid {BORDER_SOFT};padding-left:22px;">
            <div style="display:flex;flex-direction:column;gap:7px;">
              <span style="font-size:10.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{FAINT};">Stage for {html.escape(m.drug)}</span>
              <span style="display:flex;gap:3px;">{_phase_steps_html(m.phase)}</span>
              <span style="font-size:16px;font-weight:600;letter-spacing:-0.005em;">{html.escape(m.phase)}</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:3px;">
              <span style="font-size:10.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{FAINT};">Stage score</span>
              <span style="font-family:'IBM Plex Mono',monospace;font-size:20px;line-height:1.1;">{m.score:.2f}</span>
              <span style="font-size:11.5px;line-height:1.35;color:oklch(0.6 0.012 250);">how far along the evidence is &mdash; not a success probability</span>
            </div>
          </div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(message: str) -> None:
    st.markdown(
        f"""
        <div style="background:{CHIP_BG};border:1px dashed {BORDER};border-radius:8px;padding:24px;text-align:center;color:{MUTED};font-size:14px;">
          {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        f"""
        <div style="display:flex;flex-direction:column;gap:8px;border-top:1px solid {BORDER};padding-top:18px;margin-top:8px;font-size:13px;line-height:1.5;color:{MUTED};max-width:84ch;">
          <span><strong style="font-weight:600;color:oklch(0.3 0.012 250);">How to read this.</strong> Evidence Strength reflects independent cross-drug support: a solid badge (High) means 2+ other drugs on the same target already have this indication; a tinted badge (Moderate) means one drug, but at Approved/Phase 3; a dashed badge (Low) means one early-phase source, or a procedural/diagnostic-only match. Disease-mode results are a direct match against tracked programs, not an inference. Ranking always follows the drug's clinical stage on that indication.</span>
          <span>Trial data via ClinicalTrials.gov. Cached snapshot for demo purposes &mdash; not clinical advice.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def get_cache() -> dict:
    return load_cache()


def render_drug_mode(cache: dict) -> None:
    render_header(DRUG_MODE_DESCRIPTION, DRUG_MODE_STEPS)

    drug_options = sorted(cache.get("drug_targets", {}).keys())
    col1, col2, col3 = st.columns([1, 1, 1.4], gap="large")
    with col1:
        query_drug = st.selectbox("Search for a drug", drug_options)

    all_candidates = get_candidates(query_drug, cache, top_k=None)

    with col2:
        top_k = st.slider("Candidates to show", min_value=1, max_value=20, value=10)

    target_count = len({c.shared_target for c in all_candidates})
    source_count = len({c.source_drug for c in all_candidates})
    render_stats(
        col3,
        [
            (target_count, "Shared targets"),
            (source_count, "Source drugs"),
            (len(all_candidates), "Candidates found"),
        ],
    )

    candidates = all_candidates[:top_k]
    target_label = " / ".join(sorted({c.shared_target for c in all_candidates})) or "shared-target"
    render_section_header(
        f"Indications being tested for <em>{html.escape(target_label)}</em> drugs, but not for {html.escape(query_drug)}",
        f"ranked by clinical stage &middot; showing {len(candidates)} of {len(all_candidates)}",
    )

    if not candidates:
        render_empty_state(
            f"No repurposing candidates found for <strong>{html.escape(query_drug)}</strong> in the current dataset."
        )
    else:
        for rank, c in enumerate(candidates, start=1):
            render_candidate_card(rank, c)


def render_disease_mode(cache: dict) -> None:
    render_header(DISEASE_MODE_DESCRIPTION, DISEASE_MODE_STEPS)

    indication_options = list_indications(cache)
    col1, col2, col3 = st.columns([1, 1, 1.4], gap="large")
    with col1:
        indication = st.selectbox("Search for a disease", indication_options)

    all_matches = get_drugs_for_indication(indication, cache, top_k=None)

    with col2:
        top_k = st.slider("Drugs to show", min_value=1, max_value=20, value=10)

    approved_count = sum(1 for m in all_matches if m.phase == "Approved")
    render_stats(
        col3,
        [
            (approved_count, "Approved"),
            (len(all_matches) - approved_count, "In trials"),
            (len(all_matches), "Total drugs"),
        ],
    )

    matches = all_matches[:top_k]
    render_section_header(
        f"Drugs currently being tested for <em>{html.escape(indication)}</em>",
        f"ranked by clinical stage &middot; showing {len(matches)} of {len(all_matches)}",
    )

    if not matches:
        render_empty_state(
            f"No drugs found for <strong>{html.escape(indication)}</strong> in the current dataset."
        )
    else:
        for rank, m in enumerate(matches, start=1):
            render_drug_match_card(rank, m)


def main() -> None:
    inject_styles()

    cache = get_cache()
    st.markdown(
        f'<div style="font-size:11px;letter-spacing:0.06em;text-transform:uppercase;'
        f'color:{FAINT};margin-bottom:6px;">Choose what to search by</div>',
        unsafe_allow_html=True,
    )
    mode = st.radio(
        "Search mode",
        [DRUG_MODE_LABEL, DISEASE_MODE_LABEL],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == DRUG_MODE_LABEL:
        render_drug_mode(cache)
    else:
        render_disease_mode(cache)

    render_footer()


if __name__ == "__main__":
    main()
