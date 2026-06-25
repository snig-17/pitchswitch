"""Heat & anticipation model: rolling danger score per match.

Danger score (0.0-1.0) computed from:
  - Carries into the final third (x > 80)
  - Pressure events in opponent's half
  - Passes into the penalty area
  - Shot xG values
  - Set-piece indicators (corner, free kick in range, penalty)
  - Red card events

Forward-looking signal: time-based derivative (danger_change / elapsed_match_seconds).
Switch threshold: danger > 0.6 AND derivative > 0.1/s, OR danger > 0.8, OR set-piece.
"""

# Stub - Phase 2 implementation
