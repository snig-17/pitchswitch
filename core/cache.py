"""Broadcast cache loading.

Reads a committed broadcast cache JSON into ``(html, schedule)``. Returns ``None``
when the file is missing, unreadable, not valid JSON, the wrong shape, or carries
a malformed schedule — so callers degrade to a rebuild or the default broadcast
instead of surfacing a traceback. Pure (path in, tuple-or-None out) so it can be
unit-tested without importing the Streamlit app.
"""

from __future__ import annotations

import json
from numbers import Number
from pathlib import Path


def load_cached_broadcast(path: Path):
    """Return ``(html, schedule)`` from a cache file, or ``None`` if untrusted.

    ``schedule`` is a list of ``(time, narration)`` tuples. Each row is validated
    to be a 2-element sequence whose first element is a real number, so the
    downstream ``for t, narr in schedule`` unpack and ``t // 60`` formatting can't
    blow up on a cache that is valid JSON but has malformed rows.
    """
    try:
        cached = json.loads(path.read_text())
        html = cached["html"]
        rows = cached["schedule"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(html, str) or not isinstance(rows, list):
        return None
    schedule = []
    for row in rows:
        # each row must unpack as (t, narration) with a numeric t (bool is a
        # Number subclass but never a valid timestamp, so reject it)
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            return None
        if not isinstance(row[0], Number) or isinstance(row[0], bool):
            return None
        schedule.append(tuple(row))
    return html, schedule
