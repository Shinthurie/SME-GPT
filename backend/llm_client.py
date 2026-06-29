"""
Central LLM client — routes all inference through local Ollama.

Ollama must be running: `ollama serve`
Model must be pulled:   `ollama pull llama3`
"""

import hashlib
import os
import threading
import time
import requests

# ── In-process LLM response cache ────────────────────────────────────────────
# Caches pipeline LLM responses (OCR correction + extraction) so identical
# prompts (same document re-uploaded, same OCR text) skip the LLM entirely.
# TTL=1h, max=500 entries. Thread-safe via a simple lock.
_CACHE: dict[str, tuple[str, float]] = {}   # key → (response, expiry)
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECS = int(os.getenv("LLM_CACHE_TTL_SECS", "3600"))
_CACHE_MAX = int(os.getenv("LLM_CACHE_MAX_ENTRIES", "500"))


def _cache_key(prompt: str, system: str) -> str:
    return hashlib.sha256(f"{system}\x00{prompt}".encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and time.time() < entry[1]:
            return entry[0]
        if entry:
            del _CACHE[key]
    return None


def _cache_set(key: str, value: str) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            # Evict oldest quarter
            oldest = sorted(_CACHE.items(), key=lambda x: x[1][1])
            for k, _ in oldest[: _CACHE_MAX // 4]:
                del _CACHE[k]
        _CACHE[key] = (value, time.time() + _CACHE_TTL_SECS)

OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# CPU inference on llama3 8B is slow — allow up to 10 min per call
_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECS", "600"))

# ── DeepSeek (cloud) — used ONLY for the document-processing pipeline ─────────
# (OCR correction + field extraction). Querying/answering stays on Ollama (the
# finetuned model) via call_llm(). DeepSeek's API is OpenAI-compatible.
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL    = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
_DEEPSEEK_TIMEOUT = int(os.getenv("DEEPSEEK_TIMEOUT_SECS", "120"))
# Provider for the document pipeline: "deepseek" when a key is set, else "ollama".
PIPELINE_PROVIDER = os.getenv(
    "PIPELINE_LLM_PROVIDER", "deepseek" if DEEPSEEK_API_KEY else "ollama"
).strip().lower()


def call_llm(prompt: str, system: str = "", format: str | None = None) -> str:
    """
    Send a prompt to the local Ollama model and return the text response.

    Args:
        prompt:  The user-facing instruction / data.
        system:  Optional system message (strongly recommended for Llama 3).
        format:  Optional Ollama output format. Pass "json" to force the model
                 to emit a single syntactically valid JSON object (structured
                 output mode). Leave None for free-form text.

    Returns:
        The model's response text (stripped).

    Raises:
        Exception with a human-readable message on any failure.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 4096,
        },
    }
    if format:
        payload["format"] = format

    url = f"{OLLAMA_HOST}/api/chat"
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()

    except requests.exceptions.ConnectionError:
        raise Exception(
            "Cannot connect to Ollama. Make sure it is running: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise Exception(
            f"Ollama timed out after {_TIMEOUT}s. "
            "CPU inference is slow — try a smaller model or increase OLLAMA_TIMEOUT_SECS."
        )
    except requests.exceptions.HTTPError as e:
        raise Exception(f"Ollama HTTP error: {e}. Response: {response.text}")
    except (KeyError, ValueError) as e:
        raise Exception(f"Unexpected Ollama response format: {e}")


def _call_deepseek(prompt: str, system: str = "", format: str | None = None) -> str:
    """Send a prompt to DeepSeek's OpenAI-compatible chat API. Raises on failure."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0,
        "stream": False,
    }
    # DeepSeek JSON mode requires the word "json" to appear in the prompt/system;
    # our extraction prompts already instruct the model to emit JSON.
    if format == "json":
        payload["response_format"] = {"type": "json_object"}

    response = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        json=payload,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=_DEEPSEEK_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def call_pipeline_llm(prompt: str, system: str = "", format: str | None = None) -> str:
    """LLM entry point for the document-processing pipeline (OCR correction +
    field extraction). Routes to DeepSeek (cloud, fast) when configured, and
    falls back to local Ollama on any failure or when no key is set.

    Querying/answering does NOT use this — it stays on Ollama via call_llm()
    so the finetuned query model remains in the loop.

    Responses are cached for LLM_CACHE_TTL_SECS (default 1 h) so identical
    documents (re-uploads, test runs) skip the LLM entirely.
    """
    ck = _cache_key(prompt, system)
    cached = _cache_get(ck)
    if cached is not None:
        print("[LLM] Cache hit — skipping LLM call.", flush=True)
        return cached

    t0 = time.time()
    if PIPELINE_PROVIDER == "deepseek" and DEEPSEEK_API_KEY:
        try:
            result = _call_deepseek(prompt, system=system, format=format)
            print(f"[LLM] DeepSeek call in {time.time()-t0:.1f}s", flush=True)
            _cache_set(ck, result)
            return result
        except Exception as exc:
            print(
                f"[LLM] DeepSeek call failed ({exc}); falling back to Ollama.",
                flush=True,
            )
    result = call_llm(prompt, system=system, format=format)
    print(f"[LLM] Ollama call in {time.time()-t0:.1f}s", flush=True)
    _cache_set(ck, result)
    return result


def check_ollama_health() -> dict:
    """Return {ok: bool, model: str, error: str|None}."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        model_ready = any(OLLAMA_MODEL in m for m in models)
        return {
            "ok": model_ready,
            "model": OLLAMA_MODEL,
            "available_models": models,
            "error": None if model_ready else f"Model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}",
        }
    except Exception as e:
        return {"ok": False, "model": OLLAMA_MODEL, "available_models": [], "error": str(e)}
