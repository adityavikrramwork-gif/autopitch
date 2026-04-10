"""
AutoPitch v3 — API Clients (Groq & Serper)
Retry logic, rate limiting, and structured error handling.
"""

import time
from typing import Any

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import cfg
from logger import logger

# ── Rate Limiter ────────────────────────────────────────────────────────────────

_last_call_time: float = 0.0
_MIN_API_INTERVAL: float = 0.5  # seconds between API calls


def _rate_limit() -> None:
    """Simple global rate limiter to avoid API throttling."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < _MIN_API_INTERVAL:
        time.sleep(_MIN_API_INTERVAL - elapsed)
    _last_call_time = time.time()


# ── Groq Client ─────────────────────────────────────────────────────────────────

class GroqAPIError(Exception):
    """Raised when the Groq API call fails after retries."""


@retry(
    stop=stop_after_attempt(cfg.api_max_retries),
    wait=wait_exponential(multiplier=cfg.api_retry_backoff, min=1, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True,
)
def groq_call(
    prompt: str,
    groq_key: str,
    max_tokens: int = 900,
    temperature: float = 0.65,
) -> str:
    """Call the Groq LLaMA API with automatic retries on transient failures."""
    _rate_limit()

    logger.debug("Groq API call — max_tokens=%d, temperature=%.2f", max_tokens, temperature)

    try:
        resp = requests.post(
            cfg.groq_endpoint,
            json={
                "model": cfg.groq_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            timeout=cfg.groq_timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        logger.info("Groq API call succeeded — %d chars returned", len(content))
        return content

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status in (401, 403):
            logger.error("Groq auth error — check API key")
            raise GroqAPIError("Invalid Groq API key. Please check your credentials.") from exc
        if status == 429:
            logger.warning("Groq rate limit hit — will retry")
            raise
        logger.error("Groq HTTP error — status=%d", status)
        raise GroqAPIError(f"Groq API error (HTTP {status}). Please try again.") from exc

    except requests.exceptions.Timeout:
        logger.warning("Groq request timed out")
        raise

    except Exception as exc:
        logger.error("Groq unexpected error: %s", exc)
        raise GroqAPIError(f"Unexpected error calling Groq API.") from exc


# ── Serper Client ───────────────────────────────────────────────────────────────

class SerperAPIError(Exception):
    """Raised when the Serper API call fails."""


@retry(
    stop=stop_after_attempt(cfg.api_max_retries),
    wait=wait_exponential(multiplier=cfg.api_retry_backoff, min=1, max=8),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True,
)
def serper_query(query: str, serper_key: str, num: int = 5) -> dict[str, Any]:
    """Search Google via Serper API with retries on transient failures."""
    _rate_limit()

    logger.debug("Serper query: %s", query[:80])

    try:
        resp = requests.post(
            cfg.serper_endpoint,
            json={"q": query, "num": num},
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
            timeout=cfg.serper_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Serper returned %d results for: %s", len(data.get("organic", [])), query[:50])
        return data

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status in (401, 403):
            logger.error("Serper auth error — check API key")
            raise SerperAPIError("Invalid Serper API key. Please check your credentials.") from exc
        logger.error("Serper HTTP error — status=%d", status)
        raise SerperAPIError(f"Serper API error (HTTP {status}).") from exc

    except requests.exceptions.Timeout:
        logger.warning("Serper request timed out for: %s", query[:50])
        return {}

    except Exception as exc:
        logger.error("Serper unexpected error: %s", exc)
        return {}