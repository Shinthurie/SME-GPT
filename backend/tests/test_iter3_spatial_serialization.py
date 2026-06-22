"""Iteration 3 — Component 2 (layout-aware spatial serialization) tests.

Covers: row clustering (y-axis, dynamic threshold), header detection
(English + Sinhala keywords), header->row x-axis binding, the chunking
strategy (per-row vs blocks of 5-10 for >30 rows), template serialization
schema validity, and an end-to-end run against the same mock Surya v2
fixture (`invoice_mock_surya_v2.json`) Iteration 2 introduced for C1 — now
exercising the table-cell expansion added to `ocr_service.py` for C2.
"""
from pathlib import Path

from ocr_service import get_ocr_service
from spatial_serialization import (
    bind_row_to_headers,
    build_spatial_chunks,
    classify_key_value,
    cluster_rows,
    detect_header_row,
)

FIXTURE = Path(__file__).resolve().parent.parent / "sample_docs" / "invoice_mock_surya_v2.json"


def _box(text, x1, y1, x2, y2, **extra):
    return {"text": text, "bbox": [x1, y1, x2, y2], "confidence": 1.0, "label": "Text", "page": 1, **extra}


# ---------------------------------------------------------------------------
# Row clustering
# ---------------------------------------------------------------------------

def test_cluster_rows_groups_by_y_alignment():
    boxes = [
        _box("Description", 0, 10, 100, 25),
        _box("Qty", 100, 10, 150, 25),
        _box("Apple", 0, 40, 100, 55),
        _box("5", 100, 40, 150, 55),
    ]
    rows = cluster_rows(boxes)
    assert len(rows) == 2
    assert [b["text"] for b in rows[0]] == ["Description", "Qty"]
    assert [b["text"] for b in rows[1]] == ["Apple", "5"]


def test_cluster_rows_orders_within_row_by_x():
    boxes = [
        _box("Qty", 100, 10, 150, 25),
        _box("Description", 0, 12, 100, 27),
    ]
    rows = cluster_rows(boxes)
    assert len(rows) == 1
    assert [b["text"] for b in rows[0]] == ["Description", "Qty"]


def test_cluster_rows_dynamic_threshold_separates_close_but_distinct_rows():
    # text_height = 15 for every box here -> median height 15, threshold = 15*0.8 = 12.
    # Row 2 starts at y_center 40, far enough from row 1's y_center 17.5 to split.
    boxes = [
        _box("A", 0, 10, 50, 25),
        _box("B", 0, 32, 50, 47),
    ]
    rows = cluster_rows(boxes, alpha=0.8)
    assert len(rows) == 2


def test_cluster_rows_empty_input():
    assert cluster_rows([]) == []


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

def test_detect_header_row_english_keywords():
    rows = [
        [_box("Description", 0, 0, 100, 15), _box("Qty", 100, 0, 150, 15), _box("Total", 150, 0, 250, 15)],
        [_box("Apple", 0, 20, 100, 35), _box("5", 100, 20, 150, 35), _box("500", 150, 20, 250, 35)],
    ]
    header_index, header_cells = detect_header_row(rows)
    assert header_index == 0
    assert [c["canonical_field"] for c in header_cells] == ["description", "qty", "total"]


def test_detect_header_row_sinhala_keywords():
    rows = [
        [_box("විස්තරය", 0, 0, 100, 15), _box("ප්‍රමාණය", 100, 0, 150, 15), _box("මුළු", 150, 0, 250, 15)],
        [_box("X", 0, 20, 100, 35), _box("1", 100, 20, 150, 35), _box("100", 150, 20, 250, 35)],
    ]
    header_index, header_cells = detect_header_row(rows)
    assert header_index == 0
    assert [c["canonical_field"] for c in header_cells] == ["description", "qty", "total"]


def test_detect_header_row_returns_none_when_no_row_qualifies():
    rows = [
        [_box("Hello there", 0, 0, 100, 15)],
        [_box("Goodbye now", 0, 20, 100, 35)],
    ]
    header_index, header_cells = detect_header_row(rows)
    assert header_index is None
    assert header_cells == []


# ---------------------------------------------------------------------------
# Header -> row binding (x-axis nearest-center)
# ---------------------------------------------------------------------------

def test_bind_row_to_headers_nearest_x_center():
    header_cells = [
        {**_box("Description", 0, 0, 100, 15), "canonical_field": "description"},
        {**_box("Qty", 100, 0, 150, 15), "canonical_field": "qty"},
        {**_box("Total", 150, 0, 250, 15), "canonical_field": "total"},
    ]
    row = [_box("Apple", 5, 20, 95, 35), _box("5", 110, 20, 140, 35), _box("500", 160, 20, 240, 35)]
    fields = bind_row_to_headers(row, header_cells)
    assert fields["description"]["text"] == "Apple"
    assert fields["qty"]["text"] == "5"
    assert fields["total"]["text"] == "500"


def test_bind_row_to_headers_falls_back_to_unknown_column_without_headers():
    row = [_box("X", 0, 0, 50, 15), _box("Y", 50, 0, 100, 15)]
    fields = bind_row_to_headers(row, [])
    assert set(fields.keys()) == {"unknown_column_0", "unknown_column_1"}


def test_bind_row_to_headers_disambiguates_duplicate_column_assignment():
    # Two boxes both nearest to the same header -> the second gets unknown_column.
    header_cells = [{**_box("Total", 100, 0, 150, 15), "canonical_field": "total"}]
    row = [_box("500", 100, 20, 130, 35), _box("600", 105, 20, 135, 35)]
    fields = bind_row_to_headers(row, header_cells)
    assert fields["total"]["text"] == "500"
    assert fields["unknown_column_0"]["text"] == "600"


# ---------------------------------------------------------------------------
# KeyValue classification
# ---------------------------------------------------------------------------

def test_classify_key_value_matches_colon_pattern():
    row = [_box("Order ID: 8", 0, 0, 100, 15)]
    kv = classify_key_value(row)
    assert kv == {"key": "Order ID", "value": "8", "box": row[0]}


def test_classify_key_value_rejects_multi_box_rows():
    row = [_box("Order ID:", 0, 0, 50, 15), _box("8", 50, 0, 100, 15)]
    assert classify_key_value(row) is None


def test_classify_key_value_rejects_text_without_colon():
    row = [_box("Be Focus Your Look", 0, 0, 100, 15)]
    assert classify_key_value(row) is None


# ---------------------------------------------------------------------------
# build_spatial_chunks — schema + end-to-end correctness
# ---------------------------------------------------------------------------

def _required_chunk_keys(chunk):
    assert "chunk_id" in chunk
    assert "chunk_type" in chunk
    assert "text" in chunk
    assert "provenance" in chunk and "page" in chunk["provenance"] and "bbox" in chunk["provenance"]
    assert "metadata" in chunk and "source_component" in chunk["metadata"]


def test_build_spatial_chunks_top_level_schema():
    pages = [{"page": 1, "boxes": [_box("Order ID: 8", 0, 0, 100, 15)]}]
    result = build_spatial_chunks(pages, tenant_id="tenant-1", document_id="doc-1")
    assert result["tenant_id"] == "tenant-1"
    assert result["document_id"] == "doc-1"
    assert result["version"] == "1.0"
    assert isinstance(result["language_hint"], list)
    assert result["pages"][0]["page"] == 1
    assert len(result["pages"][0]["chunks"]) == 1


def test_build_spatial_chunks_never_drops_tokens_on_mock_fixture():
    service = get_ocr_service()
    pages = service.run(["invoice.png"])
    final_safe_boxes = [{"page": i + 1, "boxes": boxes} for i, boxes in enumerate(pages)]
    input_box_count = sum(len(p["boxes"]) for p in final_safe_boxes)

    result = build_spatial_chunks(final_safe_boxes, tenant_id="t1", document_id="d1")

    consumed = 0
    for page in result["pages"]:
        for chunk in page["chunks"]:
            _required_chunk_keys(chunk)
            consumed += len(chunk["provenance"]["token_bboxes"])
    assert consumed == input_box_count


def test_build_spatial_chunks_extracts_line_items_with_correct_values():
    service = get_ocr_service()
    pages = service.run(["invoice.png"])
    final_safe_boxes = [{"page": i + 1, "boxes": boxes} for i, boxes in enumerate(pages)]

    result = build_spatial_chunks(final_safe_boxes, tenant_id="t1", document_id="d1")
    chunks = result["pages"][0]["chunks"]

    line_items = [c for c in chunks if c["chunk_type"] == "line_item_row"]
    assert len(line_items) == 3
    totals = [c["fields"]["total"]["value"] for c in line_items]
    assert totals == ["600", "400", "300"]
    assert all(c["fields"]["total"]["locked_digits"] is True for c in line_items)
    assert all(c["quality"]["header_bound"] for c in line_items)

    headers = [c for c in chunks if c["chunk_type"] == "header"]
    assert len(headers) == 1
    assert "No." in headers[0]["text"]


def test_build_spatial_chunks_extracts_key_value_pairs():
    service = get_ocr_service()
    pages = service.run(["invoice.png"])
    final_safe_boxes = [{"page": i + 1, "boxes": boxes} for i, boxes in enumerate(pages)]

    result = build_spatial_chunks(final_safe_boxes, tenant_id="t1", document_id="d1")
    chunks = result["pages"][0]["chunks"]
    kv_chunks = [c for c in chunks if c["chunk_type"] == "key_value"]

    assert any("0rder ID" in list(c["fields"].keys())[0] for c in kv_chunks)
    assert any(list(c["fields"].values())[0]["value"] == "8" for c in kv_chunks)
    assert any("Date" in list(c["fields"].keys())[0] for c in kv_chunks)


def test_build_spatial_chunks_language_hint_detects_sinhala_and_english():
    service = get_ocr_service()
    pages = service.run(["invoice.png"])
    final_safe_boxes = [{"page": i + 1, "boxes": boxes} for i, boxes in enumerate(pages)]
    result = build_spatial_chunks(final_safe_boxes, tenant_id="t1", document_id="d1")
    assert result["language_hint"] == ["en", "si"]


def test_build_spatial_chunks_no_header_falls_back_to_positional_rows():
    pages = [{"page": 1, "boxes": [
        _box("X", 0, 0, 50, 15, table_id="t1", row_index=0, col_index=0),
        _box("Y", 50, 0, 100, 15, table_id="t1", row_index=0, col_index=1),
    ]}]
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    chunks = result["pages"][0]["chunks"]
    assert len(chunks) == 1
    assert chunks[0]["chunk_type"] == "line_item_row"
    assert chunks[0]["header_id"] is None
    assert chunks[0]["quality"]["header_bound"] is False
    assert set(chunks[0]["fields"].keys()) == {"unknown_column_0", "unknown_column_1"}


# ---------------------------------------------------------------------------
# Chunking strategy (component-2.md "Chunking strategy")
# ---------------------------------------------------------------------------

def _table_with_n_rows(n):
    boxes = []
    boxes.append(_box("Description", 0, 0, 100, 15, table_id="t1"))
    boxes.append(_box("Total", 100, 0, 200, 15, table_id="t1"))
    for i in range(n):
        y = 20 + i * 15
        boxes.append(_box(f"Item {i}", 0, y, 100, y + 15, table_id="t1", row_index=i + 1, col_index=0))
        boxes.append(_box(str(100 + i), 100, y, 200, y + 15, table_id="t1", row_index=i + 1, col_index=1))
    return [{"page": 1, "boxes": boxes}]


def test_chunking_strategy_one_chunk_per_row_when_at_or_under_threshold():
    pages = _table_with_n_rows(30)
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    chunks = result["pages"][0]["chunks"]
    row_chunks = [c for c in chunks if c["chunk_type"] == "line_item_row"]
    block_chunks = [c for c in chunks if c["chunk_type"] == "line_item_block"]
    assert len(row_chunks) == 30
    assert len(block_chunks) == 0


def test_chunking_strategy_blocks_of_rows_when_over_threshold():
    pages = _table_with_n_rows(40)
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    chunks = result["pages"][0]["chunks"]
    block_chunks = [c for c in chunks if c["chunk_type"] == "line_item_block"]
    row_chunks = [c for c in chunks if c["chunk_type"] == "line_item_row"]

    assert len(row_chunks) == 0
    assert len(block_chunks) > 0
    for block in block_chunks:
        assert 1 <= len(block["row_ids"]) <= 10
        assert "Headers |" in block["text"]
    total_rows_in_blocks = sum(len(b["row_ids"]) for b in block_chunks)
    assert total_rows_in_blocks == 40
