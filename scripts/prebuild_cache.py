"""Pre-build the broadcast cache so the app runs anywhere without Ollama/data.

The cached broadcast HTML is fully self-contained (tracking frames + Granite
narration + Watson TTS audio baked in), so a deployed app just serves the
cache — no LLM, no Metrica CSVs, no heavy deps at runtime. Run this locally
(with Ollama + Metrica data present), commit data/cache/, and deploy.

    python scripts/prebuild_cache.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.livefeed import build_broadcast            # noqa: E402
from core.metrica import build_unified_broadcast     # noqa: E402

MATCHUPS = [
    {"game": 1, "home": "France", "away": "Argentina"},
    {"game": 2, "home": "South Korea", "away": "Germany"},
]
# "" is the default fallback the hosted app serves for any uncached favourite.
FAVOURITES = ["", "South Korea", "Argentina", "France", "Germany"]


def main():
    try:
        from providers.llm import get_provider
        from providers.tts import get_tts
        get_provider().warmup()
        voice = get_tts().available()
    except Exception:
        voice = False

    out = Path("data/cache")
    out.mkdir(parents=True, exist_ok=True)
    for fav in FAVOURITES:
        bd = build_unified_broadcast(MATCHUPS, favourite=fav, t0=0, dur=120,
                                     fps=8, voice=voice)
        html = build_broadcast(bd)
        narrs = [g.get("narration", "") for g in bd["games"]]
        sched = [(t, narrs[gi]) for t, gi in bd["schedule"]]
        key = hashlib.md5(fav.lower().encode()).hexdigest()[:10]
        (out / f"broadcast_{key}.json").write_text(
            json.dumps({"html": html, "schedule": sched}))
        print(f"cached favourite={fav!r:16} switches={len(sched)} "
              f"voice={'yes' if any(g.get('audio') for g in bd['games']) else 'no'}")


if __name__ == "__main__":
    main()
