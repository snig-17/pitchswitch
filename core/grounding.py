"""Grounding: nation primers parsed into a small knowledge base, used to
ground Granite's narration with real team facts.

Primers live in ``data/primers/<nation>.md`` (team history, key players,
tournament context, style). When the optional ``docling`` package is
installed, each primer is parsed with IBM Docling's ``DocumentConverter`` —
the same path that would handle PDF / DOCX primers in production. Without
docling we fall back to reading the markdown directly. Either way the KB maps
a lowercased nation name to a short facts string the Director injects into
Granite prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PRIMERS_DIR = Path(__file__).resolve().parent.parent / "data" / "primers"


def _parse_with_docling(path: Path) -> str | None:
    """Parse a primer via IBM Docling. Returns markdown text, or None if
    docling is unavailable or the conversion fails (caller falls back)."""
    try:
        from docling.document_converter import DocumentConverter
    except Exception:
        return None
    try:
        result = DocumentConverter().convert(str(path))
        return result.document.export_to_markdown()
    except Exception:
        return None


@dataclass
class Grounding:
    """Nation knowledge base loaded from primer documents."""

    kb: dict[str, str] = field(default_factory=dict)  # nation(lower) -> facts
    used_docling: bool = False

    @classmethod
    def load(cls, primers_dir: Path = PRIMERS_DIR) -> "Grounding":
        kb: dict[str, str] = {}
        used_docling = False
        if primers_dir.is_dir():
            for path in sorted(primers_dir.glob("*.md")):
                text = _parse_with_docling(path)
                if text is not None:
                    used_docling = True
                else:
                    text = path.read_text(encoding="utf-8")
                nation = path.stem.replace("_", " ").lower()
                kb[nation] = text.strip()
        return cls(kb=kb, used_docling=used_docling)

    @property
    def loaded(self) -> bool:
        return bool(self.kb)

    def _lookup(self, team: str) -> str | None:
        """Find a primer for a team name (substring-tolerant)."""
        key = team.strip().lower()
        if key in self.kb:
            return self.kb[key]
        for nation, text in self.kb.items():
            if nation in key or key in nation:
                return text
        return None

    def facts_for(self, *teams: str, max_chars: int = 280) -> str:
        """Return compact primer facts for any of the given teams, one line
        each. Empty string if nothing is known (Granite then runs unground)."""
        lines = []
        for team in teams:
            text = self._lookup(team)
            if text:
                lines.append(f"{team}: {self._compact(text, max_chars)}")
        return "\n".join(lines)

    @staticmethod
    def _compact(text: str, max_chars: int) -> str:
        """Collapse a primer to a single salient sentence-ish blurb. Prefer
        the 'Key Players' / 'Style' substance, skipping the markdown heading."""
        # Drop markdown headings and blank lines, keep prose.
        prose = " ".join(
            ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        )
        prose = " ".join(prose.split())
        if len(prose) > max_chars:
            prose = prose[:max_chars].rsplit(" ", 1)[0] + "..."
        return prose


# Module-level cache: Docling parsing is slow (~6s), so load the KB once per
# process and reuse it across Director instances / Streamlit reruns.
_CACHE: Grounding | None = None


def get_grounding() -> Grounding:
    """Load the primer KB once and cache it for the process lifetime."""
    global _CACHE
    if _CACHE is None:
        _CACHE = Grounding.load()
    return _CACHE
