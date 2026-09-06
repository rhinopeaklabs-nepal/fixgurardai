"""Provider-agnostic LLM client with a no-key fallback.

FixGuard must demo on a laptop with no API key, on a VPS with a key, and on a
stage where the key has just hit a rate limit. So every caller gets a result:
either the model's answer, or a deterministic fallback the caller supplies.

Configure with:

    LLM_PROVIDER   anthropic | openai | none      (default: auto-detect)
    LLM_API_KEY    the key
    LLM_MODEL      model id
    LLM_BASE_URL   for OpenAI-compatible providers (Groq, Gemini compat, etc.)

Anything speaking the OpenAI chat-completions shape works under `openai`.
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from . import config


class LLMUnavailable(Exception):
    """No provider configured, or the provider failed. Callers fall back."""


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    latency_ms: int
    prompt_chars: int
    completion_chars: int


def is_configured() -> bool:
    return bool(config.LLM_PROVIDER != "none" and config.LLM_API_KEY)


def provider_name() -> str:
    return config.LLM_PROVIDER if is_configured() else "none"


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode())


def _call_anthropic(system: str, user: str, max_tokens: int, temperature: float) -> str:
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "content-type": "application/json",
            "x-api-key": config.LLM_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        {
            "model": config.LLM_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
    )
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip()


def _call_openai(system: str, user: str, max_tokens: int, temperature: float) -> str:
    base = config.LLM_BASE_URL.rstrip("/")
    data = _post_json(
        f"{base}/chat/completions",
        {
            "content-type": "application/json",
            "authorization": f"Bearer {config.LLM_API_KEY}",
        },
        {
            "model": config.LLM_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    choices = data.get("choices") or []
    if not choices:
        raise LLMUnavailable("provider returned no choices")
    return (choices[0].get("message", {}).get("content") or "").strip()


async def complete(
    system: str,
    user: str,
    *,
    max_tokens: int = 800,
    temperature: float = 0.0,
) -> LLMResult:
    """One completion. Raises LLMUnavailable rather than returning junk."""
    if not is_configured():
        raise LLMUnavailable("no LLM provider configured")

    started = time.monotonic()
    fn = _call_anthropic if config.LLM_PROVIDER == "anthropic" else _call_openai

    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(fn, system, user, max_tokens, temperature),
            timeout=config.LLM_TIMEOUT_S + 5,
        )
    except asyncio.TimeoutError as exc:
        raise LLMUnavailable(f"timed out after {config.LLM_TIMEOUT_S}s") from exc
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:300]
        except Exception:
            pass
        raise LLMUnavailable(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:  # noqa: BLE001 - any transport failure is a fallback
        raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc

    if not text:
        raise LLMUnavailable("empty completion")

    return LLMResult(
        text=text,
        model=config.LLM_MODEL,
        provider=config.LLM_PROVIDER,
        latency_ms=int((time.monotonic() - started) * 1000),
        prompt_chars=len(system) + len(user),
        completion_chars=len(text),
    )


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a completion.

    Models wrap JSON in prose or fences however much you ask them not to, so
    parse defensively rather than trusting the response shape.
    """
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass

    start = cleaned.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(cleaned[start : i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except ValueError:
                    return None
    return None
