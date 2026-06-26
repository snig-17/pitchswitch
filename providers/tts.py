"""IBM Watson Text to Speech provider.

Turns a switch narration into spoken commentary (a third IBM technology
alongside Granite + Docling). Optional and graceful: if no credentials are
configured, synthesize() returns None and the app stays silent.

Setup (free Lite plan):
  IBM Cloud -> Catalog -> "Text to Speech" -> create (Lite) ->
  Service credentials -> copy "apikey" and "url".
Then in .env:
  WATSON_TTS_APIKEY=...
  WATSON_TTS_URL=https://api.<region>.text-to-speech.watson.cloud.ibm.com/instances/<id>
  WATSON_TTS_VOICE=en-GB_JamesV3Voice   # optional; British voice suits football
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()


class WatsonTTS:
    def __init__(self):
        self.apikey = os.getenv("WATSON_TTS_APIKEY", "")
        self.url = os.getenv("WATSON_TTS_URL", "").rstrip("/")
        self.voice = os.getenv("WATSON_TTS_VOICE", "en-GB_JamesV3Voice")

    def available(self) -> bool:
        return bool(self.apikey and self.url)

    def synthesize(self, text: str) -> bytes | None:
        """Return MP3 audio bytes for `text`, or None on any failure.

        Watson services accept HTTP basic auth with username 'apikey'.
        """
        if not self.available() or not text:
            return None
        try:
            resp = requests.post(
                f"{self.url}/v1/synthesize?voice={self.voice}",
                auth=("apikey", self.apikey),
                headers={"Content-Type": "application/json", "Accept": "audio/mp3"},
                json={"text": text},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None


_CACHE: WatsonTTS | None = None


def get_tts() -> WatsonTTS:
    global _CACHE
    if _CACHE is None:
        _CACHE = WatsonTTS()
    return _CACHE
