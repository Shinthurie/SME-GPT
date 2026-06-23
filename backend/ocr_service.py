"""Pluggable OCR service interface (FR-08 — Iteration 2).

Wraps Colab (primary) and local Surya (fallback) behind a common ABC so the
pipeline can swap implementations without touching calling code.  The two
concrete clients remain importable standalone (Colab notebook, manual runs).
"""

from abc import ABC, abstractmethod


class OCRService(ABC):
    @abstractmethod
    def run(self, processed_pages: list) -> dict:
        """Run OCR on preprocessed page dicts; return the raw result dict."""
        ...


class ColabOCRService(OCRService):
    def __init__(self, url: str):
        self._url = url

    def run(self, processed_pages: list) -> dict:
        from colab_ocr_client import send_images_to_colab_ocr
        return send_images_to_colab_ocr(processed_pages, colab_url=self._url)


class LocalSuryaOCRService(OCRService):
    def run(self, processed_pages: list) -> dict:
        from local_surya_ocr_client import run_local_surya_ocr
        return run_local_surya_ocr(processed_pages)


def get_ocr_service(colab_url: str = "") -> OCRService:
    """Return the appropriate OCRService based on whether a Colab URL is set."""
    if colab_url.strip():
        return ColabOCRService(colab_url.strip())
    return LocalSuryaOCRService()
