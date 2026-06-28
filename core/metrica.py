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

# National kit colours (shirt, jersey-number) so avatars read as real teams.
TEAM_KITS = {
    "france": ("#1e3a8a", "#ffffff"),
    "argentina": ("#75aadb", "#0a3161"),
    "south korea": ("#c8102e", "#ffffff"),
    "germany": ("#e8e8e8", "#111111"),
    "spain": ("#c60b1e", "#ffd400"),
    "portugal": ("#006600", "#ffffff"),
    "brazil": ("#fde000", "#1b6b2f"),
    "england": ("#f4f4f4", "#0a3161"),
}
DEFAULT_HOME_KIT = ("#4da6ff", "#ffffff")
DEFAULT_AWAY_KIT = ("#ff8c42", "#111111")


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
    # fixed-length slots; each is (x, y, jersey_number) or None when off-pitch
    home: list[tuple[float, float, str] | None]
    away: list[tuple[float, float, str] | None]


def _jersey(name: str) -> str:
    """'Player11' -> '11'."""
    digits = "".join(c for c in name if c.isdigit())
    return digits or "?"


def load_frames(game: int, t0: float = 0.0, dur: float = 60.0,
                fps: int = 12) -> list[Frame]:
    """Load a downsampled window of tracking frames for one Metrica game.

    Player slots are kept in fixed column order (None when a player is off the
    pitch) so a slot index always maps to the same jersey number across frames.
    """
    home_path = DATA_DIR / f"g{game}_RawTrackingData_Home_Team.csv"
    away_path = DATA_DIR / f"g{game}_RawTrackingData_Away_Team.csv"
    ht, _hp, hpairs = _load_team(home_path)
    at, _ap, apairs = _load_team(away_path)

    ball_name, bxs, bys = hpairs[-1]      # ball is the last pair in the home file
    home_pairs = hpairs[:-1]
    away_pairs = apairs[:-1]
    home_nums = [_jersey(n) for n, _, _ in home_pairs]
    away_nums = [_jersey(n) for n, _, _ in away_pairs]

    step = max(1, round(FPS_RAW / fps))
    frames: list[Frame] = []
    for i in range(0, len(ht), step):
        t = float(ht[i])
        if t < t0:
            continue
        if t > t0 + dur:
            break

        def slots(pairs, nums):
            out = []
            for (_n, xs, ys), num in zip(pairs, nums):
                x, y = xs[i], ys[i]
                out.append((round(float(x), 4), round(float(y), 4), num)
                           if x == x and y == y else None)
            return out

        bx, by = bxs[i], bys[i]
        ball = (round(float(bx), 4), round(float(by), 4)) if bx == bx else None
        frames.append(Frame(t=round(t, 2), ball=ball,
                            home=slots(home_pairs, home_nums),
                            away=slots(away_pairs, away_nums)))
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
    near = sum(1 for p in (fr.home + fr.away) if p and abs(p[0] - end) < 0.25)
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


def _relabel(captions, home, away):
    """Rewrite Metrica's anonymised Home/Away captions with team names."""
    out = []
    for t, cap in captions:
        out.append([t, cap.replace("Home", home).replace("Away", away)])
    return out


def _narrate(home, away, danger, favourite, grounding, provider):
    """One-sentence switch call. Granite-grounded when available, else template."""
    matched = None
    if favourite:
        fav = favourite.strip().lower()
        if fav in home.lower() or fav in away.lower():
            matched = home if fav in home.lower() else away
    prefix = f"Your team {matched}! " if matched else ""
    if provider is not None and provider.is_warm():
        facts = grounding.facts_for(home, away) if grounding else ""
        prompt = (
            "You are a football match director. In ONE punchy sentence, tell the "
            f"viewer to switch to {home} vs {away}, where danger is spiking "
            f"({danger:.2f}). Make it vivid using this context:\n{facts}\n"
            "Start with 'Switch to' or 'Get to'."
        )
        try:
            out = provider.generate(prompt, max_tokens=55)
        except Exception as exc:
            # Degrade to the template switch call, but log so a real
            # signature/programming error doesn't silently serve fallback forever.
            import sys
            print(f"Narration: Granite call failed ({exc!r}); using template",
                  file=sys.stderr)
            out = None
        if out:
            return prefix + out.strip()
    return f"{prefix}Cut to {home} vs {away} — a dangerous attack is building!"


def _pick_goal(games, schedule, times):
    """Pick one watchable goal for the demo: the highest-danger frame of the
    match that is *on air* at that moment, so the viewer is actually watching
    when it goes in. Returns ``(game_index, time, side)`` with ``side='h'``
    (the home team scores), or ``None`` when no match ever reaches real danger.
    """
    if not games or not times:
        return None

    def onair_at(at):
        gi = schedule[0][1] if schedule else 0
        for s in schedule:
            if s[0] <= at:
                gi = s[1]
            else:
                break
        return gi

    best = None  # (danger, time, game_index)
    for k, t in enumerate(times):
        gi = onair_at(t)
        dl = games[gi].get("danger", [])
        dv = dl[k] if k < len(dl) else 0.0
        if best is None or dv > best[0]:
            best = (dv, t, gi)
    if best is None or best[0] <= 0:
        return None
    return best[2], round(best[1], 1), "h"


def build_unified_broadcast(matchups, favourite: str = "", t0: float = 0.0,
                            dur: float = 120.0, fps: int = 8,
                            margin: float = 0.12, dwell: float = 5.0,
                            narrate: bool = True, voice: bool = False):
    """One broadcast over real tracking: the Director cuts to whichever match's
    danger is pulling ahead (rising differential). Each switch gets a
    Granite-grounded narration. matchups: [{game, home, away}].
    """
    from core.personalize import Personalizer
    grounding = provider = None
    if narrate:
        try:
            from core.grounding import get_grounding
            from providers.llm import get_provider
            grounding = get_grounding()
            provider = get_provider()
        except Exception:
            provider = None

    pz = Personalizer.from_input(favourite)
    games = []
    for m in matchups:
        frames = load_frames(m["game"], t0=t0, dur=dur, fps=fps)
        mult = pz.multiplier(m["home"], m["away"])
        danger = [min(frame_danger(f) * mult, 1.0) for f in frames]
        hshirt, hnum = TEAM_KITS.get(m["home"].lower(), DEFAULT_HOME_KIT)
        ashirt, anum = TEAM_KITS.get(m["away"].lower(), DEFAULT_AWAY_KIT)
        games.append({
            "home": m["home"], "away": m["away"],
            "label": f"{m['home']} vs {m['away']}",
            "frames": frames, "danger": danger,
            "home_color": hshirt, "home_num": hnum,
            "away_color": ashirt, "away_num": anum,
            "captions": _relabel(load_events(m["game"], t0, dur), m["home"], m["away"]),
        })

    # Coach: explain rule events (penalty/foul/card/corner/goal) per match,
    # Granite-generated + Docling-grounded, spoken in a distinct voice.
    from core.coach import explain, load_coach_events
    COACH_VOICE = "en-GB_KateV3Voice"
    tts = None
    if voice:
        try:
            from providers.tts import get_tts
            tts = get_tts()
        except Exception:
            tts = None
    text_by_cat: dict[str, str] = {}     # one Granite explanation per category
    audio_by_cat: dict[str, str | None] = {}
    for g, m in zip(games, matchups):
        coach = []
        for ct, cat in load_coach_events(m["game"], t0, dur):
            if cat not in text_by_cat:
                text_by_cat[cat] = explain(cat, provider)
            text = text_by_cat[cat]
            if tts is not None and cat not in audio_by_cat:
                import base64
                raw = tts.synthesize(text, voice=COACH_VOICE)
                audio_by_cat[cat] = base64.b64encode(raw).decode("ascii") if raw else None
            coach.append([ct, cat, text, audio_by_cat.get(cat)])
        g["coach"] = coach

    # One Granite-grounded narration per match (reused on each cut), plus
    # optional spoken audio. Two LLM calls total instead of one per switch.
    for g in games:
        peak = max(g["danger"]) if g["danger"] else 0.35
        g["narration"] = _narrate(g["home"], g["away"], peak, favourite,
                                   grounding, provider)
        g["audio"] = None
        if voice:
            try:
                import base64
                from providers.tts import get_tts
                clip = get_tts().synthesize(g["narration"])
                if clip:
                    g["audio"] = base64.b64encode(clip).decode("ascii")
            except Exception:
                pass

    times = [f.t for f in min((g["frames"] for g in games), key=len)]
    on = 0
    last_switch = -1e9
    prev_diff = 0.0
    schedule = [[times[0] if times else t0, 0]]   # [time, game_index]
    for k, t in enumerate(times):
        cur = games[on]["danger"][k] if k < len(games[on]["danger"]) else 0.0
        best, bestd = on, cur
        for gi, g in enumerate(games):
            if gi == on:
                continue
            d = g["danger"][k] if k < len(g["danger"]) else 0.0
            if d > bestd:
                best, bestd = gi, d
        diff = bestd - cur                       # how far ahead the other match is
        rising = diff >= prev_diff               # differential increasing
        if best != on and diff > margin and rising and t - last_switch > dwell:
            on = best
            last_switch = t
            schedule.append([round(t, 1), on])
        prev_diff = diff

    # Guarantee one watchable goal in the demo, at the on-air danger peak, with
    # the matching big GOAL overlay (rendered client-side in livefeed.py).
    for g in games:
        g["goals"] = []
    goal = _pick_goal(games, schedule, times)
    if goal:
        gi, gt, side = goal
        games[gi]["goals"].append([gt, side])
    return {"games": games, "schedule": schedule}
