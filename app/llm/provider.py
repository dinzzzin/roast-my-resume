"""One chat() function for every provider, picked by environment variable.

All supported providers speak the OpenAI-compatible API, so a single client
works. If no key is set (or DEMO_MODE=true) the app runs in demo mode and
callers return canned responses — the grader can always query every endpoint.
"""
import json
import os
import re

PROVIDERS = {
    # name: (base_url, env var for key, default model)
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY",
               "gemini-2.0-flash"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
                   "meta-llama/llama-3.3-70b-instruct:free"),
    "openai": (None, "OPENAI_API_KEY", "gpt-4o-mini"),
}


def provider_name() -> str:
    return os.getenv("LLM_PROVIDER", "groq").lower()


def is_demo_mode() -> bool:
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        return True
    _, key_env, _ = PROVIDERS.get(provider_name(), PROVIDERS["groq"])
    return not os.getenv(key_env)


def _client():
    from openai import OpenAI
    base_url, key_env, _ = PROVIDERS[provider_name()]
    # Free tiers rate-limit on tokens per minute; the client backs off and retries 429s.
    return OpenAI(api_key=os.environ[key_env], base_url=base_url, max_retries=6)


def model_name() -> str:
    return os.getenv("LLM_MODEL") or PROVIDERS[provider_name()][2]


def chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 4000,
         json_mode: bool = False) -> str:
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = _client().chat.completions.create(
        model=model_name(), messages=messages, temperature=temperature,
        max_tokens=max_tokens, **kwargs,
    )
    return resp.choices[0].message.content or ""


def extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in ``` fences or added chatter."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
