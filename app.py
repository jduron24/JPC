"""Streamlit UI for browsing ranked drug repurposing candidates.

Layout/visual design ported from a static HTML mock (Repurposing Results.dc.html).
The two interactive controls (drug search, candidate-count slider) are real Streamlit
widgets restyled with CSS; everything else is custom-rendered HTML driven entirely by
scoring.get_candidates() output -- no fields are invented beyond what Candidate has.
"""

import html

import streamlit as st

from scoring import Candidate, get_candidates, load_cache

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
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        f"""
        <div style="display:flex;flex-direction:column;gap:14px;border-bottom:1px solid {BORDER};padding-bottom:22px;margin-bottom:8px;">
          <div style="display:flex;align-items:baseline;justify-content:space-between;gap:24px;flex-wrap:wrap;">
            <h1 style="font-size:40px;line-height:1.05;margin:0;letter-spacing:-0.01em;">Drug Repurposing Candidate Finder</h1>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.09em;text-transform:uppercase;color:{FAINT};border:1px solid {BORDER};border-radius:3px;padding:5px 9px;">Demo build &middot; cached dataset</span>
          </div>
          <p style="margin:0;max-width:74ch;font-size:16.5px;line-height:1.5;color:{BODY_TEXT};">Pick a drug. We find other drugs that hit the same biological target, then surface the indications those drugs are already being tested for &mdash; and yours isn't. Each row is a hypothesis with a trial behind it, not a prediction.</p>
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:'IBM Plex Mono',monospace;font-size:12px;color:{MUTED};margin-top:2px;">
            <span style="background:{CHIP_BG};padding:6px 10px;border-radius:3px;">1 &middot; your drug</span>
            <span style="color:oklch(0.7 0.01 250);">&rarr;</span>
            <span style="background:{CHIP_BG};padding:6px 10px;border-radius:3px;">2 &middot; shared target</span>
            <span style="color:oklch(0.7 0.01 250);">&rarr;</span>
            <span style="background:{CHIP_BG};padding:6px 10px;border-radius:3px;">3 &middot; other drugs on that target</span>
            <span style="color:oklch(0.7 0.01 250);">&rarr;</span>
            <span style="background:{ACCENT};color:oklch(0.98 0.01 205);padding:6px 10px;border-radius:3px;">4 &middot; their indications, minus yours</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stats(col, all_candidates: list[Candidate]) -> None:
    target_count = len({c.shared_target for c in all_candidates})
    source_count = len({c.source_drug for c in all_candidates})
    total_count = len(all_candidates)
    with col:
        st.markdown(
            f"""
            <div style="display:flex;gap:26px;justify-content:flex-end;text-align:right;padding-top:30px;">
              <div style="display:flex;flex-direction:column;gap:3px;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:26px;line-height:1;">{target_count}</span>
                <span style="font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:{FAINT};">Shared targets</span>
              </div>
              <div style="display:flex;flex-direction:column;gap:3px;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:26px;line-height:1;">{source_count}</span>
                <span style="font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:{FAINT};">Source drugs</span>
              </div>
              <div style="display:flex;flex-direction:column;gap:3px;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:26px;line-height:1;">{total_count}</span>
                <span style="font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:{FAINT};">Candidates found</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_section_header(query_drug: str, all_candidates: list[Candidate], shown: int) -> None:
    targets = sorted({c.shared_target for c in all_candidates})
    target_label = " / ".join(targets) if targets else "shared-target"
    st.markdown(
        f"""
        <div style="display:flex;align-items:baseline;justify-content:space-between;gap:20px;flex-wrap:wrap;border-top:1px solid {BORDER};padding-top:18px;margin-top:8px;">
          <h2 style="font-size:22px;margin:0;">Indications being tested for <em>{html.escape(target_label)}</em> drugs, but not for {html.escape(query_drug)}</h2>
          <span style="font-size:12.5px;color:{MUTED};font-family:'IBM Plex Mono',monospace;">ranked by clinical stage &middot; showing {shown} of {len(all_candidates)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_candidate_card(rank: int, c: Candidate) -> None:
    phase_index = PHASES.index(c.phase)
    steps_html = "".join(
        f'<span style="height:7px;flex:1;border-radius:2px;background:{ACCENT if step <= phase_index else "oklch(0.91 0.008 250)"};"></span>'
        for step in range(len(PHASES))
    )

    if c.evidence_tier == "strong":
        evidence_html = (
            f'<span style="display:inline-flex;align-items:center;gap:6px;font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:11.5px;letter-spacing:0.05em;text-transform:uppercase;background:{ACCENT};color:white;'
            f'border-radius:3px;padding:5px 9px;">Curated mechanism note</span>'
        )
    else:
        evidence_html = (
            f'<span style="display:inline-flex;align-items:center;gap:6px;font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:11.5px;letter-spacing:0.05em;text-transform:uppercase;color:{MUTED};'
            f'border:1px dashed oklch(0.78 0.01 250);border-radius:3px;padding:5px 9px;">Target match only &middot; not yet curated</span>'
        )

    if c.trial_id and c.source_link:
        trial_html = (
            f'<a href="{html.escape(c.source_link)}" target="_blank" rel="noopener" '
            f'style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;">{html.escape(c.trial_id)} &#8599;</a>'
        )
    else:
        trial_html = (
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12.5px;color:oklch(0.62 0.012 250);">'
            f"no linked trial record</span>"
        )

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
              {evidence_html}
              {trial_html}
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:14px;border-left:1px solid {BORDER_SOFT};padding-left:22px;">
            <div style="display:flex;flex-direction:column;gap:7px;">
              <span style="font-size:10.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{FAINT};">Stage for {html.escape(c.source_drug)}</span>
              <span style="display:flex;gap:3px;">{steps_html}</span>
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


def render_empty_state(query_drug: str) -> None:
    st.markdown(
        f"""
        <div style="background:{CHIP_BG};border:1px dashed {BORDER};border-radius:8px;padding:24px;text-align:center;color:{MUTED};font-size:14px;">
          No repurposing candidates found for <strong>{html.escape(query_drug)}</strong> in the current dataset.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        f"""
        <div style="display:flex;flex-direction:column;gap:8px;border-top:1px solid {BORDER};padding-top:18px;margin-top:8px;font-size:13px;line-height:1.5;color:{MUTED};max-width:84ch;">
          <span><strong style="font-weight:600;color:oklch(0.3 0.012 250);">How to read this.</strong> Every candidate is a shared-target inference. A dashed &ldquo;not yet curated&rdquo; tag is the honest default: the target link is real, but no human has written a mechanism note for it yet. Ranking follows the source drug's clinical stage on that indication.</span>
          <span>Trial data via ClinicalTrials.gov. Cached snapshot for demo purposes &mdash; not clinical advice.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def get_cache() -> dict:
    return load_cache()


def main() -> None:
    inject_styles()
    render_header()

    cache = get_cache()
    drug_options = sorted(cache.get("drug_targets", {}).keys())

    col1, col2, col3 = st.columns([1, 1, 1.4], gap="large")
    with col1:
        query_drug = st.selectbox("Search for a drug", drug_options)

    all_candidates = get_candidates(query_drug, cache, top_k=None)

    with col2:
        top_k = st.slider("Candidates to show", min_value=1, max_value=20, value=10)

    render_stats(col3, all_candidates)

    candidates = all_candidates[:top_k]
    render_section_header(query_drug, all_candidates, shown=len(candidates))

    if not candidates:
        render_empty_state(query_drug)
    else:
        for rank, c in enumerate(candidates, start=1):
            render_candidate_card(rank, c)

    render_footer()


if __name__ == "__main__":
    main()
