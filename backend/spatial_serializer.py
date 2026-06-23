"""Component 2 — Layout-Aware Spatial Serialization (Iteration 3).

Takes the per-box safe-corrected OCR output (final_safe_boxes.json) produced by
Iteration 2 and produces a flat list of SpatialChunk dicts (spatial_chunks.json)
with deterministic row clustering, header detection, and template-based
classification.

Each SpatialChunk:
  chunk_id  : str        — "p{page}_r{row}" unique within the document
  type      : str        — "Header" | "KeyValue" | "LineItem" | "Text"
  page      : int        — 0-indexed page number
  bbox      : [x1,y1,x2,y2] — enclosing bbox of all boxes in the row
  text      : str        — space-joined text of all boxes in the row
  token_ids : list[int]  — indices into that page's safe_boxes list (provenance)
  header_ref: str|None   — chunk_id of the nearest Header row, or None for Headers
"""

import re
import statistics


# ── keyword sets ──────────────────────────────────────────────────────────────

_HEADER_KEYWORDS_EN = {
    "invoice", "invoices", "receipt", "receipts", "delivery", "note", "order",
    "purchase", "quotation", "statement", "proforma",
    "date", "no", "num", "number", "ref", "reference",
    "description", "item", "items", "product", "service",
    "qty", "quantity", "unit", "price", "rate", "amount", "total",
    "subtotal", "sub-total", "tax", "vat", "gst", "discount",
    "supplier", "customer", "buyer", "seller", "vendor",
    "payment", "due", "balance", "paid", "bill", "contact",
}

_HEADER_KEYWORDS_SI = {
    "ඉන්වොයිස්", "රිසිට්", "දිනය", "ඉදිරිපත", "ගෙවිය",
    "ලැබිය", "ප‍්‍රමාණය", "මිල", "එකතුව", "මුළු",
    "ගෙවීම", "සැපයුම්", "ප්‍රමාණය",
}


# ── bbox helpers ──────────────────────────────────────────────────────────────

def _bbox(box: dict) -> list:
    return box.get("bbox") or [0, 0, 0, 0]


def _y_center(box: dict) -> float:
    b = _bbox(box)
    return (b[1] + b[3]) / 2 if len(b) >= 4 else 0.0


def _x_center(box: dict) -> float:
    b = _bbox(box)
    return (b[0] + b[2]) / 2 if len(b) >= 4 else 0.0


def _x1(box: dict) -> float:
    b = _bbox(box)
    return b[0] if b else 0.0


def merge_bboxes(boxes: list) -> list:
    """Return the minimal enclosing [x1,y1,x2,y2] for a list of boxes."""
    valid = [_bbox(b) for b in boxes if len(_bbox(b)) >= 4]
    if not valid:
        return [0, 0, 0, 0]
    return [
        min(b[0] for b in valid),
        min(b[1] for b in valid),
        max(b[2] for b in valid),
        max(b[3] for b in valid),
    ]


# ── row clustering ────────────────────────────────────────────────────────────

def cluster_rows_by_y(boxes: list, gap_threshold: float = None) -> list:
    """Group boxes into rows using y-axis proximity.

    Algorithm:
      1. Sort boxes by y-center.
      2. Compute dynamic threshold = max(5px, 1.5 × median inter-center gap).
      3. A box joins the current row if its y-center is within the threshold
         of the previous row's maximum y-center; otherwise it starts a new row.
      4. Each row is sorted left-to-right by x1.

    The boxes may contain extra keys (e.g. _pg_idx) that are passed through
    unchanged.
    """
    if not boxes:
        return []

    sorted_boxes = sorted(boxes, key=_y_center)

    if gap_threshold is None:
        centers = [_y_center(b) for b in sorted_boxes]
        gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
        gap_threshold = (
            max(5.0, statistics.median(gaps) * 1.5) if gaps else 15.0
        )

    rows = [[sorted_boxes[0]]]
    for box in sorted_boxes[1:]:
        last_row_max_y = max(_y_center(b) for b in rows[-1])
        if _y_center(box) - last_row_max_y <= gap_threshold:
            rows[-1].append(box)
        else:
            rows.append([box])

    return [sorted(row, key=_x1) for row in rows]


# ── header detection ──────────────────────────────────────────────────────────

def _has_header_keyword(text: str) -> bool:
    lower = text.lower()
    words = set(re.sub(r"[^\w\s඀-෿]", " ", lower).split())
    if words & _HEADER_KEYWORDS_EN:
        return True
    for kw in _HEADER_KEYWORDS_SI:
        if kw in text:
            return True
    return False


def is_header_row(row: list) -> bool:
    """Return True if this row looks like a document or table header.

    Checks:
      - Any box text contains a known English or Sinhala header keyword.
      - Single all-caps word longer than 3 chars (e.g. "INVOICE", "RECEIPT").
    """
    texts = [b.get("text", "").strip() for b in row]
    combined = " ".join(texts)

    if _has_header_keyword(combined):
        return True

    # Single all-caps label (e.g. "INVOICE", "SUBTOTAL")
    if len(row) == 1 and texts[0].isupper() and len(texts[0]) > 3:
        return True

    return False


# ── row classification ────────────────────────────────────────────────────────

def _row_has_numbers(row: list) -> bool:
    return any(re.search(r"\d", b.get("text", "")) for b in row)


def classify_row(row: list, is_header: bool) -> str:
    """Classify a non-empty row into a chunk type.

    Rules (applied in order):
      Header   — is_header is True
      KeyValue — exactly 2 boxes (key: value pair)
      LineItem — 3+ boxes where at least one contains a digit (table row)
      Text     — everything else
    """
    if is_header:
        return "Header"
    n = len(row)
    if n == 2:
        return "KeyValue"
    if n >= 3 and _row_has_numbers(row):
        return "LineItem"
    return "Text"


# ── header binding ────────────────────────────────────────────────────────────

def bind_to_nearest_header(row_x_center: float, header_chunks: list) -> str | None:
    """Return the chunk_id of the Header whose x-center is nearest to row_x_center."""
    if not header_chunks:
        return None
    return min(
        header_chunks,
        key=lambda h: abs(h["_x_center"] - row_x_center),
    )["chunk_id"]


# ── main serializer ───────────────────────────────────────────────────────────

def serialize_safe_boxes(safe_boxes_by_page: list) -> list:
    """Produce a flat list of SpatialChunk dicts from per-page safe_boxes.

    safe_boxes_by_page: list[list[dict]]
      Outer list is pages (0-indexed), inner list is safe-box dicts as produced
      by correct_boxes_for_page() in llm_correction.py.

    Returns a flat list of SpatialChunk dicts sorted by page then row.
    """
    chunks = []
    header_chunks: list = []

    for page_idx, page_boxes in enumerate(safe_boxes_by_page or []):
        if not page_boxes:
            continue

        # Tag each box with its page-level index before clustering so we can
        # recover token_ids after rows are rearranged by y-sort.
        tagged = [{"_pg_idx": i, **b} for i, b in enumerate(page_boxes)]
        rows = cluster_rows_by_y(tagged)

        for row_idx, row in enumerate(rows):
            if not row:
                continue

            chunk_id = f"p{page_idx}_r{row_idx}"
            header = is_header_row(row)
            chunk_type = classify_row(row, header)
            row_x = statistics.mean(_x_center(b) for b in row)
            bbox = merge_bboxes(row)
            text = " ".join(
                b.get("text", "").strip()
                for b in row
                if b.get("text", "").strip()
            )
            token_ids = [b["_pg_idx"] for b in row]
            href = (
                None
                if chunk_type == "Header"
                else bind_to_nearest_header(row_x, header_chunks)
            )

            chunk = {
                "chunk_id": chunk_id,
                "type": chunk_type,
                "page": page_idx,
                "bbox": bbox,
                "text": text,
                "token_ids": token_ids,
                "header_ref": href,
            }
            chunks.append(chunk)

            if chunk_type == "Header":
                header_chunks.append({**chunk, "_x_center": row_x})

    return chunks
