"""
Central LLM client — routes inference to Gemini (preferred), DeepSeek, or local Ollama.

Priority:
  Pipeline tasks (OCR correction + extraction):
    PIPELINE_LLM_PROVIDER env var, defaulting to:
      gemini   if GEMINI_API_KEY is set
      deepseek if DEEPSEEK_API_KEY is set
      ollama   otherwise
  Query tasks (PAL planner + answer, Q&A):
    QUERY_LLM_PROVIDER env var, defaulting to:
      gemini if GEMINI_API_KEY is set
      ollama otherwise

Fine-tuned model endpoints (set after Vertex AI fine-tuning completes):
  GEMINI_TUNED_EXTRACTION_MODEL — e.g. "tunedModels/sme-gpt-extraction-v1"
  GEMINI_TUNED_QUERY_MODEL      — e.g. "tunedModels/sme-gpt-query-v1"
  When unset, the base GEMINI_MODEL is used for both tasks.
"""

import hashlib
import os
import threading
import time
import requests

# ── In-process LLM response cache ─────────────────────────────────────────────
_CACHE: dict[str, tuple[str, float]] = {}
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
            oldest = sorted(_CACHE.items(), key=lambda x: x[1][1])
            for k, _ in oldest[: _CACHE_MAX // 4]:
                del _CACHE[k]
        _CACHE[key] = (value, time.time() + _CACHE_TTL_SECS)


# ── Ollama ─────────────────────────────────────────────────────────────────────
OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
_OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECS", "600"))

# ── Gemini (Google AI Studio key / Vertex AI) ──────────────────────────────────
GEMINI_API_KEY               = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL                 = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_TUNED_EXTRACTION_MODEL = os.getenv("GEMINI_TUNED_EXTRACTION_MODEL", "").strip()
GEMINI_TUNED_QUERY_MODEL      = os.getenv("GEMINI_TUNED_QUERY_MODEL", "").strip()
_GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT_SECS", "60"))

# ── DeepSeek (cloud, OpenAI-compatible) ───────────────────────────────────────
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL    = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
_DEEPSEEK_TIMEOUT = int(os.getenv("DEEPSEEK_TIMEOUT_SECS", "120"))

# ── Provider selection ─────────────────────────────────────────────────────────
_default_pipeline = (
    "gemini"   if GEMINI_API_KEY else
    "deepseek" if DEEPSEEK_API_KEY else
    "ollama"
)
PIPELINE_PROVIDER = os.getenv("PIPELINE_LLM_PROVIDER", _default_pipeline).strip().lower()

_default_query = "gemini" if GEMINI_API_KEY else "ollama"
QUERY_PROVIDER = os.getenv("QUERY_LLM_PROVIDER", _default_query).strip().lower()


# ── Gemini caller ──────────────────────────────────────────────────────────────

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _call_gemini(
    prompt: str,
    system: str = "",
    format: str | None = None,
    model_override: str = "",
) -> str:
    """Call Gemini via direct REST API — no google-generativeai SDK required.

    model_override: tuned model ID (e.g. 'tunedModels/sme-gpt-extraction-v1').
    format='json': requests JSON output via response_mime_type.
    """
    model_name = model_override or GEMINI_MODEL
    url = f"{_GEMINI_API_BASE}/models/{model_name}:generateContent?key={GEMINI_API_KEY}"

    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system}"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    generation_config: dict = {"temperature": 0, "maxOutputTokens": 4096}
    if format == "json":
        generation_config["responseMimeType"] = "application/json"

    payload = {"contents": contents, "generationConfig": generation_config}

    try:
        resp = requests.post(url, json=payload, timeout=_GEMINI_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.exceptions.HTTPError as e:
        err = resp.json().get("error", {})
        raise Exception(f"Gemini API error ({model_name}): {err.get('message', e)}")
    except Exception as e:
        raise Exception(f"Gemini call failed ({model_name}): {e}")


# ── DeepSeek caller ────────────────────────────────────────────────────────────

def _call_deepseek(prompt: str, system: str = "", format: str | None = None) -> str:
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


# ── Ollama caller ──────────────────────────────────────────────────────────────

def _call_ollama(prompt: str, system: str = "", format: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 4096},
    }
    if format:
        payload["format"] = format

    url = f"{OLLAMA_HOST}/api/chat"
    try:
        response = requests.post(url, json=payload, timeout=_OLLAMA_TIMEOUT)
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot connect to Ollama. Make sure it is running: ollama serve")
    except requests.exceptions.Timeout:
        raise Exception(
            f"Ollama timed out after {_OLLAMA_TIMEOUT}s. "
            "CPU inference is slow — try a smaller model or increase OLLAMA_TIMEOUT_SECS."
        )
    except requests.exceptions.HTTPError as e:
        raise Exception(f"Ollama HTTP error: {e}. Response: {response.text}")
    except (KeyError, ValueError) as e:
        raise Exception(f"Unexpected Ollama response format: {e}")


# ── Public entry points ────────────────────────────────────────────────────────

def call_llm(prompt: str, system: str = "", format: str | None = None) -> str:
    """Q&A / PAL planning / answer generation.

    Routes to Gemini (with tuned query model if set) when GEMINI_API_KEY is
    configured; falls back to Ollama on any failure or when no key is set.
    Responses are NOT cached here — the caller should cache if needed.
    """
    if QUERY_PROVIDER == "gemini" and GEMINI_API_KEY:
        try:
            t0 = time.time()
            result = _call_gemini(
                prompt, system=system, format=format,
                model_override=GEMINI_TUNED_QUERY_MODEL,
            )
            print(f"[LLM] Gemini query call in {time.time()-t0:.1f}s "
                  f"(model: {GEMINI_TUNED_QUERY_MODEL or GEMINI_MODEL})", flush=True)
            return result
        except Exception as exc:
            print(f"[LLM] Gemini query failed ({exc}); falling back to Ollama.", flush=True)

    return _call_ollama(prompt, system=system, format=format)


def call_pipeline_llm(prompt: str, system: str = "", format: str | None = None) -> str:
    """Document pipeline LLM (OCR correction + field extraction).

    Routes to:
      1. Gemini (tuned extraction model if set)  — when PIPELINE_PROVIDER=gemini
      2. DeepSeek                                — when PIPELINE_PROVIDER=deepseek
      3. Ollama                                  — fallback / offline
    Responses are cached (TTL=1h) so identical documents skip the LLM.
    """
    ck = _cache_key(prompt, system)
    cached = _cache_get(ck)
    if cached is not None:
        print("[LLM] Cache hit — skipping pipeline LLM call.", flush=True)
        return cached

    t0 = time.time()

    if PIPELINE_PROVIDER == "gemini" and GEMINI_API_KEY:
        try:
            result = _call_gemini(
                prompt, system=system, format=format,
                model_override=GEMINI_TUNED_EXTRACTION_MODEL,
            )
            print(f"[LLM] Gemini pipeline call in {time.time()-t0:.1f}s "
                  f"(model: {GEMINI_TUNED_EXTRACTION_MODEL or GEMINI_MODEL})", flush=True)
            _cache_set(ck, result)
            return result
        except Exception as exc:
            print(f"[LLM] Gemini pipeline failed ({exc}); trying next provider.", flush=True)

    if DEEPSEEK_API_KEY and PIPELINE_PROVIDER in ("deepseek", "gemini"):
        try:
            result = _call_deepseek(prompt, system=system, format=format)
            print(f"[LLM] DeepSeek pipeline call in {time.time()-t0:.1f}s", flush=True)
            _cache_set(ck, result)
            return result
        except Exception as exc:
            print(f"[LLM] DeepSeek pipeline failed ({exc}); falling back to Ollama.", flush=True)

    result = _call_ollama(prompt, system=system, format=format)
    print(f"[LLM] Ollama pipeline call in {time.time()-t0:.1f}s", flush=True)
    _cache_set(ck, result)
    return result


def check_ollama_health() -> dict:
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


def check_gemini_health() -> dict:
    if not GEMINI_API_KEY:
        return {"ok": False, "model": GEMINI_MODEL, "error": "GEMINI_API_KEY not set"}
    try:
        _call_gemini("Hello", model_override="")
        return {
            "ok": True,
            "model": GEMINI_TUNED_QUERY_MODEL or GEMINI_MODEL,
            "pipeline_model": GEMINI_TUNED_EXTRACTION_MODEL or GEMINI_MODEL,
            "error": None,
        }
    except Exception as e:
        return {"ok": False, "model": GEMINI_MODEL, "error": str(e)}
