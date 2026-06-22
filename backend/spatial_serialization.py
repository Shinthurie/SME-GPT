"""Component 2 — Layout-Aware Spatial Serialization.

Runs after C1 (ocr_correction.py), before vector indexing and C3
(docs/components/component-2.md). Consumes the canonical box schema shared
with C1 (`text, bbox, confidence, label, page`, plus C1's `source`/
`locked_digits` and the table-cell fields `table_id/row_index/col_index` from
`ocr_service.boxes_from_surya_v2_page`) and turns it into deterministic,
template-based `SpatialChunk`s with full provenance. No LLM is involved here —
serialization is structural only.

Algorithm (component-2.md §"Algorithm"):
1. Row clustering (y-axis, dynamic threshold).
2. Header detection (English + Sinhala keywords).
3. Header -> row binding (x-axis nearest-center).
4. Template serialization (LineItem / KeyValue / Header / section_text).

Rule: never drop tokens — every input box ends up in exactly one chunk.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"

# component-2.md "Header detection" + "Canonical-field mapping"
HEADER_KEYWORDS: dict[str, str] = {
    # English
    "description": "description",
    "item": "item",
    "qty": "qty",
    "quantity": "qty",
    "unit price": "unit_price",
    "unitprice": "unit_price",
    "total": "total",
    "amount": "total",
    "tax": "tax",
    "vat": "tax",
    "no.": "item",
    # Sinhala
    "විස්තරය": "description",
    "ප්‍රමාණය": "qty",
    "ඒකක මිල": "unit_price",
    "මුළු": "total",
    "මුදල": "total",
    "බදු": "tax",
    "වැට්": "tax",
}

_KEY_VALUE_RE = re.compile(r"^\s*([^:]{1,40}):\s*(.+?)\s*$")


def _y_center(box: dict) -> float:
    return (box["bbox"][1] + box["bbox"][3]) / 2.0


def _x_center(box: dict) -> float:
    return (box["bbox"][0] + box["bbox"][2]) / 2.0


def _text_height(box: dict) -> float:
    return max(box["bbox"][3] - box["bbox"][1], 1e-6)


def cluster_rows(boxes: list[dict], alpha: float = 0.8) -> list[list[dict]]:
    """Group boxes into rows by vertical alignment (component-2.md step 2).

    `dynamic_y_threshold = median(text_height) * alpha`. Boxes within
    `threshold` of a row's running y-center join that row; otherwise they
    start a new row. Boxes are sorted by y then x first so rows come out in
    reading order and ties bind left-to-right.
    """
    if not boxes:
        return []

    heights = sorted(_text_height(b) for b in boxes)
    median_height = heights[len(heights) // 2]
    threshold = max(median_height * alpha, 1e-6)

    ordered = sorted(boxes, key=lambda b: (_y_center(b), _x_center(b)))

    rows: list[list[dict]] = []
    row_y_sum = 0.0
    for box in ordered:
        y = _y_center(box)
        if rows and abs(y - row_y_sum / len(rows[-1])) <= threshold:
            rows[-1].append(box)
            row_y_sum += y
        else:
            rows.append([box])
            row_y_sum = y

    for row in rows:
        row.sort(key=_x_center)
    return rows


def _match_header_keyword(text: str) -> str | None:
    """Match a header cell's text against a known keyword, anchored to word
    boundaries so short keywords (e.g. "no.") don't false-positive inside
    unrelated words (e.g. "now")."""
    normalized = text.strip().lower()
    if normalized in HEADER_KEYWORDS:
        return HEADER_KEYWORDS[normalized]
    for keyword, field in HEADER_KEYWORDS.items():
        pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"
        if re.search(pattern, normalized):
            return field
    return None


def detect_header_row(rows: list[list[dict]]) -> tuple[int | None, list[dict]]:
    """Find the row most likely to be a table header (component-2.md step 3).

    A row is a header candidate if at least half its cells match a known
    English/Sinhala keyword. Returns `(row_index, header_cells)` where each
    header cell carries its box plus the resolved `canonical_field`. Returns
    `(None, [])` if no row qualifies (component-2.md failure table: "No header
    detected -> positional row chunks only").
    """
    best_index, best_cells, best_score = None, [], 0.0
    for i, row in enumerate(rows):
        cells = []
        matches = 0
        for box in row:
            field = _match_header_keyword(box["text"])
            if field:
                matches += 1
            cells.append({**box, "canonical_field": field})
        score = matches / len(row) if row else 0.0
        if score >= 0.5 and score > best_score:
            best_index, best_cells, best_score = i, cells, score

    if best_index is None:
        return None, []
    return best_index, best_cells


def bind_row_to_headers(row: list[dict], header_cells: list[dict]) -> dict[str, dict]:
    """Assign each data box to its nearest header by x-center distance
    (component-2.md step 4). Ambiguous/columnless boxes fall back to
    `unknown_column_{n}` (component-2.md failure table: "Sparse/shifted
    columns -> unknown_column; preserve token order")."""
    fields: dict[str, dict] = {}
    unknown_count = 0
    for box in row:
        if not header_cells:
            key = f"unknown_column_{unknown_count}"
            unknown_count += 1
        else:
            nearest = min(header_cells, key=lambda h: abs(_x_center(h) - _x_center(box)))
            key = nearest.get("canonical_field") or nearest["text"].strip().lower() or "unknown_column"
            if key in fields:
                key = f"unknown_column_{unknown_count}"
                unknown_count += 1
        fields[key] = box
    return fields


def classify_key_value(row: list[dict]) -> dict | None:
    """A single-box row matching `Key: Value` is a KeyValue candidate
    (component-2.md template `KeyValue | {key}: {value}`)."""
    if len(row) != 1:
        return None
    match = _KEY_VALUE_RE.match(row[0]["text"])
    if not match:
        return None
    return {"key": match.group(1).strip(), "value": match.group(2).strip(), "box": row[0]}


_DISPLAY_NAMES = {
    "description": "Description",
    "item": "Item",
    "qty": "Qty",
    "unit_price": "UnitPrice",
    "total": "Total",
    "tax": "Tax",
    "discount": "Discount",
}


def _display_name(field_key: str) -> str:
    if field_key in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[field_key]
    return field_key.replace("_", " ").title()


def _has_digits(text: str) -> bool:
    return bool(re.search(r"\d", text or ""))


def _union_bbox(boxes: list[dict]) -> list[float]:
    return [
        min(b["bbox"][0] for b in boxes),
        min(b["bbox"][1] for b in boxes),
        max(b["bbox"][2] for b in boxes),
        max(b["bbox"][3] for b in boxes),
    ]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_header(chunk_id: str, header_id: str, table_id: str | None, header_cells: list[dict], page: int) -> dict:
    """Template: `Headers | {col1} | {col2} | ...` (component-2.md step 5)."""
    cols = [c["text"] for c in header_cells]
    token_bboxes = {c["_token_id"]: c["bbox"] for c in header_cells}
    return {
        "chunk_id": chunk_id,
        "chunk_type": "header",
        "table_id": table_id,
        "header_id": header_id,
        "text": "Headers | " + " | ".join(cols),
        "provenance": {"page": page, "bbox": _union_bbox(header_cells), "token_bboxes": token_bboxes},
        "metadata": {"source_component": "component_2", "created_at": _now_iso()},
    }


def serialize_line_item_row(
    chunk_id: str,
    row_id: str,
    header_id: str | None,
    table_id: str | None,
    fields: dict[str, dict],
    page: int,
    row_cluster_confidence: float = 1.0,
) -> dict:
    """Template: `LineItem | Description: {desc} | Qty: {qty} | ...`
    (component-2.md step 5). `fields` maps canonical field key -> bound box."""
    boxes = list(fields.values())
    field_entries: dict[str, dict] = {}
    token_bboxes: dict[str, list[float]] = {}
    text_parts: list[str] = []
    for key, box in fields.items():
        tok = box["_token_id"]
        token_bboxes[tok] = box["bbox"]
        entry = {"value": box["text"], "token_ids": [tok]}
        if _has_digits(box["text"]):
            entry["locked_digits"] = True
        field_entries[key] = entry
        text_parts.append(f"{_display_name(key)}: {box['text']}")

    confidences = [b.get("confidence", 1.0) for b in boxes]
    struct_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "chunk_id": chunk_id,
        "chunk_type": "line_item_row",
        "table_id": table_id,
        "row_id": row_id,
        "header_id": header_id,
        "text": "LineItem | " + " | ".join(text_parts),
        "fields": field_entries,
        "provenance": {"page": page, "bbox": _union_bbox(boxes), "token_bboxes": token_bboxes},
        "quality": {
            "struct_confidence": round(struct_confidence, 4),
            "header_bound": header_id is not None,
            "row_cluster_confidence": row_cluster_confidence,
        },
        "metadata": {"source_component": "component_2", "created_at": _now_iso()},
    }


def serialize_line_item_block(
    chunk_id: str,
    row_ids: list[str],
    header_id: str | None,
    table_id: str | None,
    rows_fields: list[dict[str, dict]],
    header_cells: list[dict],
    page: int,
) -> dict:
    """Chunking strategy for `row_count > 30` (component-2.md "Chunking
    strategy"): one chunk per 5-10 rows, header repeated inside each block."""
    header_line = "Headers | " + " | ".join(c["text"] for c in header_cells) if header_cells else "Headers |"
    row_lines = []
    token_bboxes: dict[str, list[float]] = {}
    all_boxes: list[dict] = []
    rows_out = []
    for row_id, fields in zip(row_ids, rows_fields):
        parts = []
        field_entries = {}
        for key, box in fields.items():
            tok = box["_token_id"]
            token_bboxes[tok] = box["bbox"]
            all_boxes.append(box)
            entry = {"value": box["text"], "token_ids": [tok]}
            if _has_digits(box["text"]):
                entry["locked_digits"] = True
            field_entries[key] = entry
            parts.append(f"{_display_name(key)}: {box['text']}")
        row_lines.append("LineItem | " + " | ".join(parts))
        rows_out.append({"row_id": row_id, "fields": field_entries})

    return {
        "chunk_id": chunk_id,
        "chunk_type": "line_item_block",
        "table_id": table_id,
        "header_id": header_id,
        "row_ids": row_ids,
        "rows": rows_out,
        "text": "\n".join([header_line, *row_lines]),
        "provenance": {"page": page, "bbox": _union_bbox(all_boxes), "token_bboxes": token_bboxes},
        "quality": {"header_bound": header_id is not None},
        "metadata": {"source_component": "component_2", "created_at": _now_iso()},
    }


def serialize_key_value(chunk_id: str, key: str, value: str, box: dict, page: int) -> dict:
    """Template: `KeyValue | {key}: {value}` (component-2.md step 5)."""
    tok = box["_token_id"]
    entry = {"value": value, "token_ids": [tok]}
    if _has_digits(value):
        entry["locked_digits"] = True
    return {
        "chunk_id": chunk_id,
        "chunk_type": "key_value",
        "text": f"KeyValue | {key}: {value}",
        "fields": {key: entry},
        "provenance": {"page": page, "bbox": box["bbox"], "token_bboxes": {tok: box["bbox"]}},
        "metadata": {"source_component": "component_2", "created_at": _now_iso()},
    }


def serialize_section_text(chunk_id: str, row: list[dict], page: int) -> dict:
    """Anything that isn't a header, line item, or key/value pair — preserved
    verbatim with provenance (component-2.md failure table: "never drop
    tokens")."""
    token_bboxes = {b["_token_id"]: b["bbox"] for b in row}
    return {
        "chunk_id": chunk_id,
        "chunk_type": "section_text",
        "text": " ".join(b["text"] for b in row),
        "provenance": {"page": page, "bbox": _union_bbox(row), "token_bboxes": token_bboxes},
        "metadata": {"source_component": "component_2", "created_at": _now_iso()},
    }


_BLOCK_ROW_THRESHOLD = 30
_BLOCK_SIZE = 8


def _chunk_row_groups(row_ids: list[str], rows_fields: list[dict]) -> list[tuple[list[str], list[dict]]]:
    """component-2.md "Chunking strategy": `row_count <= 30` -> one chunk per
    row; else blocks of 5-10 rows (header repeated inside each, handled by the
    caller)."""
    if len(row_ids) <= _BLOCK_ROW_THRESHOLD:
        return [([rid], [f]) for rid, f in zip(row_ids, rows_fields)]
    groups = []
    for i in range(0, len(row_ids), _BLOCK_SIZE):
        groups.append((row_ids[i:i + _BLOCK_SIZE], rows_fields[i:i + _BLOCK_SIZE]))
    return groups


def build_spatial_chunks(
    pages: list[dict],
    tenant_id: str,
    document_id: str,
    header_alpha: float = 0.8,
) -> dict:
    """Top-level C2 entry point. `pages` is the `final_safe_boxes.json` shape
    from C1 (`ocr_correction.correct_pages` / `write_final_safe_boxes`):
    `[{"page": n, "boxes": [canonical box, ...]}, ...]`.

    Returns the exact `spatial_chunks.json` top-level schema
    (docs/components/component-2.md "Output").
    """
    chunk_seq = 0
    languages: set[str] = set()
    pages_out = []

    for page_entry in pages:
        page_number = page_entry["page"]
        boxes = [dict(b) for b in page_entry.get("boxes", [])]
        for i, box in enumerate(boxes):
            box["_token_id"] = f"tok_p{page_number}_{i:03d}"
            languages.add("si" if re.search(r"[඀-෿]", box["text"]) else "en")

        rows = cluster_rows(boxes, alpha=header_alpha)
        header_index, header_cells = detect_header_row(rows)
        header_table_id = None
        if header_index is not None:
            ids = {b.get("table_id") for b in rows[header_index]} - {None}
            header_table_id = next(iter(ids), None)

        chunks: list[dict] = []
        table_counter = 0
        line_item_row_ids: list[str] = []
        line_item_fields: list[dict] = []

        def _flush_line_items(header_id: str | None, table_id: str | None):
            nonlocal chunk_seq
            for group_row_ids, group_fields in _chunk_row_groups(line_item_row_ids, line_item_fields):
                block_chunk_id = f"ch_{chunk_seq:06d}"
                chunk_seq += 1
                if len(group_row_ids) == 1:
                    chunks.append(serialize_line_item_row(
                        block_chunk_id, group_row_ids[0], header_id, table_id, group_fields[0], page_number,
                    ))
                else:
                    chunks.append(serialize_line_item_block(
                        block_chunk_id, group_row_ids, header_id, table_id, group_fields, header_cells, page_number,
                    ))
            line_item_row_ids.clear()
            line_item_fields.clear()

        header_id = f"hdr_{table_counter:02d}" if header_index is not None else None

        for row_index, row in enumerate(rows):
            if row_index == header_index:
                chunk_id = f"ch_{chunk_seq:06d}"
                chunk_seq += 1
                chunks.append(serialize_header(chunk_id, header_id, header_table_id, header_cells, page_number))
                continue

            row_table_ids = {b.get("table_id") for b in row} - {None}
            in_header_table = header_table_id is not None and header_table_id in row_table_ids

            if in_header_table:
                fields = bind_row_to_headers(row, header_cells)
                row_id = f"row_{row_index:03d}"
                line_item_row_ids.append(row_id)
                line_item_fields.append(fields)
                continue

            # Boundary of the table (or no header at all): flush any buffered
            # line-item rows before handling this row as KeyValue/section_text.
            if line_item_row_ids:
                _flush_line_items(header_id, header_table_id)

            if row_table_ids:
                # Table cells with no detected header -> positional row chunks
                # (component-2.md failure table: "No header detected").
                fields = bind_row_to_headers(row, [])
                chunk_id = f"ch_{chunk_seq:06d}"
                chunk_seq += 1
                chunks.append(serialize_line_item_row(
                    chunk_id, f"row_{row_index:03d}", None, next(iter(row_table_ids)), fields, page_number,
                ))
                continue

            kv = classify_key_value(row)
            chunk_id = f"ch_{chunk_seq:06d}"
            chunk_seq += 1
            if kv is not None:
                chunks.append(serialize_key_value(chunk_id, kv["key"], kv["value"], kv["box"], page_number))
            else:
                chunks.append(serialize_section_text(chunk_id, row, page_number))

        if line_item_row_ids:
            _flush_line_items(header_id, header_table_id)

        pages_out.append({"page": page_number, "chunks": chunks})

    return {
        "tenant_id": tenant_id,
        "document_id": document_id,
        "version": SCHEMA_VERSION,
        "language_hint": sorted(languages) or ["en"],
        "pages": pages_out,
    }
