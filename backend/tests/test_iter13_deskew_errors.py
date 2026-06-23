"""Iteration 13 — Deskew preprocessing (GAP-F) + standardised error handling (GAP-I).

Deskew is tested directly against `document_pipeline._deskew_image()` with
synthetic numpy images (no real document fixture needed). The global error
handlers are tested against the real `app.py` via `TestClient` with
`raise_server_exceptions=False` -- otherwise the test client re-raises the
original exception instead of returning the handler's response, which would
defeat the point of testing what the *client* actually receives.
"""
from __future__ import annotations

import math
import os

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
except Exception:
    pass


@pytest.fixture(scope="module")
def app_module():
    import app as app_mod
    return app_mod


@pytest.fixture()
def client(app_module):
    return TestClient(app_module.app, raise_server_exceptions=False)


def _token(app_module, **claims):
    import jwt as pyjwt
    return pyjwt.encode(claims, app_module.JWT_SECRET, algorithm=app_module.JWT_ALGORITHM)


def _bearer(app_module, **claims):
    return f"Bearer {_token(app_module, **claims)}"


def _synthetic_doc_image(angle_deg: float = 0.0) -> np.ndarray:
    """A white canvas with black horizontal bars (text-line stand-ins),
    optionally rotated -- determine_skew() needs line-like structure to
    detect an angle, a blank or single-blob image won't do."""
    img = np.full((300, 300, 3), 255, dtype=np.uint8)
    for y in range(40, 260, 30):
        cv2.rectangle(img, (30, y), (270, y + 8), (0, 0, 0), -1)

    if angle_deg == 0.0:
        return img

    h, w = img.shape[:2]
    rot_mat = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(img, rot_mat, (w, h), borderValue=(255, 255, 255))


# ---------------------------------------------------------------------------
# Deskew (GAP-F)
# ---------------------------------------------------------------------------

def test_deskew_trivial_angle_unchanged():
    from document_pipeline import _deskew_image

    img = _synthetic_doc_image(0.0)
    out = _deskew_image(img)

    assert np.array_equal(out, img)


def test_deskew_5deg_rotation_corrected():
    from deskew import determine_skew
    from document_pipeline import _deskew_image

    img = _synthetic_doc_image(5.0)
    before_angle = determine_skew(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)) or 0.0

    out = _deskew_image(img)
    after_angle = determine_skew(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)) or 0.0

    assert abs(after_angle) < abs(before_angle)


# ---------------------------------------------------------------------------
# Standardised errors (GAP-I)
# ---------------------------------------------------------------------------

def test_error_response_model_shape(app_module):
    body = app_module.ErrorResponse(error_code="DOCUMENT_NOT_FOUND", message="not found").model_dump()

    assert body == {"success": False, "error_code": "DOCUMENT_NOT_FOUND", "message": "not found"}


def test_global_handler_hides_exception_message(client, app_module, monkeypatch):
    def _boom(user_id):
        raise RuntimeError("secret_path/db_connection_string_leak")

    monkeypatch.setattr(app_module, "load_all_records", _boom)

    resp = client.get("/documents", headers={"Authorization": _bearer(app_module, userId="user-1")})

    assert resp.status_code == 500
    body = resp.json()
    assert body == {
        "success": False,
        "error_code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred.",
    }
    assert "secret_path" not in resp.text


def test_404_maps_to_correct_error_code(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "build_document_detail", lambda user_id, document_id: None)

    resp = client.get("/documents/FAKE", headers={"Authorization": _bearer(app_module, userId="user-1")})

    assert resp.status_code == 404
    assert resp.json() == {
        "success": False,
        "error_code": "DOCUMENT_NOT_FOUND",
        "message": "Document not found.",
    }


def test_403_maps_to_forbidden_error_code(client, app_module):
    resp = client.delete(
        "/documents/INV1",
        headers={"Authorization": _bearer(app_module, userId="user-1", role="auditor")},
    )

    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN"
