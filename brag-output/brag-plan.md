# Brag Plan: PitchSwitch

## What is this app?
An AI multi-match whip-around for the World Cup — it watches every simultaneous
match at once and cuts you to the one about to boil over *before* the goal, then
shows you *why* (a live danger differential on screen) with IBM Granite calling
each switch out loud.

## The angle
A broadcast control room, played as a sports trailer. The whole product is
"RedZone, but it gets you there *before* the goal instead of after" — so the
video is built around one before/after turn, then proves it with the actual
on-screen mechanism: two danger bars on the blue→yellow→red ramp, one pulling
ahead, the gold ON AIR marker snapping over, the red switch banner slamming in.
No generic SaaS; this is a gallery feed, dark and urgent. Red means *now*.

## Hook (first 2-3 seconds)
Black pitch. Three condensed-uppercase lines hit like a trailer title card:
**TWO GAMES. ONE SCREEN. SAME KICKOFF.** — the real World Cup group-finale
problem, stated as stakes. A red flicker on the last line.

## Key moments (the middle)
- **The turn:** "RedZone shows you the goal — AFTER." → "PitchSwitch cuts you
  there — BEFORE." The word BEFORE slams in red on a strong beat.
- **The product, doing its thing:** the real DIRECTOR — LIVE DANGER panel. Two
  match bars; KOR vs GER climbs the danger ramp (blue→yellow→red) and pulls
  ahead of MEX vs SWE. The gold ▶ ON AIR marker snaps onto Korea.
- **The cut + the proof:** the red switch banner slams — Granite's call in
  white, then the amber **WHY: danger 0.62 (+0.21)** line. Then the number that
  matters: **~70 seconds before the goal.**

## Outro / punchline
Three IBM techs tick in (Granite · Docling · Watson), then the wordmark lands:
**PITCHSWITCH** — "Like RedZone. It just gets you there first." Cut to black.

## User flow worth showing
The product's core loop *is* the centerpiece: danger rises on one match →
differential crosses → Director cuts → on-screen WHY explains it. Scenes 3–4
recreate that exact loop from the live broadcast overlays (`core/livefeed.py`),
not a marketing diagram.

## Tone
- Preset: cinematic
- Creative direction: live sports-broadcast trailer / control-room sizzle
- Interpretation: big condensed-uppercase type, dramatic slams and holds (not
  rapid chaos), red reserved for the danger and the cut, gold for ON AIR.
  Confidence through scale and restraint.

## Format: landscape — 1920x1080
## Duration: ~21s

## Visual identity (from the project)
- Background: `#0d1f12` (pitch black), pitch surface `#15311a`
- Accent: `#ff3b3b` (danger red — the cut, ON AIR)
- Gold: `#ffd400` (ON AIR marker, "your team")
- Text: `#e8efe9`; WHY amber `#ffe08a`; muted `#9fb0c4`
- Danger ramp: `#4da6ff` → `#ffcc00` → `#ff3b3b` (the one chart-color rule)
- Display font: Oswald (condensed, uppercase, 0.5px tracking — real lower-third face)
- Body font: system sans-serif
- Strongest visual element: the DIRECTOR — LIVE DANGER panel + the red switch
  banner with the amber WHY line (the AI's decision made legible)

## Share copy (draft)
PitchSwitch: like NFL RedZone, but for soccer — and it cuts you to the match
about to score *before* the goal, then shows you why. ~70s of warning, IBM
Granite calling every switch.

## Audio direction
- Role: cinematic support — a driving, confident bed that builds to the cut and
  the wordmark; restrained, never busy.
- Music: `happy-beats-business-moves-vol-11-by-ende-dot-app.mp3` (114.84 BPM,
  driving; strong cues well-spread across 0–25s for scene slams).
- Music treatment: full-energy bed from 0s; small duck under the WHY/70s read so
  the claim lands; ring under the final wordmark, short fade-out at the end.
- Music cue guidance: bundled preset
  `cues/happy-beats-business-moves-vol-11-...music-cues.json`. Strong cues:
  1.60, 3.70, 5.80, 8.96, 12.65, 17.91, 22.65. Lock the big moments —
  BEFORE slam → 5.80; ON AIR snap → 8.96; switch banner slam → 12.65; wordmark
  → 17.91. Hook lines snap to the beat grid (1.60 / 2.65 / 3.70).
- Audio-reactive treatment: subtle — use music RMS/bass to make the danger glow
  and the ON AIR/banner presence breathe. No waveform/equalizer visuals.
- SFX posture: sparse, motion-matched, professional restraint — one UI tick per
  danger-bar climb, a heavier impact on the switch-banner slam, a clean
  announcement hit on the wordmark.
- Audio-coupled moments: hook lines (beat reveal), ON AIR snap (tick on cue),
  switch banner (impact slam), 70s count-up, wordmark (announcement).
- Restraint rule: audio must not turn into a hype-reel mush — keep the bed under
  the type, never let SFX stack, let the WHY line read in relative quiet.

## Storyboard

### Scene 1 — Hook / the problem — 4.0s
Black pitch. "TWO GAMES." then "ONE SCREEN." then "SAME KICKOFF." stack in,
condensed uppercase, each held to read. Faint pitch stripes. Last line gets a
red underline flicker.
Sequential/interaction: yes — three lines arrive one by one on the beat grid
(~1.60 / 2.65 / 3.70), then the full stack holds ~0.6s.
Audio intent: bed establishes, tense and driving.
Audio-coupled idea: beat-aligned line reveals; soft tick per line.
Music: driving bed from 0s.
Transition mood: hard cut → Scene 2

### Scene 2 — The turn (before/after) — 4.0s
Two stacked lines. Top, muted: "RedZone shows you the goal — AFTER." Below, big:
"PitchSwitch cuts you there — BEFORE." BEFORE slams in danger-red and scales.
Sequential/interaction: yes — AFTER line settles first, then BEFORE slams.
Audio intent: build into the slam.
Audio-coupled idea: BEFORE slam // beat-locked 5.80, with an impact accent.
Music: bed continues, lift into 5.80.
Transition mood: dramatic → Scene 3

### Scene 3 — The product: live danger — 5.0s
Recreate the DIRECTOR — LIVE DANGER panel (top-right) over the dark pitch with a
scorebug (▶ LIVE + clock) top-left. Two rows: "KOR v GER" and "MEX v SWE", each
a danger bar on the ramp. KOR's bar climbs blue→yellow→red and overtakes MEX;
the gold ▶ ON AIR marker snaps onto KOR. A red danger glow grows over the
attacking third.
Sequential/interaction: yes — bars fill continuously; ON AIR marker snaps on cue.
Audio intent: rising tension as the bar climbs.
Audio-coupled idea: ON AIR snap // beat-locked 8.96 with a UI tick; glow breathes
with bass (subtle audio-reactive).
Music: bed climbs.
Transition mood: hard cut → Scene 4

### Scene 4 — The cut + the proof — 4.5s
The red switch banner slams across the upper third: "SWITCH → KOR v GER" in
white, then the amber line **WHY: danger 0.62 (+0.21)**. Below it the payoff
count-up: **~70s before the goal**, with a one-line Granite-style call.
Sequential/interaction: yes — banner slams, then WHY line, then 70 counts up
(0→70). Hold the full set to read.
Audio intent: the bed peaks on the slam, then ducks under the WHY/70 read.
Audio-coupled idea: banner slam // beat-locked 12.65 with a heavy impact;
70 count-up ticks; music ducks for the read.
Music: peak then duck.
Transition mood: hard cut → Scene 5

### Scene 5 — Tech + wordmark — 3.5s
Three small IBM techs tick in on a row — "GRANITE · narration" "DOCLING ·
grounded primers" "WATSON · spoken commentary" — then clear, and the wordmark
**PITCHSWITCH** lands center with the tagline "Like RedZone. It just gets you
there first." Red dot over the I. Cut to black.
Sequential/interaction: yes — three tech chips arrive one by one, then wordmark
slams.
Audio intent: resolve — clean announcement hit on the wordmark, then fade.
Audio-coupled idea: wordmark // beat-locked 17.91 with an announcement SFX;
music rings then fades.
Music: ring under wordmark, short fade-out.
Transition mood: cut to black (end)

**Music mood for this video:** cinematic / driving sports-trailer bed.
**Audio summary:** a confident driving bed that establishes the stakes, lifts
into the BEFORE slam and the ON AIR snap, peaks on the switch-banner cut, ducks
to let the ~70s proof read, then rings out under the wordmark and fades.
