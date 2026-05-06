import os
from pathlib import Path
from typing import Dict, List

from PIL import Image

try:
    from surya.foundation import FoundationPredictor
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor
except Exception:
    FoundationPredictor = None
    RecognitionPredictor = None
    DetectionPredictor = None


_SURYA_READY = False
_foundation_predictor = None
_recognition_predictor = None
_detection_predictor = None


def _ensure_surya_loaded():
    global _SURYA_READY
    global _foundation_predictor
    global _recognition_predictor
    global _detection_predictor

    if _SURYA_READY:
        return

    if FoundationPredictor is None:
        raise ImportError(
            "Surya OCR is not installed. Run:\n"
            "pip install git+https://github.com/VikParuchuri/surya.git"
        )

    os.environ.setdefault("TORCH_DEVICE", "cpu")
    os.environ.setdefault("RECOGNITION_BATCH_SIZE", "8")

    _foundation_predictor = FoundationPredictor()
    _recognition_predictor = RecognitionPredictor(_foundation_predictor)
    _detection_predictor = DetectionPredictor()

    _SURYA_READY = True


def _normalize_polygon(poly):
    if poly is None:
        return None
    try:
        if hasattr(poly, "tolist"):
            return poly.tolist()
        return list(poly)
    except Exception:
        return poly


def _normalize_bbox(bbox):
    if bbox is None:
        return None
    try:
        if hasattr(bbox, "tolist"):
            return bbox.tolist()
        return list(bbox)
    except Exception:
        return bbox


def _pil_from_path(path: Path):
    img = Image.open(path)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")

    return img


def _prediction_to_page_data(prediction):
    text_lines = []
    lines = getattr(prediction, "text_lines", None) or []

    for line in lines:
        text_lines.append({
            "text": getattr(line, "text", "") or "",
            "confidence": float(getattr(line, "confidence", 0.0) or 0.0),
            "polygon": _normalize_polygon(getattr(line, "polygon", None)),
            "bbox": _normalize_bbox(getattr(line, "bbox", None)),
        })

    full_text = "\n".join(
        line["text"].strip()
        for line in text_lines
        if line["text"].strip()
    ).strip()

    return {
        "page": 0,
        "text": full_text,
        "text_lines": text_lines,
    }


def _run_surya_on_single_image(image_path: Path) -> Dict:
    _ensure_surya_loaded()

    image = _pil_from_path(image_path)

    predictions = _recognition_predictor(
        [image],
        det_predictor=_detection_predictor
    )

    if not predictions:
        raise ValueError(f"No OCR predictions returned for {image_path.name}")

    prediction = predictions[0]
    page_data = _prediction_to_page_data(prediction)

    return {
        "text": page_data["text"],
        "pages": [page_data],
        "raw": {
            image_path.stem: [
                {
                    "page": 0,
                    "text_lines": page_data["text_lines"]
                }
            ]
        }
    }


def run_local_surya_ocr(processed_pages: List[dict]) -> dict:
    versions = {
        "orig": {"pages": [], "text": ""},
        "P": {"pages": [], "text": ""},
        "M": {"pages": [], "text": ""},
    }

    failures = {}

    for page_index, page in enumerate(processed_pages, start=1):
        for version_name, file_key in [("orig", "orig"), ("P", "P"), ("M", "M")]:
            image_path = Path(page[file_key])

            try:
                result = _run_surya_on_single_image(image_path)

                page_entry = {
                    "page": page_index,
                    "text": result["text"],
                    "text_lines": result["pages"][0]["text_lines"],
                }

                versions[version_name]["pages"].append(page_entry)

                if result["text"].strip():
                    if versions[version_name]["text"].strip():
                        versions[version_name]["text"] += f"\n\n=== PAGE {page_index} ===\n"
                    versions[version_name]["text"] += result["text"].strip()

            except Exception as e:
                failures[f"{version_name}_page_{page_index}"] = str(e)

    return {
        "success": True,
        "engine": "local_surya",
        "versions": versions,
        "failures": failures,
    }