"""Generate professional PNG document images from manually entered data.

Used by POST /documents/manual so that manually entered receipts, invoices,
POs and delivery notes get a real visual document image stored alongside the
structured data — exactly like OCR-processed documents.

Requires: Pillow (already in requirements.txt as part of the image pipeline).
"""
from __future__ import annotations

import io
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

# ── Font loader ───────────────────────────────────────────────────────────────
try:
    from PIL import ImageFont

    def _font(size: int = 14, bold: bool = False) -> Any:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for c in candidates:
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
        return ImageFont.load_default()
except ImportError:
    raise ImportError("Pillow is required: pip install pillow")

# ── Canvas helpers ────────────────────────────────────────────────────────────
W, H = 794, 1123   # A4 at 96 dpi

DOC_COLORS = {
    "receipt": "#16a34a",
    "invoice": "#2252b5",
    "po":      "#7c3aed",
    "dn":      "#ea6c0a",
}

def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), "white")
    return img, ImageDraw.Draw(img)

def _hline(d: ImageDraw.ImageDraw, y: int, x1: int = 50, x2: int = 744,
           color: str = "#cccccc", width: int = 1) -> None:
    d.line([(x1, y), (x2, y)], fill=color, width=width)

def _text(d: ImageDraw.ImageDraw, xy: tuple[int, int], txt: str,
          size: int = 13, bold: bool = False,
          color: str = "#1a1a1a", anchor: str = "la") -> None:
    d.text(xy, str(txt or ""), font=_font(size, bold), fill=color, anchor=anchor)

def _header(d: ImageDraw.ImageDraw, doc_type: str, doc_no: str,
            company_name: str, doc_date: str, color: str) -> None:
    # Top colour bar
    d.rectangle([(0, 0), (W, 90)], fill=color)
    _text(d, (50, 14), company_name or "Your Company", 22, bold=True, color="white")
    _text(d, (50, 50), "SME-GPT Document System", 11, color="#ffffffcc")
    _text(d, (W - 50, 22), doc_type.upper(), 18, bold=True, color="white", anchor="ra")
    _text(d, (W - 50, 56), f"No: {doc_no}", 11, color="#ffffffdd", anchor="ra")
    # Sub-strip
    d.rectangle([(0, 90), (W, 114)], fill="#f3f4f6")
    _text(d, (50, 96), f"Date: {doc_date}", 11, color="#444444")
    _text(d, (W - 50, 96), f"[MANUAL ENTRY] · SME-GPT", 10, color="#888888", anchor="ra")
    _hline(d, 114, color="#dddddd", width=2)

def _items_table(d: ImageDraw.ImageDraw, items: list[dict], y: int,
                 show_price: bool = True) -> int:
    """Draw line-items table. Returns next Y position."""
    # Header row
    _text(d, (50, y), "Description", 11, bold=True, color="#555555")
    if show_price:
        _text(d, (490, y), "Qty",        11, bold=True, color="#555555", anchor="ra")
        _text(d, (600, y), "Unit Price", 11, bold=True, color="#555555", anchor="ra")
        _text(d, (744, y), "Amount (LKR)", 11, bold=True, color="#555555", anchor="ra")
    else:
        _text(d, (600, y), "Qty",  11, bold=True, color="#555555", anchor="ra")
        _text(d, (744, y), "Unit", 11, bold=True, color="#555555", anchor="ra")
    y += 14
    _hline(d, y)
    y += 10

    for item in items:
        desc  = str(item.get("description", "") or "")[:55]
        qty   = str(item.get("quantity",    "") or "")
        price = item.get("unit_price")
        total = item.get("line_total")
        _text(d, (50, y), desc, 12)
        if show_price:
            _text(d, (490, y), qty,  12, anchor="ra")
            if price not in (None, "", "NULL"):
                _text(d, (600, y), f"{float(str(price)):,.2f}", 12, anchor="ra")
            if total not in (None, "", "NULL"):
                _text(d, (744, y), f"{float(str(total)):,.2f}", 12, anchor="ra")
        else:
            _text(d, (600, y), qty,                  12, anchor="ra")
            _text(d, (744, y), str(item.get("unit", "pcs")), 12, anchor="ra")
        y += 22
        _hline(d, y, color="#eeeeee")
        y += 8

    return y

def _money(val: Any) -> float:
    try:
        return float(str(val).replace(",", "")) if val not in (None, "", "NULL") else 0.0
    except (ValueError, TypeError):
        return 0.0


# ── Template generators ───────────────────────────────────────────────────────

def _generate_receipt(data: dict) -> bytes:
    img, d = _new_canvas()
    color = DOC_COLORS["receipt"]
    _header(d, "Receipt", data.get("order_id", ""), data.get("company_name", ""),
            data.get("date", ""), color)

    y = 132
    supplier = str(data.get("supplier_name", "") or "Customer")
    _text(d, (50, y), "Received From:", 11, color="#666666"); y += 16
    _text(d, (50, y), supplier, 17, bold=True); y += 28
    if data.get("notes"):
        _text(d, (50, y), str(data["notes"]), 11, color="#666666"); y += 18
    _hline(d, y); y += 16

    items = data.get("items", [])
    y = _items_table(d, items, y, show_price=True)

    subtotal = sum(_money(i.get("line_total")) for i in items)
    if not subtotal:
        subtotal = _money(data.get("final_total_amount"))
    tax_rate = _money(data.get("tax_rate"))
    tax_amt  = round(subtotal * tax_rate / 100, 2) if tax_rate else _money(data.get("tax_amount"))
    total    = round(subtotal + tax_amt, 2)
    cur      = str(data.get("currency", "LKR") or "LKR")

    y += 8
    _hline(d, y, color="#aaaaaa"); y += 14
    if tax_rate:
        _text(d, (600, y), "Subtotal", 11, color="#666666")
        _text(d, (744, y), f"{subtotal:,.2f}", 11, anchor="ra")
        y += 18
        _text(d, (600, y), f"Tax ({tax_rate:.0f}%)", 11, color="#666666")
        _text(d, (744, y), f"{tax_amt:,.2f}", 11, anchor="ra")
        y += 16
        _hline(d, y, color="#333333", width=2); y += 14
    _text(d, (580, y), f"TOTAL ({cur})", 13, bold=True)
    _text(d, (744, y), f"{total:,.2f}", 18, bold=True, color=color, anchor="ra")
    y += 40

    # Footer banner
    d.rectangle([(50, y), (744, y + 50)], fill="#f0fdf4", outline="#bbf7d0")
    _text(d, (397, y + 12), f"Payment received. Thank you, {supplier.split()[0]}!",
          12, color="#166534", anchor="ma")
    _text(d, (397, y + 32), f"Receipt: {data.get('order_id','')}  ·  Created via SME-GPT",
          10, color="#166534", anchor="ma")

    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(150, 150))
    return buf.getvalue()


def _generate_invoice(data: dict) -> bytes:
    img, d = _new_canvas()
    color = DOC_COLORS["invoice"]
    _header(d, "Invoice", data.get("order_id", ""), data.get("company_name", ""),
            data.get("date", ""), color)

    y = 132
    supplier = str(data.get("supplier_name", "") or "Customer")
    # Two-column party block
    _text(d, (50,  y), "BILLED TO",   10, bold=True, color="#888888")
    _text(d, (420, y), "BILLED FROM", 10, bold=True, color="#888888")
    y += 16
    _text(d, (50,  y), supplier,                   15, bold=True)
    _text(d, (420, y), str(data.get("company_name") or ""), 15, bold=True)
    y += 22
    due_date = data.get("due_date") or ""
    if due_date:
        _text(d, (50, y), f"Due: {due_date}", 11, color="#dc2626")
    if data.get("notes"):
        _text(d, (420, y), str(data["notes"]), 11, color="#555555")
    y += 20
    _hline(d, y, color="#dddddd", width=2); y += 16

    items = data.get("items", [])
    y = _items_table(d, items, y, show_price=True)

    subtotal = sum(_money(i.get("line_total")) for i in items)
    if not subtotal:
        subtotal = _money(data.get("final_total_amount"))
    tax_rate = _money(data.get("tax_rate"))
    tax_amt  = round(subtotal * tax_rate / 100, 2) if tax_rate else _money(data.get("tax_amount"))
    total    = round(subtotal + tax_amt, 2)
    cur      = str(data.get("currency", "LKR") or "LKR")

    y += 8
    _hline(d, y, color="#aaaaaa"); y += 14
    for lbl, val in [("Subtotal", subtotal), (f"Tax ({tax_rate:.0f}%)" if tax_rate else None, tax_amt)]:
        if lbl and val:
            _text(d, (600, y), lbl, 11, color="#666666")
            _text(d, (744, y), f"{val:,.2f}", 11, anchor="ra")
            y += 18
    _hline(d, y, color=color, width=2); y += 14
    _text(d, (580, y), f"TOTAL ({cur})", 14, bold=True)
    _text(d, (744, y), f"{total:,.2f}", 18, bold=True, color=color, anchor="ra")
    y += 40

    d.rectangle([(50, y), (744, y + 44)], fill="#eff6ff", outline="#bfdbfe")
    _text(d, (397, y + 10), f"Invoice: {data.get('order_id','')}  ·  Created via SME-GPT",
          10, color="#1e40af", anchor="ma")
    _text(d, (397, y + 28), "Please transfer to your registered bank account.",
          10, color="#1e40af", anchor="ma")

    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(150, 150))
    return buf.getvalue()


def _generate_po(data: dict) -> bytes:
    img, d = _new_canvas()
    color = DOC_COLORS["po"]
    _header(d, "Purchase Order", data.get("order_id", ""), data.get("company_name", ""),
            data.get("date", ""), color)

    y = 132
    supplier = str(data.get("supplier_name", "") or "Supplier")
    _text(d, (50,  y), "SUPPLIER",    10, bold=True, color="#888888")
    _text(d, (420, y), "ORDERED BY",  10, bold=True, color="#888888")
    y += 16
    _text(d, (50,  y), supplier, 15, bold=True)
    _text(d, (420, y), str(data.get("company_name") or ""), 14, bold=True)
    y += 22
    if data.get("due_date"):
        _text(d, (50, y), f"Required by: {data['due_date']}", 11, color=color)
    if data.get("notes"):
        _text(d, (420, y), str(data["notes"]), 11, color="#555555")
    y += 28
    _hline(d, y, color="#dddddd", width=2); y += 16

    items = data.get("items", [])
    y = _items_table(d, items, y, show_price=True)

    total = sum(_money(i.get("line_total")) for i in items)
    if not total:
        total = _money(data.get("final_total_amount"))
    cur = str(data.get("currency", "LKR") or "LKR")

    y += 10
    _hline(d, y, color=color, width=2); y += 14
    _text(d, (580, y), f"ORDER TOTAL ({cur})", 14, bold=True)
    _text(d, (744, y), f"{total:,.2f}", 18, bold=True, color=color, anchor="ra")
    y += 40

    d.rectangle([(50, y), (744, y + 44)], fill="#f5f3ff", outline="#ddd6fe")
    _text(d, (397, y + 12), f"PO: {data.get('order_id','')}  ·  Authorised by: {data.get('company_name','')}",
          10, color="#5b21b6", anchor="ma")
    _text(d, (397, y + 30), "This PO is valid for 30 days from issue date.",
          10, color="#5b21b6", anchor="ma")

    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(150, 150))
    return buf.getvalue()


def _generate_dn(data: dict) -> bytes:
    img, d = _new_canvas()
    color = DOC_COLORS["dn"]
    _header(d, "Delivery Note", data.get("order_id", ""), data.get("company_name", ""),
            data.get("date", ""), color)

    y = 132
    supplier = str(data.get("supplier_name", "") or "Supplier")
    _text(d, (50,  y), "DELIVERED BY", 10, bold=True, color="#888888")
    _text(d, (420, y), "RECEIVED BY",  10, bold=True, color="#888888")
    y += 16
    _text(d, (50,  y), supplier, 15, bold=True)
    _text(d, (420, y), str(data.get("company_name") or ""), 14, bold=True)
    y += 22
    if data.get("due_date"):
        _text(d, (50, y), f"Delivery Date: {data['due_date']}", 11, color=color)
    if data.get("notes"):
        _text(d, (420, y), str(data["notes"]), 11, color="#555555")
    y += 28
    _hline(d, y, color="#dddddd", width=2); y += 16

    items = data.get("items", [])
    # DN items: show qty + unit, no price
    items_dn = [
        {**i, "unit": str(i.get("unit") or i.get("description", "pcs")[:4])}
        for i in items
    ]
    y = _items_table(d, items_dn, y, show_price=False)
    y += 20

    _hline(d, y, color=color, width=2); y += 20

    # Signature boxes
    for lx, label in [(50, "Delivered By"), (420, "Received By")]:
        d.rectangle([(lx, y), (lx + 290, y + 80)], outline="#dddddd")
        _text(d, (lx + 10, y + 10), label, 10, bold=True, color="#555555")
        _text(d, (lx + 10, y + 54), "Name: _______________________", 10, color="#999999")
        _text(d, (lx + 10, y + 70), "Signature: ____________________", 10, color="#999999")
    y += 100

    d.rectangle([(50, y), (744, y + 40)], fill="#fff7ed", outline="#fed7aa")
    _text(d, (397, y + 12), f"DN: {data.get('order_id','')}  ·  {data.get('notes','')}  ·  Created via SME-GPT",
          10, color="#c2410c", anchor="ma")

    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(150, 150))
    return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────

def generate_document_image(data: dict) -> bytes:
    """Generate a PNG document image from manual-entry data.

    Args:
        data: dict with keys: document_type, order_id, date, company_name,
              supplier_name, currency, items, tax_rate, tax_amount, notes,
              final_total_amount, due_date.

    Returns:
        PNG bytes ready to write to disk.
    """
    doc_type = str(data.get("document_type", "receipt") or "receipt").lower().strip()
    generators = {
        "receipt": _generate_receipt,
        "invoice": _generate_invoice,
        "po":      _generate_po,
        "dn":      _generate_dn,
    }
    fn = generators.get(doc_type, _generate_receipt)
    return fn(data)


def save_document_image_bytes(image_bytes: bytes, document_id: str,
                              save_dir: str = "saved_documents") -> str | None:
    """Write PNG bytes to the saved_documents directory and return the relative URL."""
    try:
        os.makedirs(save_dir, exist_ok=True)
        path = Path(save_dir) / f"{document_id}.png"
        path.write_bytes(image_bytes)
        return f"/saved-documents/{document_id}.png"
    except Exception as exc:
        print(f"[MANUAL-GEN] failed to save image for {document_id}: {exc}", flush=True)
        return None
