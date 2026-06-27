"""
Central LLM client — routes all inference through local Ollama.

Ollama must be running: `ollama serve`
Model must be pulled:   `ollama pull llama3`
"""

import os
import requests

OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# CPU inference on llama3 8B is slow — allow up to 10 min per call
_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECS", "600"))


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
