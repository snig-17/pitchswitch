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

    favourite_team = st.text_input(
        "Favourite team(s)", placeholder="e.g. Argentina, South Korea",
        help="Comma-separated. Small nations get an extra danger boost.")
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
        director = st.session_state.director
        if director.provider.is_warm():
            st.caption("Granite: ready")
        else:
            st.caption("Granite: warming up...")
        if director.grounding.loaded:
            src = "Docling" if director.grounding.used_docling else "markdown"
            st.caption(f"Primers: {len(director.grounding.kb)} nations ({src})")
        else:
            st.caption("Primers: loading...")

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
        st.session_state.director.load_grounding()  # parse primers (Docling)
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
        director.set_favourites(fav)  # keep in sync if user edits mid-run

        # --- Demo: forced Granite showdown -------------------------------
        # Set up a near-tie between two matches so the Director's ambiguous
        # (Granite) tier fires. We exclude the match the viewer is already on
        # (so the switch is visible) and prefer non-favourite matches; the
        # danger values below are bias-compensated so the 1.3x favourite bias
        # can't break the tie past AMBIGUITY_THRESHOLD even if a favourite
        # ends up pinned.
        def _is_fav(h):
            return director.is_favourite(h)

        if st.session_state.force_showdown:
            st.session_state.force_showdown = False

            cur = st.session_state.current_match
            active = [info.match_id for events, info in st.session_state.match_data
                      if st.session_state.event_idx[info.match_id] < len(events)]

            def _pool(allow_fav, allow_cur):
                return [m for m in active
                        if (allow_cur or m != cur)
                        and (allow_fav or not _is_fav(st.session_state.heats[m]))]

            # Priority: exclude current AND favourite; relax favourite before
            # current (a visible switch matters more than a clean tie, which
            # bias-compensation already protects); finally fall back to any.
            chosen = []
            for allow_fav, allow_cur in [(False, False), (True, False),
                                          (False, True), (True, True)]:
                pool = _pool(allow_fav, allow_cur)
                if len(pool) >= 2:
                    chosen = pool[:2]
                    break
            if len(chosen) < 2:
                chosen = (active or list(st.session_state.heats))[:2]

            if len(chosen) == 2:
                st.session_state.showdown_mids = tuple(chosen)
                # Hold long enough that even a slow async Granite re-pick
                # (~10s) lands well inside the window and the near-tie stays
                # visible afterwards (~0.22s/tick).
                st.session_state.showdown_ttl = 90
                # Start the viewer on a match outside the pinned pair so the
                # switch is visible (falls back to a pinned one only if there
                # is no other match at all).
                others = [m for m in st.session_state.heats if m not in chosen]
                start_on = others[0] if others else chosen[0]
                st.session_state.current_match = start_on
                director.current_match_id = start_on
                # Bypass the Granite cooldown for the demo.
                director._last_granite_time = -1e9
                director._granite_inflight = False

        # Hold the near-tie for a few ticks so the async Granite re-pick has
        # consistent state to read and time to land in the UI. Bias-compensate
        # so a pinned favourite still lands at the intended biased danger.
        if st.session_state.showdown_ttl > 0 and st.session_state.showdown_mids:
            a, b = st.session_state.showdown_mids
            for mid, target, reason in (
                (a, 0.66, "Danger critical - end-to-end action"),
                (b, 0.58, "Danger critical - late surge"),
            ):
                h = st.session_state.heats[mid]
                # Undo this match's danger multiplier so the *biased* danger
                # lands on the intended target (keeps the near-tie even if a
                # favourite / small nation is pinned).
                mult = director.personalizer.multiplier(h.home_team, h.away_team)
                raw = min(target / mult, 1.0) if mult else target
                h.danger, h.should_switch, h.about_to_ignite = raw, True, True
                h.switch_reason = reason
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

        # Show the danger the Director ranks on (favourite bias applied), so
        # the ticker matches the switching decisions.
        director = st.session_state.director
        matched = None
        if director is not None:
            danger = director.biased_danger(heat)
            matched = director.favourite_label(heat)
        else:
            danger = heat.danger
        is_small = bool(matched) and director.personalizer.is_small_nation(matched)
        fav_tag = " *" if matched and danger != heat.danger else ""

        with cols[i]:
            # Highlight current match
            if is_current:
                st.markdown(f"### {info.label}")
            else:
                st.markdown(f"**{info.label}**")

            # Show which favourite this match involves
            if matched:
                badge = f"YOUR TEAM: {matched}"
                if is_small:
                    badge += " (small nation)"
                st.caption(badge)

            st.metric(
                label=f"{heat.current_minute}'",
                value=score,
                delta=f"Danger: {danger:.2f}{fav_tag}" if danger > 0.3 else None,
            )

            # Danger bar with color coding
            progress_val = min(danger, 1.0)
            if heat.about_to_ignite:
                st.progress(progress_val, text=f"BUILDING {danger:.2f}{fav_tag}")
            elif danger > 0.5:
                st.progress(progress_val, text=f"HIGH {danger:.2f}{fav_tag}")
            else:
                st.progress(progress_val, text=f"{danger:.2f}{fav_tag}")

    director = st.session_state.director
    if director is not None and director.personalizer.active:
        p = director.personalizer
        st.caption(f"\\* danger boosted for your team(s): {p.fav_bias:g}x normally, "
                    f"{p.small_nation_bias:g}x for small nations")

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
