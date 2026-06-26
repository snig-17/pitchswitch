# Changelog

All notable changes to PitchSwitch are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project is a hackathon
submission, so versions are milestones rather than published releases.

## [0.1.0] — 2026-06-26

First complete, hosted submission for the IBM SkillsBuild AI Builders Challenge.
An AI multi-match whip-around for the World Cup: the Director cuts you to whichever
match is about to ignite, before the goal, and explains why.

### Added
- **Anticipation model** (`core/heat.py`): rolling danger score with a forward-looking
  derivative, calibrated on StatsBomb open data (`scripts/calibrate.py`) — ~71s average
  lead time before a goal at the 120s window.
- **Live broadcast feed** (`core/metrica.py`, `core/livefeed.py`): one self-contained
  HTML5 canvas over real 25fps Metrica tracking — 22 numbered national-kit avatars, the
  ball, danger glow, and client-side switching between matches.
- **The switch-explainer** — a `DIRECTOR — LIVE DANGER` panel (a bar per match, on-air
  highlighted) and a `WHY: danger +Δ` line on every cut, so the Director's decision is
  visible, not magic. Mirrored on the pre-Start landing as a tale-of-the-tape teaser.
- **Coach** (`core/coach.py`): explainable-AI rules companion — IBM Granite generates a
  one-sentence rule explanation for penalties/fouls/cards/corners/goals, grounded on the
  Laws of the Game parsed by IBM Docling, with vetted canonical fallbacks.
- **Three IBM technologies**: Granite (switch narration + Coach), Docling (team-primer +
  Laws grounding), Watson Text to Speech (spoken commentary).
- **Small-nation personalization** (`core/personalize.py`): favourite-team and
  small-nation switching bias.
- **Self-contained broadcast cache** so the hosted app runs with no Ollama, data, or keys.
- **Test suite + CI**: 18 pytest unit tests over the live path + a GitHub Actions workflow.
- **Docs**: `DESIGN.md` (broadcast design system), `TESTING.md`, `CLAUDE.md`, `LICENSE` (MIT).

### Changed
- README honesty pass: documented that the live feed decides switches deterministically
  by the danger differential (Granite writes the call, it doesn't pick the cut); the
  calibrated event-model Director backs the offline accuracy numbers.
- Quick Start split into a 30-second runtime path (cache committed, no data/Ollama) vs an
  optional rebuild/calibration path.
- Landing redesigned ("tale of the tape") and the broadcast theme codified in `DESIGN.md`.

### Fixed
- Heat-model derivative off-by-one: it compared danger two events back instead of one,
  lagging and roughly doubling the rising-danger signal. Now a true one-step slope, with
  a regression test (`tests/test_heat.py`). Calibration numbers unchanged.
- Hardened the canvas embed: LLM/caption text is `\u`-escaped before going into the
  `<script>` block, closing a script-context breakout.
- Hardened the hosted fallback: `warmup()` moved inside the build try so an unseeded
  favourite always degrades to the default broadcast.

### Removed
- Dead code: `core/pitchcam.py`, `metrica.build_broadcast`, `replay.replay_concurrent`,
  and the unused `PITCH_LENGTH` constant.
