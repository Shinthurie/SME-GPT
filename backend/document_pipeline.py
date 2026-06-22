import os
import time
import shutil
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import cv2
from pdf2image import convert_from_path

from colab_ocr_client import send_images_to_colab_ocr
from ocr_selector import select_best_ocr_version
from llm_correction import llm_refine_text, clean_ocr_text
from ocr_to_json_extractor import extract_structured_json_from_text
from arithmetic_validator import validate_arithmetic
from correction_engine import correct_extracted_fields
from local_surya_ocr_client import run_local_surya_ocr

COLAB_OCR_URL = os.getenv("COLAB_OCR_URL", "").strip()
POPPLER_PATH = os.getenv("POPPLER_PATH", "")

TEMP_BASE = Path("temp_processing")
RAW_DIR = TEMP_BASE / "raw"
PAGES_DIR = TEMP_BASE / "pages"
ORIG_DIR = PAGES_DIR / "orig"
P_DIR = PAGES_DIR / "P"
M_DIR = PAGES_DIR / "M"

def ensure_dirs():
    for d in [RAW_DIR, ORIG_DIR, P_DIR, M_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _safe_remove_file(path: Path, retries: int = 5, delay: float = 0.3):
    for i in range(retries):
        try:
            if path.exists():
                path.unlink()
            return
        except PermissionError:
            if i == retries - 1:
                raise
            time.sleep(delay)


def _safe_remove_dir_contents(folder: Path):
    if not folder.exists():
        return

    for child in folder.iterdir():
        if child.is_file():
            _safe_remove_file(child)
        elif child.is_dir():
            shutil.rmtree(child, ignore_errors=True)


def clean_temp_files():
    ensure_dirs()
    for folder in [RAW_DIR, ORIG_DIR, P_DIR, M_DIR]:
        _safe_remove_dir_contents(folder)


def save_uploaded_file(upload_path: str) -> Path:
    ensure_dirs()

    src = Path(upload_path)
    if not src.exists():
        raise FileNotFoundError(f"Uploaded file not found: {upload_path}")

    # Clean only old files if needed, but do not wipe everything on every upload
    dst = RAW_DIR / src.name
    shutil.copy(src, dst)
    return dst

def standardize_to_images(raw_file_path: Path) -> list[Path]:
    output_paths: list[Path] = []

    if raw_file_path.suffix.lower() == ".pdf":
        if POPPLER_PATH:
            images = convert_from_path(str(raw_file_path), dpi=300, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_path(str(raw_file_path), dpi=300)

        if not images:
            raise ValueError("No pages found in uploaded PDF.")

        for i, image in enumerate(images, start=1):
            output_path = ORIG_DIR / f"page_{i:03d}.png"
            image.save(output_path, "PNG")
            output_paths.append(output_path)            
    else:
        output_path = ORIG_DIR / "page_001.png"
        shutil.copy(raw_file_path, output_path)
        output_paths.append(output_path)

    return output_paths

def preprocess_images(orig_paths: list[Path]) -> list[dict]:
    processed_pages = []
    for orig_path in orig_paths:
        filename = orig_path.name
        p_path = P_DIR / filename
        m_path = M_DIR / filename

        img = cv2.imread(str(orig_path))
        if img is None:
            raise ValueError(f"Failed to read standardized image: {orig_path}")

        h, w = img.shape[:2]

        target_w = 1600
        if w < target_w:
            scale = target_w / w
            img = cv2.resize(
                img,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_CUBIC
            )

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Printed-friendly version
        den = cv2.fastNlMeansDenoising(gray, None, 12, 7, 21)
        p_img = cv2.adaptiveThreshold(
            den,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            9
        )
        cv2.imwrite(str(p_path), p_img)

        # Messy-document-friendly version
        m_img = cv2.bilateralFilter(gray, 9, 60, 60)
        m_img = cv2.normalize(m_img, None, 0, 255, cv2.NORM_MINMAX)
        cv2.imwrite(str(m_path), m_img)

        processed_pages.append({
            "page_name": filename,
            "orig": str(orig_path),
            "P": str(p_path),
            "M": str(m_path),
        })

    return processed_pages


def _merge_page_texts(page_entries: list) -> str:
    merged_parts = []

    for idx, page_entry in enumerate(page_entries, start=1):
        if isinstance(page_entry, dict):
            page_text = str(page_entry.get("text", "") or "").strip()
        else:
            page_text = str(page_entry or "").strip()

        if not page_text:
            continue

        merged_parts.append(f"=== PAGE {idx} ===\n{page_text}")

    return "\n\n".join(merged_parts).strip()


def _normalize_multi_page_ocr_result(ocr_result: dict) -> dict:
    versions = ocr_result.get("versions", {}) or {}
    failures = ocr_result.get("failures", {}) or {}
    normalized_versions = {}

    for version_name, version_data in versions.items():
        if isinstance(version_data, dict):
            pages = version_data.get("pages", []) or []
            merged_text = version_data.get("text", "") or ""

            if pages and not merged_text.strip():
                merged_text = _merge_page_texts(pages)
            elif pages and merged_text.strip():
                merged_text = merged_text.strip()
            else:
                merged_text = str(merged_text or "").strip()

            normalized_versions[version_name] = {
                "text": merged_text,
                "pages": pages,
            }

        elif isinstance(version_data, list):
            merged_text = _merge_page_texts(version_data)
            normalized_versions[version_name] = {
                "text": merged_text,
                "pages": version_data,
            }
        else:
            normalized_versions[version_name] = {
                "text": str(version_data or "").strip(),
                "pages": [],
            }

    return {
        "versions": normalized_versions,
        "failures": failures,
    }
def build_preview_from_versions(version_paths: list[dict]) -> dict:
    final_colab_url = COLAB_OCR_URL or os.getenv("COLAB_OCR_URL", "").strip()

    if final_colab_url:
        try:
            print("[PIPELINE] Trying Colab OCR...", flush=True)
            ocr_result = send_images_to_colab_ocr(
                processed_pages=version_paths,
                colab_url=final_colab_url,
            )
            print("[PIPELINE] Colab OCR completed", flush=True)
        except Exception as e:
            print(f"[PIPELINE] Colab OCR failed: {e}", flush=True)
            print("[PIPELINE] Falling back to local Surya OCR...", flush=True)
            ocr_result = run_local_surya_ocr(version_paths)
            print("[PIPELINE] Local Surya OCR completed", flush=True)
    else:
        print("[PIPELINE] No COLAB_OCR_URL set — using local Surya OCR...", flush=True)
        ocr_result = run_local_surya_ocr(version_paths)
        print("[PIPELINE] Local Surya OCR completed", flush=True)

    normalized_ocr = _normalize_multi_page_ocr_result(ocr_result)
    versions = normalized_ocr.get("versions", {})
    failures = normalized_ocr.get("failures", {})

    if not versions:
        raise ValueError(f"No OCR versions returned from Colab OCR API. Failures: {failures}")

    selection = select_best_ocr_version(versions)

    selected_version = selection["selected_version"]
    selected_text = selection["selected_text"]

    if not selected_text.strip():
        raise ValueError("Selected OCR text is empty.")

    print("[PIPELINE] OCR selection finished", flush=True)
    selected_text = clean_ocr_text(selected_text)

    print("[PIPELINE] Starting LLM correction...", flush=True)
    corrected_text = llm_refine_text(selected_text)
    print("[PIPELINE] LLM correction finished", flush=True)
 
    print("[PIPELINE] Starting structured extraction...", flush=True)
    extracted_json = extract_structured_json_from_text(selected_text)
    print("[PIPELINE] Structured extraction finished", flush=True)

    extracted_json["document_type"] = str(
        extracted_json.get("document_type", "unknown")
    ).strip().lower() or "unknown"

    extracted_json["corrected_text"] = corrected_text
    extracted_json["raw_text"] = selected_text
    extracted_json["ocr_selected_version"] = selected_version
    extracted_json["ocr_scores"] = selection.get("scores", {})
    extracted_json["ocr_failures"] = failures

    extracted_json = correct_extracted_fields(extracted_json)

    arithmetic_validation = validate_arithmetic(extracted_json)
    extracted_json["arithmetic_validation"] = arithmetic_validation
    extracted_json["arithmetic_status"] = arithmetic_validation.get("status", "not_checked")

    recommended = arithmetic_validation.get("recommended", {}) or {}

    if extracted_json["arithmetic_status"] == "mismatch":
        # Keep raw total as extracted OCR value
        if recommended.get("final_total_amount") is not None:
            extracted_json["final_total_amount"] = recommended["final_total_amount"]

        if recommended.get("payable_amount") is not None:
            extracted_json["payable_amount"] = recommended["payable_amount"]

    return {
        "selected_ocr_version": selected_version,
        "selected_ocr_text": selected_text,
        "corrected_text": corrected_text,
        "extracted_fields": extracted_json,
        "ocr_scores": selection.get("scores", {}),
        "ocr_failures": failures,
    }

def process_uploaded_document(upload_path: str):
    raw_file = save_uploaded_file(upload_path)
    orig_images = standardize_to_images(raw_file)
    processed_pages = preprocess_images(orig_images)

    if not processed_pages:
        raise ValueError("No processed pages were created.")

    preview = build_preview_from_versions(processed_pages)

    return {
        "uploaded_file": str(raw_file),
        "standard_image": processed_pages[0]["orig"],
        "standard_images": [p["orig"] for p in processed_pages],
        "preprocessed_versions": processed_pages,
        "page_count": len(processed_pages),
        "selected_ocr_version": preview["selected_ocr_version"],
        "selected_ocr_text": preview["selected_ocr_text"],
        "corrected_text": preview["corrected_text"],
        "ocr_scores": preview.get("ocr_scores", {}),
        "ocr_failures": preview.get("ocr_failures", {}),
        "extracted_fields": preview["extracted_fields"],
    }