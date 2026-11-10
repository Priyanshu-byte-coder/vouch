"""OpenAI-compatible LLM client with JSON helpers, caching and usage/cost tracking.

Reasoning models spend their token budget on hidden "thinking" (EXPERIMENTS.md S0), so
parsing calls run with thinking off; judging calls can turn it on with a larger budget.
"""

import json
import re
from contextvars import ContextVar
from dataclasses import dataclass, field

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .cache import get_cache, make_key
from .config import get_settings


@dataclass
class Usage:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    models: set[str] = field(default_factory=set)

    def add(self, model: str, tokens_in: int, tokens_out: int) -> None:
        s = get_settings()
        self.calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.cost_usd += tokens_in / 1e6 * s.llm_price_in_per_m + tokens_out / 1e6 * s.llm_price_out_per_m
        self.models.add(model)


# Usage for the current job (each pipeline run sets its own); falls back to a process-wide total.
_global_usage = Usage()
current_usage: ContextVar[Usage] = ContextVar("current_usage", default=_global_usage)


class LLMJSONError(ValueError):
    """The model did not return parseable JSON."""


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_loose(text: str):
    """Parse JSON from a model reply: strips code fences and surrounding prose."""
    t = _FENCE.sub("", text.strip())
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if not starts:
        raise LLMJSONError(f"no JSON in reply: {text[:120]!r}")
    start = min(starts)
    end = t.rfind("}" if t[start] == "{" else "]")
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError as e:
        raise LLMJSONError(f"invalid JSON in reply: {text[:120]!r}") from e


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncOpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key or "none", timeout=s.llm_timeout,
                              max_retries=0)
    return _client


_RETRYABLE = (APIConnectionError, APITimeoutError)


def _is_retryable_status(e: BaseException) -> bool:
    return isinstance(e, APIStatusError) and (e.status_code == 429 or e.status_code >= 500)


@retry(retry=retry_if_exception_type(_RETRYABLE) | retry_if_exception_type(APIStatusError),
       wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(4), reraise=True)
async def _complete(model: str, messages: list[dict], thinking: bool, max_tokens: int, temperature: float):
    extra = {"chat_template_kwargs": {"enable_thinking": thinking}}
    if not thinking:
        extra["reasoning_effort"] = "none"
    try:
        return await get_client().chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, extra_body=extra)
    except APIStatusError as e:
        if not _is_retryable_status(e):
            raise LLMJSONError(f"LLM request rejected: HTTP {e.status_code}") from e
        raise


async def chat_json(prompt: str | list[dict], *, model: str | None = None, system: str | None = None,
                    thinking: bool = False, max_tokens: int | None = None, temperature: float = 0.0,
                    use_cache: bool = True):
    """Ask for JSON and return the parsed object. Cached by (model, messages, params)."""
    s = get_settings()
    model = model or (s.llm_model_judge if thinking else s.llm_model_parse)
    max_tokens = max_tokens or (6000 if thinking else 1500)
    messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
    if system:
        messages = [{"role": "system", "content": system}, *messages]

    cache = get_cache()
    key = make_key(model, messages, thinking, max_tokens, temperature)
    if use_cache:
        hit = cache.get("llm", key)
        if hit is not cache._MISS:
            return hit

    last_err: Exception | None = None
    for attempt in range(2):  # one extra try with a firmer instruction if the JSON is broken
        msgs = messages if attempt == 0 else [
            *messages, {"role": "user", "content": "Your last reply was not valid JSON. Reply with ONLY valid JSON."}]
        resp = await _complete(model, msgs, thinking, max_tokens, temperature)
        u = resp.usage
        current_usage.get().add(model, getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0)
        content = resp.choices[0].message.content or ""
        try:
            result = parse_json_loose(content)
        except LLMJSONError as e:
            last_err = e
            continue
        if use_cache:
            cache.set("llm", key, result)
        return result
    raise last_err or LLMJSONError("no reply")
