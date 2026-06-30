# PitchSwitch

> Like NFL RedZone, but for soccer — and it switches you *before* the goal, not after.

**▶ [Live demo](https://pitchswitch-g5cvhbdq89gvdfxmb4awmn.streamlit.app)** — one AI feed that cuts to whichever World Cup match is heating up, shows you *why*, and calls every switch out loud. Pick a team, hit Start.

## The problem

In the World Cup group stage, the last two games in every group kick off **at the same time** — a rule FIFA introduced in 1982 so nobody can play to a convenient scoreline. You can only watch one screen, and the goal that decides the group always seems to land on the other one. In 2018, fans on Mexico–Sweden missed South Korea knocking the defending champions out in stoppage time.

Broadcasters don't fix this. NFL RedZone works because American football stops between plays and scores constantly. Soccer is the opposite — it flows nonstop and barely scores, so switching you to a goal *after* it happens just shows you what you already missed. And smaller nations get almost no airtime, even when theirs is the game worth watching.

## The solution

PitchSwitch watches every match at once and gets you to the action **before** it happens.

- **A live danger score** for each match from play-by-play data — carries into the final third, pressure in the box, shots, set pieces. The key signal is *how fast danger is rising*, which catches a game about to boil over instead of one that already has. On the test matches it flagged goals **~71 seconds early** on average.
- **The Director cuts** to whichever match's danger is pulling ahead — and shows you the on-screen danger bars and the differential that triggered the cut.
- **IBM Granite calls each switch** in a line a presenter would actually say — *"Switch to Brazil–Croatia, penalty about to be taken after VAR"* — grounded in real team context, so it knows Son drives Korea's press.
- **Coach** explains the game for new fans: when a penalty, card, or goal happens, it states the rule in one plain sentence — grounded on the actual Laws of the Game, never guessing at referee judgment.
- **Pick your team** — including the small nations broadcasters ignore — and the switching leans toward them.

The main screen is **one live broadcast over real 25fps player tracking** (all 22 players in national kits), narrated out loud in a British commentator voice. It plays like a control room, not a dashboard.

## AI / technical approach

```
Metrica tracking (25fps, 22 players + ball)        StatsBomb events
        │                                                 │
  per-frame danger + differential          rolling danger + rising-danger derivative
        │  (deterministic switch schedule)        (anticipation model + calibration)
        └────────────────────┬───────────────────────────┘
                             ▼
     IBM Granite narration, grounded by IBM Docling team + rule primers
                             ▼
     IBM Watson Text to Speech  →  Streamlit live feed (HTML5 canvas)
```

**Three IBM technologies:** **Granite** (switch narration + Coach reasoning), **Docling** (grounds Granite in team primers + the Laws of the Game), **Watson Text to Speech** (spoken commentary). The LLM provider is swappable (`providers/llm.py`) — Granite runs locally via Ollama, or on watsonx.ai / Replicate.

The switch itself is decided **deterministically** by the danger differential you see on screen, so a cut is never blocked on LLM latency — Granite writes the *call*, it doesn't pick it. Danger is a rolling 90-second window of events; the forward-looking signal is its **time derivative** — how fast danger is climbing — which is what enables switching *before* the moment, not after.

Accuracy on real data (StatsBomb open events, `scripts/calibrate.py`, 120s window, 15 goals):

| Predicted | Avg lead time | False positive |
|:--:|:--:|:--:|
| 7/15 (47%) | **71s** | 42% |

The headline is lead time: ~71 seconds of warning before a goal. Soccer is low-scoring, so perfect recall isn't the point — surfacing the matches heating up, *early*, is. Full methodology and window sensitivity are in [ARCHITECTURE.md](ARCHITECTURE.md).

The tracking feed uses Metrica's open data mapped to World Cup fixtures — an illustrative stand-in for a licensed broadcast feed, since FIFA blocks real match video from embedding.

## Why it matters for soccer & the FIFA World Cup

- **It's structurally a World Cup problem.** Simultaneous final-round kickoffs exist *only* because of FIFA's group-stage rule — this isn't a generic highlights tool, it solves something specific to the tournament.
- **It fits how soccer actually behaves.** A flowing, low-scoring sport defeats after-the-fact switching; anticipation is the only thing that helps, and that's the whole model.
- **2026 is in North America** — millions of first-time viewers who don't know offside from a throw-in. Coach makes the tournament watchable for them.
- **Small nations get a stage.** Personalization biases the feed toward the teams broadcasters skip — *"Your team Cape Verde has a corner in a 0-0, get in."*

## Quick start

No install needed — open the **[live demo](https://pitchswitch-g5cvhbdq89gvdfxmb4awmn.streamlit.app)**. To run locally (the broadcast cache is committed, so no data download, no Ollama, no API keys):

```bash
git clone https://github.com/snig-17/pitchswitch.git
cd pitchswitch
pip install -r requirements.txt
streamlit run app.py          # pick a team, hit Start
```

Rebuilding the cache or reproducing the accuracy numbers is the heavier path (ML deps + local Granite) — see [ARCHITECTURE.md](ARCHITECTURE.md).

## Built with

IBM **Granite** · IBM **Docling** · IBM **Watson Text to Speech** · **Metrica** open tracking · **StatsBomb** open events · **Streamlit** + HTML5 canvas

## More

[ARCHITECTURE.md](ARCHITECTURE.md) · [DESIGN.md](DESIGN.md) · [TESTING.md](TESTING.md) (`pytest`, green in CI) · [CHANGELOG.md](CHANGELOG.md) · MIT [LICENSE](LICENSE)
