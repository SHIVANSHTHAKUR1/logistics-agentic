from __future__ import annotations

from typing import Any, List, Optional, Tuple


try:
    from .groq_models import groq_models
except Exception:
    groq_models = {}

# User requirement: use Gemini and Groq only.
# Avoid importing OpenAI/Ollama providers entirely to prevent import-time failures
# and accidental usage.
openai_models = {}
ollama_models = {}

try:
    from .gemini_models import gemini_models
except Exception:
    gemini_models = {}

# Try to find a working model in order of preference
DEFAULT_MODEL = None


def _looks_like_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    # Gemini
    if "resourceexhausted" in s or "quota" in s:
        return True
    if "429" in s and ("rate" in s or "quota" in s or "exceeded" in s):
        return True
    # OpenAI/Groq/others
    if "rate limit" in s or "ratelimit" in s:
        return True
    return False


class FailoverChatModel:
    """A tiny wrapper that fails over across multiple configured LangChain chat models.

    Motivation: free-tier Gemini quotas can be very low per model/project and cause
    hard failures. This wrapper tries other configured models automatically.
    """

    def __init__(self, models: List[Tuple[str, Any]]):
        self._models = [(k, m) for (k, m) in models if m is not None]
        self._cursor = 0

    def invoke(self, messages, **kwargs):
        if not self._models:
            raise RuntimeError("No LLM models available. Please check your API keys in .env file")

        last_error: Optional[Exception] = None
        tried = 0
        while tried < len(self._models):
            key, model = self._models[self._cursor]
            self._cursor = (self._cursor + 1) % len(self._models)
            tried += 1
            try:
                return model.invoke(messages, **kwargs)
            except Exception as e:
                last_error = e
                # If provider is rate-limited/quota-limited, try next model.
                if _looks_like_rate_limit(e):
                    continue
                # Non-rate-limit errors should surface immediately.
                raise
        # Everything failed (likely all rate-limited)
        raise last_error or RuntimeError("All configured LLM models failed")

preferred: List[Tuple[str, Any]] = []

# Requirement: Groq + Gemini only.
# Prefer Groq first for speed/cost, then Gemini as fallback (or vice-versa if you want).
if groq_models:
    for model_key in [
        "llama-3.1-8b-instant",
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    ]:
        if model_key in groq_models and groq_models[model_key] is not None:
            preferred.append((f"groq:{model_key}", groq_models[model_key]))

if gemini_models:
    for model_key in [
        "gemini-3-flash",
        "gemini-2.0-flash",
        "gemini-2.5-pro",
        "gemini-flash-latest",
        "gemini-pro-latest",
    ]:
        if model_key in gemini_models and gemini_models[model_key] is not None:
            preferred.append((f"gemini:{model_key}", gemini_models[model_key]))

if preferred:
    DEFAULT_MODEL = FailoverChatModel(preferred)
    print("Using failover LLM chain with:", ", ".join(k for k, _ in preferred))
else:
    DEFAULT_MODEL = None
    print("Warning: No LLM models available. Please check your API keys in .env file")
