# PitchSwitch

**AI-powered multi-match whip-around companion for the FIFA World Cup 2026.**

During the World Cup group stage, the final round of matches kicks off simultaneously. Fans watching one match miss the buildup to a goal in another. PitchSwitch watches all live matches at once and switches you to the match that's about to produce something, anticipating the moment before it happens, not reacting after.

## The Problem

NFL RedZone works because American football is discrete: plays stop, scoring is frequent, clean cut-points exist. Soccer is continuous and low-scoring. A naive "switch when a goal happens" tool would sit idle for 40 minutes and then cut you in after the goal you wanted to see.

PitchSwitch solves this with **anticipation**: detecting that a dangerous moment is building (sustained final-third pressure, rising xG, a penalty about to be taken) and switching you there seconds before the shot, save, or goal.

## Technical Approach

```
statsbombpy (WC data)
        |
  replay.py (asyncio, virtual clock, concurrent matches)
        |
  heat.py (rolling 90s danger score, time-based derivative)
        |
  director.py (heuristic + IBM Granite reasoning)
        |
  personalize.py (favourite team bias)
        |
  app.py (Streamlit dashboard + Danger Ticker)
```

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

<!-- TODO: Fill after Phase 2 calibration -->

| Metric | Value |
|--------|-------|
| Dangerous moments predicted | --/-- |
| Average lead time before event | --s |
| False positive rate | --% |

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
git clone https://github.com/YOUR_USERNAME/pitchswitch.git
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
