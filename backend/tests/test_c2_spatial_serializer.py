"""Iteration 3 — Component 2: spatial serialization unit tests.

Pure Python, no DB/LLM/OCR — runs in CI with no secrets.

Covers:
  - cluster_rows_by_y      (y-axis row clustering)
  - is_header_row          (keyword + heuristic header detection)
  - classify_row           (Header / KeyValue / LineItem / Text)
  - bind_to_nearest_header (x-center nearest-header lookup)
  - merge_bboxes           (enclosing bbox)
  - serialize_safe_boxes   (end-to-end + schema validation)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spatial_serializer import (
    cluster_rows_by_y,
    is_header_row,
    classify_row,
    bind_to_nearest_header,
    merge_bboxes,
    serialize_safe_boxes,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _box(text, x1, y1, x2, y2, conf=0.9):
    return {"text": text, "bbox": [x1, y1, x2, y2], "confidence": conf,
            "locked_digits": [], "source": "original"}


_CHUNK_KEYS = {"chunk_id", "type", "page", "bbox", "text", "token_ids", "header_ref"}


# ── cluster_rows_by_y ─────────────────────────────────────────────────────────

def test_cluster_empty():
    assert cluster_rows_by_y([]) == []


def test_cluster_single_box():
    boxes = [_box("A", 0, 0, 100, 20)]
    rows = cluster_rows_by_y(boxes)
    assert len(rows) == 1
    assert len(rows[0]) == 1


def test_cluster_two_rows():
    boxes = [
        _box("A", 0, 0, 100, 20),    # y-center = 10
        _box("B", 0, 5, 100, 15),    # y-center = 10  → same row
        _box("C", 0, 100, 100, 120), # y-center = 110 → new row
    ]
    rows = cluster_rows_by_y(boxes, gap_threshold=30)
    assert len(rows) == 2
    assert len(rows[0]) == 2  # A and B
    assert len(rows[1]) == 1  # C


def test_cluster_boxes_sorted_left_to_right():
    boxes = [
        _box("Right", 200, 0, 300, 20),
        _box("Left",    0, 0, 100, 20),
    ]
    rows = cluster_rows_by_y(boxes, gap_threshold=5)
    assert rows[0][0]["text"] == "Left"
    assert rows[0][1]["text"] == "Right"


def test_cluster_dynamic_threshold():
    """Small gaps should stay in one row; large gap creates a new row."""
    boxes = [
        _box("R1A", 0,  0, 50, 20),
        _box("R1B", 60, 2, 110, 22),
        _box("R2A", 0, 100, 50, 120),
    ]
    rows = cluster_rows_by_y(boxes)
    assert len(rows) == 2


def test_cluster_all_same_row():
    boxes = [_box(f"W{i}", i * 50, 10, (i + 1) * 50, 30) for i in range(5)]
    rows = cluster_rows_by_y(boxes)
    assert len(rows) == 1
    assert len(rows[0]) == 5


# ── is_header_row ─────────────────────────────────────────────────────────────

def test_header_keyword_en_invoice():
    row = [_box("Invoice No.", 0, 0, 100, 20)]
    assert is_header_row(row) is True


def test_header_keyword_en_total():
    row = [_box("Total Amount", 0, 0, 100, 20)]
    assert is_header_row(row) is True


def test_header_keyword_en_description_qty():
    row = [
        _box("Description", 0, 0, 150, 20),
        _box("Qty", 160, 0, 200, 20),
        _box("Price", 210, 0, 270, 20),
    ]
    assert is_header_row(row) is True


def test_header_all_caps_single():
    row = [_box("INVOICE", 0, 0, 100, 20)]
    assert is_header_row(row) is True


def test_header_not_all_caps_short():
    row = [_box("ok", 0, 0, 20, 20)]
    assert is_header_row(row) is False


def test_header_plain_number_not_header():
    row = [_box("1500.00", 0, 0, 100, 20)]
    assert is_header_row(row) is False


def test_header_sinhala_keyword():
    row = [_box("මුළු එකතුව", 0, 0, 100, 20)]
    assert is_header_row(row) is True


# ── classify_row ──────────────────────────────────────────────────────────────

def test_classify_header():
    row = [_box("Invoice", 0, 0, 100, 20)]
    assert classify_row(row, is_header=True) == "Header"


def test_classify_keyvalue_two_boxes():
    row = [_box("Date", 0, 0, 60, 20), _box("2024-01-15", 70, 0, 200, 20)]
    assert classify_row(row, is_header=False) == "KeyValue"


def test_classify_lineitem_three_boxes_with_number():
    row = [
        _box("Printer Paper", 0, 0, 150, 20),
        _box("5", 160, 0, 200, 20),
        _box("250.00", 210, 0, 300, 20),
    ]
    assert classify_row(row, is_header=False) == "LineItem"


def test_classify_text_single_box_no_number():
    row = [_box("Thank you for your business", 0, 0, 200, 20)]
    assert classify_row(row, is_header=False) == "Text"


def test_classify_text_three_boxes_no_number():
    row = [_box("A", 0, 0, 50, 20), _box("B", 60, 0, 110, 20), _box("C", 120, 0, 170, 20)]
    assert classify_row(row, is_header=False) == "Text"


# ── bind_to_nearest_header ────────────────────────────────────────────────────

def test_bind_no_headers():
    assert bind_to_nearest_header(100.0, []) is None


def test_bind_single_header():
    headers = [{"chunk_id": "p0_r0", "_x_center": 150.0}]
    assert bind_to_nearest_header(100.0, headers) == "p0_r0"


def test_bind_nearest_of_two():
    headers = [
        {"chunk_id": "left_h",  "_x_center":  50.0},
        {"chunk_id": "right_h", "_x_center": 400.0},
    ]
    assert bind_to_nearest_header(60.0, headers) == "left_h"
    assert bind_to_nearest_header(380.0, headers) == "right_h"


# ── merge_bboxes ──────────────────────────────────────────────────────────────

def test_merge_bboxes_single():
    assert merge_bboxes([_box("X", 10, 20, 30, 40)]) == [10, 20, 30, 40]


def test_merge_bboxes_multiple():
    boxes = [_box("A", 10, 5, 50, 25), _box("B", 60, 10, 120, 30)]
    assert merge_bboxes(boxes) == [10, 5, 120, 30]


def test_merge_bboxes_empty():
    assert merge_bboxes([]) == [0, 0, 0, 0]


# ── serialize_safe_boxes ──────────────────────────────────────────────────────

def _invoice_page():
    """Synthetic page resembling a simple invoice."""
    return [
        _box("INVOICE",          100, 10,  300, 30),   # 0 — doc header
        _box("Date",               0, 50,   60, 70),   # 1 \
        _box("2024-01-15",        70, 50,  200, 70),   # 2 /  key-value pair
        _box("Description",        0, 100, 150, 120),  # 3 \
        _box("Qty",              160, 100, 200, 120),  # 4  > table header
        _box("Amount",           210, 100, 300, 120),  # 5 /
        _box("Printer Paper",      0, 150, 150, 170),  # 6 \
        _box("5",                160, 150, 200, 170),  # 7  > line item
        _box("1250.00",          210, 150, 300, 170),  # 8 /
        _box("Total",              0, 200,  60, 220),  # 9  \
        _box("1250.00",           70, 200, 200, 220),  # 10 /  key-value
    ]


def test_serialize_returns_list():
    chunks = serialize_safe_boxes([_invoice_page()])
    assert isinstance(chunks, list)
    assert len(chunks) > 0


def test_serialize_chunk_schema():
    chunks = serialize_safe_boxes([_invoice_page()])
    for chunk in chunks:
        assert _CHUNK_KEYS == set(chunk.keys()), f"Schema mismatch in {chunk}"


def test_serialize_chunk_ids_unique():
    chunks = serialize_safe_boxes([_invoice_page()])
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_serialize_page_index_correct():
    page0 = [_box("Invoice", 0, 0, 100, 20)]
    page1 = [_box("Total", 0, 0, 80, 20)]
    chunks = serialize_safe_boxes([page0, page1])
    pages = [c["page"] for c in chunks]
    assert 0 in pages
    assert 1 in pages


def test_serialize_header_has_no_header_ref():
    chunks = serialize_safe_boxes([_invoice_page()])
    headers = [c for c in chunks if c["type"] == "Header"]
    assert len(headers) > 0
    for h in headers:
        assert h["header_ref"] is None


def test_serialize_non_header_gets_header_ref():
    chunks = serialize_safe_boxes([_invoice_page()])
    non_headers = [c for c in chunks if c["type"] != "Header"]
    # At least some non-headers should be bound to a header
    bound = [c for c in non_headers if c["header_ref"] is not None]
    assert len(bound) > 0


def test_serialize_token_ids_are_ints():
    chunks = serialize_safe_boxes([_invoice_page()])
    for chunk in chunks:
        assert all(isinstance(t, int) for t in chunk["token_ids"])


def test_serialize_token_ids_within_page_bounds():
    page = _invoice_page()
    chunks = serialize_safe_boxes([page])
    page_chunks = [c for c in chunks if c["page"] == 0]
    for chunk in page_chunks:
        for idx in chunk["token_ids"]:
            assert 0 <= idx < len(page)


def test_serialize_bbox_valid():
    chunks = serialize_safe_boxes([_invoice_page()])
    for chunk in chunks:
        x1, y1, x2, y2 = chunk["bbox"]
        assert x1 <= x2
        assert y1 <= y2


def test_serialize_empty_input():
    assert serialize_safe_boxes([]) == []
    assert serialize_safe_boxes([[]])  == []


def test_serialize_multipage_token_ids_per_page():
    """token_ids should be page-local, not global."""
    page0 = [_box("Invoice", 0, 0, 100, 20), _box("Date", 0, 50, 100, 70)]
    page1 = [_box("Total", 0, 0, 80, 20), _box("500.00", 90, 0, 200, 20)]
    chunks = serialize_safe_boxes([page0, page1])
    for chunk in chunks:
        page_len = len(page0) if chunk["page"] == 0 else len(page1)
        for idx in chunk["token_ids"]:
            assert 0 <= idx < page_len


def test_serialize_text_concatenated():
    page = [
        _box("Hello",  0, 0, 50, 20),
        _box("World", 60, 0, 120, 20),
    ]
    chunks = serialize_safe_boxes([page])
    assert len(chunks) == 1
    assert "Hello" in chunks[0]["text"]
    assert "World" in chunks[0]["text"]
