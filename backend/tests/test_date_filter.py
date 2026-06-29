"""Tests for the multi-format document date filter.

Verifies that filter_records_by_doc_date() correctly handles all date formats
that OCR can produce: ISO, DD/MM/YYYY, MM/DD/YYYY, DD MMM YYYY, etc.
"""
from __future__ import annotations
import pytest


def _rec(date_str: str) -> dict:
    return {"docDate": date_str, "documentId": f"DOC-{date_str}"}


# ── _parse_doc_date ────────────────────────────────────────────────────────────

def test_parse_iso_date():
    from dataset_manager import _parse_doc_date
    from datetime import date
    assert _parse_doc_date("2026-04-15") == date(2026, 4, 15)

def test_parse_dd_mm_yyyy():
    from dataset_manager import _parse_doc_date
    from datetime import date
    assert _parse_doc_date("15/04/2026") == date(2026, 4, 15)

def test_parse_mm_dd_yyyy():
    from dataset_manager import _parse_doc_date
    from datetime import date
    assert _parse_doc_date("04/15/2026") == date(2026, 4, 15)

def test_parse_dd_mmm_yyyy():
    from dataset_manager import _parse_doc_date
    from datetime import date
    assert _parse_doc_date("15 Apr 2026") == date(2026, 4, 15)

def test_parse_dd_mmmm_yyyy():
    from dataset_manager import _parse_doc_date
    from datetime import date
    assert _parse_doc_date("15 April 2026") == date(2026, 4, 15)

def test_parse_mmm_dd_comma_yyyy():
    from dataset_manager import _parse_doc_date
    from datetime import date
    assert _parse_doc_date("Apr 15, 2026") == date(2026, 4, 15)

def test_parse_date_with_time_suffix():
    from dataset_manager import _parse_doc_date
    from datetime import date
    assert _parse_doc_date("2026-04-15 00:00:00") == date(2026, 4, 15)

def test_parse_null_returns_none():
    from dataset_manager import _parse_doc_date
    assert _parse_doc_date("NULL") is None
    assert _parse_doc_date("") is None
    assert _parse_doc_date(None) is None

def test_parse_garbage_returns_none():
    from dataset_manager import _parse_doc_date
    assert _parse_doc_date("not-a-date") is None

def test_parse_us_format_oct_2023():
    """10/20/2023 appears in screenshot — MM/DD/YYYY."""
    from dataset_manager import _parse_doc_date
    from datetime import date
    result = _parse_doc_date("10/20/2023")
    # MM/DD/YYYY: October 20, 2023
    assert result == date(2023, 10, 20)


# ── filter_records_by_doc_date ────────────────────────────────────────────────

def test_filter_no_bounds_returns_all():
    from dataset_manager import filter_records_by_doc_date
    recs = [_rec("2026-01-15"), _rec("2026-06-01"), _rec("2023-10-20")]
    assert len(filter_records_by_doc_date(recs)) == 3

def test_filter_iso_dates_in_range():
    from dataset_manager import filter_records_by_doc_date
    recs = [_rec("2026-02-10"), _rec("2026-03-15"), _rec("2026-04-01")]
    result = filter_records_by_doc_date(recs, "2026-02-01", "2026-02-28")
    assert len(result) == 1
    assert result[0]["docDate"] == "2026-02-10"

def test_filter_mixed_formats_february():
    """The screenshot scenario: filter Feb 2026, various format dates."""
    from dataset_manager import filter_records_by_doc_date
    recs = [
        _rec("10/20/2023"),   # Oct 20 2023 → excluded
        _rec("15 Apr 2026"),  # Apr 15 2026 → excluded
        _rec("15 Jan 2026"),  # Jan 15 2026 → excluded
        _rec("2026-02-14"),   # Feb 14 2026 → INCLUDED
        _rec("14/02/2026"),   # Feb 14 2026 DD/MM/YYYY → INCLUDED
        _rec("02/14/2026"),   # Feb 14 2026 MM/DD/YYYY → INCLUDED
    ]
    result = filter_records_by_doc_date(recs, "2026-02-01", "2026-02-28")
    dates = [r["docDate"] for r in result]
    assert "10/20/2023" not in dates
    assert "15 Apr 2026" not in dates
    assert "15 Jan 2026" not in dates
    assert "2026-02-14" in dates

def test_filter_date_to_is_inclusive():
    """date_to = 2026-02-28 should include a doc dated 2026-02-28."""
    from dataset_manager import filter_records_by_doc_date
    recs = [_rec("2026-02-28"), _rec("2026-03-01")]
    result = filter_records_by_doc_date(recs, "2026-02-01", "2026-02-28")
    assert len(result) == 1
    assert result[0]["docDate"] == "2026-02-28"

def test_filter_unparseable_date_included():
    """Records with unrecognisable dates are included (over-include, not exclude)."""
    from dataset_manager import filter_records_by_doc_date
    recs = [_rec("not-a-date"), _rec("NULL"), _rec("2025-01-01")]
    result = filter_records_by_doc_date(recs, "2026-01-01", "2026-12-31")
    ids = [r["docDate"] for r in result]
    assert "not-a-date" in ids
    assert "NULL" in ids
    assert "2025-01-01" not in ids

def test_filter_only_date_from():
    from dataset_manager import filter_records_by_doc_date
    recs = [_rec("2025-12-31"), _rec("2026-01-01"), _rec("2026-06-30")]
    result = filter_records_by_doc_date(recs, "2026-01-01", None)
    dates = [r["docDate"] for r in result]
    assert "2025-12-31" not in dates
    assert "2026-01-01" in dates
    assert "2026-06-30" in dates

def test_filter_only_date_to():
    from dataset_manager import filter_records_by_doc_date
    recs = [_rec("2025-06-01"), _rec("2026-01-15"), _rec("2026-07-01")]
    result = filter_records_by_doc_date(recs, None, "2026-01-31")
    dates = [r["docDate"] for r in result]
    assert "2025-06-01" in dates
    assert "2026-01-15" in dates
    assert "2026-07-01" not in dates
