"""Coach: event classification + grounded-fallback explanations."""

from core.coach import classify, explain, CANONICAL, LAW_REF


def test_classify_maps_known_events():
    assert classify("SHOT", "Goal") == "goal"
    assert classify("SET PIECE", "Corner") == "corner"
    assert classify("FAULT RECEIVED", "") == "foul"
    assert classify("CARD", "Yellow") == "card"
    assert classify("CHALLENGE", "Penalty") == "penalty"  # subtype-driven


def test_classify_ignores_noise():
    assert classify("PASS", "") is None
    assert classify("BALL LOST", "") is None
    assert classify("", "") is None


def test_explain_falls_back_to_canonical_without_provider():
    # No warm LLM provider -> the vetted canonical sentence, every category.
    for cat in CANONICAL:
        out = explain(cat, provider=None)
        assert out == CANONICAL[cat]
        assert len(out) > 20


def test_explain_unknown_category_is_empty():
    assert explain("offside", provider=None) == ""


class _RaisingProvider:
    """A warm provider whose generate() blows up (timeout, connection drop)."""
    def is_warm(self):
        return True

    def generate(self, *a, **k):
        raise RuntimeError("llm down")


def test_explain_degrades_to_canonical_when_provider_raises():
    # A raising LLM must not propagate — Coach degrades to the vetted sentence.
    for cat in CANONICAL:
        assert explain(cat, provider=_RaisingProvider()) == CANONICAL[cat]


def test_every_canonical_has_a_law_reference():
    # Each explainable category cites a Law of the Game.
    for cat in CANONICAL:
        assert cat in LAW_REF and LAW_REF[cat].startswith("Law")
