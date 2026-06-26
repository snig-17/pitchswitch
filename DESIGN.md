# PitchSwitch — Design System

> Source of truth for the PitchSwitch visual language. This codifies the design
> that already ships; change the app and this doc in the same commit.

## The memorable thing

**A broadcast control room that cuts you to the goal before it happens.**

Not a dashboard, not an analytics tool. The product should feel like the gallery
of a live TV broadcast: dark, urgent, in-the-moment. Every visual decision serves
that feeling. If something makes it look like a SaaS dashboard (light grey, card
grids, soft pastel charts), it is wrong.

## Principles

1. **Dark by default.** The page chrome matches the pitch so the live canvas blends
   into the page instead of floating in light-grey Streamlit. The screen is a feed,
   not a document.
2. **Red means now.** Red is reserved for danger and the live cut. It is never
   decorative. When the viewer sees red, something is happening.
3. **The pitch is the hero.** Type, panels, and captions are broadcast overlays on
   top of the feed — lower-thirds and scorebugs, not page furniture. Overlays are
   semi-transparent so the pitch reads through them.
4. **Condensed, uppercase, sporty.** Display type is Oswald (the condensed face used
   in real sports lower-thirds). Headings shout; body stays quiet.
5. **Show the why.** When the Director cuts, the screen explains itself (danger bars +
   differential). The design makes the AI's decision legible, not magic.

## Color

Chrome tokens live in `.streamlit/config.toml`; canvas tokens are constants in
`core/livefeed.py` and `core/metrica.py` (`TEAM_KITS`). Keep them in sync with this.

### Core palette

| Token | Hex | Role |
|-------|-----|------|
| Pitch black | `#0d1f12` | Page background + canvas outer frame |
| Pitch green | `#15311a` | Sidebar, widgets, the pitch surface |
| Danger red | `#ff3b3b` | Primary. Danger, ON AIR, the live cut. Never decorative |
| Text | `#e8efe9` | Primary body text on dark |
| Pitch line | `#cfe8d0` | Pitch markings (lines, circles, boxes) |

### Accent + state

| Token | Hex | Role |
|-------|-----|------|
| Broadcast gold | `#ffd400` | ON AIR marker, Coach band, "your team" highlight |
| Caution | `#ffcc00` | Danger bar, mid danger (0.3–0.5) |
| Calm blue | `#4da6ff` | Danger bar, low danger (<0.3); default home kit |
| WHY amber | `#ffe08a` | The "WHY: danger +Δ" switch-explainer line |
| Muted | `#9fb0c4` | Off-air / secondary labels in the danger panel |
| Header green | `#9fdcae` | Panel section labels ("DIRECTOR — LIVE DANGER") |

### Danger ramp (the one chart color rule)

Danger 0→1 maps to **calm blue → caution yellow → danger red**:

```
danger < 0.3   →  #4da6ff   (calm blue)
0.3 ≤ d < 0.5  →  #ffcc00   (caution)
danger ≥ 0.5   →  #ff3b3b   (danger red)
```

Used by the live-danger bars and the scorebug danger readout. This is the only
place color encodes data — keep it consistent everywhere danger is shown.

### Team kits (national colours)

Avatars use real national kit colours so they read as the actual teams
(`TEAM_KITS` in `core/metrica.py`): France `#1e3a8a`, Argentina `#75aadb`,
South Korea `#c8102e`, Germany `#e8e8e8`, Spain `#c60b1e`, Portugal `#006600`,
Brazil `#fde000`, England `#f4f4f4`. Default kits: home `#4da6ff`, away `#ff8c42`.
Shorts `#26324a`, skin `#f0c8a0`.

## Typography

Two faces, clear jobs:

- **Display — [Oswald](https://fonts.google.com/specimen/Oswald)** (weights 500/600/700).
  All page headings (`h1`–`h3`), uppercase, letter-spacing `0.5px`. This is the
  broadcast-graphic voice. Loaded via Google Fonts in `app.py`.
- **Feed — system sans-serif.** The canvas overlays use the system `sans-serif`
  stack for speed and crispness at small sizes on the live feed.

### Scale (canvas overlays, 900×560 frame)

| Element | Size / weight |
|---------|---------------|
| Scorebug match label | bold 16px |
| Switch banner (Granite call) | bold 15px |
| Play-by-play caption | 14px |
| Clock / Coach body | 13px |
| WHY differential / Coach label | bold 12px |
| Danger-panel match labels | 11px (bold when on air) |
| Section header ("DIRECTOR — LIVE DANGER") | bold 10px |
| ON AIR marker | bold 9px |
| Avatar jersey number | bold 6px |

Rule: bold + larger = "happening now" (the cut, the danger). Lighter + smaller =
ambient context (clock, off-air labels).

## Component vocabulary

The broadcast is built from a fixed set of overlays drawn on the canvas
(`core/livefeed.py`, `_BROADCAST_TEMPLATE`). Treat these as the component library:

- **Pitch** — green surface, faint mowing stripes (`rgba(255,255,255,0.025)`),
  `#cfe8d0` markings. The stage everything sits on.
- **Avatars** — shirt + sleeves + shorts + head + jersey number, in national kit
  colours, with a ground shadow (`rgba(0,0,0,0.35)`). The ball is white, black-outlined.
- **Danger glow** — red gradient (`rgba(255,59,59,…)`) over the attacking third when
  danger climbs. Intensity tracks the danger value.
- **Scorebug** (top-left) — match label + `▶ LIVE` + clock. Always present.
- **DIRECTOR — LIVE DANGER panel** (top-right) — one bar per match on the danger
  ramp, on-air match highlighted with a gold `▶ ON AIR` marker. Background
  `rgba(8,20,12,0.82)`. This is the differentiator made visible.
- **Switch banner** (upper third, on a cut, ~4.5s) — red band `rgba(255,59,59,0.88)`,
  the Granite call in white, then the amber **WHY: danger X (+Δ)** line.
- **Coach band** (lower third, on a rule event, ~7s) — dark band `rgba(10,25,15,0.92)`
  with a gold left edge + `COACH` label, plain-language rule text in `#eef`.
- **Play-by-play caption** (bottom) — `rgba(0,0,0,0.6)` band, white text.

## Motion

- The feed runs its own **60fps** `requestAnimationFrame` loop (self-contained, no
  Streamlit reruns). Players interpolate between tracking frames — glide, never teleport.
- **Switches** dwell (~5s minimum) so the feed never thrashes between matches. The
  banner shows for ~4.5s after a cut; the Coach band ~7s after a rule event.
- Danger glow and bar fills update continuously with the danger value. No spinners,
  no skeleton states — it's a live feed, it's always moving.

## Do / Don't

**Do**
- Keep red for danger and the live cut only.
- Keep overlays semi-transparent so the pitch reads through.
- Use Oswald uppercase for headings; system sans for the feed.
- Encode danger with the blue→yellow→red ramp, everywhere, identically.

**Don't**
- No light-grey dashboard chrome, card grids, or pastel charts.
- No decorative gradients, blobs, or drop shadows beyond the avatar ground shadow.
- No second accent colour competing with red and gold.
- Don't put non-danger information in red.

## Accessibility

- Body text `#e8efe9` on `#0d1f12` is ~14:1 contrast (AAA).
- Danger is never encoded by colour alone — it always carries a number (the bar value,
  the `WHY: danger 0.62` readout), so colour-blind viewers get the magnitude.
- Spoken layers (Granite commentary, Coach) are optional and tap-to-enable; the feed
  is fully usable muted.

## Where it lives

- Chrome theme: `.streamlit/config.toml`
- Canvas tokens + components: `core/livefeed.py`
- Team kit colours: `core/metrica.py` (`TEAM_KITS`)
- Display font load + heading CSS: `app.py`
