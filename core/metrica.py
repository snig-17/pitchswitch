"""Metrica Sports tracking loader.

Parses Metrica's open 25fps tracking CSVs (all 22 players + ball, normalized
0-1 coordinates) into compact frames for the live broadcast feed. This gives
genuine continuous player movement, unlike the event-only StatsBomb data.

Data (gitignored, ~30MB each): data/metrica/g{N}_RawTrackingData_{Home,Away}_Team.csv
Download with scripts/get_metrica.sh.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "metrica"
FPS_RAW = 25


def _load_team(path: Path):
    """Return (times, [(name, xs, ys), ...]) including 'Ball' as the last pair."""
    df = pd.read_csv(path, skiprows=2)
    cols = list(df.columns)
    times = df["Time [s]"].to_numpy()
    periods = df["Period"].to_numpy()
    pairs = []
    i = 3
    while i < len(cols) - 1:
        pairs.append((cols[i], df[cols[i]].to_numpy(), df[cols[i + 1]].to_numpy()))
        i += 2
    return times, periods, pairs


@dataclass
class Frame:
    t: float
    ball: tuple[float, float] | None
    home: list[tuple[float, float]]
    away: list[tuple[float, float]]


def load_frames(game: int, t0: float = 0.0, dur: float = 60.0,
                fps: int = 12, max_players: int = 11) -> list[Frame]:
    """Load a downsampled window of tracking frames for one Metrica game.

    t0/dur in seconds of match time; fps is the output frame rate.
    """
    home_path = DATA_DIR / f"g{game}_RawTrackingData_Home_Team.csv"
    away_path = DATA_DIR / f"g{game}_RawTrackingData_Away_Team.csv"
    ht, _hp, hpairs = _load_team(home_path)
    at, _ap, apairs = _load_team(away_path)

    # Ball is the last pair in the home file
    ball_name, bxs, bys = hpairs[-1]
    home_pairs = hpairs[:-1]
    away_pairs = apairs[:-1]

    step = max(1, round(FPS_RAW / fps))
    frames: list[Frame] = []
    n = len(ht)
    for i in range(0, n, step):
        t = float(ht[i])
        if t < t0:
            continue
        if t > t0 + dur:
            break
        home = []
        for _name, xs, ys in home_pairs:
            x, y = xs[i], ys[i]
            if x == x and y == y:  # not NaN
                home.append((round(float(x), 4), round(float(y), 4)))
            if len(home) >= max_players:
                break
        away = []
        for _name, xs, ys in away_pairs:
            x, y = xs[i], ys[i]
            if x == x and y == y:
                away.append((round(float(x), 4), round(float(y), 4)))
            if len(away) >= max_players:
                break
        bx, by = bxs[i], bys[i]
        ball = (round(float(bx), 4), round(float(by), 4)) if bx == bx else None
        frames.append(Frame(t=round(t, 2), ball=ball, home=home, away=away))
    return frames


def frame_danger(fr: Frame) -> float:
    """Danger proxy from tracking: ball deep toward either goal + players
    clustered at that end. 0..1."""
    if not fr.ball:
        return 0.0
    bx = fr.ball[0]
    edge = max(bx, 1 - bx)                 # 0.5 (center) .. 1.0 (goal line)
    base = max(0.0, (edge - 0.60) / 0.40)  # ramps up inside the final third
    end = 1.0 if bx > 0.5 else 0.0
    near = sum(1 for p in (fr.home + fr.away) if abs(p[0] - end) < 0.25)
    return round(min(base * (0.55 + 0.08 * near), 1.0), 3)


def load_events(game: int, t0: float, dur: float):
    """Return [(t, caption)] of Metrica events in the window, for play-by-play."""
    df = pd.read_csv(DATA_DIR / f"g{game}_RawEventsData.csv")
    out = []
    for _, r in df.iterrows():
        t = r.get("Start Time [s]")
        if t != t or t < t0 or t > t0 + dur:
            continue
        typ = str(r.get("Type", "")).title()
        sub = r.get("Subtype")
        team = str(r.get("Team", "")).title()
        if typ.upper() in ("BALL LOST", "BALL OUT", "CHALLENGE"):
            continue  # noise; keep the watchable beats
        cap = f"{team} — {typ}"
        if isinstance(sub, str) and sub:
            cap += f" ({sub.title()})"
        out.append([round(float(t), 1), cap])
    return out


def build_broadcast(games=(1, 2), t0: float = 0.0, dur: float = 180.0,
                    fps: int = 10, dwell: float = 4.0):
    """Assemble a multi-match broadcast: frames + danger + a switch schedule +
    play-by-play captions, ready to hand to the canvas. Switching is greedy on
    the danger proxy with a dwell guard."""
    gdata = []
    for g in games:
        frames = load_frames(g, t0=t0, dur=dur, fps=fps)
        dser = [frame_danger(f) for f in frames]
        gdata.append({"label": f"MATCH {len(gdata)+1}", "frames": frames,
                      "danger": dser, "captions": load_events(g, t0, dur)})

    # Common time grid = the shorter game's frame times
    times = [f.t for f in min((gd["frames"] for gd in gdata), key=len)]
    on = 0
    last_switch = -1e9
    schedule = [[times[0] if times else t0, 0, "KICK OFF"]]
    for k, t in enumerate(times):
        best, bestd = on, -1.0
        for gi, gd in enumerate(gdata):
            d = gd["danger"][k] if k < len(gd["danger"]) else 0.0
            if d > bestd:
                best, bestd = gi, d
        cur = gdata[on]["danger"][k] if k < len(gdata[on]["danger"]) else 0.0
        if best != on and t - last_switch > dwell and bestd > cur + 0.12 and bestd > 0.25:
            on = best
            last_switch = t
            schedule.append([round(t, 1), on, "Danger building — cut to MATCH " + str(on + 1)])
    return {"games": gdata, "schedule": schedule}
