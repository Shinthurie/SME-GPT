"""Supabase Storage client for document images.

Images were previously written only to the backend's local `saved_documents/`
folder, so they never persisted across machines/deployments (the Supabase
Postgres DB is shared, but the image files were not). This module uploads each
saved image to a Supabase Storage bucket and mints short-lived signed URLs for
viewing, so images display anywhere the shared DB is used.

Uses the Storage REST API directly via `requests` (already a dependency) — no
extra SDK. Every function degrades gracefully: if storage isn't configured or a
call fails, it returns False/None and the caller falls back to local disk.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

_SIGN_EXPIRES_SECS = int(os.getenv("SUPABASE_SIGN_EXPIRES_SECS", "3600"))
_TIMEOUT = 30

_IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp"]
_CONTENT_TYPE = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _clean(value: str) -> str:
    # .env values may carry surrounding quotes/whitespace (e.g. URL= "https://…").
    return (value or "").strip().strip('"').strip("'").strip()


def _url() -> str:
    return _clean(os.getenv("SUPABASE_URL", "")).rstrip("/")


def _key() -> str:
    return _clean(os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))


def _bucket() -> str:
    return _clean(os.getenv("SUPABASE_STORAGE_BUCKET", "documents")) or "documents"


def is_enabled() -> bool:
    """True only when URL, service-role key, and bucket are all configured."""
    return bool(_url() and _key() and _bucket())


def _headers(extra: dict | None = None) -> dict:
    key = _key()
    headers = {"Authorization": f"Bearer {key}", "apikey": key}
    if extra:
        headers.update(extra)
    return headers


def _object_name(document_id: str, ext: str) -> str:
    ext = ext.lower()
    if ext not in _IMAGE_EXTS:
        ext = ".png"
    return f"{document_id}{ext}"


def upload_image(local_path: str | Path, document_id: str) -> bool:
    """Upload (upsert) a local image file to the bucket under `<document_id><ext>`.

    Returns True on success, False on any failure (caller keeps the local copy).
    """
    if not is_enabled():
        return False
    path = Path(local_path)
    if not path.exists():
        return False

    ext = path.suffix.lower() if path.suffix.lower() in _IMAGE_EXTS else ".png"
    object_name = _object_name(document_id, ext)
    endpoint = f"{_url()}/storage/v1/object/{_bucket()}/{object_name}"
    try:
        data = path.read_bytes()
        resp = requests.post(
            endpoint,
            headers=_headers({
                "Content-Type": _CONTENT_TYPE.get(ext, "image/png"),
                "x-upsert": "true",
            }),
            data=data,
            timeout=_TIMEOUT,
        )
        return resp.status_code in (200, 201)
    except requests.RequestException as exc:
        print(f"[storage_client] upload failed for {document_id}: {exc}", flush=True)
        return False


def _find_object_name(document_id: str) -> str | None:
    """Locate the stored object for a document via the Storage list API.

    Returns the exact object name (e.g. "IN5.png") or None if not present.
    A single list call (rather than probing each extension) keeps view latency low.
    """
    endpoint = f"{_url()}/storage/v1/object/list/{_bucket()}"
    try:
        resp = requests.post(
            endpoint,
            headers=_headers({"Content-Type": "application/json"}),
            json={"prefix": "", "search": document_id, "limit": 100},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        wanted = {_object_name(document_id, ext) for ext in _IMAGE_EXTS}
        for item in resp.json() or []:
            name = item.get("name")
            if name in wanted:
                return name
    except (requests.RequestException, ValueError) as exc:
        print(f"[storage_client] list failed for {document_id}: {exc}", flush=True)
    return None


def get_signed_url(document_id: str) -> str | None:
    """Return a short-lived signed URL for the document's image, or None.

    Works for private buckets. Returns None when storage is disabled, the object
    doesn't exist, or signing fails.
    """
    if not is_enabled():
        return None
    object_name = _find_object_name(document_id)
    if not object_name:
        return None

    endpoint = f"{_url()}/storage/v1/object/sign/{_bucket()}/{object_name}"
    try:
        resp = requests.post(
            endpoint,
            headers=_headers({"Content-Type": "application/json"}),
            json={"expiresIn": _SIGN_EXPIRES_SECS},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        signed = resp.json().get("signedURL") or resp.json().get("signedUrl")
        if not signed:
            return None
        # signedURL is relative to /storage/v1 (e.g. "/object/sign/documents/IN5.png?token=…")
        if signed.startswith("/"):
            return f"{_url()}/storage/v1{signed}"
        return signed
    except (requests.RequestException, ValueError) as exc:
        print(f"[storage_client] sign failed for {document_id}: {exc}", flush=True)
        return None
