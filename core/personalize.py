"""Personalization: favourite-team bias for switching decisions.

Supports MULTIPLE favourite teams (comma-separated) and an extra boost for
small footballing nations that broadcasters routinely ignore. When no
favourite is set the multiplier is 1.0 (no effect), so the Director falls
back to pure danger ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Multiplier applied to a favourite team's danger score.
FAV_BIAS = 1.3
# Stronger multiplier for small nations: broadcasters skip them, so we lean
# in harder. Used INSTEAD of FAV_BIAS (not stacked) when the favourite is a
# small nation, so the effective boost stays easy to explain.
SMALL_NATION_BIAS = 1.6

# Curated set of "small" footballing nations (lowercase) — the long tail that
# broadcasters routinely ignore. Not exhaustive; World Cup 2026 has 48 teams
# with many debutants, so this is meant to grow.
SMALL_NATIONS = {
    "saudi arabia", "south korea", "iran", "japan", "australia",
    "iceland", "wales", "panama", "qatar", "new zealand", "canada",
    "jamaica", "honduras", "costa rica", "trinidad and tobago",
    "curacao", "curaçao", "cape verde", "uzbekistan", "jordan", "haiti",
    "morocco", "senegal", "ghana", "nigeria", "tunisia", "egypt",
    "ecuador", "peru", "bolivia", "venezuela", "serbia", "slovenia",
}


@dataclass
class Personalizer:
    """Computes favourite-team bias for one or more selected teams."""

    teams: list[str] = field(default_factory=list)  # normalized, lowercase
    fav_bias: float = FAV_BIAS
    small_nation_bias: float = SMALL_NATION_BIAS

    @classmethod
    def from_input(cls, raw: str) -> "Personalizer":
        """Parse a comma-separated favourites string into a Personalizer."""
        teams = [t.strip().lower() for t in (raw or "").split(",") if t.strip()]
        return cls(teams=teams)

    @property
    def active(self) -> bool:
        return bool(self.teams)

    def matched_team(self, home_team: str, away_team: str) -> str | None:
        """Return the actual team name this match involves a favourite for,
        or None. Substring match so "korea" matches "South Korea"."""
        h, a = home_team.lower(), away_team.lower()
        for t in self.teams:
            if t in h:
                return home_team
            if t in a:
                return away_team
        return None

    def is_favourite(self, home_team: str, away_team: str) -> bool:
        return self.matched_team(home_team, away_team) is not None

    def is_small_nation(self, team: str) -> bool:
        return team.strip().lower() in SMALL_NATIONS

    def multiplier(self, home_team: str, away_team: str) -> float:
        """Danger multiplier for this match (1.0 if no favourite involved)."""
        matched = self.matched_team(home_team, away_team)
        if not matched:
            return 1.0
        return self.small_nation_bias if self.is_small_nation(matched) else self.fav_bias

    def biased(self, danger: float, home_team: str, away_team: str) -> float:
        """Apply the favourite multiplier to a danger score, capped at 1.0."""
        return min(danger * self.multiplier(home_team, away_team), 1.0)
