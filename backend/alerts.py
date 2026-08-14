"""Proactive financial alerts.

Background-scanned conditions (unlike the chatbot in pal_qa.py/financial_advisor.py,
which only answers when asked) surfaced to the user without a question being asked.
Stored in ActivityLog (type="ALERT") -- same no-migration-needed pattern already
used for type="BUDGET_SETTINGS" in data_tools.get_financial_snapshot().
"""
from __future__ import annotations

import json
import uuid
from datetime import date

import data_tools as dt
from db import get_conn

ALERT_TYPE = "ALERT"


def _current_period() -> str:
    return date.today().strftime("%Y-%m")


def _compute_alerts(snapshot: dict, period: str) -> list[dict]:
    """Pure rule evaluation over an already-computed financial snapshot --
    no I/O, easy to unit test independently of the DB."""
    alerts = []

    net_this = snapshot.get("net_this_month", 0.0)
    net_last = snapshot.get("net_last_month", 0.0)

    if net_this < 0:
        alerts.append({
            "rule_id": "negative_cash_flow",
            "period": period,
            "severity": "warning",
            "title": "Negative cash flow this month",
            "message": f"You've spent more than you've earned this month (net {net_this:,.2f}).",
        })

    if net_last > 0 and net_this < net_last * 0.5:
        alerts.append({
            "rule_id": "cash_flow_decline",
            "period": period,
            "severity": "warning",
            "title": "Cash flow dropped sharply",
            "message": (
                f"Your net cash flow fell from {net_last:,.2f} last month to "
                f"{net_this:,.2f} this month -- a drop of more than 50%."
            ),
        })

    return alerts


def _already_alerted(user_id: str, rule_id: str, period: str) -> bool:
    query = """
    SELECT content FROM "ActivityLog"
    WHERE "userId" = %s AND type = %s AND "createdAt" >= date_trunc('month', NOW())
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(user_id), ALERT_TYPE))
            rows = cur.fetchall()
    for row in rows:
        content = row.get("content") if isinstance(row, dict) else row[0]
        try:
            payload = json.loads(content) if content else {}
        except Exception:
            continue
        if payload.get("rule_id") == rule_id and payload.get("period") == period:
            return True
    return False


def _save_alert(user_id: str, alert: dict):
    query = """
    INSERT INTO "ActivityLog" (id, "userId", type, content, "createdAt")
    VALUES (%s, %s, %s, %s, NOW())
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(uuid.uuid4()), str(user_id), ALERT_TYPE, json.dumps(alert, ensure_ascii=False)))
        conn.commit()


def check_alerts_for_user(user_id: str, company_name: str) -> list[dict]:
    """Compute + persist any newly-fired alerts for one user (deduped to at
    most one per rule per calendar month). Returns the alerts actually saved
    this call (empty if nothing fired or everything was already alerted)."""
    snapshot = dt.get_financial_snapshot(user_id, company_name)
    period = _current_period()
    candidates = _compute_alerts(snapshot, period)

    saved = []
    for alert in candidates:
        if _already_alerted(user_id, alert["rule_id"], period):
            continue
        _save_alert(user_id, alert)
        saved.append(alert)
    return saved


def load_recent_alerts(user_id: str, limit: int = 20) -> list[dict]:
    query = """
    SELECT id, content, "createdAt" FROM "ActivityLog"
    WHERE "userId" = %s AND type = %s
    ORDER BY "createdAt" DESC
    LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(user_id), ALERT_TYPE, limit))
            rows = cur.fetchall()

    cols = ["id", "content", "createdAt"]
    alerts = []
    for row in rows:
        r = row if isinstance(row, dict) else dict(zip(cols, row))
        try:
            payload = json.loads(r["content"]) if r.get("content") else {}
        except Exception:
            payload = {}
        alerts.append({
            "id": str(r["id"]),
            "created_at": r["createdAt"].isoformat() if r.get("createdAt") else "",
            **payload,
        })
    return alerts
