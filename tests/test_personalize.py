"""Personalizer: favourite-team and small-nation switching bias."""

from core.personalize import Personalizer, FAV_BIAS, SMALL_NATION_BIAS


def test_no_favourite_is_neutral():
    pz = Personalizer.from_input("")
    assert pz.active is False
    assert pz.multiplier("France", "Argentina") == 1.0


def test_favourite_gets_fav_bias():
    pz = Personalizer.from_input("Argentina")
    assert pz.multiplier("France", "Argentina") == FAV_BIAS
    # not involved -> neutral
    assert pz.multiplier("Spain", "Portugal") == 1.0


def test_small_nation_gets_stronger_bias():
    pz = Personalizer.from_input("South Korea")
    # South Korea is in SMALL_NATIONS -> the stronger multiplier, not FAV_BIAS
    assert pz.multiplier("South Korea", "Germany") == SMALL_NATION_BIAS
    assert SMALL_NATION_BIAS > FAV_BIAS


def test_multi_team_and_substring_match():
    pz = Personalizer.from_input("korea, argentina")
    assert pz.matched_team("South Korea", "Germany") == "South Korea"
    assert pz.matched_team("France", "Argentina") == "Argentina"
    assert pz.is_favourite("Spain", "Portugal") is False


def test_biased_danger_caps_at_one():
    pz = Personalizer.from_input("South Korea")
    # 0.8 * 1.6 = 1.28 -> must clamp to 1.0
    assert pz.biased(0.8, "South Korea", "Germany") == 1.0
    # unbiased match passes the value through
    assert pz.biased(0.5, "Spain", "Portugal") == 0.5
