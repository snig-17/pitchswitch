"""Director: compares matches and decides when to switch.

Two-tier decision system:
  - Heuristic: handles clear winners (one match >0.15 above all others).
    Switch happens immediately, no LLM latency.
  - Granite: fires on ambiguous calls (2+ matches within 0.15 danger).
    Reasons over structured match state, decides which match deserves
    the viewer's attention, generates narration.

Narration is async: the switch happens on the heuristic, Granite's
narration text arrives when the LLM responds. If the LLM is unavailable,
a template-based fallback narration is used instead.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from core.heat import MatchHeat
from core.personalize import Personalizer
from providers.llm import LLMProvider, get_provider

# Ambiguity threshold: if top 2 matches are within this delta,
# it's ambiguous and Granite should reason about it.
AMBIGUITY_THRESHOLD = 0.15

# Minimum danger to consider a match for switching
MIN_SWITCH_DANGER = 0.30

# Cooldown between Granite calls (seconds of match time)
GRANITE_COOLDOWN_SECONDS = 60.0


@dataclass
class SwitchDecision:
    """Result of a switch decision."""
    should_switch: bool
    target_match_id: int | None
    target_label: str
    reason: str  # heuristic reason
    narration: str  # LLM-generated or template fallback
    is_granite_decision: bool  # True if Granite made the call
    danger: float
    source: str  # "heuristic", "granite", "penalty", "fallback"


@dataclass
class Director:
    """Orchestrates multi-match switching decisions."""
    provider: LLMProvider = field(default_factory=get_provider)
    personalizer: Personalizer = field(default_factory=Personalizer)

    # State
    current_match_id: int | None = None
    _last_granite_time: float = 0.0
    _pending_narration: str | None = None
    _pending_decision: SwitchDecision | None = None  # async Granite re-pick
    _granite_inflight: bool = False  # a Granite decision thread is running
    _narration_lock: threading.Lock = field(default_factory=threading.Lock)
    _llm_available: bool | None = None  # cached availability check

    def decide(self, heats: dict[int, MatchHeat]) -> SwitchDecision | None:
        """Given all match heat states, decide whether to switch.

        Returns a SwitchDecision if a switch should happen, None otherwise.
        """
        if not heats:
            return None

        # Rank matches by biased danger
        ranked = []
        for mid, heat in heats.items():
            biased = self._apply_bias(heat)
            ranked.append((mid, heat, biased))
        ranked.sort(key=lambda x: x[2], reverse=True)

        top_mid, top_heat, top_danger = ranked[0]

        # Nothing worth switching to
        if top_danger < MIN_SWITCH_DANGER:
            return None

        # Already on the best match
        if top_mid == self.current_match_id and not top_heat.should_switch:
            return None

        # Penalty always switches immediately
        if top_heat.should_switch and "Penalty" in top_heat.switch_reason:
            self.current_match_id = top_mid
            narration = self._penalty_narration(top_heat)
            return SwitchDecision(
                should_switch=True,
                target_match_id=top_mid,
                target_label=top_heat.label,
                reason=top_heat.switch_reason,
                narration=narration,
                is_granite_decision=False,
                danger=top_danger,
                source="penalty",
            )

        # Check ambiguity: are the top 2 close?
        is_ambiguous = (len(ranked) >= 2 and
                         ranked[0][2] - ranked[1][2] < AMBIGUITY_THRESHOLD and
                         ranked[1][2] > MIN_SWITCH_DANGER)

        if is_ambiguous and top_mid != self.current_match_id:
            # Ambiguous: ask Granite which close match deserves attention,
            # but do it in the background so the UI never blocks. We still
            # switch immediately on the heuristic below; if Granite picks a
            # different match its decision arrives via get_pending_decision().
            self._maybe_start_granite(ranked[:3])

        # Clear winner (or Granite running in the background): heuristic switch
        if top_mid != self.current_match_id and top_heat.should_switch:
            self.current_match_id = top_mid
            narration = self._heuristic_narration(top_heat)

            # For clear winners, fire async Granite narration to upgrade the
            # template text. (Ambiguous calls already get narration from the
            # background decision, so skip the duplicate LLM request.)
            if not is_ambiguous:
                self._request_granite_narration(top_heat)

            return SwitchDecision(
                should_switch=True,
                target_match_id=top_mid,
                target_label=top_heat.label,
                reason=top_heat.switch_reason,
                narration=narration,
                is_granite_decision=False,
                danger=top_danger,
                source="heuristic",
            )

        return None

    def get_pending_narration(self) -> str | None:
        """Check if async Granite narration has arrived."""
        with self._narration_lock:
            if self._pending_narration:
                narr = self._pending_narration
                self._pending_narration = None
                return narr
        return None

    def set_favourites(self, raw: str) -> None:
        """Update the favourite team(s) from a comma-separated string."""
        self.personalizer = Personalizer.from_input(raw)

    def biased_danger(self, heat: MatchHeat) -> float:
        """Public: the danger the Director actually ranks on (favourite bias
        applied). Use this for display so the UI matches switching decisions."""
        return self._apply_bias(heat)

    def is_favourite(self, heat: MatchHeat) -> bool:
        """Whether this match involves one of the viewer's favourite teams."""
        return self.personalizer.is_favourite(heat.home_team, heat.away_team)

    def favourite_label(self, heat: MatchHeat) -> str | None:
        """The favourite team name this match involves, or None."""
        return self.personalizer.matched_team(heat.home_team, heat.away_team)

    def _apply_bias(self, heat: MatchHeat) -> float:
        """Apply favourite team bias to danger score (delegated)."""
        return self.personalizer.biased(heat.danger, heat.home_team, heat.away_team)

    def _is_llm_available(self) -> bool:
        """Check LLM availability (cached)."""
        if self._llm_available is None:
            self._llm_available = self.provider.is_available()
        return self._llm_available

    def get_pending_decision(self) -> SwitchDecision | None:
        """Check if an async Granite re-pick has arrived (non-blocking)."""
        with self._narration_lock:
            if self._pending_decision:
                dec = self._pending_decision
                self._pending_decision = None
                return dec
        return None

    def warmup(self) -> None:
        """Warm the LLM in the background so the first real call isn't a
        cold model load (which can take 30s+ and blow past request timeouts).
        """
        def _warm():
            try:
                self.provider.warmup()
            except Exception:
                pass
        threading.Thread(target=_warm, daemon=True).start()

    def _maybe_start_granite(self, top_matches: list) -> None:
        """Kick off a background Granite decision for ambiguous matches.

        Non-blocking: respects availability, warmth, the cooldown, and an
        in-flight guard so we never spawn overlapping LLM calls. The result
        lands in _pending_decision for the next call to get_pending_decision().
        """
        if (self._granite_inflight or not self._is_llm_available()
                or not self.provider.is_warm()):
            return

        # Cooldown check (in match-seconds)
        current_time = top_matches[0][1].current_minute * 60
        if current_time - self._last_granite_time < GRANITE_COOLDOWN_SECONDS:
            return

        self._granite_inflight = True
        self._last_granite_time = current_time
        thread = threading.Thread(
            target=self._run_granite_decision,
            args=(top_matches,),
            daemon=True,
        )
        thread.start()

    def _run_granite_decision(self, top_matches: list) -> None:
        """Background worker: ask Granite which match to watch, store result."""
        try:
            prompt = self._build_decision_prompt(top_matches)
            response = self.provider.generate(prompt, max_tokens=150)

            if not response:
                # Transient (timeout / model busy). Don't permanently disable
                # Granite — a single slow call shouldn't kill it for the session.
                return

            # Only let Granite pick a genuinely switch-worthy match. Matches
            # are passed in for context, but switching the viewer to a cold
            # match just because the model named it would be wrong.
            candidates = [(mid, heat, d) for mid, heat, d in top_matches
                          if d >= MIN_SWITCH_DANGER] or top_matches

            # Parse: Granite should name which candidate to watch
            chosen_mid = candidates[0][0]  # default to highest danger
            chosen_heat = candidates[0][1]
            for mid, heat, danger in candidates:
                if (heat.home_team.lower() in response.lower() or
                        heat.away_team.lower() in response.lower()):
                    chosen_mid = mid
                    chosen_heat = heat
                    break

            decision = SwitchDecision(
                should_switch=True,
                target_match_id=chosen_mid,
                target_label=chosen_heat.label,
                reason=f"Granite reasoning (ambiguous: top matches within {AMBIGUITY_THRESHOLD})",
                narration=response.strip(),
                is_granite_decision=True,
                danger=self._apply_bias(chosen_heat),
                source="granite",
            )
            with self._narration_lock:
                self._pending_decision = decision
        finally:
            self._granite_inflight = False

    def _build_decision_prompt(self, top_matches: list) -> str:
        """Build a structured prompt for Granite's switching decision."""
        lines = [
            "You are a football match director for a multi-match viewing experience.",
            "Multiple matches are happening simultaneously. Based on the current state,",
            "decide which match the viewer should watch RIGHT NOW and explain why in",
            "one punchy sentence (like a TV presenter switching between matches).",
            "",
            "Current match states:",
        ]

        for mid, heat, biased_danger in top_matches:
            state = heat.get_state_summary()
            context = heat.get_recent_context(3)
            matched = self.personalizer.matched_team(heat.home_team, heat.away_team)
            is_fav = f" [VIEWER'S FAVOURITE TEAM: {matched}]" if matched else ""

            lines.append(f"\n  {heat.label} ({state['score']}, {state['minute']}'){is_fav}")
            lines.append(f"    Danger: {state['danger']:.2f} (derivative: {state['derivative']:+.4f}/s)")
            if state['late_game']:
                lines.append(f"    LATE GAME - tight scoreline!")
            if state['about_to_ignite']:
                lines.append(f"    BUILDING - danger rising fast")
            if context:
                lines.append(f"    Recent: {'; '.join(context[:2])}")

        lines.append("")
        lines.append("Which match should we switch to? Reply with ONE sentence, starting with")
        lines.append("'Switch to [Team A] vs [Team B]' and explain why.")

        return "\n".join(lines)

    def _request_granite_narration(self, heat: MatchHeat) -> None:
        """Fire async Granite narration (non-blocking)."""
        if not self._is_llm_available() or not self.provider.is_warm():
            return

        def _generate():
            prompt = self._build_narration_prompt(heat)
            response = self.provider.generate(prompt, max_tokens=80)
            if response:
                with self._narration_lock:
                    self._pending_narration = response.strip()

        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()

    def _build_narration_prompt(self, heat: MatchHeat) -> str:
        """Build a narration prompt for the current switch."""
        state = heat.get_state_summary()
        context = heat.get_recent_context(5)

        matched = self.personalizer.matched_team(heat.home_team, heat.away_team)
        is_fav = f" The viewer follows {matched}." if matched else ""
        if matched and self.personalizer.is_small_nation(matched):
            is_fav += " (a small nation broadcasters usually ignore)."

        prompt = (
            f"You are a match commentator. Generate a one-sentence switch call.\n"
            f"Match: {heat.label} ({state['score']}, {state['minute']}'){is_fav}\n"
            f"Danger level: {state['danger']:.2f} (rising: {state['derivative']:+.4f}/s)\n"
        )
        if state['late_game']:
            prompt += "This is LATE GAME with a tight scoreline.\n"
        if context:
            prompt += f"Recent action: {'; '.join(context[:3])}\n"
        if heat.switch_reason:
            prompt += f"Reason: {heat.switch_reason}\n"

        prompt += (
            "\nWrite ONE punchy sentence a TV presenter would say to switch viewers "
            "to this match. Be specific about what's happening. Example: "
            "'Get to France vs Argentina NOW, Mbappe is through on goal after a "
            "lightning counter-attack!'"
        )
        return prompt

    def _heuristic_narration(self, heat: MatchHeat) -> str:
        """Generate template-based narration when Granite is unavailable."""
        state = heat.get_state_summary()
        score = state["score"]
        minute = state["minute"]

        # Personalization prefix
        matched = self.personalizer.matched_team(heat.home_team, heat.away_team)
        prefix = f"Your team {matched}! " if matched else ""

        if "Penalty" in heat.switch_reason:
            return f"{prefix}Switch to {heat.label} - PENALTY! ({score}, {minute}')"

        if state["late_game"]:
            return (f"{prefix}Switch to {heat.label} - late drama! "
                    f"({score}, {minute}') Danger at {state['danger']:.2f}")

        if state["about_to_ignite"]:
            return (f"{prefix}Switch to {heat.label} - danger building fast! "
                    f"({score}, {minute}')")

        return (f"{prefix}Switch to {heat.label} - action heating up "
                f"({score}, {minute}') Danger: {state['danger']:.2f}")

    def _penalty_narration(self, heat: MatchHeat) -> str:
        """Special narration for penalty events."""
        state = heat.get_state_summary()
        matched = self.personalizer.matched_team(heat.home_team, heat.away_team)
        prefix = f"YOUR TEAM {matched}! " if matched else ""
        return (f"{prefix}PENALTY at {heat.label}! "
                f"({state['score']}, {state['minute']}')")


def create_director(favourite_team: str = "") -> Director:
    """Create a new Director with the configured LLM provider.

    favourite_team accepts a comma-separated list of teams.
    """
    return Director(personalizer=Personalizer.from_input(favourite_team))
