"""Replay engine: loads StatsBomb matches and replays them on a virtual clock.

Uses asyncio for concurrent multi-match replay. Each match is an async
coroutine that yields events at real match pacing (scaled by speed_factor).
"""

# Stub - Phase 1 implementation
