"""Client for OpenAI-compatible chat completions: Gemini (several keys, rotated) with Groq as a spare.
Gnani is used for speech only.

Design notes
- Voice needs a fast, predictable turn: one hard deadline and a circuit breaker, so a provider
  outage costs one slow turn, not every turn.
- Gemini's free quota is counted per Google project, so GEMINI_API_KEY .. GEMINI_API_KEY8 (from
  separate projects) add up. Each call starts on the next key (round robin). A key that hits its
  limit rests for a while and the call moves straight on to the next key. If every Gemini key is
  resting, Groq is used when it is configured.
- It never raises. Callers get an LLMResult and fall back to the rule-based dialogue.
- User text is never logged above DEBUG (it can contain personal details). Keys are never logged:
  only labels such as "gemini#3".
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_THINK = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)
_BREAKER_THRESHOLD = 4     # consecutive failed turns (every key tried) before we stop trying for a while
_BREAKER_COOLDOWN_S = 30.0
_MINUTE_REST_S = 5.0       # a per-minute limit: the provider's own hint is used if it is longer
_DAILY_REST_S = 3600.0     # a daily quota: leave that key alone for an hour
_BAD_KEY_REST_S = 3600.0   # an invalid or blocked key: leave it alone for an hour
_ATTEMPT_CAP_S = 8.0       # one slow key must not use up the whole turn
_failures = 0
_open_until = 0.0
_resting: dict[str, float] = {}      # key -> time.monotonic() when it may be used again
_model_override: dict[str, str] = {}  # key -> model it can actually use (learned from a "no longer available" 404)
_rotation = itertools.count()
_client: tuple[Any, httpx.AsyncClient] | None = None


@dataclass
class LLMResult:
    ok: bool
    text: str = ""
    error: str | None = None
    provider: str = ""
    model: str = ""
    latency_ms: int = 0
    key: str = ""       # label of the key that answered, e.g. "gemini#3" (never the key itself)


def _endpoint(base: str) -> str:
    base = base.strip().rstrip("/")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def _targets(s: Settings) -> list[dict[str, str]]:
    """Endpoints to try for one call, in order.

    Ready Gemini keys on the main model first (starting at a different key every call, so the load is
    spread), then ready keys that only work on the fallback model (slower), then Groq, then keys that
    are resting, as a last resort.
    """
    now = time.monotonic()
    fast: list[dict[str, str]] = []
    slow: list[dict[str, str]] = []
    resting: list[dict[str, str]] = []
    keys = s.gemini_keys
    main_model = (s.gemini_model or "gemini-2.5-flash").strip()
    if keys:
        start = next(_rotation) % len(keys)
        for i in range(len(keys)):
            idx = (start + i) % len(keys)
            key = keys[idx]
            model = _model_override.get(key, main_model)
            t = {
                "provider": "gemini",
                "label": f"gemini#{idx + 1}",
                "url": _endpoint(s.gemini_base_url),
                "key": key,
                "model": model,
                "fallback_model": (s.gemini_fallback_model or "").strip(),
            }
            if _resting.get(key, 0.0) > now:
                resting.append(t)
            else:
                (slow if model != main_model else fast).append(t)
    spare: list[dict[str, str]] = []
    groq_key = (s.groq_api_key or "").strip()
    if groq_key:
        spare.append(
            {
                "provider": "groq",
                "label": "groq",
                "url": _endpoint(s.groq_base_url),
                "key": groq_key,
                "model": (s.groq_model or "openai/gpt-oss-120b").strip(),
                "fallback_model": "",
            }
        )
    return fast + slow + spare + resting


def llm_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.gemini_keys or (s.groq_api_key or "").strip())


def _model_params(model: str, settings: Settings) -> dict[str, Any]:
    """Per-model-family request parameters.

    Reasoning models spend completion tokens on thinking, so voice needs low effort and the
    reasoning text excluded from the reply.
    """
    m = model.lower()
    if m.startswith("gemini"):
        # Gemini's OpenAI-compatible endpoint takes reasoning_effort: none | low | medium | high.
        effort = (settings.gemini_reasoning_effort or "none").strip().lower()
        return {"reasoning_effort": effort if effort in ("none", "low", "medium", "high") else "none"}
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
        logger.warning("LLM circuit open for %.0fs after %d failed turns", _BREAKER_COOLDOWN_S, _failures)


def _retry_delay(resp: httpx.Response) -> float:
    """Seconds the provider asks us to wait: the Retry-After header (Groq), or Gemini's "Please retry in 314.7ms" in the body."""
    try:
        return float(resp.headers.get("retry-after", ""))
    except ValueError:
        pass
    m = re.search(r"retry in ([\d.]+)\s*(ms|s)\b", resp.text or "", re.IGNORECASE)
    if m:
        secs = float(m.group(1)) / (1000.0 if m.group(2).lower() == "ms" else 1.0)
        return secs + 0.1
    return 0.4


def _rest_key(key: str, seconds: float) -> None:
    _resting[key] = time.monotonic() + seconds


def key_status(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Which keys are ready or resting, for a health check. Never includes the keys themselves."""
    s = settings or get_settings()
    now = time.monotonic()
    out = [
        {"key": f"gemini#{i + 1}", "ready": _resting.get(k, 0.0) <= now, "rests_for_s": max(0, round(_resting.get(k, 0.0) - now))}
        for i, k in enumerate(s.gemini_keys)
    ]
    if (s.groq_api_key or "").strip():
        out.append({"key": "groq", "ready": True, "rests_for_s": 0})
    return out


# outcomes of one request to one key
_OK, _NEXT, _STOP = "ok", "next", "stop"


async def _request(target: dict[str, str], payload: dict[str, Any], timeout: float) -> tuple[str, Any]:
    """One request to one key. Returns (_OK, (text, usage)) | (_NEXT, error) to try another key | (_STOP, error) when no key can help."""
    label = target["label"]
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {target['key']}"}
    dropped_once = False
    while True:
        try:
            resp = await asyncio.wait_for(_http().post(target["url"], headers=headers, json=payload), timeout=timeout)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            return _NEXT, f"{label}: {type(exc).__name__}"[:120]

        code = resp.status_code
        body = (resp.text or "").lower()

        if code == 429:
            if "perday" in body or "per day" in body or "daily" in body:
                _rest_key(target["key"], _DAILY_REST_S)
                return _NEXT, f"{label}: daily quota used up"
            _rest_key(target["key"], max(_MINUTE_REST_S, _retry_delay(resp)))
            return _NEXT, f"{label}: rate limited"

        if code in (500, 502, 503, 504):
            _rest_key(target["key"], 2.0)       # overloaded: try another key, come back soon
            return _NEXT, f"{label}: HTTP {code}"

        if code == 404 and "no longer available" in body and target.get("fallback_model") and payload.get("model") != target["fallback_model"]:
            # This account can no longer call the main model. Remember that and use the fallback model for it.
            _model_override[target["key"]] = target["fallback_model"]
            logger.info("%s: %s is not available to this account, using %s", label, payload.get("model"), target["fallback_model"])
            payload["model"] = target["fallback_model"]
            continue

        if code in (401, 403) or "api key not valid" in body or "api_key_invalid" in body:
            _rest_key(target["key"], _BAD_KEY_REST_S)
            return _NEXT, f"{label}: key rejected (HTTP {code})"

        if code == 400:
            # A model may reject an optional parameter. Drop the ones the error names, retry once.
            names = [k for k in ("include_reasoning", "reasoning_format", "reasoning_effort", "temperature") if k in body and k in payload]
            if names and not dropped_once:
                dropped_once = True
                for k in names:
                    payload.pop(k, None)
                continue
            return _STOP, f"{label}: HTTP 400: {resp.text[:160]}"      # the request itself is wrong: another key will not help

        if code >= 400:
            return _NEXT, f"{label}: HTTP {code}"

        try:
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or choice.get("text") or "").strip()
        except Exception:
            return _NEXT, f"{label}: non-JSON response"
        text = _THINK.sub("", text).strip()  # defensive: never speak reasoning text
        if not text:
            finish = choice.get("finish_reason")
            return _STOP, f"{label}: empty completion (finish_reason={finish}); raise LLM_MAX_TOKENS if this is 'length'"
        return _OK, (text, data.get("usage") or {})


async def chat(messages: list[dict[str, str]], *, settings: Settings | None = None, max_tokens: int | None = None) -> LLMResult:
    s = settings or get_settings()
    targets = _targets(s)
    if not targets:
        return LLMResult(ok=False, error="not configured")
    if time.monotonic() < _open_until:
        return LLMResult(ok=False, error="circuit open", provider=targets[0]["provider"])

    started = time.monotonic()
    deadline = started + s.llm_timeout_s
    errors: list[str] = []
    # With a single key there is nothing to rotate to, so give it one cheap second try.
    plan = targets if len(targets) > 1 else targets * 2

    for i, target in enumerate(plan):
        remaining = deadline - time.monotonic()
        if remaining <= 0.5:
            errors.append("out of time")
            break
        if i > 0 and target is plan[i - 1]:
            await asyncio.sleep(min(0.4, max(0.0, remaining - 1.0)))
        payload: dict[str, Any] = {
            "model": target["model"],
            "messages": messages,
            "temperature": s.llm_temperature,
            "max_completion_tokens": max(max_tokens or 0, s.llm_max_tokens),
            **_model_params(target["model"], s),
        }
        outcome, data = await _request(target, payload, min(remaining, _ATTEMPT_CAP_S))
        if outcome == _OK:
            text, usage = data
            _record(True)
            ms = int((time.monotonic() - started) * 1000)
            model_used = payload["model"]      # may differ from the target's model if the key was moved to the fallback model
            logger.info(
                "LLM ok %s model=%s %dms tokens prompt=%s completion=%s%s",
                target["label"], model_used, ms, usage.get("prompt_tokens"), usage.get("completion_tokens"),
                f" (after {len(errors)} skipped)" if errors else "",
            )
            return LLMResult(ok=True, text=text, provider=target["provider"], model=model_used, latency_ms=ms, key=target["label"])
        errors.append(str(data))
        if outcome == _STOP:
            break

    _record(False)
    logger.warning("LLM failed after %d attempt(s): %s", len(errors), "; ".join(errors)[:400])
    return LLMResult(
        ok=False,
        error="; ".join(errors)[:300] or "unknown",
        provider=targets[0]["provider"],
        model=targets[0]["model"],
        latency_ms=int((time.monotonic() - started) * 1000),
    )
