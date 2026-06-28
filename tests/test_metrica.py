"""Metrica tracking helpers: per-frame danger proxy + jersey parsing."""

from core.metrica import Frame, frame_danger, _jersey, _narrate


def _frame(ball, home=None, away=None):
    return Frame(t=0.0, ball=ball, home=home or [], away=away or [])


def test_danger_zero_at_midfield():
    # Ball at the centre circle is not dangerous.
    assert frame_danger(_frame((0.5, 0.5))) == 0.0


def test_danger_zero_when_ball_missing():
    assert frame_danger(_frame(None)) == 0.0


def test_danger_rises_when_ball_is_deep():
    deep = frame_danger(_frame((0.95, 0.5)))
    assert deep > 0.0
    # deeper than the final-third threshold (0.60) is required for any danger
    assert frame_danger(_frame((0.62, 0.5))) < deep


def test_clustering_near_goal_increases_danger():
    bare = frame_danger(_frame((0.95, 0.5)))
    crowded = frame_danger(_frame(
        (0.95, 0.5),
        away=[(0.95, 0.5, "1"), (0.95, 0.4, "2"), (0.96, 0.6, "3")],
    ))
    assert crowded > bare


def test_danger_never_exceeds_one():
    packed = frame_danger(_frame(
        (0.99, 0.5),
        home=[(0.99, 0.5, str(i)) for i in range(11)],
        away=[(0.99, 0.5, str(i)) for i in range(11)],
    ))
    assert 0.0 <= packed <= 1.0


def test_jersey_parsing():
    assert _jersey("Player11") == "11"
    assert _jersey("Ball") == "?"


class _RaisingProvider:
    """A warm provider whose generate() raises (timeout, connection drop)."""
    def is_warm(self):
        return True

    def generate(self, *a, **k):
        raise RuntimeError("llm down")


def test_narrate_degrades_to_template_when_provider_raises():
    # A raising LLM must not propagate — narration degrades to the template call.
    out = _narrate("France", "Argentina", 0.8, "", None, _RaisingProvider())
    assert "Cut to France vs Argentina" in out
