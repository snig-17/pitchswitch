# Hyperframes Composition Brief: PitchSwitch

## Objective
Create a ~21s cinematic launch-style brag video for PitchSwitch — a live
broadcast control-room trailer for an AI World Cup whip-around.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: ~21 seconds

## Source Material
- Project root: `/Users/snigdhatiwari/pitchswitch`
- Primary files read: `README.md`, `DESIGN.md`, `.streamlit/config.toml`,
  `core/livefeed.py` (broadcast overlays + tokens)
- Product name: PitchSwitch
- Tagline / strongest claim: "Like NFL RedZone, but for soccer, and it switches
  you *before* the goal instead of after."
- Key UI to recreate: the DIRECTOR — LIVE DANGER panel (per-match danger bars on
  the blue→yellow→red ramp + gold ▶ ON AIR marker) and the red switch banner
  with the amber WHY line. Plus the scorebug (▶ LIVE + clock).
- Copy that must appear verbatim / near-verbatim:
  - TWO GAMES. ONE SCREEN. SAME KICKOFF.
  - PitchSwitch cuts you there — BEFORE.
  - DIRECTOR — LIVE DANGER
  - ▶ ON AIR
  - WHY: danger 0.62 (+0.21)
  - ~70s before the goal
  - PITCHSWITCH

## Creative Direction
- Tone preset: cinematic
- Creative direction: live sports-broadcast trailer / control-room sizzle
- Interpretation: big condensed-uppercase Oswald type, dramatic slams and holds
  (not chaotic cuts), red reserved for danger + the cut, gold for ON AIR.
- Angle: a broadcast control room played as a sports trailer, built around one
  before/after turn then proven with the actual on-screen danger differential.
- Hook: black pitch, "TWO GAMES. ONE SCREEN. SAME KICKOFF." stacking in.
- Outro / punchline: wordmark PITCHSWITCH — "Like RedZone. It just gets you there first."
- Avoid: generic SaaS language; abstract filler visuals; light-grey dashboard
  chrome; any second accent competing with red + gold; visual redesign of the brand.

## Visual Identity
- Background: `#0d1f12` (pitch black); pitch surface `#15311a`
- Text: `#e8efe9`; muted `#9fb0c4`; WHY amber `#ffe08a`
- Accent: `#ff3b3b` (danger red); gold `#ffd400`
- Danger ramp: `#4da6ff` → `#ffcc00` → `#ff3b3b`
- Display font: Oswald (500/600/700), uppercase, letter-spacing 0.5px
- Body font: system sans-serif
- Visual references: scorebug, DIRECTOR LIVE-DANGER panel, red switch banner +
  amber WHY line, faint pitch mowing stripes, red danger glow.

## Storyboard
Use `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook — 4.0s — "TWO GAMES. ONE SCREEN. SAME KICKOFF." stacking in on the beat grid.
2. The turn — 4.0s — "RedZone … AFTER" then "PitchSwitch … BEFORE" (BEFORE slams red, // beat 5.80).
3. Live danger — 5.0s — DIRECTOR panel; KOR bar climbs the ramp + overtakes; gold ON AIR snaps (// beat 8.96).
4. The cut + proof — 4.5s — red switch banner slams (// beat 12.65) + amber WHY line + "~70s" count-up.
5. Tech + wordmark — 3.5s — Granite/Docling/Watson chips, then PITCHSWITCH wordmark slams (// beat 17.91), cut to black.

## Audio
- Audio role: cinematic support — driving confident bed, restrained.
- Audio arc: establish → lift into BEFORE slam → rising danger → peak on the cut
  → duck under the ~70s proof → ring under wordmark → fade.
- Music: `happy-beats-business-moves-vol-11-by-ende-dot-app.mp3` (114.84 BPM).
- Music treatment: full bed from 0s; small duck under the WHY/70 read; ring then
  short fade-out under the wordmark.
- Music cue guidance: bundled preset
  `cues/happy-beats-business-moves-vol-11-...music-cues.json`. Strong cues 1.60,
  3.70, 5.80, 8.96, 12.65, 17.91, 22.65. Lock 4: BEFORE→5.80, ON AIR→8.96,
  banner→12.65, wordmark→17.91. Hook lines snap to grid 1.60/2.65/3.70.
- Audio-reactive treatment: subtle — danger glow + ON AIR/banner presence breathe
  with RMS/bass. No waveform/equalizer visuals.
- Audio-coupled moments:
  - Hook lines — beat-aligned reveals + soft ticks
  - ON AIR snap — UI tick on cue
  - Switch banner — heavy impact slam
  - ~70 count-up — ticks; music ducks
  - Wordmark — clean announcement hit, then fade
- SFX selection guidance: sparse, motion-matched. interface/ui ticks for the
  danger climb + ON AIR; impact for the banner slam; a clean announcement-style
  hit for the wordmark. Never stack SFX.
- SFX analysis guidance: use `assets/sfx/sfx-analysis.md`; prefer low
  high-frequency-risk files for repeated ticks.
- Exact SFX choice: choose filenames/timestamps after the animation exists.
- Audio files: copy chosen music + SFX into `brag-output/composition/assets/`.

## Hyperframes Instructions
Use the current hyperframes skill suite (core/animation/creative/media/cli).
Single paused GSAP timeline, standalone root, deterministic. Show the real
DIRECTOR panel + switch banner. Keep all text readable (cinematic holds). Lint +
validate + inspect before render.
