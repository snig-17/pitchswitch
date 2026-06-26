"""Swappable LLM provider interface for IBM Granite.

Supports three backends:
  - ollama: Local Granite via Ollama (free, no account needed)
  - watsonx: IBM watsonx.ai (cloud, needs IBM Cloud account)
  - replicate: Replicate (cloud, needs API token)

Usage:
    provider = get_provider()
    response = provider.generate("Why is this match dangerous right now?")
"""

import os
import json
import requests
from abc import ABC, abstractmethod

from dotenv import load_dotenv

# Load .env so OLLAMA_MODEL / LLM_PROVIDER / API keys are available before
# any provider reads them via os.getenv.
load_dotenv()


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        """Generate a response from the LLM. Returns empty string on failure."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is reachable."""
        ...

    def warmup(self) -> None:
        """Optionally pre-load the model so the first real call isn't slow.
        Default is a no-op; cloud providers don't need it.
        """
        return None

    def is_warm(self) -> bool:
        """Whether the model is loaded and ready for fast generation.
        Cloud providers are always warm; local model servers override this.
        """
        return True


class OllamaProvider(LLMProvider):
    # Generation timeout. Cold model loads are handled by warmup(), so once
    # warm a generation should comfortably finish within this window. Generous
    # because narration runs async (off the UI thread) and real Granite on CPU
    # can take 10-40s depending on model size.
    GEN_TIMEOUT = 60
    # Cold load of a local model can take 30s+; give warmup a long leash.
    WARMUP_TIMEOUT = 180

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "granite3.1-dense")
        self._warm = False  # set once the model is loaded and responding

    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": max_tokens}},
                timeout=self.GEN_TIMEOUT,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")
            if text:
                self._warm = True
            return text
        except Exception:
            return ""

    def warmup(self) -> None:
        """Load the model into memory with a tiny throwaway generation."""
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": "hi", "stream": False,
                      "options": {"num_predict": 1}},
                timeout=self.WARMUP_TIMEOUT,
            )
            resp.raise_for_status()
            self._warm = True
        except Exception:
            pass

    def is_warm(self) -> bool:
        return self._warm

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


class WatsonxProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("WATSONX_API_KEY", "")
        self.project_id = os.getenv("WATSONX_PROJECT_ID", "")
        self.url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
        # Granite text model; override per region (e.g. eu-gb has no Granite).
        self.model = os.getenv("WATSONX_MODEL", "ibm/granite-3-8b-instruct")

    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        if not self.api_key or not self.project_id:
            return ""
        try:
            # Get IAM token
            token_resp = requests.post(
                "https://iam.cloud.ibm.com/identity/token",
                data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                      "apikey": self.api_key},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            token_resp.raise_for_status()
            token = token_resp.json()["access_token"]

            resp = requests.post(
                f"{self.url}/ml/v1/text/generation?version=2024-03-14",
                json={
                    "model_id": self.model,
                    "input": prompt,
                    "project_id": self.project_id,
                    "parameters": {"max_new_tokens": max_tokens},
                },
                headers={"Authorization": f"Bearer {token}",
                          "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return results[0]["generated_text"] if results else ""
        except Exception:
            return ""

    def is_available(self) -> bool:
        return bool(self.api_key and self.project_id)


class ReplicateProvider(LLMProvider):
    def __init__(self):
        self.token = os.getenv("REPLICATE_API_TOKEN", "")
        self.model = os.getenv("REPLICATE_MODEL", "ibm-granite/granite-3.1-8b-instruct")

    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        if not self.token:
            return ""
        try:
            resp = requests.post(
                "https://api.replicate.com/v1/predictions",
                json={"model": self.model,
                      "input": {"prompt": prompt, "max_tokens": max_tokens}},
                headers={"Authorization": f"Bearer {self.token}",
                          "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            prediction = resp.json()
            # Poll for result
            get_url = prediction.get("urls", {}).get("get", "")
            if not get_url:
                return ""
            for _ in range(30):
                import time
                time.sleep(1)
                r = requests.get(get_url,
                                 headers={"Authorization": f"Bearer {self.token}"},
                                 timeout=10)
                data = r.json()
                if data.get("status") == "succeeded":
                    output = data.get("output", "")
                    return "".join(output) if isinstance(output, list) else str(output)
                if data.get("status") == "failed":
                    return ""
            return ""
        except Exception:
            return ""

    def is_available(self) -> bool:
        return bool(self.token)


_PROVIDERS = {
    "ollama": OllamaProvider,
    "watsonx": WatsonxProvider,
    "replicate": ReplicateProvider,
}


_PROVIDER_CACHE: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Get the configured LLM provider (cached singleton, so warmth persists)."""
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is None:
        provider_name = os.getenv("LLM_PROVIDER", "ollama").lower()
        cls = _PROVIDERS.get(provider_name, OllamaProvider)
        _PROVIDER_CACHE = cls()
    return _PROVIDER_CACHE
