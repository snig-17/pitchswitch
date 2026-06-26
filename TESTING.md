# Testing

100% test coverage is the key to great vibe coding. Tests let you move fast,
trust your instincts, and ship with confidence — without them, vibe coding is
just yolo coding. With tests, it's a superpower.

## Framework

[pytest](https://docs.pytest.org/) (+ `pytest-cov`). Tests live in `tests/`,
config in `pytest.ini`.

## How to run

```bash
pip install -r requirements.txt statsbombpy pytest   # slim test deps
pytest                                               # runs tests/
pytest --cov=core --cov=providers                    # with coverage
```

CI runs the same on every push / PR (`.github/workflows/test.yml`).

## What's covered

The suite targets the **live broadcast path** (no browser, no LLM, no network):

| File | Unit | Asserts |
|------|------|---------|
| `test_metrica.py` | `frame_danger`, `_jersey` | danger 0 at midfield / no ball; rises when deep; clustering near goal raises it; clamps to [0,1] |
| `test_personalize.py` | `Personalizer` | no favourite = neutral; fav bias vs stronger small-nation bias; multi-team substring match; biased danger caps at 1.0 |
| `test_coach.py` | `classify`, `explain` | event→category mapping; noise ignored; canonical fallback when no LLM; every category cites a Law |
| `test_heat.py` | `MatchHeat.update` | **regression:** the rising-danger derivative is a true one-step slope (`d_now - d_prev`), not the two-event lag a prior bug produced |

## Layers

- **Unit** — pure functions in `core/` and `providers/`. The current suite.
- **Integration** — the StatsBomb pipeline (`scripts/calibrate.py`) and the
  Metrica broadcast build are exercised by running them with real data; not yet
  automated (they need the gitignored datasets).
- **E2E / browser** — the Streamlit UI; verified manually via `/qa` + `browse`.

## Conventions

- One behaviour per test, named `test_<behaviour>`.
- Assert what the code *does* (real values), never `assert x is not None`.
- No secrets, API keys, or network in tests. Build inputs in-process
  (e.g. `MatchEvent(...)`, `Frame(...)`), don't load datasets.
- When you fix a bug, add a regression test that fails without the fix
  (see `test_heat.py` for the pattern).
