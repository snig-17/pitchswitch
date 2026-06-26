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
