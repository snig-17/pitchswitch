# PitchSwitch

> Like NFL RedZone, but for soccer, and it switches you *before* the goal instead of after.

## The Problem

In the World Cup group stage, the final round of matches in each group kicks off at the exact same time. This isn't an accident. FIFA made it a rule after West Germany and Austria played out a result in 1982 that knocked Algeria out, so now both games in a group run simultaneously and nobody can play to a convenient scoreline.

The catch is you can only watch one screen. Take the 2018 group finale: Germany were playing South Korea while Mexico played Sweden at the same moment, and the two results were tangled together. Pick the Mexico game and you miss South Korea knocking the defending champions out in stoppage time. It happened again in 2022, Japan vs Spain running alongside Germany vs Costa Rica, with the qualifying table flipping three or four times in the last ten minutes across two pitches you couldn't watch at once.

Broadcasters don't really fix this. NFL RedZone works because American football stops between plays and scores constantly, so there are clean moments to cut to. Soccer is the opposite. It flows nonstop and barely scores, so a tool that just switches you to a goal after it goes in is useless, because it shows you the thing you already missed. And smaller nations get almost no airtime at all, even when theirs is the game worth watching.

## The Solution

PitchSwitch watches every match at once and tries to get you to the action *before* it happens, not after.

It gives each match a live danger score from the play-by-play data, things like balls carried into the final third, pressure in the box, shots, corners and penalties. The key signal is how fast that danger is rising, which is what catches a game about to boil over instead of one that already has. On the test matches it flagged goals with about 70 seconds of warning on average.

When two matches heat up at the same time and the call isn't obvious, IBM Granite reads the full state of all of them, decides where to send you, and explains it in a line a TV presenter would actually say. Those lines are grounded in real team context parsed with IBM Docling, so the narration knows Son drives Korea's press and Mbappe is France's outlet, not just the score.

You can name your teams too, including the small nations broadcasters ignore, and it leans the switching toward them. The main screen is a live tactical view of whatever match you've been cut to, and it jumps between games the way a director in a control room would.

## Technical Approach

```
statsbombpy (World Cup event data)
        |
  replay.py        asyncio virtual clock, concurrent matches
        |
  heat.py          rolling 90s danger score + rising-danger derivative
        |
  director.py      heuristic switch + IBM Granite reasoning on close calls
        |        \
        |         grounding.py   IBM Docling parses team primers -> KB
        |         personalize.py multi-team + small-nation bias
        |
  pitchcam.py      mplsoccer live tactical feed
        |
  app.py           Streamlit UI: broadcast feed, danger ticker, accuracy
```

LLM provider is swappable (`providers/llm.py`): Granite runs locally via Ollama, or on IBM watsonx.ai / Replicate in the cloud.

### How the Anticipation Model Works

Each match maintains a **danger score** (0.0 to 1.0) computed from a rolling 90-second window of events:
- Carries into the final third
- Pressure events in the opponent's half
- Passes into the penalty area
- Shot xG accumulation
- Set-piece indicators (penalty, corner, free kick in range)
- Late-game tight-scoreline multiplier (1.5x in last 15 minutes)

The **forward-looking signal** is the time-based derivative: how fast danger is climbing. A sharp rise triggers the "about to ignite" flag even before the absolute danger peaks. This is what enables switching before the moment, not after.

### IBM Granite Integration

IBM Granite serves as the reasoning engine for ambiguous switching decisions. When two or more matches are close in danger (within 0.15), Granite evaluates the structured match state and decides which match deserves the viewer's attention, generating a natural-language narration: "Switch to Brazil-Croatia, penalty about to be taken after VAR review."

For clear winners (one match far above the others), a heuristic handles the switch instantly. Granite narration arrives asynchronously so the switch is never delayed by LLM latency.

### Docling Grounding

Nation-specific primers (team history, key players, tournament context) in `data/primers/*.md` are parsed via IBM Docling into a local knowledge base (`core/grounding.py`). When the Director builds a Granite prompt, it injects the relevant teams' facts so the narration is grounded in real context: "Switch to South Korea vs Germany - Son Heung-min is leading the Taegeuk Warriors' famous never-say-die press."

Docling is optional: if the package isn't installed the app falls back to reading the markdown primers directly, so grounding works either way. The KB loads in a background thread at startup, so the ~6s parse never blocks the replay.

## Model Accuracy

Measured across the three demo matches (15 goals) with `scripts/calibrate.py`, using a 120-second lead window:

| Metric | Value |
|--------|-------|
| Dangerous moments predicted | 7/15 (47%) |
| Average lead time before event | 71s |
| False positive rate | 42% |

**The headline is lead time: ~71 seconds of warning before a goal.** That's the whole point — switching you *before* the moment, not after.

### Methodology

`python scripts/calibrate.py [--window SECONDS]` replays each match through the heat model and scores the switch signal:

- **Ground truth** = goals; shots (goals + attempts) form the broader "dangerous moment" set used for false-positive scoring, since anticipating a shot or save is also a valid switch.
- **Predicted (recall)**: a goal is predicted if a switch fired for that match in the window *strictly before* the goal — measuring anticipation, not reaction to the goal's own xG spike.
- **False positive**: a switch with no shot/goal within the window after it.

Sensitivity to the window (the model degrades gracefully, not cherry-picked):

| Window | Predicted | Avg lead | False positive |
|--------|-----------|----------|----------------|
| 90s | 4/15 (27%) | 44s | 49% |
| 120s | 7/15 (47%) | 71s | 42% |
| 180s | 9/15 (60%) | 98s | 27% |

Soccer is low-scoring and many goals come from quick counters with little buildup, so perfect recall isn't the goal — surfacing the matches that are *heating up*, early, is. The false-positive rate reflects that most flagged danger (sustained pressure, corners) is genuine even when it doesn't produce a shot within the window.

## Personalization

Select your favourite team(s), including small nations that broadcasters ignore. PitchSwitch biases switching toward their matches: "Your team Cape Verde has a corner in a 0-0, get in."

## Judging Criteria Mapping

| Criterion | Feature | Evidence |
|-----------|---------|----------|
| **Technical Execution** | Anticipation model + Granite reasoning + Docling RAG | Rolling danger score with forward-looking derivative; Granite reasons over structured state; Docling grounds narration |
| **Innovation** | Multi-match anticipation + small-nation personalization | Uncontested: no tool predicts and switches pre-event; small-nation bias is unique |
| **Challenge Fit** | "AI Inside the Match" + World Cup specific | Dead-on theme; structurally WC-specific (simultaneous group-stage games) |
| **Implementation & Feasibility** | Free data, swappable LLM, clear product path | StatsBomb free data; provider interface for watsonx/Replicate/Ollama; 10x = broadcast control room API |

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/snig-17/pitchswitch.git
cd pitchswitch
pip install -r requirements.txt

# 2. Configure LLM provider
cp .env.example .env
# Edit .env with your provider credentials

# 3. Run
streamlit run app.py
```

## Future Work

- Connect to real-time match feeds (Opta, Stats Perform) for live World Cup 2026
- Broadcast control room API: feed anticipation signals to human directors
- Social watch parties with combined team preferences
- Mobile companion app

## Built With

- **IBM Granite** (core AI reasoning + narration)
- **IBM Docling** (document parsing for team primers)
- **StatsBomb** open data (real World Cup match events)
- **Streamlit** (dashboard UI)
- **Claude Code** (development tool)
