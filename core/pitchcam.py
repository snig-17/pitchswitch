"""Pitch-cam: render a match as a live broadcast-style tactical feed.

Turns the StatsBomb event coordinates into an animated 2D pitch -- the ball
trail, recent action, shots/goals, and a danger glow in the attacking third --
so the main view shows "the game" and cuts between matches when the Director
switches. This is the visual layer over the same data the model reasons on.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless backend for Streamlit
import matplotlib.pyplot as plt
from mplsoccer import Pitch

from core.heat import MatchHeat
from core.replay import MatchEvent, FINAL_THIRD_X

# Broadcast palette
PITCH_GREEN = "#15311a"
PITCH_LINES = "#cfe8d0"
BG = "#0d1f12"
HOME_COLOR = "#4da6ff"   # blue
AWAY_COLOR = "#ff8c42"   # orange
BALL_COLOR = "#ffffff"
GOAL_COLOR = "#ffd700"

# How many recent events to show as the live action trail
TRAIL = 10


def render_feed(heat: MatchHeat, recent_events: list[MatchEvent], score: str,
                just_switched: bool = False, is_favourite: bool = False):
    """Return a matplotlib Figure: a broadcast-style view of the match."""
    pitch = Pitch(pitch_type="statsbomb", pitch_color=PITCH_GREEN,
                  line_color=PITCH_LINES, linewidth=1.2, line_zorder=1)
    fig, ax = pitch.draw(figsize=(9, 5.8))
    fig.set_facecolor(BG)

    evs = [e for e in (recent_events or []) if e.location][-TRAIL:]

    # Danger glow over the attacking third when the match is heating up
    if heat.danger > 0.35:
        alpha = min(0.06 + heat.danger * 0.22, 0.30)
        ax.axvspan(FINAL_THIRD_X, 120, color="#ff3b3b", alpha=alpha, zorder=0)

    # Ball-movement trail (older -> newer fades in)
    if len(evs) >= 2:
        xs = [e.location[0] for e in evs]
        ys = [e.location[1] for e in evs]
        pitch.lines(xs[:-1], ys[:-1], xs[1:], ys[1:], ax=ax,
                    color="white", lw=2, alpha=0.35, comet=True, zorder=2)

    # Event markers, sized/faded by recency, coloured by team
    n = len(evs)
    for i, e in enumerate(evs):
        recency = (i + 1) / n
        col = HOME_COLOR if e.team == heat.home_team else AWAY_COLOR
        pitch.scatter(e.location[0], e.location[1], ax=ax,
                      s=40 + 200 * recency, color=col,
                      alpha=0.2 + 0.6 * recency, edgecolors="none", zorder=3)

    # Shots and goals stand out
    for e in evs:
        if e.event_type == "Shot":
            is_goal = e.shot_outcome == "Goal"
            pitch.scatter(e.location[0], e.location[1], ax=ax, marker="*",
                          s=900 if is_goal else 450,
                          color=GOAL_COLOR if is_goal else "white",
                          edgecolors="black", linewidth=1, zorder=5)
            if is_goal:
                ax.text(e.location[0], e.location[1] + 5, "GOAL!", color=GOAL_COLOR,
                        fontsize=14, fontweight="bold", ha="center", zorder=6)

    # The ball = most recent located event
    if evs:
        b = evs[-1]
        pitch.scatter(b.location[0], b.location[1], ax=ax, s=170,
                      color=BALL_COLOR, edgecolors="black", linewidth=1.6, zorder=6)

    # Team colour key (top-left) -- score/minute live in the Streamlit header
    home, away = heat.home_team, heat.away_team
    fig.text(0.03, 0.95, f"● {home}", color=HOME_COLOR, fontsize=11,
             fontweight="bold", va="top")
    fig.text(0.03, 0.905, f"● {away}", color=AWAY_COLOR, fontsize=11,
             fontweight="bold", va="top")

    # Danger readout (top-right)
    dcol = "#ff3b3b" if heat.danger > 0.5 else ("#ffcc00" if heat.danger > 0.3 else "#8fbf8f")
    label = "IGNITING" if heat.about_to_ignite else ("HIGH" if heat.danger > 0.5 else "DANGER")
    fig.text(0.97, 0.95, f"{label} {heat.danger:.2f}", color=dcol, fontsize=13,
             fontweight="bold", ha="right", va="top")

    # On-air / switch badge
    if just_switched:
        fig.text(0.97, 0.90, "▶ ON AIR", color="#ff3b3b", fontsize=11,
                 fontweight="bold", ha="right", va="top")
    if is_favourite:
        fig.text(0.03, 0.05, "★ YOUR TEAM", color=GOAL_COLOR, fontsize=11,
                 fontweight="bold", va="bottom")

    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.02)
    return fig
