"""Forge3D LLM clients — BYO API keys, pick your model, stay local & private.

Supported providers: openai | anthropic | openrouter | ollama | custom
(OpenAI-compatible). Keys come from (priority order):
  1. CLI / chat slash commands
  2. config/forge3d.config.json  (never committed — see .gitignore)
  3. environment variables
Keys are never logged or sent anywhere except the chosen provider.
"""
import json
import os
import urllib.request

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "config", "forge3d.config.json")

DEFAULTS = {
    "openai":     {"base": "https://api.openai.com/v1",
                   "model": "gpt-4o-mini", "env": "OPENAI_API_KEY"},
    "anthropic":  {"base": "https://api.anthropic.com/v1",
                   "model": "claude-sonnet-4-5", "env": "ANTHROPIC_API_KEY"},
    "openrouter": {"base": "https://openrouter.ai/api/v1",
                   "model": "meta-llama/llama-3.3-70b-instruct",
                   "env": "OPENROUTER_API_KEY"},
    "ollama":     {"base": "http://localhost:11434/v1",
                   "model": "llama3.1", "env": None},
}


class LLMError(Exception):
    pass


def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
        except Exception:
            pass
    return cfg


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=1)


def resolve(provider=None, model=None, api_key=None, base_url=None):
    """Returns dict(provider, model, api_key, base_url)."""
    cfg = load_config()
    provider = provider or os.environ.get("FORGE3D_PROVIDER") or \
        cfg.get("provider") or "openai"
    if provider not in DEFAULTS and provider != "custom":
        raise LLMError(f"unknown provider '{provider}'. Choose from: "
                       + ", ".join(list(DEFAULTS) + ["custom"]))
    d = DEFAULTS.get(provider, {"base": base_url, "model": model, "env": None})
    model = model or os.environ.get("FORGE3D_MODEL") or cfg.get("model") or d["model"]
    api_key = api_key or os.environ.get("FORGE3D_API_KEY") or \
        cfg.get("api_key") or (os.environ.get(d["env"]) if d["env"] else None)
    base_url = base_url or cfg.get("base_url") or d["base"]
    if provider == "ollama" or (base_url and "localhost" in base_url):
        api_key = api_key or "local"
    if not api_key:
        raise LLMError(
            f"No API key for provider '{provider}'. Set it via "
            f"`config/forge3d.config.json` ({'{"provider": "...", "api_key": "..."}'})"
            f" or env var {d.get('env') or 'FORGE3D_API_KEY'}. "
            "Local option: install Ollama and use --provider ollama (free, offline).")
    return {"provider": provider, "model": model, "api_key": api_key,
            "base_url": base_url}


def _http_json(url, headers, payload, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={**headers, "Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:800]
        raise LLMError(f"HTTP {e.code} from provider: {body}")
    except Exception as e:
        raise LLMError(f"request failed: {e}")


def chat(messages, system=None, provider=None, model=None, api_key=None,
         base_url=None, temperature=0.4, max_tokens=4000):
    """messages: list of {'role': 'user'|'assistant', 'content': str}.
    Returns assistant text."""
    r = resolve(provider, model, api_key, base_url)
    if r["provider"] == "anthropic":
        payload = {"model": r["model"], "max_tokens": max_tokens,
                   "messages": messages, "temperature": temperature}
        if system:
            payload["system"] = system
        data = _http_json(r["base_url"] + "/messages",
                          {"x-api-key": r["api_key"],
                           "anthropic-version": "2023-06-01"}, payload)
        return "".join(b.get("text", "") for b in data.get("content", []))
    # OpenAI-compatible (openai, openrouter, ollama, custom)
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    headers = {"Authorization": f"Bearer {r['api_key']}"}
    payload = {"model": r["model"], "messages": msgs,
               "temperature": temperature, "max_tokens": max_tokens}
    data = _http_json(r["base_url"] + "/chat/completions", headers, payload)
    return data["choices"][0]["message"]["content"]
