"""Accuracy calibration for the PitchSwitch anticipation model.

Replays each demo match event-by-event through the heat model and measures how
well the switch signal anticipates dangerous moments.

Methodology
-----------
Lead window W (default 120s).

- Ground-truth dangerous moment = a Goal. Shots (goals + attempts) form the
  broader "dangerous moment" set used for false-positive scoring, since
  anticipating a shot/save is also a valid switch.
- A switch *episode* = an event where the model set should_switch=True (the
  20s dwell guard spaces these out, so each is a distinct call).
- Goal predicted (recall): a goal at time T is "predicted" if a switch episode
  fired for that match in [T - W, T) -- strictly before the goal, so we measure
  anticipation, not reaction to the goal's own xG spike.
- Lead time: T - (earliest switch episode time within that window).
- False positive: a switch episode with no shot/goal in (t, t + W] for that
  match. False-positive rate = false positives / total episodes.

Usage:
    python scripts/calibrate.py [--window SECONDS]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/calibrate.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.heat import create_heat  # noqa: E402
from core.replay import get_demo_matches, load_match  # noqa: E402


def _is_goal(ev) -> bool:
    return ev.event_type == "Shot" and ev.shot_outcome == "Goal"


def _is_shot(ev) -> bool:
    return ev.event_type == "Shot"


def calibrate_match(events, info, window: float):
    """Replay one match and return its raw timeline of episodes and moments."""
    heat = create_heat(info.match_id, info.label, info.home_team, info.away_team)

    switch_times: list[float] = []   # times should_switch fired
    goal_times: list[float] = []     # goal event times
    shot_times: list[float] = []     # all shot (incl. goal) times

    for ev in events:
        if _is_shot(ev):
            shot_times.append(ev.match_seconds)
            if _is_goal(ev):
                goal_times.append(ev.match_seconds)
        heat.update(ev)
        if heat.should_switch:
            switch_times.append(ev.match_seconds)

    # Recall + lead time per goal
    predicted = 0
    lead_times: list[float] = []
    for t in goal_times:
        in_window = [s for s in switch_times if t - window <= s < t]
        if in_window:
            predicted += 1
            lead_times.append(t - min(in_window))

    # False positives per switch episode (scored against shots, not just goals)
    false_positives = 0
    for s in switch_times:
        if not any(s < shot <= s + window for shot in shot_times):
            false_positives += 1

    return {
        "label": info.label,
        "goals": len(goal_times),
        "predicted": predicted,
        "lead_times": lead_times,
        "episodes": len(switch_times),
        "false_positives": false_positives,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=float, default=120.0,
                    help="lead/false-positive window in seconds (default 120)")
    args = ap.parse_args()
    window = args.window

    rows = []
    for match_id, _label in get_demo_matches():
        events, info = load_match(match_id)
        rows.append(calibrate_match(events, info, window))

    # Per-match table
    print(f"\nPitchSwitch accuracy calibration (window = {window:.0f}s)\n")
    print(f"{'Match':<40} {'goals':>6} {'pred':>5} {'lead':>7} {'eps':>5} {'FP':>4}")
    print("-" * 72)
    for r in rows:
        avg_lead = sum(r["lead_times"]) / len(r["lead_times"]) if r["lead_times"] else 0
        print(f"{r['label']:<40} {r['goals']:>6} {r['predicted']:>5} "
              f"{avg_lead:>6.0f}s {r['episodes']:>5} {r['false_positives']:>4}")

    # Pooled totals
    goals = sum(r["goals"] for r in rows)
    predicted = sum(r["predicted"] for r in rows)
    all_leads = [lt for r in rows for lt in r["lead_times"]]
    episodes = sum(r["episodes"] for r in rows)
    fps = sum(r["false_positives"] for r in rows)

    hit_rate = 100 * predicted / goals if goals else 0
    avg_lead = sum(all_leads) / len(all_leads) if all_leads else 0
    fp_rate = 100 * fps / episodes if episodes else 0

    print("-" * 72)
    print(f"\nTOTALS across {len(rows)} matches:")
    print(f"  Dangerous moments predicted : {predicted}/{goals} ({hit_rate:.0f}%)")
    print(f"  Average lead time           : {avg_lead:.0f}s")
    print(f"  False positive rate         : {fp_rate:.0f}% ({fps}/{episodes} episodes)")
    print()
    print("README table values:")
    print(f"  | Dangerous moments predicted | {predicted}/{goals} |")
    print(f"  | Average lead time before event | {avg_lead:.0f}s |")
    print(f"  | False positive rate | {fp_rate:.0f}% |")
    print()


if __name__ == "__main__":
    main()
