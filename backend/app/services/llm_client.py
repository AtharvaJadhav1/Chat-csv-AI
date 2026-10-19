"""Thin, provider-agnostic LLM client for any OpenAI-compatible /chat/completions API."""
from typing import Protocol

import httpx

from ..config import Settings


class LLMError(Exception):
    """The LLM could not be reached or returned an unusable response."""


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete_json(self, system: str, user: str) -> str:
        s = self.settings
        payload = {
            "model": s.llm_model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {s.openai_api_key}"}
        url = f"{s.openai_base_url.rstrip('/')}/chat/completions"
        try:
            with httpx.Client(timeout=s.llm_timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 400 and "response_format" in resp.text:
                    payload.pop("response_format")
                    resp = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise LLMError("The AI service timed out. Please try again.")
        except httpx.HTTPError:
            raise LLMError("Could not reach the AI service. Check your network and OPENAI_BASE_URL.")
        if resp.status_code in (401, 403):
            raise LLMError("The AI service rejected the API key. Check OPENAI_API_KEY.")
        if resp.status_code == 429:
            raise LLMError("The AI service is rate limiting requests. Please wait a moment and retry.")
        if resp.status_code >= 400:
            raise LLMError(f"The AI service returned an error (HTTP {resp.status_code}): {self._provider_message(resp)}")
        try:
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError):
            raise LLMError("The AI service returned an unexpected response format.")

    @staticmethod
    def _provider_message(resp: httpx.Response) -> str:
        """The provider's own error text (never contains our key); helps diagnose bad model names or access."""
        try:
            message = resp.json()["error"]["message"]
        except (KeyError, TypeError, ValueError):
            message = resp.text
        return " ".join(str(message).split())[:250] or "no details"
