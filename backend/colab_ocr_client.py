import os
import requests


def send_images_to_colab_ocr(processed_pages: list[dict], colab_url: str = None) -> dict:
    final_colab_url = (colab_url or os.getenv("COLAB_OCR_URL", "")).strip()

    if not final_colab_url:
        raise ValueError("COLAB_OCR_URL is empty. Please set it before running the backend.")

    url = final_colab_url.rstrip("/") + "/ocr"

    opened_files = []
    multipart_files = []

    try:
        for idx, page in enumerate(processed_pages, start=1):
            orig_file = open(page["orig"], "rb")
            p_file = open(page["P"], "rb")
            m_file = open(page["M"], "rb")

            opened_files.extend([orig_file, p_file, m_file])

            multipart_files.append(("orig", (f"page_{idx:03d}_orig.png", orig_file, "image/png")))
            multipart_files.append(("p_img", (f"page_{idx:03d}_p.png", p_file, "image/png")))
            multipart_files.append(("m_img", (f"page_{idx:03d}_m.png", m_file, "image/png")))

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