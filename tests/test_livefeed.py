"""Live feed: script-context escaping (the LLM trust boundary)."""

from core.livefeed import _safe_embed, build_broadcast
from core.metrica import Frame


def test_safe_embed_neutralizes_script_breakout():
    # A "</script>" in any embedded string must not close the <script> tag.
    out = _safe_embed({"x": "</script><script>alert(1)</script>"})
    assert "</script>" not in out
    assert "<script>" not in out
    assert "\\u003c" in out


def test_safe_embed_escapes_angle_brackets():
    assert _safe_embed({"a": "<b>"}) == '{"a": "\\u003cb\\u003e"}'


def test_build_broadcast_escapes_llm_narration():
    # LLM narration is untrusted; a script-breakout payload must be escaped
    # before it lands in the inline <script> data blob.
    payload = "</script><img src=x onerror=alert(1)>"
    bd = {
        "games": [{
            "label": "A vs B", "home": "A", "away": "B",
            "narration": payload, "danger": [0.1], "captions": [],
            "coach": [],
            "frames": [Frame(t=0.0, ball=(0.5, 0.5), home=[], away=[])],
        }],
        "schedule": [[0.0, 0]],
    }
    html = build_broadcast(bd)
    assert payload not in html                 # raw payload never reaches the DOM
    assert "\\u003c/script\\u003e\\u003cimg" in html  # it's \\u-escaped instead


def test_build_broadcast_tolerates_missing_captions():
    # A game dict without a 'captions' key must build (gd.get default), not KeyError.
    bd = {
        "games": [{
            "label": "A vs B", "home": "A", "away": "B",
            "narration": "go", "danger": [0.1], "coach": [],
            "frames": [Frame(t=0.0, ball=(0.5, 0.5), home=[], away=[])],
        }],
        "schedule": [[0.0, 0]],
    }
    html = build_broadcast(bd)
    assert "bc" in html  # canvas id present — it rendered


def test_build_broadcast_embeds_goals_and_overlay():
    # A goal in the data must be embedded, and the template must carry the big
    # GOAL overlay that renders it on screen.
    bd = {
        "games": [{
            "label": "A vs B", "home": "A", "away": "B",
            "narration": "go", "danger": [0.1], "captions": [], "coach": [],
            "goals": [[12.0, "h"]],
            "frames": [Frame(t=0.0, ball=(0.5, 0.5), home=[], away=[])],
        }],
        "schedule": [[0.0, 0]],
    }
    html = build_broadcast(bd)
    assert '[12.0, "h"]' in html        # goal data embedded
    assert "GOAL" in html               # overlay text present in the template


def test_build_broadcast_tolerates_missing_goals():
    # A game dict without a 'goals' key must build (gd.get default), not KeyError.
    bd = {
        "games": [{
            "label": "A vs B", "home": "A", "away": "B",
            "narration": "go", "danger": [0.1], "captions": [], "coach": [],
            "frames": [Frame(t=0.0, ball=(0.5, 0.5), home=[], away=[])],
        }],
        "schedule": [[0.0, 0]],
    }
    html = build_broadcast(bd)
    assert "bc" in html
