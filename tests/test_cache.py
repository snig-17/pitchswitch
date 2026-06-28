"""Broadcast cache loader: trusts a good cache, degrades on a bad one."""

import json

from core.cache import load_cached_broadcast


def _write(tmp_path, payload):
    p = tmp_path / "broadcast.json"
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    return p


def test_valid_cache_returns_html_and_tuple_schedule(tmp_path):
    p = _write(tmp_path, {"html": "<canvas>", "schedule": [[0.0, "Kick off"], [12.5, "Cut!"]]})
    html, schedule = load_cached_broadcast(p)
    assert html == "<canvas>"
    assert schedule == [(0.0, "Kick off"), (12.5, "Cut!")]
    assert all(isinstance(row, tuple) for row in schedule)


def test_missing_file_returns_none(tmp_path):
    assert load_cached_broadcast(tmp_path / "nope.json") is None


def test_invalid_json_returns_none(tmp_path):
    assert load_cached_broadcast(_write(tmp_path, "{not json")) is None


def test_missing_key_returns_none(tmp_path):
    assert load_cached_broadcast(_write(tmp_path, {"html": "<canvas>"})) is None
    assert load_cached_broadcast(_write(tmp_path, {"schedule": []})) is None


def test_wrong_top_level_types_return_none(tmp_path):
    assert load_cached_broadcast(_write(tmp_path, {"html": 123, "schedule": []})) is None
    assert load_cached_broadcast(_write(tmp_path, {"html": "<c>", "schedule": "nope"})) is None


def test_malformed_schedule_row_returns_none(tmp_path):
    # The whole point of the helper: a valid-JSON cache with bad rows must NOT
    # slip through to crash `for t, narr in schedule` / `t // 60` downstream.
    bad_rows = [
        [[0.0]],                       # 1-element row -> unpack ValueError downstream
        [[0.0, "ok", "extra"]],        # 3-element row
        [["3:00", "narr"]],            # non-numeric t -> t // 60 TypeError downstream
        [[True, "narr"]],              # bool t is not a real timestamp
        ["just a string"],             # row not a sequence pair
    ]
    for rows in bad_rows:
        p = _write(tmp_path, {"html": "<c>", "schedule": rows})
        assert load_cached_broadcast(p) is None, rows


def test_empty_schedule_is_valid(tmp_path):
    html, schedule = load_cached_broadcast(_write(tmp_path, {"html": "<c>", "schedule": []}))
    assert html == "<c>" and schedule == []
