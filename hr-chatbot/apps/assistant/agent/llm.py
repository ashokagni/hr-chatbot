from __future__ import annotations

import json
import os
import time
import urllib.request

_CACHE: dict = {"expires": 0.0, "choice": None, "error": None}


class LLMNotConfigured(RuntimeError):
    pass


def resolve_llm() -> tuple[str, str]:
    now = time.time()
    if _CACHE["expires"] > now:
        if _CACHE["error"]:
            raise LLMNotConfigured(_CACHE["error"])
        return _CACHE["choice"]
    try:
        choice = _resolve_uncached()
    except LLMNotConfigured as exc:
        _CACHE.update(choice=None, error=str(exc), expires=now + 30)
        raise
    _CACHE.update(choice=choice, error=None, expires=now + 30)
    return choice


def describe_llm() -> str:
    try:
        provider, model = resolve_llm()
    except LLMNotConfigured:
        return "CrewAI · no model configured"
    return f"CrewAI · {provider} · {model}"


def build_llm():
    provider, model = resolve_llm()
    from crewai import LLM

    if provider == "ollama":
        # CrewAI's client expects a key even when the call goes to a local Llama.
        os.environ.setdefault("OPENAI_API_KEY", "not-used-for-ollama")
        return LLM(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            temperature=0,
        )
    if provider == "groq":
        # CrewAI's LiteLLM path forwards its prompt-cache marker to Groq, which
        # rejects it. The native OpenAI client strips the marker, and Groq
        # serves an OpenAI-compatible API.
        from crewai.llms.providers.openai.completion import OpenAICompletion

        return OpenAICompletion(
            model=model.removeprefix("groq/"),
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ["GROQ_API_KEY"],
            temperature=0,
        )
    return LLM(model=model, api_key=os.environ["OPENAI_API_KEY"], temperature=0)


def _resolve_uncached() -> tuple[str, str]:
    provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    if provider == "ollama":
        return "ollama", _ollama_model()
    if provider == "groq":
        _require("GROQ_API_KEY", "Set GROQ_API_KEY to use Groq's free Llama API.")
        return "groq", os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    if provider == "openai":
        _require("OPENAI_API_KEY", "Set OPENAI_API_KEY to use a paid OpenAI model.")
        return "openai", os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
    # A configured hosted key wins over a local Ollama container. Local Llama on
    # CPU takes minutes per question, so auto mode should not pick it when a
    # faster provider is already configured.
    if os.getenv("GROQ_API_KEY"):
        return "groq", os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    if os.getenv("OPENAI_API_KEY"):
        return "openai", os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
    if _ollama_reachable():
        return "ollama", _ollama_model()
    raise LLMNotConfigured(
        "No language model is configured. Use a free local Llama with Ollama "
        "(ollama pull llama3.2), a free Groq Llama key (GROQ_API_KEY), or a paid OpenAI key (OPENAI_API_KEY)."
    )


def _ollama_model() -> str:
    name = os.getenv("OLLAMA_MODEL", "llama3.2")
    return name if name.startswith("ollama/") else f"ollama/{name}"


def _ollama_reachable() -> bool:
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=0.8) as response:
            if response.status != 200:
                return False
            json.loads(response.read().decode("utf-8"))
            return True
    except Exception:
        return False


def _require(env_name: str, message: str) -> None:
    if not os.getenv(env_name):
        raise LLMNotConfigured(message)
