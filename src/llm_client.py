"""Provider-agnostic LLM call used by the naive baseline (and the Day 2+ pipeline).

Provider and model come from config/settings.yaml -> llm. Secrets come only from .env.
Supported providers:
  * dashscope  - Alibaba Cloud Model Studio, OpenAI-compatible endpoint (e.g. deepseek-v4.1-flash, qwen-*)
  * anthropic  - kept as an alternative
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv

from src.taxonomy import ROOT, load_settings


class LLMNotConfigured(RuntimeError):
    """Raised when the API key for the configured provider is missing."""


class LLMCallError(RuntimeError):
    """Raised when the provider call fails (network, auth, rate limit, server error)."""


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model: str


def _cfg() -> dict:
    return load_settings()["llm"]


def api_key_env_var() -> str:
    return _cfg()["api_key_env"]


def is_configured() -> bool:
    load_dotenv(ROOT / ".env")
    key = os.getenv(api_key_env_var(), "")
    return bool(key) and "REPLACE_ME" not in key


def call_llm(prompt: str, system: str | None = None) -> LLMResponse:
    cfg = _cfg()
    if not is_configured():
        raise LLMNotConfigured(f"{api_key_env_var()} not set in .env")
    key = os.environ[api_key_env_var()]
    start = time.perf_counter()

    if cfg["provider"] == "dashscope":
        import openai

        client = openai.OpenAI(api_key=key, base_url=cfg["base_url"], timeout=cfg["timeout_seconds"], max_retries=2)
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        try:
            r = client.chat.completions.create(model=cfg["model"], max_tokens=cfg["max_tokens"], messages=messages)
        except openai.APIError as e:
            raise LLMCallError(f"{type(e).__name__}: {e}") from e
        text = r.choices[0].message.content or ""
        in_tok, out_tok = r.usage.prompt_tokens, r.usage.completion_tokens  # completion includes reasoning tokens

    elif cfg["provider"] == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=key, timeout=cfg["timeout_seconds"])
        kwargs = {"system": system} if system else {}
        try:
            r = client.messages.create(model=cfg["model"], max_tokens=cfg["max_tokens"],
                                       messages=[{"role": "user", "content": prompt}], **kwargs)
        except anthropic.APIError as e:
            raise LLMCallError(f"{type(e).__name__}: {e}") from e
        text = "".join(b.text for b in r.content if b.type == "text")
        in_tok, out_tok = r.usage.input_tokens, r.usage.output_tokens
    else:
        raise ValueError(f"unknown llm.provider: {cfg['provider']}")

    return LLMResponse(text=text, input_tokens=in_tok, output_tokens=out_tok,
                       latency_ms=round((time.perf_counter() - start) * 1000, 1), model=cfg["model"])
