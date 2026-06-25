"""Replay engine: loads StatsBomb matches and replays them on a virtual clock.

Uses asyncio for concurrent multi-match replay. Each match is an async
coroutine that yields events at real match pacing (scaled by speed_factor).

Events use match-time timestamps (not wall-clock), so the danger model's
time-based derivative is independent of replay speed.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
from statsbombpy import sb


# StatsBomb pitch is 120x80 yards
PITCH_LENGTH = 120
FINAL_THIRD_X = 80  # x > 80 = final third


@dataclass
class MatchEvent:
    """A single event from a match, normalized for the replay engine."""
    match_id: int
    match_label: str  # "France vs Argentina"
    event_id: str
    event_type: str  # Pass, Carry, Shot, Pressure, etc.
    minute: int
    second: int
    match_seconds: float  # minute * 60 + second (for derivative calc)
    team: str
    player: str
    location: list | None  # [x, y] or None
    end_location: list | None  # for carries/passes
    # Shot-specific
    xg: float | None
    shot_outcome: str | None
    # Set-piece indicators
    is_penalty: bool
    is_corner: bool
    is_free_kick: bool
    # Card
    is_red_card: bool
    # Raw data for Granite narration context
    raw_type_detail: str  # e.g. "Shot - Goal", "Foul Committed - Penalty"


@dataclass
class MatchState:
    """Live state of a single match during replay."""
    match_id: int
    label: str
    home_team: str
    away_team: str
    home_score: int = 0
    away_score: int = 0
    minute: int = 0
    events: list[MatchEvent] = field(default_factory=list)
    total_events: int = 0


@dataclass
class MatchInfo:
    """Metadata for a loaded match."""
    match_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    label: str
    event_count: int


def _parse_event(row: pd.Series, match_id: int, match_label: str) -> MatchEvent | None:
    """Parse a StatsBomb event row into a MatchEvent."""
    event_type = row.get("type", "")
    if event_type in ("Starting XI", "Half Start", "Half End", "Camera On",
                       "Camera off", "Player On", "Player Off"):
        return None

    minute = int(row.get("minute", 0))
    second = int(row.get("second", 0))

    location = row.get("location")
    if isinstance(location, (list, tuple)) and len(location) >= 2:
        location = [float(location[0]), float(location[1])]
    else:
        location = None

    end_location = None
    if event_type == "Carry":
        el = row.get("carry_end_location")
        if isinstance(el, (list, tuple)) and len(el) >= 2:
            end_location = [float(el[0]), float(el[1])]
    elif event_type == "Pass":
        el = row.get("pass_end_location")
        if isinstance(el, (list, tuple)) and len(el) >= 2:
            end_location = [float(el[0]), float(el[1])]

    # Shot data
    xg = None
    shot_outcome = None
    if event_type == "Shot":
        xg_val = row.get("shot_statsbomb_xg")
        if pd.notna(xg_val):
            xg = float(xg_val)
        shot_outcome = row.get("shot_outcome", None)

    # Set-piece detection
    foul_penalty = row.get("foul_committed_penalty")
    is_foul_penalty = pd.notna(foul_penalty) and bool(foul_penalty)
    shot_type_str = str(row.get("shot_type", "")).lower() if pd.notna(row.get("shot_type")) else ""
    is_penalty = is_foul_penalty or shot_type_str == "penalty"
    pass_type_str = str(row.get("pass_type", "")).lower() if pd.notna(row.get("pass_type")) else ""
    is_corner = pass_type_str == "corner"
    is_free_kick = pass_type_str == "free kick"

    # Red card
    foul_card = row.get("foul_committed_card")
    bad_card = row.get("bad_behaviour_card")
    card = str(foul_card) if pd.notna(foul_card) else ""
    if not card and pd.notna(bad_card):
        card = str(bad_card)
    is_red_card = "red" in str(card).lower() or "second yellow" in str(card).lower()

    # Type detail for narration
    detail_parts = [event_type]
    if shot_outcome:
        detail_parts.append(str(shot_outcome))
    if is_penalty:
        detail_parts.append("Penalty")
    raw_type_detail = " - ".join(detail_parts)

    return MatchEvent(
        match_id=match_id,
        match_label=match_label,
        event_id=str(row.get("id", "")),
        event_type=event_type,
        minute=minute,
        second=second,
        match_seconds=minute * 60.0 + second,
        team=str(row.get("team", "")),
        player=str(row.get("player", "")),
        location=location,
        end_location=end_location,
        xg=xg,
        shot_outcome=shot_outcome,
        is_penalty=is_penalty,
        is_corner=is_corner,
        is_free_kick=is_free_kick,
        is_red_card=is_red_card,
        raw_type_detail=raw_type_detail,
    )


def _cache_path(match_id: int) -> Path:
    """Path to cached match data."""
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / f"match_{match_id}.json"


def _save_cache(match_id: int, events_df: pd.DataFrame, match_info: dict) -> None:
    """Cache match events as JSON for offline fallback."""
    cache_file = _cache_path(match_id)
    data = {
        "match_id": match_id,
        "info": match_info,
        "events": json.loads(events_df.to_json(orient="records", default_handler=str)),
    }
    cache_file.write_text(json.dumps(data, default=str))


def _load_cache(match_id: int) -> tuple[pd.DataFrame, dict] | None:
    """Load cached match data. Returns (events_df, match_info) or None."""
    cache_file = _cache_path(match_id)
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        events_df = pd.DataFrame(data["events"])
        return events_df, data["info"]
    except (json.JSONDecodeError, KeyError):
        return None


def load_match(match_id: int) -> tuple[list[MatchEvent], MatchInfo]:
    """Load a single match. Tries StatsBomb API first, falls back to cache."""
    # Try cache first for speed, then API
    cached = _load_cache(match_id)
    if cached is not None:
        events_df, info = cached
        source = "cache"
    else:
        try:
            events_df = sb.events(match_id=match_id)
            # We need match info - get it from the events or matches endpoint
            # For now, extract from events
            teams = events_df["team"].unique().tolist()
            info = {
                "home_team": teams[0] if len(teams) > 0 else "Unknown",
                "away_team": teams[1] if len(teams) > 1 else "Unknown",
                "home_score": 0,
                "away_score": 0,
            }
            # Count goals from shot outcomes
            goals = events_df[(events_df["type"] == "Shot") &
                              (events_df["shot_outcome"] == "Goal")]
            for _, goal in goals.iterrows():
                if goal["team"] == info["home_team"]:
                    info["home_score"] += 1
                else:
                    info["away_score"] += 1
            source = "api"
            _save_cache(match_id, events_df, info)
        except Exception:
            # Try cache as fallback
            cached = _load_cache(match_id)
            if cached is None:
                raise RuntimeError(f"Match {match_id}: API unreachable and no cached data")
            events_df, info = cached
            source = "cache"

    label = f"{info['home_team']} vs {info['away_team']}"

    # Parse events
    parsed = []
    for _, row in events_df.iterrows():
        event = _parse_event(row, match_id, label)
        if event is not None:
            parsed.append(event)

    # Sort by match time
    parsed.sort(key=lambda e: e.match_seconds)

    match_info = MatchInfo(
        match_id=match_id,
        home_team=info["home_team"],
        away_team=info["away_team"],
        home_score=info["home_score"],
        away_score=info["away_score"],
        label=label,
        event_count=len(parsed),
    )

    print(f"  Loaded {label} ({len(parsed)} events, {info['home_score']}-{info['away_score']}) [{source}]")
    return parsed, match_info


async def replay_match(
    events: list[MatchEvent],
    match_info: MatchInfo,
    speed_factor: float,
    event_callback,
) -> None:
    """Replay a single match as an async coroutine.

    Yields events at real match pacing scaled by speed_factor.
    Calls event_callback(event, match_state) for each event.
    """
    speed_factor = max(speed_factor, 0.1)  # Guard against zero/negative

    state = MatchState(
        match_id=match_info.match_id,
        label=match_info.label,
        home_team=match_info.home_team,
        away_team=match_info.away_team,
        total_events=len(events),
    )

    prev_match_seconds = 0.0

    for event in events:
        # Sleep proportional to inter-event gap
        gap = event.match_seconds - prev_match_seconds
        if gap > 0:
            await asyncio.sleep(gap / speed_factor)
        prev_match_seconds = event.match_seconds

        # Update match state
        state.minute = event.minute
        state.events.append(event)

        # Track score from goals
        if event.event_type == "Shot" and event.shot_outcome == "Goal":
            if event.team == state.home_team:
                state.home_score += 1
            else:
                state.away_score += 1

        # Notify
        await event_callback(event, state)


async def replay_concurrent(
    match_configs: list[tuple[int, str]],  # [(match_id, "optional label"), ...]
    speed_factor: float = 60.0,
    event_callback=None,
) -> None:
    """Replay multiple matches concurrently on a shared virtual clock.

    Each match runs as its own async coroutine. Events from all matches
    interleave naturally based on their match timestamps.
    """
    if event_callback is None:
        async def event_callback(event, state):
            pass

    print(f"Loading {len(match_configs)} matches...")
    matches = []
    for match_id, *_ in match_configs:
        events, info = load_match(match_id)
        matches.append((events, info))

    print(f"Starting concurrent replay at {speed_factor}x speed...")
    tasks = [
        replay_match(events, info, speed_factor, event_callback)
        for events, info in matches
    ]
    await asyncio.gather(*tasks)
    print("Replay complete.")


# --- Demo preset matches ---
# These are known dramatic WC 2018 matches good for demo
DEMO_MATCHES = [
    (7580, "France vs Argentina (R16, 4-3)"),      # Mbappe breakout, 7 goals, penalty
    (7576, "Portugal vs Spain (Group, 3-3)"),      # Ronaldo hat-trick, dramatic
    (7567, "South Korea vs Germany (Group, 2-0)"), # Upset, late goals at 91' and 95'
]


def get_demo_matches() -> list[tuple[int, str]]:
    """Return the curated demo preset matches."""
    return DEMO_MATCHES


# --- CLI test ---
if __name__ == "__main__":
    async def print_event(event: MatchEvent, state: MatchState):
        if event.event_type in ("Shot", "Carry", "Pressure"):
            loc_str = f" at ({event.location[0]:.0f},{event.location[1]:.0f})" if event.location else ""
            extra = ""
            if event.xg is not None:
                extra = f" xG={event.xg:.3f}"
            if event.shot_outcome:
                extra += f" [{event.shot_outcome}]"
            print(f"  [{state.label}] {event.minute}' {event.event_type}: "
                  f"{event.player}{loc_str}{extra}")

    print("=== PitchSwitch Replay Engine Test ===\n")

    # Load one match to validate
    match_id = 7580  # France vs Argentina
    events, info = load_match(match_id)

    print(f"\n--- Event Type Breakdown ---")
    from collections import Counter
    type_counts = Counter(e.event_type for e in events)
    for etype, count in type_counts.most_common():
        print(f"  {etype}: {count}")

    print(f"\n--- Key Stats ---")
    carries = [e for e in events if e.event_type == "Carry"]
    final_third = [e for e in carries if e.location and e.location[0] > FINAL_THIRD_X]
    progressive = [e for e in carries if e.location and e.end_location
                    and e.end_location[0] - e.location[0] > 10]
    pressures = [e for e in events if e.event_type == "Pressure"]
    shots = [e for e in events if e.event_type == "Shot"]
    goals = [e for e in shots if e.shot_outcome == "Goal"]
    penalties = [e for e in events if e.is_penalty]

    print(f"  Carries: {len(carries)} ({len(final_third)} in final third, {len(progressive)} progressive)")
    print(f"  Pressures: {len(pressures)}")
    print(f"  Shots: {len(shots)} (xG range: {min(s.xg for s in shots if s.xg):.3f} - {max(s.xg for s in shots if s.xg):.3f})")
    print(f"  Goals: {len(goals)}")
    print(f"  Penalties: {len(penalties)}")
    print(f"  Match time span: {events[0].match_seconds:.0f}s - {events[-1].match_seconds:.0f}s")
    print(f"  Avg gap between events: {(events[-1].match_seconds - events[0].match_seconds) / len(events):.2f}s")

    print(f"\n--- Quick Replay (first 5 minutes, key events only, 600x speed) ---")
    first_5 = [e for e in events if e.minute < 5]

    async def run_quick():
        for e in first_5:
            await print_event(e, MatchState(
                match_id=info.match_id, label=info.label,
                home_team=info.home_team, away_team=info.away_team,
            ))

    asyncio.run(run_quick())
    print("\n=== Replay engine validated ===")
