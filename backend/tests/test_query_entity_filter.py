"""Party-scoped payable/receivable queries: 'how much do we owe TechRentLk'
must filter to that party instead of summing every payable.

Covers the two bugs: extract_named_entity missing the 'owe X' pattern, and
filter_named_entity matching space-sensitively (so 'techrentlk' != 'techrent lk').
"""
from __future__ import annotations

import pandas as pd

import data_tools as dt


def test_extract_entity_after_owe():
    assert dt.extract_named_entity("how much do we owe TechRent LK") == "techrent lk"
    assert dt.extract_named_entity("how much do we owe TechRentLk") == "techrentlk"
    assert dt.extract_named_entity("how much do we owe to AECC Global") == "aecc global"


def test_extract_entity_none_for_plain_total():
    # No party named -> no entity -> caller sums all payables.
    assert dt.extract_named_entity("how much payable do we have") == ""
    assert dt.extract_named_entity("what is our total payable") == ""


def _df():
    return pd.DataFrame([
        {"company_name": "My Co", "supplier_name": "TechRent LK"},
        {"company_name": "My Co", "supplier_name": "AECC Global Pvt. Ltd."},
        {"company_name": "My Co", "supplier_name": "ESOL college pvt Ltd"},
    ])


def test_filter_matches_despite_missing_space():
    out = dt.filter_named_entity(_df(), "techrentlk")
    assert len(out) == 1
    assert out.iloc[0]["supplier_name"] == "TechRent LK"


def test_filter_matches_with_space():
    out = dt.filter_named_entity(_df(), "techrent lk")
    assert len(out) == 1
    assert out.iloc[0]["supplier_name"] == "TechRent LK"


def test_filter_no_match_returns_empty():
    out = dt.filter_named_entity(_df(), "nonexistent vendor")
    assert out.empty


def test_filter_empty_target_returns_all():
    out = dt.filter_named_entity(_df(), "")
    assert len(out) == 3
