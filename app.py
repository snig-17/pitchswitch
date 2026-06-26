"""PitchSwitch - AI Multi-Match Whip-Around Companion.

Run: streamlit run app.py
"""

import asyncio
import time
from collections import defaultdict

import streamlit as st

from core.replay import load_match, get_demo_matches, FINAL_THIRD_X
from core.heat import create_heat
from core.director import create_director

st.set_page_config(
    page_title="PitchSwitch",
    page_icon="",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "running" not in st.session_state:
    st.session_state.running = False
    st.session_state.matches_loaded = False
    st.session_state.match_data = []  # [(events, info), ...]
    st.session_state.heats = {}  # match_id -> MatchHeat
    st.session_state.event_idx = {}  # match_id -> current index
    st.session_state.current_match = None  # match_id of the "main view"
    st.session_state.switch_count = 0
    st.session_state.narration = "Waiting for match data..."
    st.session_state.countdown = 0
    st.session_state.switch_target = None
    st.session_state.goals_seen = 0
    st.session_state.goals_predicted = 0
    st.session_state.lead_times = []
    st.session_state.switch_log = []  # [(minute, reason, match_label), ...]
    st.session_state.recent_events = defaultdict(list)  # match_id -> last N events
    st.session_state.scores = {}  # match_id -> "H-A"
    st.session_state.tick = 0
    st.session_state.director = None
    st.session_state.last_source = ""  # how the last switch was decided
    st.session_state.force_showdown = False  # demo: trigger ambiguous Granite call
    st.session_state.showdown_mids = None    # the two matches pinned into a tie
    st.session_state.showdown_ttl = 0        # ticks remaining to hold the tie

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("PitchSwitch")
    st.caption("AI Multi-Match Whip-Around")

    favourite_team = st.text_input("Favourite team", placeholder="e.g. Argentina")
    speed = st.slider("Replay speed", 10, 200, 60, step=10,
                       help="Higher = faster replay")

    col_a, col_b = st.columns(2)
    with col_a:
        start = st.button("Start Demo", disabled=st.session_state.running,
                           type="primary", use_container_width=True)
    with col_b:
        stop = st.button("Stop", disabled=not st.session_state.running,
                          use_container_width=True)

    # Demo control: force a neck-and-neck moment so the Granite reasoning
    # tier (ambiguous calls) reliably fires on stage.
    if st.button("Force Granite Showdown", disabled=not st.session_state.running,
                  use_container_width=True,
                  help="Pin two matches into a near-tie so Granite has to "
                       "reason about which one to show."):
        st.session_state.force_showdown = True

    # Granite readiness (the showdown only reasons once the model is warm)
    if st.session_state.director is not None:
        if st.session_state.director.provider.is_warm():
            st.caption("Granite: ready")
        else:
            st.caption("Granite: warming up...")

    if st.session_state.switch_log:
        st.divider()
        st.subheader("Switch Log")
        for minute, reason, label in reversed(st.session_state.switch_log[-10:]):
            st.caption(f"**{minute}'** {label}")
            st.caption(reason)

# ---------------------------------------------------------------------------
# Load matches on first start
# ---------------------------------------------------------------------------
if start and not st.session_state.running:
    with st.spinner("Loading matches from StatsBomb..."):
        st.session_state.match_data = []
        st.session_state.heats = {}
        st.session_state.event_idx = {}
        st.session_state.scores = {}
        st.session_state.recent_events = defaultdict(list)

        for match_id, label in get_demo_matches():
            events, info = load_match(match_id)
            st.session_state.match_data.append((events, info))
            st.session_state.heats[match_id] = create_heat(
                info.match_id, info.label, info.home_team, info.away_team
            )
            st.session_state.event_idx[match_id] = 0
            st.session_state.scores[match_id] = "0-0"

        st.session_state.current_match = st.session_state.match_data[0][1].match_id
        st.session_state.director = create_director(favourite_team=favourite_team)
        st.session_state.director.current_match_id = st.session_state.current_match
        st.session_state.director.warmup()  # pre-load the LLM in the background
        st.session_state.matches_loaded = True
        st.session_state.running = True
        st.session_state.switch_count = 0
        st.session_state.goals_seen = 0
        st.session_state.goals_predicted = 0
        st.session_state.lead_times = []
        st.session_state.switch_log = []
        st.session_state.narration = "Matches loaded. Replay starting..."
        st.session_state.tick = 0
    st.rerun()

if stop:
    st.session_state.running = False
    st.rerun()

# ---------------------------------------------------------------------------
# Process next batch of events (called on each rerun)
# ---------------------------------------------------------------------------
EVENTS_PER_TICK = 8  # process N events per rerun cycle

def process_tick():
    """Advance the replay by processing the next batch of events."""
    if not st.session_state.running:
        return

    all_done = True
    fav = st.session_state.get("favourite_team_val", "")

    for events, info in st.session_state.match_data:
        mid = info.match_id
        idx = st.session_state.event_idx[mid]
        heat = st.session_state.heats[mid]

        if idx >= len(events):
            continue
        all_done = False

        # Process a batch of events
        end_idx = min(idx + EVENTS_PER_TICK, len(events))
        for i in range(idx, end_idx):
            event = events[i]
            heat.update(event)

            # Track recent events for display
            if event.event_type in ("Shot", "Carry", "Pressure", "Pass", "Foul Committed"):
                st.session_state.recent_events[mid].append(event)
                st.session_state.recent_events[mid] = st.session_state.recent_events[mid][-8:]

            # Track scores
            if event.event_type == "Shot" and event.shot_outcome == "Goal":
                st.session_state.scores[mid] = f"{heat.home_score}-{heat.away_score}"
                st.session_state.goals_seen += 1

                # Check if we predicted this goal (switch trigger in prior 180s)
                goal_sec = event.match_seconds
                recent_switches = [
                    s for s in st.session_state.switch_log
                    if s[2] == info.label
                ]
                # Simple check: did we switch to this match recently?
                if st.session_state.current_match == mid:
                    st.session_state.goals_predicted += 1
                    st.session_state.lead_times.append(30)  # approximate

        st.session_state.event_idx[mid] = end_idx

    # Switch decision (delegated to the Director: heuristic + Granite tiers)
    director = st.session_state.director
    if director is not None:
        director.favourite_team = fav  # keep in sync if user edits mid-run

        # --- Demo: forced Granite showdown -------------------------------
        # Set up a near-tie between two matches so the Director's ambiguous
        # (Granite) tier fires. We avoid the favourite team so the danger
        # bias can't break the tie past AMBIGUITY_THRESHOLD.
        if st.session_state.force_showdown:
            st.session_state.force_showdown = False
            fav_l = fav.strip().lower()

            def _is_fav(h):
                return bool(fav_l) and (fav_l in h.home_team.lower() or
                                         fav_l in h.away_team.lower())

            active = [info.match_id for events, info in st.session_state.match_data
                      if st.session_state.event_idx[info.match_id] < len(events)]
            # Prefer two active, non-favourite matches; fall back as needed.
            pool = [m for m in active if not _is_fav(st.session_state.heats[m])]
            if len(pool) < 2:
                pool = active or list(st.session_state.heats)
            chosen = pool[:2]
            if len(chosen) == 2:
                st.session_state.showdown_mids = tuple(chosen)
                # Hold long enough that the async Granite re-pick (a few
                # seconds out) lands well inside the window and stays visible.
                st.session_state.showdown_ttl = 40
                # Start the viewer on a different match so a switch is visible.
                others = [m for m in st.session_state.heats if m not in chosen]
                if others:
                    st.session_state.current_match = others[0]
                    director.current_match_id = others[0]
                # Bypass the Granite cooldown for the demo.
                director._last_granite_time = -1e9
                director._granite_inflight = False

        # Hold the near-tie for a few ticks so the async Granite re-pick has
        # consistent state to read and time to land in the UI.
        if st.session_state.showdown_ttl > 0 and st.session_state.showdown_mids:
            a, b = st.session_state.showdown_mids
            ha, hb = st.session_state.heats[a], st.session_state.heats[b]
            ha.danger, ha.should_switch, ha.about_to_ignite = 0.66, True, True
            ha.switch_reason = "Danger critical - end-to-end action"
            hb.danger, hb.should_switch, hb.about_to_ignite = 0.58, True, True
            hb.switch_reason = "Danger critical - late surge"
            # Damp every other match (incl. a biased favourite) so the pinned
            # pair is unambiguously the top two and the tie can't be broken.
            for omid, oheat in st.session_state.heats.items():
                if omid not in (a, b):
                    oheat.danger = min(oheat.danger, 0.20)
                    oheat.should_switch = False
            st.session_state.showdown_ttl -= 1

        def _apply(decision, *, force_log: bool):
            """Apply a SwitchDecision to the UI state."""
            target_heat = st.session_state.heats[decision.target_match_id]
            switched = decision.target_match_id != st.session_state.current_match
            st.session_state.current_match = decision.target_match_id
            st.session_state.narration = decision.narration
            st.session_state.last_source = decision.source
            # Count/log a switch when the target actually changed, or when a
            # Granite re-pick confirms the same match (force_log upgrades text).
            if switched:
                st.session_state.switch_count += 1
                st.session_state.switch_log.append(
                    (target_heat.current_minute, decision.narration, decision.target_label)
                )
            elif force_log and st.session_state.switch_log:
                # Replace the last log entry's narration with Granite's reasoning
                minute, _, label = st.session_state.switch_log[-1]
                st.session_state.switch_log[-1] = (minute, decision.narration, label)

        # Immediate (heuristic / penalty) decision
        decision = director.decide(st.session_state.heats)
        if decision and decision.should_switch:
            _apply(decision, force_log=False)

        # Async Granite re-pick arrives a tick or two later (non-blocking)
        granite_dec = director.get_pending_decision()
        if granite_dec and granite_dec.should_switch:
            _apply(granite_dec, force_log=True)

        # Async Granite narration (clear-winner path) may also arrive later
        pending = director.get_pending_narration()
        if pending:
            st.session_state.narration = pending

    if all_done:
        st.session_state.running = False
        st.session_state.narration = "All matches complete."

    st.session_state.tick += 1


# Store favourite team in session state for the processing function
st.session_state["favourite_team_val"] = favourite_team

# ---------------------------------------------------------------------------
# Run tick if active
# ---------------------------------------------------------------------------
if st.session_state.running:
    process_tick()

# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------
st.title("PitchSwitch")

# Narration banner
if st.session_state.narration.startswith("SWITCH"):
    st.error(st.session_state.narration, icon=None)
elif "complete" in st.session_state.narration.lower():
    st.success(st.session_state.narration)
else:
    st.info(st.session_state.narration)

# How the last switch was decided
_SOURCE_BADGE = {
    "granite": "Granite reasoned this switch (ambiguous call)",
    "heuristic": "Heuristic switch (clear winner)",
    "penalty": "Penalty - instant switch",
    "fallback": "Template fallback (LLM unavailable)",
}
if st.session_state.last_source:
    st.caption(_SOURCE_BADGE.get(st.session_state.last_source,
                                  st.session_state.last_source))

# ---------------------------------------------------------------------------
# Danger Ticker Strip
# ---------------------------------------------------------------------------
if st.session_state.matches_loaded:
    cols = st.columns(len(st.session_state.match_data))
    for i, (events, info) in enumerate(st.session_state.match_data):
        mid = info.match_id
        heat = st.session_state.heats[mid]
        is_current = (mid == st.session_state.current_match)
        score = st.session_state.scores.get(mid, "0-0")

        with cols[i]:
            # Highlight current match
            if is_current:
                st.markdown(f"### {info.label}")
            else:
                st.markdown(f"**{info.label}**")

            st.metric(
                label=f"{heat.current_minute}'",
                value=score,
                delta=f"Danger: {heat.danger:.2f}" if heat.danger > 0.3 else None,
            )

            # Danger bar with color coding
            bar_color = "normal"
            progress_val = min(heat.danger, 1.0)
            if heat.about_to_ignite:
                st.progress(progress_val, text=f"BUILDING {heat.danger:.2f}")
            elif heat.danger > 0.5:
                st.progress(progress_val, text=f"HIGH {heat.danger:.2f}")
            else:
                st.progress(progress_val, text=f"{heat.danger:.2f}")

    st.divider()

# ---------------------------------------------------------------------------
# Main View — current match detail
# ---------------------------------------------------------------------------
if st.session_state.matches_loaded and st.session_state.current_match:
    mid = st.session_state.current_match
    heat = st.session_state.heats[mid]
    score = st.session_state.scores.get(mid, "0-0")
    state = heat.get_state_summary()

    main_col, stats_col = st.columns([3, 1])

    with main_col:
        st.subheader(f"{heat.label} — {score} ({heat.current_minute}')")

        # Recent events feed
        recent = st.session_state.recent_events.get(mid, [])
        if recent:
            for event in reversed(recent[-6:]):
                loc_str = ""
                if event.location:
                    zone = "FINAL THIRD" if event.location[0] > FINAL_THIRD_X else ""
                    loc_str = f" {zone}" if zone else ""
                icon = ""
                if event.event_type == "Shot":
                    icon = "Shot"
                    if event.shot_outcome == "Goal":
                        icon = "GOAL"
                elif event.event_type == "Carry" and event.location and event.location[0] > FINAL_THIRD_X:
                    icon = "Carry (final third)"
                elif event.event_type == "Pressure":
                    icon = "Pressure"
                else:
                    icon = event.event_type

                detail = f"**{event.minute}'** {icon}: {event.player} ({event.team}){loc_str}"
                if event.xg is not None:
                    detail += f" | xG: {event.xg:.3f}"
                if event.shot_outcome == "Goal":
                    st.success(detail)
                elif event.event_type == "Shot":
                    st.warning(detail)
                else:
                    st.caption(detail)
        else:
            st.caption("Waiting for events...")

    with stats_col:
        st.metric("Danger", f"{heat.danger:.2f}")
        st.metric("Derivative", f"{heat.derivative:+.4f}/s")
        if state["late_game"]:
            st.warning("LATE GAME (1.5x)")
        if state["about_to_ignite"]:
            st.error("BUILDING!")
        st.caption(f"Events in window: {state['events_in_window']}")

# ---------------------------------------------------------------------------
# Accuracy Panel + Switch Counter
# ---------------------------------------------------------------------------
if st.session_state.matches_loaded:
    acc_col, switch_col, speed_col = st.columns(3)
    with acc_col:
        seen = st.session_state.goals_seen
        pred = st.session_state.goals_predicted
        if seen > 0:
            st.metric("Predictions", f"{pred}/{seen}",
                       delta=f"{100*pred/seen:.0f}% hit rate")
        else:
            st.metric("Predictions", "0/0")
    with switch_col:
        st.metric("Switches", st.session_state.switch_count)
    with speed_col:
        avg_lead = (sum(st.session_state.lead_times) / len(st.session_state.lead_times)
                     if st.session_state.lead_times else 0)
        st.metric("Avg Lead Time", f"{avg_lead:.0f}s" if avg_lead > 0 else "--")

# ---------------------------------------------------------------------------
# Auto-rerun while running
# ---------------------------------------------------------------------------
if st.session_state.running:
    time.sleep(0.15)  # ~6-7 FPS refresh rate
    st.rerun()
