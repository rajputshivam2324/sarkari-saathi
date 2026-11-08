"""Client for Groq (OpenAI-compatible chat completions). Gnani is used for speech only.

Design notes
- Voice needs a fast, predictable turn: one hard deadline, one cheap retry, and a circuit
  breaker so a provider outage costs one slow turn, not every turn.
- It never raises. Callers get an LLMResult and fall back to the rule-based dialogue.
- User text is never logged above DEBUG (it can contain personal details).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_THINK = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)
_BREAKER_THRESHOLD = 4     # consecutive failures before we stop trying for a while
_BREAKER_COOLDOWN_S = 30.0
_failures = 0
_open_until = 0.0
_client: tuple[Any, httpx.AsyncClient] | None = None


@dataclass
class LLMResult:
    ok: bool
    text: str = ""
    error: str | None = None
    provider: str = ""
    model: str = ""
    latency_ms: int = 0


def _endpoint(base: str) -> str:
    base = base.strip().rstrip("/")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def resolve(settings: Settings | None = None) -> dict[str, str] | None:
    """The Groq endpoint, or None when no GROQ_API_KEY is set."""
    s = settings or get_settings()
    key = (s.groq_api_key or "").strip()
    if not key:
        return None
    return {
        "provider": "groq",
        "url": _endpoint(s.groq_base_url),
        "key": key,
        "model": (s.groq_model or "openai/gpt-oss-120b").strip(),
    }


def llm_configured(settings: Settings | None = None) -> bool:
    return resolve(settings) is not None


def _model_params(model: str, settings: Settings) -> dict[str, Any]:
    """Per-model-family request parameters (per Groq's reasoning docs).

    Reasoning models spend completion tokens on thinking, so voice needs low effort and the
    reasoning text excluded from the reply.
    """
    m = model.lower()
    effort = (settings.groq_reasoning_effort or "low").strip().lower()
    if m.startswith("openai/gpt-oss"):
        return {"reasoning_effort": effort if effort in ("low", "medium", "high") else "low", "include_reasoning": False}
    if m.startswith("qwen/qwen3"):
        # Qwen 3.x can reason too; "none" turns thinking off, and hidden keeps any thinking out of the text.
        return {"reasoning_effort": "none" if effort in ("none", "low") else effort, "reasoning_format": "hidden"}
    return {}


def _http() -> httpx.AsyncClient:
    """One pooled client per event loop (keeps TLS connections warm between turns)."""
    global _client
    loop = asyncio.get_running_loop()
    if _client is None or _client[0] is not loop:
        _client = (loop, httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=4.0)))
    return _client[1]


def _record(ok: bool) -> None:
    global _failures, _open_until
    if ok:
        _failures = 0
        return
    _failures += 1
    if _failures >= _BREAKER_THRESHOLD:
        _open_until = time.monotonic() + _BREAKER_COOLDOWN_S
        logger.warning("LLM circuit open for %.0fs after %d failures", _BREAKER_COOLDOWN_S, _failures)


async def chat(messages: list[dict[str, str]], *, settings: Settings | None = None) -> LLMResult:
    s = settings or get_settings()
    target = resolve(s)
    if target is None:
        return LLMResult(ok=False, error="not configured")
    if time.monotonic() < _open_until:
        return LLMResult(ok=False, error="circuit open", provider=target["provider"])

    headers = {"Content-Type": "application/json"}
    headers["Authorization"] = f"Bearer {target['key']}"

    payload: dict[str, Any] = {
        "model": target["model"],
        "messages": messages,
        "temperature": s.llm_temperature,
        "max_completion_tokens": s.llm_max_tokens,
        **_model_params(target["model"], s),
    }

    started = time.monotonic()
    deadline = started + s.llm_timeout_s
    last_error = "unknown"

    for attempt in (1, 2):
        remaining = deadline - time.monotonic()
        if remaining <= 0.5:
            break
        try:
            resp = await asyncio.wait_for(
                _http().post(target["url"], headers=headers, json=payload), timeout=remaining
            )
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"[:200]
            if attempt == 1:
                await asyncio.sleep(0.25)
                continue
            break

        if resp.status_code == 400:
            # A model may reject an optional parameter. Drop the ones the error names, retry once.
            body = resp.text.lower()
            dropped = [k for k in ("include_reasoning", "reasoning_format", "reasoning_effort", "temperature") if k in body and k in payload]
            if dropped and attempt == 1:
                for k in dropped:
                    payload.pop(k, None)
                continue
            last_error = f"HTTP 400: {resp.text[:200]}"
            break

        if resp.status_code in (429, 500, 502, 503, 504):
            last_error = f"HTTP {resp.status_code}"
            if attempt == 1:
                try:
                    wait = float(resp.headers.get("retry-after", "0.4"))
                except ValueError:
                    wait = 0.4
                if wait > max(0.0, deadline - time.monotonic() - 2.0):
                    break  # Groq asks for longer than a voice turn can wait: fall back now
                await asyncio.sleep(min(wait, 3.0))
                continue
            break

        if resp.status_code >= 400:
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            break

        try:
            choice = (resp.json().get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or choice.get("text") or "").strip()
        except Exception:
            last_error = "non-JSON response"
            break
        text = _THINK.sub("", text).strip()  # defensive: never speak reasoning text
        if not text:
            finish = choice.get("finish_reason")
            last_error = f"empty completion (finish_reason={finish}); raise LLM_MAX_TOKENS if this is 'length'"
            break

        _record(True)
        ms = int((time.monotonic() - started) * 1000)
        logger.info("LLM ok provider=%s model=%s %dms", target["provider"], target["model"], ms)
        return LLMResult(ok=True, text=text, provider=target["provider"], model=target["model"], latency_ms=ms)

    _record(False)
    logger.warning("LLM failed provider=%s: %s", target["provider"], last_error)
    return LLMResult(
        ok=False,
        error=last_error,
        provider=target["provider"],
        model=target["model"],
        latency_ms=int((time.monotonic() - started) * 1000),
    )
