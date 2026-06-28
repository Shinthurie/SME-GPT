"""IT-23 — Overdue payment alerts.

Pure, DB-free logic for deciding which documents represent money that is
overdue, so the result is unit-testable without a database. The live endpoint
in app.py feeds tenant-scoped records (from load_records) into
compute_overdue_alerts() and returns the list to the frontend, which turns each
entry into a notification.

Records do not carry a normalized timestamp (createdAt is not mapped into the
record dict), so dates come from the free-text `date` / `due_date` fields and
are parsed with a tolerant multi-format parser.
"""
from __future__ import annotations

from datetime import date, datetime

# Formats seen on Sri Lankan SME documents + ISO from pickers.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%m/%d/%Y",
    "%d/%m/%y",
    "%Y/%m/%d",
)

# Payment states that mean "settled" — never overdue.
_SETTLED_PAID = {"paid"}
_SETTLED_RECEIVED = {"received"}
# Invoice statuses that are closed (paid/cancelled) — never overdue.
_CLOSED_INVOICE = {"paid", "cancelled", "draft"}

DEFAULT_DAYS_THRESHOLD = 30


def parse_loose_date(value) -> date | None:
    """Best-effort parse of a free-text date string into a date.

    Returns None for empty / "NULL" / unparseable input so callers can skip it.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in ("NULL", "NONE"):
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _amount_of(record: dict):
    """Pick the most meaningful outstanding amount for display."""
    for key in ("payable_amount", "final_total_amount", "raw_total_amount"):
        raw = record.get(key)
        if raw in (None, "", "NULL"):
            continue
        try:
            return float(str(raw).replace(",", ""))
        except (ValueError, TypeError):
            continue
    return None


def evaluate_record(record: dict, today: date, days_threshold: int = DEFAULT_DAYS_THRESHOLD):
    """Return an alert dict if this single record is overdue, else None.

    A document is overdue when it represents money still owed AND either its
    printed due_date has passed, or (when no due_date is given) the document is
    older than `days_threshold` days.
    """
    doc_type = _norm(record.get("document_type"))
    flow = _norm(record.get("effective_flow_type") or record.get("flow_type"))

    # POs are orders and DNs are deliveries — neither is a payment-overdue
    # concept even though a PO carries flow_type "payable".
    if doc_type in ("po", "dn"):
        return None

    # Decide whether this doc represents outstanding money, and which side.
    kind = None  # "payable" | "receivable"
    if doc_type == "invoice":
        inv_status = _norm(record.get("invoice_status"))
        if inv_status in _CLOSED_INVOICE:
            return None
        # Invoice direction follows its flow.
        if flow == "receivable" or _norm(record.get("received_status")) == "not_received":
            kind = "receivable"
        else:
            kind = "payable"
    elif flow == "payable":
        if _norm(record.get("paid_status")) in _SETTLED_PAID:
            return None
        kind = "payable"
    elif flow == "receivable":
        if _norm(record.get("received_status")) in _SETTLED_RECEIVED:
            return None
        kind = "receivable"
    else:
        # receipts, cash flows, po, dn — not a payment-overdue concept here.
        return None

    due = parse_loose_date(record.get("due_date"))
    doc_date = parse_loose_date(record.get("date"))

    days_overdue = None
    if due is not None:
        if due >= today:
            return None
        days_overdue = (today - due).days
    elif doc_date is not None:
        age = (today - doc_date).days
        if age <= days_threshold:
            return None
        days_overdue = age
    else:
        # No usable date at all — cannot assert overdue.
        return None

    counterparty = record.get("supplier_name") or record.get("company_name") or ""
    return {
        "document_id": record.get("document_id", ""),
        "document_type": doc_type,
        "kind": kind,
        "counterparty": "" if str(counterparty).upper() == "NULL" else counterparty,
        "amount": _amount_of(record),
        "currency": (record.get("currency") if record.get("currency") not in (None, "", "NULL") else "LKR"),
        "due_date": due.isoformat() if due else None,
        "doc_date": doc_date.isoformat() if doc_date else None,
        "days_overdue": days_overdue,
    }


def compute_overdue_alerts(records, today: date | None = None, days_threshold: int = DEFAULT_DAYS_THRESHOLD):
    """Map a list of records to overdue alerts, sorted most-overdue first."""
    if today is None:
        today = date.today()
    alerts = []
    for record in records or []:
        alert = evaluate_record(record, today, days_threshold)
        if alert is not None:
            alerts.append(alert)
    alerts.sort(key=lambda a: a.get("days_overdue") or 0, reverse=True)
    return alerts
