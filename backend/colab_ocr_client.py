import os
import requests


# Which preprocessing variants to OCR. Colab runs OCR on every variant sent, so
# fewer variants = proportionally faster. "orig" is always sent (the server
# requires it). Extras default to the binarized "P" (printed-friendly) variant.
# Override with OCR_VARIANTS, e.g. "orig" (fastest, ~3x) or "orig,p_img,m_img" (max accuracy).
_VARIANT_FIELD_TO_KEY = {"p_img": "P", "m_img": "M"}


def _selected_extra_variants() -> list[str]:
    raw = os.getenv("OCR_VARIANTS", "orig,p_img")
    fields = {v.strip().lower() for v in raw.split(",") if v.strip()}
    # orig is mandatory and handled separately; keep only valid extras, preserve order
    return [f for f in ("p_img", "m_img") if f in fields]


def send_images_to_colab_ocr(processed_pages: list[dict], colab_url: str = None) -> dict:
    final_colab_url = (colab_url or os.getenv("COLAB_OCR_URL", "")).strip()

    if not final_colab_url:
        raise ValueError("COLAB_OCR_URL is empty. Please set it before running the backend.")

    url = final_colab_url.rstrip("/") + "/ocr"

    extra_variants = _selected_extra_variants()
    print(
        f"[COLAB-OCR] sending variants per page: {['orig'] + extra_variants} "
        f"({len(extra_variants) + 1} OCR pass(es)/page)",
        flush=True,
    )

    opened_files = []
    multipart_files = []

    try:
        for idx, page in enumerate(processed_pages, start=1):
            orig_file = open(page["orig"], "rb")
            opened_files.append(orig_file)
            multipart_files.append(("orig", (f"page_{idx:03d}_orig.png", orig_file, "image/png")))

            for field in extra_variants:
                variant_key = _VARIANT_FIELD_TO_KEY[field]
                vfile = open(page[variant_key], "rb")
                opened_files.append(vfile)
                multipart_files.append(
                    (field, (f"page_{idx:03d}_{field}.png", vfile, "image/png"))
                )

        response = requests.post(
            url,
            files=multipart_files,
            timeout=600,
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        raise Exception("Colab OCR API timed out.")
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Could not connect to Colab OCR API: {e}")
    except requests.exceptions.HTTPError as e:
        raise Exception(
            f"HTTP error from Colab OCR API: {e}\n"
            f"Response body: {response.text if 'response' in locals() else 'No response'}"
        )
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass