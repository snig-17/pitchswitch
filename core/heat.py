"""Heat & anticipation model: rolling danger score per match.

Danger score (0.0-1.0) computed from a rolling 90-second window of events:
  - Carries into the final third (x > 80)
  - Pressure events in opponent's half
  - Passes into the penalty area
  - Shot xG values
  - Set-piece indicators (corner, free kick in range, penalty)
  - Red card events

Forward-looking signal: time-based derivative (danger_change / elapsed_match_seconds).
Exponential decay smoothing handles sparse event periods.

Switch threshold:
  - danger > 0.6 AND derivative > 0.1/s, OR
  - danger > 0.8 (absolute), OR
  - set-piece awarded (penalty, free kick in range)

Late-game multiplier: 1.5x in last 15 minutes with tight scoreline (within 1 goal).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.replay import MatchEvent, FINAL_THIRD_X

# Pitch zones
PENALTY_AREA_X = 102  # x > 102 = penalty area (approx)
OPPONENT_HALF_X = 60  # x > 60 = opponent's half

# Danger model parameters
WINDOW_SECONDS = 90.0
DECAY_ALPHA = 0.03  # exponential decay rate per second (slower decay = longer memory)
MIN_DERIVATIVE_EVENTS = 3  # need at least 3 events to compute derivative

# Feature weights -- tuned against WC 2018 France vs Argentina
# Key insight: events are dense (~1.6s apart), so individual contributions
# must be small enough that steady midfield play stays under 0.4, but
# final-third pressure sequences push above 0.5 within 30 seconds.
W_CARRY_FINAL_THIRD = 0.04
W_PROGRESSIVE_CARRY = 0.06
W_PRESSURE_OPP_HALF = 0.02
W_PASS_PENALTY_AREA = 0.05
W_SHOT_XG = 0.8  # xG is already 0-1, scale slightly
W_CORNER = 0.12
W_FREE_KICK = 0.08
W_PENALTY = 0.40
W_RED_CARD = 0.20

# Switch thresholds -- tuned to fire 8-15 times per 90-minute match
SWITCH_DANGER_RISING = 0.35
SWITCH_DERIVATIVE_MIN = 0.005  # per second (was 0.1, too high for dense events)
SWITCH_DANGER_ABSOLUTE = 0.55
MIN_DWELL_SECONDS = 20.0

# Late-game
LATE_GAME_MINUTE = 75
LATE_GAME_MULTIPLIER = 1.5


@dataclass
class DangerEvent:
    """An event with its computed danger contribution."""
    match_seconds: float
    contribution: float  # raw danger contribution of this event
    event_type: str
    detail: str  # for narration context


@dataclass
class MatchHeat:
    """Rolling danger state for a single match."""
    match_id: int
    label: str
    home_team: str
    away_team: str

    # Current state
    danger: float = 0.0
    derivative: float = 0.0
    about_to_ignite: bool = False
    should_switch: bool = False
    switch_reason: str = ""

    # Score tracking (for late-game multiplier)
    home_score: int = 0
    away_score: int = 0
    current_minute: int = 0

    # Rolling window
    _events: list[DangerEvent] = field(default_factory=list)
    _prev_time: float = 0.0
    _last_switch_time: float = 0.0

    def update(self, event: MatchEvent) -> None:
        """Process a new event and recalculate danger score."""
        self.current_minute = event.minute

        # Track score
        if event.event_type == "Shot" and event.shot_outcome == "Goal":
            if event.team == self.home_team:
                self.home_score += 1
            else:
                self.away_score += 1

        # Compute this event's danger contribution
        contribution = self._score_event(event)
        if contribution > 0:
            self._events.append(DangerEvent(
                match_seconds=event.match_seconds,
                contribution=contribution,
                event_type=event.event_type,
                detail=event.raw_type_detail,
            ))

        # Prune old events outside the rolling window
        cutoff = event.match_seconds - WINDOW_SECONDS
        self._events = [e for e in self._events if e.match_seconds > cutoff]

        # Compute danger score with exponential decay
        now = event.match_seconds
        raw_danger = 0.0
        for de in self._events:
            age = now - de.match_seconds
            weight = math.exp(-DECAY_ALPHA * age)
            raw_danger += de.contribution * weight

        # Clamp to 0-1
        raw_danger = min(raw_danger, 1.0)

        # Late-game multiplier
        if self._is_late_game():
            raw_danger = min(raw_danger * LATE_GAME_MULTIPLIER, 1.0)

        # Compute time-based derivative against the PREVIOUS event's danger.
        # self.danger still holds the prior value here — it's updated just below —
        # so this is (danger_now - danger_prev) / elapsed, a true one-step slope.
        elapsed = now - self._prev_time if self._prev_time > 0 else 1.0
        elapsed = max(elapsed, 0.1)  # guard against zero
        if len(self._events) >= MIN_DERIVATIVE_EVENTS:
            self.derivative = (raw_danger - self.danger) / elapsed
        else:
            self.derivative = 0.0

        self._prev_time = now
        self.danger = raw_danger

        # Forward-looking signal
        self.about_to_ignite = (
            self.danger > 0.4 and self.derivative > 0.05
        )

        # Switch decision
        self._evaluate_switch(event)

    def _score_event(self, event: MatchEvent) -> float:
        """Compute the danger contribution of a single event."""
        score = 0.0
        loc_x = event.location[0] if event.location else 0.0

        if event.event_type == "Carry":
            if loc_x > FINAL_THIRD_X:
                score += W_CARRY_FINAL_THIRD
            # Progressive carry bonus
            if event.location and event.end_location:
                progress = event.end_location[0] - event.location[0]
                if progress > 10:
                    score += W_PROGRESSIVE_CARRY

        elif event.event_type == "Pressure":
            if loc_x > OPPONENT_HALF_X:
                score += W_PRESSURE_OPP_HALF

        elif event.event_type == "Pass":
            end_x = event.end_location[0] if event.end_location else 0.0
            if end_x > PENALTY_AREA_X:
                score += W_PASS_PENALTY_AREA

        elif event.event_type == "Shot":
            if event.xg is not None:
                score += event.xg * W_SHOT_XG

        # Set-piece bonuses (stack on top)
        if event.is_penalty:
            score += W_PENALTY
        elif event.is_corner:
            score += W_CORNER
        elif event.is_free_kick and loc_x > FINAL_THIRD_X:
            score += W_FREE_KICK

        if event.is_red_card:
            score += W_RED_CARD

        return score

    def _is_late_game(self) -> bool:
        """Check if we're in the late-game tight-scoreline window."""
        if self.current_minute < LATE_GAME_MINUTE:
            return False
        score_diff = abs(self.home_score - self.away_score)
        return score_diff <= 1

    def _evaluate_switch(self, event: MatchEvent) -> None:
        """Determine if this match should trigger a switch."""
        self.should_switch = False
        self.switch_reason = ""

        # Dwell time guard
        if event.match_seconds - self._last_switch_time < MIN_DWELL_SECONDS:
            return

        # Penalty always switches
        if event.is_penalty:
            self.should_switch = True
            self.switch_reason = f"Penalty! {event.player} ({event.team})"
            self._last_switch_time = event.match_seconds
            return

        # High absolute danger
        if self.danger > SWITCH_DANGER_ABSOLUTE:
            self.should_switch = True
            self.switch_reason = f"Danger critical ({self.danger:.2f}) - {event.team} attacking"
            self._last_switch_time = event.match_seconds
            return

        # Rising danger
        if self.danger > SWITCH_DANGER_RISING and self.derivative > SWITCH_DERIVATIVE_MIN:
            self.should_switch = True
            self.switch_reason = (
                f"Danger rising fast ({self.danger:.2f}, +{self.derivative:.3f}/s) "
                f"- {event.team} building"
            )
            self._last_switch_time = event.match_seconds
            return

    def get_state_summary(self) -> dict:
        """Return current state for the director and UI."""
        return {
            "match_id": self.match_id,
            "label": self.label,
            "danger": round(self.danger, 3),
            "derivative": round(self.derivative, 4),
            "about_to_ignite": self.about_to_ignite,
            "should_switch": self.should_switch,
            "switch_reason": self.switch_reason,
            "score": f"{self.home_score}-{self.away_score}",
            "minute": self.current_minute,
            "late_game": self._is_late_game(),
            "events_in_window": len(self._events),
        }

    def get_recent_context(self, n: int = 5) -> list[str]:
        """Return last N danger events as narration context."""
        recent = self._events[-n:] if self._events else []
        return [f"{de.detail} (contribution: {de.contribution:.3f})" for de in recent]


def create_heat(match_id: int, label: str, home_team: str, away_team: str) -> MatchHeat:
    """Create a new MatchHeat tracker for a match."""
    return MatchHeat(
        match_id=match_id,
        label=label,
        home_team=home_team,
        away_team=away_team,
    )


# --- CLI test ---
if __name__ == "__main__":
    from core.replay import load_match

    match_id = 7580  # France vs Argentina
    events, info = load_match(match_id)

    heat = create_heat(info.match_id, info.label, info.home_team, info.away_team)

    print(f"=== Danger Model Test: {info.label} ===\n")

    # Track switches and goals for accuracy
    switches = []
    goals = []

    for event in events:
        heat.update(event)

        if event.event_type == "Shot" and event.shot_outcome == "Goal":
            goals.append((event.minute, event.player, event.team, heat.danger))

        if heat.should_switch:
            switches.append((event.minute, event.match_seconds, heat.danger,
                              heat.derivative, heat.switch_reason))

    print(f"--- Goals ---")
    for minute, player, team, danger_at_goal in goals:
        print(f"  {minute}' GOAL: {player} ({team}) [danger at goal: {danger_at_goal:.3f}]")

    print(f"\n--- Switch Triggers ({len(switches)}) ---")
    for minute, seconds, danger, deriv, reason in switches:
        print(f"  {minute}' danger={danger:.3f} deriv={deriv:+.4f}/s: {reason}")

    # Accuracy: how many goals had a switch trigger BEFORE them?
    print(f"\n--- Anticipation Accuracy ---")
    predicted = 0
    for g_min, g_player, g_team, _ in goals:
        g_seconds = g_min * 60
        # Look for a switch within 120 seconds before the goal
        pre_switches = [s for s in switches
                         if 0 < g_seconds - s[1] < 120]
        if pre_switches:
            lead = g_seconds - pre_switches[-1][1]
            print(f"  {g_min}' {g_player}: PREDICTED ({lead:.0f}s lead)")
            predicted += 1
        else:
            print(f"  {g_min}' {g_player}: MISSED")

    print(f"\n  Hit rate: {predicted}/{len(goals)} ({100*predicted/len(goals):.0f}%)")
    print(f"  Total switch triggers: {len(switches)}")
