"""PitchSwitch - AI Multi-Match Whip-Around Companion.

Run: streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components

from core.livefeed import build_broadcast as broadcast_canvas
from core.metrica import build_unified_broadcast as assemble_unified
from providers.tts import get_tts

st.set_page_config(
    page_title="PitchSwitch",
    page_icon="",
    layout="wide",
)

# Broadcast-style display type: Oswald (the condensed face used in sports
# lower-thirds) for headings, so the title reads like a broadcast graphic
# instead of the default Streamlit sans.
st.markdown(
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&display=swap');"
    "h1,h2,h3{font-family:'Oswald',sans-serif!important;letter-spacing:.5px;text-transform:uppercase;}"
    "h1{font-weight:700!important;}"
    "</style>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "running" not in st.session_state:
    st.session_state.running = False
    st.session_state.matches_loaded = False
    st.session_state.broadcast_html = ""   # self-contained canvas for the feed
    st.session_state.broadcast_error = ""
    st.session_state.schedule = []         # the Director's switch calls

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("PitchSwitch")
    st.caption("AI Multi-Match Whip-Around")

    favourite_team = st.text_input(
        "Favourite team(s)", placeholder="e.g. Argentina, South Korea",
        help="Comma-separated. Small nations get an extra danger boost.")
    col_a, col_b = st.columns(2)
    with col_a:
        start = st.button("Start Demo", disabled=st.session_state.running,
                           type="primary", use_container_width=True)
    with col_b:
        stop = st.button("Stop", disabled=not st.session_state.running,
                          use_container_width=True)

    st.divider()
    st.caption("One AI whip-around feed over real player tracking. The Director "
               "cuts between matches when one's danger pulls ahead. Granite "
               "narrates each switch, grounded by Docling team primers.")

# ---------------------------------------------------------------------------
# Load matches on first start
# ---------------------------------------------------------------------------
# Real tracking games mapped to World Cup fixtures (so Granite/Docling/
# personalization work on real movement). Team labels are illustrative.
MATCHUPS = [
    {"game": 1, "home": "France", "away": "Argentina"},
    {"game": 2, "home": "South Korea", "away": "Germany"},
]

if start and not st.session_state.running:
    import hashlib
    import json
    from pathlib import Path
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{favourite_team.lower()}".encode()).hexdigest()[:10]
    cache_file = cache_dir / f"broadcast_{key}.json"

    if cache_file.exists():
        # Instant: reuse a previously built broadcast for these favourites.
        with st.spinner("Loading broadcast..."):
            cached = json.loads(cache_file.read_text())
            st.session_state.broadcast_html = cached["html"]
            st.session_state.schedule = [tuple(s) for s in cached["schedule"]]
            st.session_state.broadcast_error = ""
    else:
        with st.spinner("Warming Granite + Docling, building the broadcast "
                        "(first run for these teams takes ~30s)..."):
            from providers.llm import get_provider
            get_provider().warmup()  # synchronous so switch narration is Granite
            try:
                bd = assemble_unified(MATCHUPS, favourite=favourite_team,
                                      t0=0, dur=120, fps=8,
                                      voice=get_tts().available())
                html = broadcast_canvas(bd)
                narrs = [g.get("narration", "") for g in bd["games"]]
                sched = [(t, narrs[gi]) for t, gi in bd["schedule"]]
                st.session_state.broadcast_html = html
                st.session_state.schedule = sched
                st.session_state.broadcast_error = ""
                cache_file.write_text(json.dumps({"html": html, "schedule": sched}))
            except Exception as exc:
                # Hosted/no-Ollama fallback: serve a pre-built default broadcast
                # so the demo always works even when live build isn't possible.
                default = cache_dir / f"broadcast_{hashlib.md5(b'').hexdigest()[:10]}.json"
                if default.exists():
                    cached = json.loads(default.read_text())
                    st.session_state.broadcast_html = cached["html"]
                    st.session_state.schedule = [tuple(s) for s in cached["schedule"]]
                    st.session_state.broadcast_error = ""
                else:
                    st.session_state.broadcast_error = str(exc)
                    st.session_state.broadcast_html = ""
    st.session_state.matches_loaded = True
    st.session_state.running = True
    st.rerun()

if stop:
    st.session_state.running = False
    st.rerun()

# ---------------------------------------------------------------------------
# UI Layout — single unified broadcast feed
# ---------------------------------------------------------------------------
st.title("PitchSwitch")
st.caption("One AI whip-around feed over real player tracking — the Director "
           "cuts to whichever match is heating up.")

if not st.session_state.matches_loaded:
    st.info("Pick your favourite team(s), then hit Start Demo. The Director "
            "watches both matches and cuts you to the one about to ignite.")
elif not st.session_state.get("broadcast_html"):
    err = st.session_state.get("broadcast_error", "")
    st.warning("Tracking data not found — run `bash scripts/get_metrica.sh`, "
               "then Start again." + (f"\n\n({err})" if err else ""))
else:
    components.html(st.session_state.broadcast_html, height=620, scrolling=False)
    st.caption("Real 25fps player tracking (Metrica open data) mapped to World "
               "Cup fixtures: a representative stand-in for the licensed "
               "broadcast feed (FIFA blocks real match video from embedding). "
               "Granite narrates each switch, Docling-grounded; your team(s) "
               "get a danger boost.")
    sched = st.session_state.get("schedule", [])
    if sched:
        with st.expander("Director's switch calls"):
            for t, narr in sched:
                st.caption(f"**{int(t // 60)}:{int(t % 60):02d}** — {narr}")
