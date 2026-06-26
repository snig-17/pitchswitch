"""Heat model derivative — regression for the off-by-one fix.

The rising-danger derivative must be a true one-step slope:
(danger_now - danger_prev_event) / elapsed. A prior bug compared against the
danger from TWO events ago, lagging and roughly doubling the signal.
"""

from core.heat import create_heat, MIN_DERIVATIVE_EVENTS
from core.replay import MatchEvent


def _shot(match_seconds, xg=0.1):
    return MatchEvent(
        match_id=1, match_label="A vs B", event_id="e", event_type="Shot",
        minute=int(match_seconds // 60), second=int(match_seconds % 60),
        match_seconds=match_seconds, team="A", player="x",
        location=[100, 40], end_location=None, xg=xg, shot_outcome="Saved",
        is_penalty=False, is_corner=False, is_free_kick=False, is_red_card=False,
        raw_type_detail="Shot",
    )


def test_derivative_is_one_step_slope():
    h = create_heat(1, "A vs B", "A", "B")
    h.update(_shot(600.0)); d1 = h.danger
    h.update(_shot(601.0)); d2 = h.danger
    h.update(_shot(602.0)); d3 = h.danger     # 3rd event => derivative active

    assert MIN_DERIVATIVE_EVENTS == 3
    assert d1 < d2 < d3                         # danger accumulates each shot
    # elapsed between event 2 and 3 is 1.0s, so derivative == d3 - d2
    assert abs(h.derivative - (d3 - d2)) < 1e-9
    # the old two-event-lag bug would have produced d3 - d1 instead
    assert abs(h.derivative - (d3 - d1)) > 1e-9


def test_derivative_zero_before_min_events():
    h = create_heat(1, "A vs B", "A", "B")
    h.update(_shot(600.0))
    assert h.derivative == 0.0
    h.update(_shot(601.0))
    assert h.derivative == 0.0
