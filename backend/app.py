import asyncio
import os
import json
import shutil
import tempfile
import threading
import uuid
from copy import deepcopy
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()  # must run before any local module is imported so env vars are set

import jwt
import psycopg
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from document_pipeline import process_uploaded_document
from dataset_manager import (
    upsert_confirmed_record,
    save_input_json,
    find_duplicate_record,
    load_all_records,
    get_record_by_id_for_user,
    update_record_for_user,
    delete_record_for_user,
)
from ai_helper import generate_explainable_answer
from data_tools import analyze_financial_query

JWT_SECRET = os.getenv("JWT_SECRET", "your_super_secret_key_123")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_4PXZCgONkeL8@ep-proud-bird-a1wq695o.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
)

app = FastAPI(title="SME-GPT Financial Document Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.56.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSING_SESSIONS: Dict[str, Dict[str, Any]] = {}

SAVED_DOCS_DIR = Path("saved_documents")
SAVED_DOCS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/saved-documents", StaticFiles(directory=str(SAVED_DOCS_DIR)), name="saved-documents")


# =========================
# DB HELPERS
# =========================
def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg.connect(DATABASE_URL)


def ensure_query_history_table():
    if not DATABASE_URL:
        return

    query = """
    CREATE TABLE IF NOT EXISTS query_history (
        id UUID PRIMARY KEY,
        user_id TEXT NOT NULL,
        company_name TEXT,
        question TEXT NOT NULL,
        answer TEXT,
        explanation TEXT,
        metrics JSONB,
        evidence JSONB,
        source_file TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()


@app.on_event("startup")
def startup_event():
    try:
        ensure_query_history_table()
        print("[DB] Query history table ready", flush=True)
    except Exception as e:
        print(f"[DB] Query history table init skipped/failed: {e}", flush=True)


def save_query_history_to_db(
    user_id: str,
    company_name: str,
    question: str,
    answer: str,
    explanation: str,
    metrics: dict,
    evidence: list,
    source_file: str,
):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")

    history_id = str(uuid.uuid4())

    query = """
    INSERT INTO query_history (
        id, user_id, company_name, question, answer, explanation, metrics, evidence, source_file
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    history_id,
                    str(user_id),
                    company_name,
                    question,
                    answer,
                    explanation,
                    json.dumps(metrics, ensure_ascii=False),
                    json.dumps(evidence, ensure_ascii=False),
                    source_file,
                ),
            )
        conn.commit()

    return history_id


def load_query_history_for_user(user_id: str):
    if not DATABASE_URL:
        return []

    query = """
    SELECT id, company_name, question, answer, explanation, metrics, evidence, source_file, created_at
    FROM query_history
    WHERE user_id = %s
    ORDER BY created_at DESC
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(user_id),))
            rows = cur.fetchall()

    history = []
    for row in rows:
        history.append({
            "id": str(row[0]),
            "company_name": row[1] or "",
            "question": row[2] or "",
            "answer": row[3] or "",
            "explanation": row[4] or "",
            "metrics": row[5] or {},
            "evidence": row[6] or [],
            "source_file": row[7] or "",
            "created_at": row[8].isoformat() if row[8] else "",
        })
    return history


def get_query_history_item_for_user(user_id: str, history_id: str):
    query = """
    SELECT id, company_name, question, answer, explanation, metrics, evidence, source_file, created_at
    FROM query_history
    WHERE user_id = %s AND id = %s
    LIMIT 1
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(user_id), str(history_id)))
            row = cur.fetchone()

    if not row:
        return None

    return {
        "id": str(row[0]),
        "company_name": row[1] or "",
        "question": row[2] or "",
        "answer": row[3] or "",
        "explanation": row[4] or "",
        "metrics": row[5] or {},
        "evidence": row[6] or [],
        "source_file": row[7] or "",
        "created_at": row[8].isoformat() if row[8] else "",
    }


def delete_query_history_item_for_user(user_id: str, history_id: str):
    query = """
    DELETE FROM query_history
    WHERE user_id = %s AND id = %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(user_id), str(history_id)))
            deleted = cur.rowcount
        conn.commit()

    return deleted > 0


def clear_query_history_for_user(user_id: str):
    query = """
    DELETE FROM query_history
    WHERE user_id = %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(user_id),))
            deleted = cur.rowcount
        conn.commit()

    return deleted


# =========================
# AUTH HELPERS
# =========================
def get_current_user_id(authorization: str = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization format.")

    token = authorization.replace("Bearer ", "").strip()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId") or payload.get("id") or payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload.")

        return str(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


# =========================
# NORMALIZATION HELPERS
# =========================
def safe_text(value: Any, default: str = "NULL") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def safe_number(value: Any):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return "NULL"

    cleaned = (
        text.replace(",", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("LKR", "")
        .replace("$", "")
        .strip()
    )

    if not cleaned:
        return "NULL"

    try:
        return float(cleaned)
    except Exception:
        return "NULL"


def normalize_items(items: Any):
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue

        normalized.append({
            "description": safe_text(item.get("description", ""), default=""),
            "quantity": safe_number(item.get("quantity")),
            "unit_price": safe_number(item.get("unit_price")),
            "line_total": safe_number(item.get("line_total")),
        })
    return normalized


def to_preview_data(fields: dict) -> dict:
    arithmetic = fields.get("arithmetic_validation", {}) or {}

    return {
        "document_type": safe_text(fields.get("document_type")),
        "order_id": safe_text(fields.get("order_id")),
        "flow_type": safe_text(fields.get("flow_type")),
        "company_name": safe_text(fields.get("company_name")),
        "supplier_name": safe_text(fields.get("supplier_name")),
        "date": safe_text(fields.get("date")),
        "currency": safe_text(fields.get("currency")),
        "raw_total_amount": safe_number(fields.get("raw_total_amount")),
        "final_total_amount": safe_number(fields.get("final_total_amount")),
        "payable_amount": safe_number(fields.get("payable_amount")),
        "cash_return": safe_number(fields.get("cash_return")),
        "received_status": safe_text(fields.get("received_status")),
        "paid_status": safe_text(fields.get("paid_status")),
        "language": safe_text(fields.get("language", "unknown")),
        "items": normalize_items(fields.get("items", [])),
        "arithmetic_status": safe_text(fields.get("arithmetic_status", "not_checked")),
        "arithmetic_validation": arithmetic,
        "raw_text": safe_text(fields.get("raw_text"), default=""),
        "corrected_text": safe_text(fields.get("corrected_text"), default=""),
        "recommended_total_from_items": safe_number(fields.get("recommended_total_from_items")),
    }


def merge_edited_preview_into_fields(original_fields: dict, edited_preview: dict) -> dict:
    merged = deepcopy(original_fields)

    editable_keys = [
        "document_type",
        "order_id",
        "flow_type",
        "company_name",
        "supplier_name",
        "date",
        "currency",
        "raw_total_amount",
        "final_total_amount",
        "payable_amount",
        "cash_return",
        "received_status",
        "paid_status",
        "language",
        "items",
        "raw_text",
        "corrected_text",
    ]

    for key in editable_keys:
        if key not in edited_preview:
            continue

        if key == "items":
            merged[key] = normalize_items(edited_preview.get("items", []))
        elif key in {"raw_total_amount", "final_total_amount", "payable_amount", "cash_return"}:
            merged[key] = safe_number(edited_preview.get(key))
        else:
            merged[key] = safe_text(edited_preview.get(key))

    merged["status"] = "confirmed"
    return merged


# =========================
# DOCUMENT FILE HELPERS
# =========================
def get_saved_image_url(document_id: str):
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        path = SAVED_DOCS_DIR / f"{document_id}{ext}"
        if path.exists():
            return f"/saved-documents/{path.name}"
    return None


def save_document_image_from_session(session_meta: dict, document_id: str):
    src = session_meta.get("standard_image")
    if not src:
        return None

    src_path = Path(src)
    if not src_path.exists():
        return None

    ext = src_path.suffix.lower() if src_path.suffix else ".png"
    if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
        ext = ".png"

    dst = SAVED_DOCS_DIR / f"{document_id}{ext}"
    shutil.copy(src_path, dst)
    return f"/saved-documents/{dst.name}"


def build_document_detail(user_id: str, document_id: str):
    record = get_record_by_id_for_user(user_id=user_id, document_id=document_id)
    if not record:
        return None

    effective_flow = record.get("effective_flow_type") or record.get("flow_type")

    return {
        **record,
        "original_flow_type": record.get("flow_type"),
        "flow_type": effective_flow,
        "image_url": get_saved_image_url(document_id),
    }


def build_dashboard_summary(records: List[dict]):
    total = len(records)
    invoice = sum(1 for r in records if str(r.get("document_type", "")).strip().lower() == "invoice")
    receipt = sum(1 for r in records if str(r.get("document_type", "")).strip().lower() == "receipt")
    po = sum(1 for r in records if str(r.get("document_type", "")).strip().lower() == "po")
    dn = sum(1 for r in records if str(r.get("document_type", "")).strip().lower() == "dn")

    total_payable = 0.0
    total_receivable = 0.0

    for r in records:
        flow = str(r.get("flow_type", "")).strip().lower()
        amount = safe_number(r.get("payable_amount"))
        if amount == "NULL":
            amount = safe_number(r.get("final_total_amount"))
        if amount == "NULL":
            amount = safe_number(r.get("raw_total_amount"))
        amount = 0.0 if amount == "NULL" else float(amount)

        if flow == "payable":
            total_payable += amount
        elif flow == "receivable":
            total_receivable += amount

    return {
        "total_documents": total,
        "invoice_count": invoice,
        "receipt_count": receipt,
        "po_count": po,
        "dn_count": dn,
        "total_payable_amount": round(total_payable, 2),
        "total_receivable_amount": round(total_receivable, 2),
    }

def derive_effective_flow_type(flow_type: str, received_status: str, paid_status: str) -> str:
    flow = str(flow_type or "").strip().lower()
    received = str(received_status or "").strip().lower()
    paid = str(paid_status or "").strip().lower()

    if flow == "receivable" and received == "received":
        return "income"

    if flow == "payable" and paid == "paid":
        return "expense"

    return flow
# =========================
# REQUEST MODELS
# =========================
class ConfirmSaveRequest(BaseModel):
    session_id: str
    edited_preview: dict
    force_save: bool = False


class QueryRequest(BaseModel):
    company_name: str
    question: str


class UpdateDocumentRequest(BaseModel):
    company_name: Optional[str] = None
    supplier_name: Optional[str] = None
    date: Optional[str] = None
    document_type: Optional[str] = None
    order_id: Optional[str] = None
    flow_type: Optional[str] = None
    currency: Optional[str] = None
    raw_total_amount: Optional[Any] = None
    final_total_amount: Optional[Any] = None
    payable_amount: Optional[Any] = None
    cash_return: Optional[Any] = None
    received_status: Optional[str] = None
    paid_status: Optional[str] = None
    language: Optional[str] = None
    items: Optional[List[dict]] = None


# =========================
# ROUTES
# =========================
@app.get("/health")
def health():
    return {"success": True, "message": "Backend is running."}


@app.post("/process-document")
async def process_document(
    file: UploadFile = File(...),
    authorization: str = Header(default=None),
):
    user_id = get_current_user_id(authorization)
    temp_dir = tempfile.mkdtemp(prefix="smegpt_")

    try:
        if not file.filename:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No file uploaded."}
            )

        ext = Path(file.filename).suffix.lower()
        allowed_exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

        if ext not in allowed_exts:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Unsupported file type. Use PDF, PNG, JPG, JPEG, or WEBP."
                }
            )

        temp_file_path = os.path.join(temp_dir, file.filename)
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = process_uploaded_document(temp_file_path)
        fields = result["extracted_fields"]
        preview = to_preview_data(fields)

        session_id = str(uuid.uuid4())
        PROCESSING_SESSIONS[session_id] = {
            "user_id": user_id,
            "fields": fields,
            "preview": preview,
            "meta": {
                "uploaded_file": result.get("uploaded_file"),
                "standard_image": result.get("standard_image"),
                "selected_ocr_version": result.get("selected_ocr_version"),
                "ocr_scores": result.get("ocr_scores", {}),
                "ocr_failures": result.get("ocr_failures", {}),
            }
        }

        return {
            "success": True,
            "message": "Document processed successfully.",
            "session_id": session_id,
            "preview": preview,
            "meta": {
                "uploaded_file": result.get("uploaded_file"),
                "standard_image": result.get("standard_image"),
                "selected_ocr_version": result.get("selected_ocr_version"),
                "ocr_scores": result.get("ocr_scores", {}),
                "ocr_failures": result.get("ocr_failures", {}),
                "arithmetic_status": fields.get("arithmetic_status", "not_checked"),
                "arithmetic_validation": fields.get("arithmetic_validation", {}),
            }
        }

    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error while processing document: {str(e)}"}
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/process-document-stream")
async def process_document_stream(
    file: UploadFile = File(...),
    authorization: str = Header(default=None),
):
    user_id = get_current_user_id(authorization)
    content = await file.read()
    filename = file.filename or "document"

    ext = Path(filename).suffix.lower()
    if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        async def _bad_type():
            yield f"data: {json.dumps({'stage': 'error', 'step': 0, 'message': 'Unsupported file type. Use PDF, PNG, JPG, JPEG or WEBP.'})}\n\n"
        return StreamingResponse(_bad_type(), media_type="text/event-stream")

    progress_q: Queue = Queue()
    done_event = threading.Event()

    def emit(stage: str, step: int, message: str, **extra):
        progress_q.put({"stage": stage, "step": step, "message": message, **extra})

    def run():
        temp_dir = tempfile.mkdtemp(prefix="smegpt_")
        session_id = str(uuid.uuid4())
        try:
            temp_path = os.path.join(temp_dir, filename)
            with open(temp_path, "wb") as fh:
                fh.write(content)

            # Stage 1 — PDF / image conversion
            emit("pdf_conversion", 1, "Converting document to images…")

            from document_pipeline import (
                save_uploaded_file,
                standardize_to_images,
                preprocess_images,
                _normalize_multi_page_ocr_result,
                COLAB_OCR_URL as _COLAB_URL,
            )
            from colab_ocr_client import send_images_to_colab_ocr
            from local_surya_ocr_client import run_local_surya_ocr
            from ocr_selector import select_best_ocr_version
            from llm_correction import llm_refine_text, clean_ocr_text
            from ocr_to_json_extractor import extract_structured_json_from_text
            from arithmetic_validator import validate_arithmetic
            from correction_engine import correct_extracted_fields

            raw_file = save_uploaded_file(temp_path)
            orig_images = standardize_to_images(raw_file)
            processed_pages = preprocess_images(orig_images)

            if not processed_pages:
                emit("error", 1, "No pages found in the uploaded document.")
                return

            # Stage 2 — OCR
            colab_url = _COLAB_URL or os.getenv("COLAB_OCR_URL", "").strip()
            page_count = len(processed_pages)

            if colab_url:
                emit("ocr", 2, f"Running Colab OCR on {page_count} page(s)…")
                try:
                    ocr_result = send_images_to_colab_ocr(processed_pages, colab_url)
                except Exception as ocr_err:
                    emit("ocr", 2, f"Colab OCR failed ({ocr_err}) — switching to local OCR…")
                    ocr_result = run_local_surya_ocr(processed_pages)
            else:
                emit("ocr", 2, f"Running local OCR on {page_count} page(s)…")
                ocr_result = run_local_surya_ocr(processed_pages)

            normalized = _normalize_multi_page_ocr_result(ocr_result)
            versions = normalized.get("versions", {})
            failures = normalized.get("failures", {})

            if not versions:
                emit("error", 2, f"OCR returned no usable text. Failures: {failures}")
                return

            selection = select_best_ocr_version(versions)
            selected_version = selection["selected_version"]
            selected_text = selection["selected_text"]

            if not selected_text.strip():
                failure_detail = ""
                if failures:
                    sample = list(failures.items())[:3]
                    failure_detail = " | ".join(f"{k}: {str(v)[:120]}" for k, v in sample)
                emit("error", 2,
                     f"OCR returned empty text. "
                     f"{'Failure details: ' + failure_detail if failure_detail else 'No text was extracted — check that COLAB_OCR_URL is set to your live ngrok URL and the Colab notebook is running.'}"
                )
                return

            selected_text = clean_ocr_text(selected_text)

            # Stage 3 — LLM correction
            emit("llm_correction", 3, "Correcting OCR text with LLM…")
            corrected_text = llm_refine_text(selected_text)

            # Stage 4 — Structured extraction
            emit("extraction", 4, "Extracting structured fields…")
            extracted_json = extract_structured_json_from_text(selected_text)
            extracted_json["document_type"] = (
                str(extracted_json.get("document_type", "unknown")).strip().lower() or "unknown"
            )
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
                if recommended.get("final_total_amount") is not None:
                    extracted_json["final_total_amount"] = recommended["final_total_amount"]
                if recommended.get("payable_amount") is not None:
                    extracted_json["payable_amount"] = recommended["payable_amount"]

            preview = to_preview_data(extracted_json)

            PROCESSING_SESSIONS[session_id] = {
                "user_id": user_id,
                "fields": extracted_json,
                "preview": preview,
                "meta": {
                    "uploaded_file": str(raw_file),
                    "standard_image": processed_pages[0]["orig"],
                    "selected_ocr_version": selected_version,
                    "ocr_scores": selection.get("scores", {}),
                    "ocr_failures": failures,
                },
            }

            emit(
                "done", 4, "Processing complete.",
                session_id=session_id,
                preview=preview,
                meta={
                    "uploaded_file": str(raw_file),
                    "standard_image": processed_pages[0]["orig"],
                    "selected_ocr_version": selected_version,
                    "ocr_scores": selection.get("scores", {}),
                    "ocr_failures": failures,
                    "arithmetic_status": extracted_json.get("arithmetic_status"),
                    "arithmetic_validation": extracted_json.get("arithmetic_validation", {}),
                },
            )

        except Exception as exc:
            import traceback
            emit("error", 0, str(exc), trace=traceback.format_exc())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            done_event.set()

    threading.Thread(target=run, daemon=True).start()

    async def generate():
        while True:
            try:
                event = progress_q.get_nowait()
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("stage") in ("done", "error"):
                    break
            except Empty:
                if done_event.is_set() and progress_q.empty():
                    break
                await asyncio.sleep(0.05)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/confirm-save")
def confirm_save(payload: ConfirmSaveRequest, authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        session = PROCESSING_SESSIONS.get(payload.session_id)

        if not session:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Session expired or not found. Please process the document again."}
            )

        if str(session.get("user_id")) != str(user_id):
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "This processing session does not belong to the current user."}
            )

        original_fields = session["fields"]
        final_data = merge_edited_preview_into_fields(original_fields, payload.edited_preview)

        duplicate = find_duplicate_record(final_data, user_id=user_id)
        if duplicate and not payload.force_save:
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "duplicate_found": True,
                    "message": "Already we have this document.",
                    "existing_document_id": duplicate.get("document_id", "NULL")
                }
            )

        save_input_json(final_data, "last_confirmed.json")
        save_result = upsert_confirmed_record(final_data, user_id=user_id)

        document_id = save_result["record"]["document_id"]
        image_url = save_document_image_from_session(session["meta"], document_id)

        PROCESSING_SESSIONS.pop(payload.session_id, None)

        return {
            "success": True,
            "duplicate_found": bool(duplicate),
            "message": "Document saved successfully.",
            "document_id": document_id,
            "image_url": image_url,
            "action": save_result["action"],
            "record": save_result["record"]
        }

    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error while saving document: {str(e)}"}
        )


@app.put("/documents/{document_id}")
def update_document(document_id: str, payload: UpdateDocumentRequest, authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        update_data = payload.dict(exclude_unset=True)

        if "items" in update_data:
            update_data["items"] = normalize_items(update_data.get("items", []))

        for numeric_key in ["raw_total_amount", "final_total_amount", "payable_amount", "cash_return"]:
            if numeric_key in update_data:
                update_data[numeric_key] = safe_number(update_data[numeric_key])

        existing = get_record_by_id_for_user(user_id=user_id, document_id=document_id)
        if not existing:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Document not found."}
            )

        next_flow_type = update_data.get("flow_type", existing.get("flow_type", ""))
        next_received_status = update_data.get("received_status", existing.get("received_status", ""))
        next_paid_status = update_data.get("paid_status", existing.get("paid_status", ""))

        effective_flow_type = derive_effective_flow_type(
            next_flow_type,
            next_received_status,
            next_paid_status,
        )

        update_data["effective_flow_type"] = effective_flow_type

        flow_changed_message = ""
        if str(next_flow_type).strip().lower() == "receivable" and str(next_received_status).strip().lower() == "received":
            flow_changed_message = "Flow type changed from receivable to income because received_status is received."
        elif str(next_flow_type).strip().lower() == "payable" and str(next_paid_status).strip().lower() == "paid":
            flow_changed_message = "Flow type changed from payable to expense because paid_status is paid."

        updated = update_record_for_user(
            user_id=user_id,
            document_id=document_id,
            updates=update_data,
        )

        if not updated:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Document not found."}
            )

        return {
            "success": True,
            "message": "Document updated successfully.",
            "flow_change_message": flow_changed_message,
            "document": updated
        }

    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error while updating document: {str(e)}"}
        )

@app.delete("/documents/{document_id}")
def delete_document(document_id: str, authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)

        deleted = delete_record_for_user(
            user_id=user_id,
            document_id=document_id,
        )

        if not deleted:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Document not found."}
            )

        return {
            "success": True,
            "message": "Document deleted successfully.",
            "document_id": document_id,
        }

    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error while deleting document: {str(e)}"}
        )

@app.get("/documents")
def get_documents(authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        records = load_all_records(user_id=user_id)

        normalized_records = []
        for record in records:
            effective_flow = record.get("effective_flow_type") or record.get("flow_type")
            normalized_records.append({
                **record,
                "original_flow_type": record.get("flow_type"),
                "flow_type": effective_flow,
            })

        return {"success": True, "documents": normalized_records}
    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )


@app.get("/documents/{document_id}")
def get_document_by_id(document_id: str, authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        document = build_document_detail(user_id=user_id, document_id=document_id)

        if not document:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Document not found."}
            )

        return {"success": True, "document": document}
    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )


@app.get("/dashboard-summary")
def dashboard_summary(authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        records = load_all_records(user_id=user_id)
        summary = build_dashboard_summary(records)
        return {
            "success": True,
            "total": summary.get("total_documents", 0),
            "invoice": summary.get("invoice_count", 0),
            "receipt": summary.get("receipt_count", 0),
            "po": summary.get("po_count", 0),
            "dn": summary.get("dn_count", 0),
            "recent_documents": records[:5] if records else [],
            "total_payable_amount": summary.get("total_payable_amount", 0.0),
            "total_receivable_amount": summary.get("total_receivable_amount", 0.0),
        }
    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error while loading dashboard summary: {str(e)}"}
        )


@app.post("/ask-query")
def ask_query(payload: QueryRequest, authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)

        if not payload.company_name.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Company name is required."}
            )

        if not payload.question.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Question is required."}
            )

        analysis_result = analyze_financial_query(
            question=payload.question.strip(),
            company_name=payload.company_name.strip(),
            user_id=user_id,
        )

        answer_bundle = generate_explainable_answer(
            question=payload.question.strip(),
            company_name=payload.company_name.strip(),
            result=analysis_result,
        )

        history_saved = True
        history_error = ""
        history_id = None

        try:
            history_id = save_query_history_to_db(
                user_id=user_id,
                company_name=payload.company_name.strip(),
                question=payload.question.strip(),
                answer=analysis_result.get("direct_answer") or answer_bundle.get("short_answer", ""),
                explanation=analysis_result.get("explanation", ""),
                metrics=analysis_result.get("metrics", {}),
                evidence=analysis_result.get("evidence", []),
                source_file=analysis_result.get("source_file", ""),
            )
        except Exception as save_err:
            history_saved = False
            history_error = str(save_err)

        return {
            "success": analysis_result.get("success", True),
            "company_name": payload.company_name.strip(),
            "question": payload.question.strip(),
            "answer": analysis_result.get("direct_answer") or answer_bundle.get("short_answer", ""),
            "explanation": answer_bundle.get("full_answer", analysis_result.get("explanation", "")),
            "evidence": analysis_result.get("evidence", []),
            "metrics": analysis_result.get("metrics", {}),
            "source_file": analysis_result.get("source_file", ""),
            "history_saved": history_saved,
            "history_error": history_error,
            "history_id": history_id,
        }

    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error while answering query: {str(e)}"}
        )


@app.get("/query-history")
def get_query_history(authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        history = load_query_history_for_user(user_id)
        return {"success": True, "history": history}
    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Failed to load query history: {str(e)}"}
        )


@app.get("/query-history/{history_id}")
def get_query_history_item(history_id: str, authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        item = get_query_history_item_for_user(user_id, history_id)

        if not item:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Query history item not found."}
            )

        return {"success": True, "item": item}
    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Failed to load query history item: {str(e)}"}
        )


@app.delete("/query-history/{history_id}")
def delete_query_history_item(history_id: str, authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        deleted = delete_query_history_item_for_user(user_id, history_id)

        if not deleted:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Query history item not found."}
            )

        return {"success": True, "message": "Query history deleted successfully."}
    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Failed to delete query history item: {str(e)}"}
        )


@app.delete("/query-history")
def clear_query_history(authorization: str = Header(default=None)):
    try:
        user_id = get_current_user_id(authorization)
        deleted_count = clear_query_history_for_user(user_id)
        return {
            "success": True,
            "message": "Query history cleared successfully.",
            "deleted_count": deleted_count,
        }
    except HTTPException as http_err:
        return JSONResponse(
            status_code=http_err.status_code,
            content={"success": False, "message": http_err.detail}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Failed to clear query history: {str(e)}"}
        )