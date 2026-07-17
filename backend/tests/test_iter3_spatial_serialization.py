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
    column_tolerance,
    detect_header_row,
    is_summary_row,
    is_table_header,
    row_aligns_to_headers,
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
# Geometric table reconstruction (Surya v1 — boxes carry no table_id)
# ---------------------------------------------------------------------------

def _hdr(text, x1, x2, field):
    return {**_box(text, x1, 0, x2, 15), "canonical_field": field}


_V1_HEADERS = [
    _hdr("Description", 0, 100, "description"),
    _hdr("Qty", 120, 160, "qty"),
    _hdr("Total", 200, 260, "total"),
]


def _v1_page(extra_rows=()):
    """A v1-style invoice table: a header row plus line items, no table_id
    anywhere (Surya v1 emits no table structure)."""
    boxes = [
        _box("Description", 0, 0, 100, 15),
        _box("Qty", 120, 0, 160, 15),
        _box("Total", 200, 0, 260, 15),
        _box("Printer Paper", 0, 20, 100, 35),
        _box("5", 120, 20, 160, 35),
        _box("600", 200, 20, 260, 35),
        _box("Ink Cartridge", 0, 40, 100, 55),
        _box("2", 120, 40, 160, 55),
        _box("400", 200, 40, 260, 55),
    ]
    boxes.extend(extra_rows)
    return [{"page": 1, "boxes": boxes}]


def _line_items(pages):
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    return [c for c in result["pages"][0]["chunks"] if c["chunk_type"] == "line_item_row"]


def test_is_table_header_requires_two_distinct_canonical_fields():
    assert is_table_header(_V1_HEADERS) is True
    # A lone "Total: 1250.00" line scores 1.0 in detect_header_row but must not
    # anchor a table.
    assert is_table_header([_hdr("Total", 0, 100, "total")]) is False
    # Two cells, same field -> not a table.
    assert is_table_header([_hdr("Total", 0, 100, "total"), _hdr("Amount", 120, 200, "total")]) is False


def test_column_tolerance_scales_with_header_spacing():
    # header x-centers 50/140/230 -> median gap 90 * 0.6
    assert column_tolerance(_V1_HEADERS) == 54.0
    assert column_tolerance([_hdr("Total", 0, 100, "total")]) == 0.0


def test_row_aligns_to_headers_accepts_wide_cell_overlapping_narrow_header():
    row = [_box("Widget assembly kit, large", 0, 20, 200, 35), _box("600", 200, 20, 260, 35)]
    assert row_aligns_to_headers(row, _V1_HEADERS, column_tolerance(_V1_HEADERS)) is True


def test_row_aligns_to_headers_rejects_single_cell_and_offset_rows():
    assert row_aligns_to_headers([_box("Thanks!", 0, 20, 80, 35)], _V1_HEADERS, 60.0) is False
    far = [_box("A", 900, 20, 940, 35), _box("B", 960, 20, 1000, 35)]
    assert row_aligns_to_headers(far, _V1_HEADERS, 60.0) is False


def test_is_summary_row_needs_both_narrow_row_and_summary_label():
    assert is_summary_row([_box("Total", 0, 60, 60, 75), _box("1000", 200, 60, 260, 75)], _V1_HEADERS) is True
    # Full-width row matching "total" on the description is a real line item.
    line_item = [_box("Total station tripod", 0, 20, 100, 35), _box("2", 120, 20, 160, 35), _box("45000", 200, 20, 260, 35)]
    assert is_summary_row(line_item, _V1_HEADERS) is False
    # Narrow row with no summary label.
    assert is_summary_row([_box("Colombo", 0, 60, 60, 75)], _V1_HEADERS) is False


def test_v1_boxes_without_table_id_now_produce_line_items():
    """The regression this change targets: on v1 geometry every row below the
    header used to fall through to section_text."""
    items = _line_items(_v1_page())
    assert len(items) == 2
    assert [c["fields"]["description"]["value"] for c in items] == ["Printer Paper", "Ink Cartridge"]
    assert [c["fields"]["qty"]["value"] for c in items] == ["5", "2"]
    assert [c["fields"]["total"]["value"] for c in items] == ["600", "400"]
    assert all(c["quality"]["header_bound"] for c in items)
    assert all(c["table_id"] is None for c in items)
    assert all(c["fields"]["total"]["locked_digits"] is True for c in items)


def test_geometric_binding_stops_at_summary_row():
    pages = _v1_page([
        _box("Subtotal", 0, 60, 80, 75),
        _box("1000", 200, 60, 260, 75),
        # Anything after the totals block stays out of the table.
        _box("Grand Total", 0, 80, 90, 95),
        _box("1150", 200, 80, 260, 95),
    ])
    items = _line_items(pages)
    assert [c["fields"]["description"]["value"] for c in items] == ["Printer Paper", "Ink Cartridge"]


def test_geometric_binding_stops_at_large_vertical_gap():
    # Median text height 15 -> gap limit 37.5. This row starts 100px below.
    pages = _v1_page([
        _box("Detached", 0, 155, 100, 170),
        _box("9", 120, 155, 160, 170),
        _box("999", 200, 155, 260, 170),
    ])
    items = _line_items(pages)
    assert len(items) == 2
    assert "Detached" not in [c["fields"].get("description", {}).get("value") for c in items]


def test_geometric_binding_stops_at_non_aligned_row():
    pages = _v1_page([
        _box("Please remit within 30 days", 600, 60, 900, 75),
        _box("of the invoice date", 600, 75, 900, 90),
    ])
    items = _line_items(pages)
    assert len(items) == 2


def test_geometric_binding_leaves_rows_above_the_header_alone():
    pages = _v1_page()
    pages[0]["boxes"].append(_box("ACME Traders", 0, -40, 120, -25))
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    chunks = result["pages"][0]["chunks"]
    assert any(c["chunk_type"] == "section_text" and "ACME Traders" in c["text"] for c in chunks)
    assert len([c for c in chunks if c["chunk_type"] == "line_item_row"]) == 2


def test_geometric_binding_does_not_engage_without_a_real_table_header():
    pages = [{"page": 1, "boxes": [
        _box("Total: 1250.00", 0, 0, 120, 15),
        _box("Thank you for your business", 0, 20, 200, 35),
        _box("Please call us", 0, 40, 150, 55),
    ]}]
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    chunks = result["pages"][0]["chunks"]
    assert [c["chunk_type"] for c in chunks if c["chunk_type"] == "line_item_row"] == []


def test_geometric_binding_never_drops_tokens():
    pages = _v1_page([
        _box("Subtotal", 0, 60, 80, 75),
        _box("1000", 200, 60, 260, 75),
        _box("Thanks for your business", 0, 200, 200, 215),
    ])
    input_boxes = len(pages[0]["boxes"])
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    consumed = sum(
        len(c["provenance"]["token_bboxes"]) for p in result["pages"] for c in p["chunks"]
    )
    assert consumed == input_boxes


def test_geometric_binding_ignored_when_table_ids_are_present():
    """Surya v2 geometry must keep taking the table_id path unchanged."""
    pages = _table_with_n_rows(3)
    result = build_spatial_chunks(pages, tenant_id="t1", document_id="d1")
    items = [c for c in result["pages"][0]["chunks"] if c["chunk_type"] == "line_item_row"]
    assert len(items) == 3
    assert all(c["table_id"] == "t1" for c in items)


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
