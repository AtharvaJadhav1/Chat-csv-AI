"""Thin, provider-agnostic LLM client for any OpenAI-compatible /chat/completions API."""
import re
import threading
import time
from typing import Protocol

import httpx

from ..config import Settings


_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def parse_duration(text: str | None) -> float | None:
    """'29.97s' / '1m2.5s' / '350ms' (Groq/OpenAI rate-limit headers) -> seconds."""
    if not text:
        return None
    parts = _DURATION.findall(text)
    if not parts:
        try:
            return float(text)
        except ValueError:
            return None
    unit = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return sum(float(v) * unit[u] for v, u in parts)


class LLMError(Exception):
    """The LLM could not be reached or returned an unusable response."""


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._local = threading.local()
        self.rate_limit_retries = 2  # how many times to wait out a 429 (the evaluation raises this)
        self.max_wait_seconds = 30.0
        self.pace_when_tokens_below = 0  # 0 = off. The evaluation sets e.g. 3200 to stay under a tokens-per-minute cap.
        self._pace_until = 0.0

    def reset_usage(self) -> None:
        self._local.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "llm_calls": 0, "waited_ms": 0}

    def usage(self) -> dict:
        return dict(getattr(self._local, "usage", {}))

    def _wait(self, seconds: float) -> None:
        """Sleep for provider rate limits, and remember how long (so speed numbers can exclude it)."""
        seconds = max(0.0, min(seconds, self.max_wait_seconds))
        if seconds <= 0:
            return
        if not hasattr(self._local, "usage"):
            self.reset_usage()
        self._local.usage["waited_ms"] += round(seconds * 1000)
        time.sleep(seconds)

    def _note_limits(self, headers) -> None:
        if not self.pace_when_tokens_below:
            return
        remaining = headers.get("x-ratelimit-remaining-tokens")
        reset = parse_duration(headers.get("x-ratelimit-reset-tokens"))
        if remaining is not None and reset is not None and int(remaining) < self.pace_when_tokens_below:
            self._pace_until = time.time() + reset + 0.5

    def _record_usage(self, data: dict) -> None:
        if not hasattr(self._local, "usage"):
            self.reset_usage()
        reported = data.get("usage") or {}
        u = self._local.usage
        u["llm_calls"] += 1
        u["prompt_tokens"] += int(reported.get("prompt_tokens") or 0)
        u["completion_tokens"] += int(reported.get("completion_tokens") or 0)
        u["total_tokens"] += int(reported.get("total_tokens") or 0)

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
        self._wait(self._pace_until - time.time())
        try:
            with httpx.Client(timeout=s.llm_timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 400 and "response_format" in resp.text:
                    payload.pop("response_format")
                    resp = client.post(url, json=payload, headers=headers)
                for _ in range(self.rate_limit_retries):
                    if resp.status_code != 429:
                        break
                    hint = parse_duration(resp.headers.get("retry-after")) or parse_duration(resp.headers.get("x-ratelimit-reset-tokens")) or 10.0
                    self._wait(hint + 0.5)
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
        self._note_limits(resp.headers)
        try:
            data = resp.json()
            self._record_usage(data)
            return data["choices"][0]["message"]["content"] or ""
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
