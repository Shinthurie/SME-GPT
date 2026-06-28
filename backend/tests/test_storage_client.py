"""Hermetic tests for storage_client — Supabase Storage REST calls are faked."""
from __future__ import annotations

import storage_client as sc


def _configure(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", '"https://proj.supabase.co"')  # quoted on purpose
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "documents")


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
    def json(self):
        return self._payload


def test_clean_strips_quotes_and_whitespace():
    assert sc._clean('  "https://x" ') == "https://x"
    assert sc._clean("'abc'") == "abc"


def test_is_enabled_requires_all_three(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert sc.is_enabled() is False
    _configure(monkeypatch)
    assert sc.is_enabled() is True


def test_upload_image_posts_with_upsert(tmp_path, monkeypatch):
    _configure(monkeypatch)
    img = tmp_path / "IN5.png"
    img.write_bytes(b"\x89PNG fake")

    captured = {}

    def fake_post(url, headers=None, data=None, timeout=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        return _Resp(200)

    monkeypatch.setattr(sc.requests, "post", fake_post)

    assert sc.upload_image(img, "IN5") is True
    assert captured["url"] == "https://proj.supabase.co/storage/v1/object/documents/IN5.png"
    assert captured["headers"]["x-upsert"] == "true"
    assert captured["headers"]["Content-Type"] == "image/png"
    assert captured["headers"]["Authorization"] == "Bearer service-key"
    assert captured["data"] == b"\x89PNG fake"


def test_upload_image_noop_when_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    img = tmp_path / "IN5.png"
    img.write_bytes(b"x")
    assert sc.upload_image(img, "IN5") is False


def test_get_signed_url_lists_then_signs(monkeypatch):
    _configure(monkeypatch)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        calls.append(url)
        if "/object/list/" in url:
            return _Resp(200, [{"name": "IN5.png"}, {"name": "other.png"}])
        if "/object/sign/" in url:
            return _Resp(200, {"signedURL": "/object/sign/documents/IN5.png?token=abc"})
        return _Resp(404)

    monkeypatch.setattr(sc.requests, "post", fake_post)

    url = sc.get_signed_url("IN5")
    assert url == "https://proj.supabase.co/storage/v1/object/sign/documents/IN5.png?token=abc"
    assert any("/object/list/" in c for c in calls)
    assert any("/object/sign/documents/IN5.png" in c for c in calls)


def test_get_signed_url_none_when_object_missing(monkeypatch):
    _configure(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        if "/object/list/" in url:
            return _Resp(200, [{"name": "somethingelse.png"}])
        return _Resp(400)

    monkeypatch.setattr(sc.requests, "post", fake_post)
    assert sc.get_signed_url("IN5") is None


def test_get_signed_url_none_when_disabled(monkeypatch):
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert sc.get_signed_url("IN5") is None
