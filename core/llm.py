"""LLM wrapper (LiteLLM). Owner: P1. Everyone calls this; nobody calls litellm directly.

LLM_MODE=mock (default) -> no network. complete() returns a canned string and complete_json()
raises LLMMockMode. Every LLM-dependent step in the repo MUST have a rule-based fallback that is
used when LLM_MODE=mock (this is what keeps tests offline and deterministic).
LLM_MODE=live -> LiteLLM using LLM_MODEL (default below) and the provider key from .env.
"""
import json
import os
import re
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

try:  # optional convenience
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

T = TypeVar("T", bound=BaseModel)
DEFAULT_MODEL = "anthropic/claude-sonnet-5-5"


class LLMMockMode(RuntimeError):
    """Raised by complete_json() in mock mode. Catch it and use your rule-based fallback."""


def llm_mode() -> str:
    return os.getenv("LLM_MODE", "mock").lower()


def is_mock() -> bool:
    return llm_mode() != "live"


def complete(prompt: str, system: Optional[str] = None, temperature: float = 0.0, max_tokens: int = 1024) -> str:
    if is_mock():
        return "[MOCK LLM] " + prompt[:200]
    import litellm

    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    resp = litellm.completion(
        model=os.getenv("LLM_MODEL", DEFAULT_MODEL), messages=messages, temperature=temperature, max_tokens=max_tokens
    )
    return resp.choices[0].message.content or ""


def complete_json(prompt: str, model_cls: Type[T], system: Optional[str] = None, retries: int = 1) -> T:
    if is_mock():
        raise LLMMockMode("complete_json() is unavailable when LLM_MODE=mock; use the rule-based fallback.")
    schema = json.dumps(model_cls.model_json_schema())
    full = f"{prompt}\n\nReturn ONLY a JSON object matching this JSON schema, no prose:\n{schema}"
    last_err: Optional[Exception] = None
    for _ in range(retries + 1):
        text = complete(full, system=system)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        try:
            return model_cls.model_validate_json(match.group(0) if match else text)
        except Exception as err:  # noqa: BLE001 - retry on any parse/validation failure
            last_err = err
    raise ValueError(f"LLM did not return valid {model_cls.__name__}: {last_err}")
