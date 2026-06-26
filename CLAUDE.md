# PitchSwitch — agent notes

AI multi-match whip-around for the World Cup. See `README.md` for the product
and `DESIGN.md` for the visual system.

Two danger engines (don't conflate them): `core/heat.py` (StatsBomb events,
calibrated, backs the README accuracy numbers via `scripts/calibrate.py`) and
`core/metrica.frame_danger` (tracking, used by the live broadcast). The live
feed decides switches by a deterministic danger differential; Granite writes
the narration + Coach, it does not pick the cut.

## Testing

Run: `pytest` (deps: `pip install -r requirements.txt statsbombpy pytest`).
Tests live in `tests/`, config in `pytest.ini`. See `TESTING.md` for details.
CI: `.github/workflows/test.yml` runs the suite on every push / PR.

Expectations:
- 100% coverage is the goal — tests make vibe coding safe.
- New function → write a corresponding test.
- Bug fix → write a regression test that fails without the fix.
- New error handling → test that triggers the error.
- New conditional (if/else) → test both paths.
- Never commit code that makes existing tests fail.
