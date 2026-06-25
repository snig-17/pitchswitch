"""PitchSwitch - AI Multi-Match Whip-Around Companion.

Run: streamlit run app.py
"""

import asyncio
import time
from collections import defaultdict

import streamlit as st

from core.replay import load_match, get_demo_matches, MatchEvent, MatchState, FINAL_THIRD_X
from core.heat import create_heat, MatchHeat

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
# Personalization bias
# ---------------------------------------------------------------------------
FAV_BIAS = 1.3

def apply_personalization(heat: MatchHeat, fav: str) -> float:
    """Return biased danger score if favourite team is playing."""
    if not fav:
        return heat.danger
    fav_lower = fav.strip().lower()
    if fav_lower in heat.home_team.lower() or fav_lower in heat.away_team.lower():
        return min(heat.danger * FAV_BIAS, 1.0)
    return heat.danger

# ---------------------------------------------------------------------------
# Process next batch of events (called on each rerun)
# ---------------------------------------------------------------------------
EVENTS_PER_TICK = 8  # process N events per rerun cycle

def process_tick():
    """Advance the replay by processing the next batch of events."""
    if not st.session_state.running:
        return

    all_done = True
    best_match = None
    best_danger = -1.0
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

        # Compute biased danger for switching
        biased = apply_personalization(heat, fav)
        if biased > best_danger:
            best_danger = biased
            best_match = mid

    # Switch decision
    if best_match and best_match != st.session_state.current_match:
        best_heat = st.session_state.heats[best_match]
        if best_heat.should_switch or best_danger > 0.4:
            reason = best_heat.switch_reason or f"Danger rising ({best_danger:.2f})"
            # Personalization note
            fav = st.session_state.get("favourite_team_val", "")
            if fav and (fav.lower() in best_heat.home_team.lower() or
                         fav.lower() in best_heat.away_team.lower()):
                reason = f"Your team! {reason}"

            st.session_state.current_match = best_match
            st.session_state.switch_count += 1
            st.session_state.narration = f"SWITCH: {reason}"
            st.session_state.switch_log.append(
                (best_heat.current_minute, reason, best_heat.label)
            )

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
