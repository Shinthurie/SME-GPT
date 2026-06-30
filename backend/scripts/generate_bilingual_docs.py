"""
Generate bilingual test documents (PO, DN, Invoice, Receipt) as PNG images.

Two sets:
  - "si" set: pure Sinhala text throughout
  - "bi" set: English + Sinhala bilingual labels/descriptions (stacked two-line
    labels: English on top, Sinhala below — concatenating "EN / SI" inline
    overflowed table columns and two-column party blocks)

Both sets tell a single coherent supply-chain story (PO -> DN -> Invoice -> Receipt)
so cross-document linking can be exercised in tests.

Output: backend/test_documents/
"""

import os
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "test_documents")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 794, 1123   # A4 at 96 dpi

# Nirmala UI renders both Latin and Sinhala glyphs correctly (verified with libraqm
# shaping for vowel-sign reordering), so a single font family covers both sets.
FONT_PATH = "C:/Windows/Fonts/Nirmala.ttc"
FONT_REGULAR_IDX = 0
FONT_BOLD_IDX = 1

_font_cache: dict = {}

def _font(size=16, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        idx = FONT_BOLD_IDX if bold else FONT_REGULAR_IDX
        _font_cache[key] = ImageFont.truetype(FONT_PATH, size, index=idx, layout_engine=ImageFont.Layout.RAQM)
    return _font_cache[key]

def new_page():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    return img, d

def hline(d, y, x1=50, x2=744, color="#cccccc", width=1):
    d.line([(x1, y), (x2, y)], fill=color, width=width)

def text(d, xy, txt, size=14, bold=False, color="#1a1a1a", anchor="la"):
    d.text(xy, str(txt), font=_font(size, bold), fill=color, anchor=anchor)

def stacked(d, x, y, lines, anchor="la", size0=13, bold0=True, color="#1a1a1a", gap=17):
    """Draw 1-2 lines stacked vertically (used for bilingual names). Returns next y."""
    for i, ln in enumerate(lines):
        sz = size0 if i == 0 else max(size0 - 2, 10)
        bold = bold0 if i == 0 else False
        col = color if i == 0 else "#555555"
        text(d, (x, y + i * gap), ln, sz, bold=bold, color=col, anchor=anchor)
    return y + len(lines) * gap

def col_header(d, x, y, en, si, bilingual, anchor="la"):
    """Draw a table column header. Bilingual headers stack EN above SI (smaller)
    to avoid overflowing narrow column widths; monolingual just draws one line."""
    if bilingual:
        text(d, (x, y), en, 10, bold=True, color="#555555", anchor=anchor)
        text(d, (x, y + 13), si, 10, bold=True, color="#555555", anchor=anchor)
        return 28
    text(d, (x, y), si, 11, bold=True, color="#555555", anchor=anchor)
    return 16

def header_block(d, doc_type, doc_no, doc_date, color, company_en, company_si, contact):
    d.rectangle([(0, 0), (W, 90)], fill=color)
    text(d, (50, 14), company_en, 20, bold=True, color="white")
    text(d, (50, 44), company_si, 14, color="white")
    text(d, (50, 66), "Sri Lanka", 11, color="#ffffffcc")
    text(d, (W - 50, 22), doc_type.upper(), 17, bold=True, color="white", anchor="ra")
    text(d, (W - 50, 56), f"No: {doc_no}", 11, color="#ffffffdd", anchor="ra")

    d.rectangle([(0, 90), (W, 115)], fill="#f3f4f6")
    text(d, (50, 97), f"Date: {doc_date}", 11, color="#444444")
    text(d, (W - 50, 97), contact, 11, color="#444444", anchor="ra")
    hline(d, 115, color="#dddddd", width=2)

DATES = [date(2026, 4, 2), date(2026, 4, 9), date(2026, 4, 16), date(2026, 4, 16)]

# ════════════════════════════════════════════════════════════════════════════
# Field-label dictionaries
# ════════════════════════════════════════════════════════════════════════════

L_SI = {
    "supplier": "සැපයුම්කරු",
    "ordered_by": "ඇණවුම් කළේ",
    "delivered_by": "බෙදා හරින ලද්දේ",
    "received_by": "භාර ගත්තේ",
    "billed_to": "බිල් කරන ලද්දේ",
    "billed_from": "බිල්පත් කළේ",
    "received_from": "ලැබුණේ",
    "required_by": "අවශ්‍ය දිනය",
    "delivery_date": "බෙදාහැරීමේ දිනය",
    "due_date": "ගෙවිය යුතු දිනය",
    "subtotal": "උප එකතුව",
    "tax": "බදු (15%)",
    "total": "මුළු එකතුව",
    "order_total": "ඇණවුම් එකතුව",
    "name": "නම",
    "signature": "අත්සන",
    "good": "✓ හොඳයි",
    "po_ref": "ඇණවුම් අංකය",
    "notes_po": "මෙම ඇණවුම නිකුත් කළ දින සිට දින 30ක් වලංගුය.",
    "notes_dn": "භාරගත් වහාම සියලුම අයිතම පරීක්ෂා කරන්න. හානි පැය 24ක් ඇතුළත වාර්තා කරන්න.",
    "thanks": "ගෙවීම ලැබුණි. ස්තූතියි",
    "bank_note": "කරුණාකර ලියාපදිංචි බැංකු ගිණුමට මුදල් මාරු කරන්න.",
}

L_BI = {
    "supplier": "Supplier / සැපයුම්කරු",
    "ordered_by": "Ordered By / ඇණවුම් කළේ",
    "delivered_by": "Delivered By / බෙදා හරින ලද්දේ",
    "received_by": "Received By / භාර ගත්තේ",
    "billed_to": "Billed To / බිල් කරන ලද්දේ",
    "billed_from": "Billed From / බිල්පත් කළේ",
    "received_from": "Received From / ලැබුණේ",
    "required_by": "Required by / අවශ්‍ය දිනය",
    "delivery_date": "Delivery Date / බෙදාහැරීමේ දිනය",
    "due_date": "Due Date / ගෙවිය යුතු දිනය",
    "subtotal": "Subtotal / උප එකතුව",
    "tax": "VAT (15%) / බදු",
    "total": "TOTAL (LKR) / මුළු එකතුව",
    "order_total": "ORDER TOTAL / ඇණවුම් එකතුව",
    "name": "Name / නම",
    "signature": "Signature / අත්සන",
    "good": "✓ Good / හොඳයි",
    "po_ref": "PO Ref / ඇණවුම් අංකය",
    "notes_po": "This PO is valid for 30 days from issue date. / මෙම ඇණවුම දින 30ක් වලංගුය.",
    "notes_dn": "Inspect all items on receipt. Report damage within 24 hours. / භාරගත් වහාම පරීක්ෂා කරන්න.",
    "thanks": "Payment received. Thank you / ගෙවීම ලැබුණි. ස්තූතියි",
    "bank_note": "Please transfer to the registered bank account. / කරුණාකර බැංකු ගිණුමට මාරු කරන්න.",
}

# Column header text pairs (en, si) — shared by both sets; "si" set only uses [1]
HEAD = {
    "description": ("Description", "විස්තරය"),
    "qty": ("Qty", "ප්‍රමාණය"),
    "unit": ("Unit", "ඒකකය"),
    "unit_price": ("Unit Price", "ඒකක මිල"),
    "amount": ("Amount (LKR)", "මුදල (රු.)"),
    "condition": ("Condition", "තත්ත්වය"),
}

# ════════════════════════════════════════════════════════════════════════════
# Story data — two parallel supply chains (PO -> DN -> Invoice -> Receipt)
# ════════════════════════════════════════════════════════════════════════════

SI_STORY = {
    "company_en": "Lanka Agri Supplies",
    "company_lines": ["Lanka Agri Supplies / ලංකා කෘෂි සැපයුම් (පුද්) සමාගම"],
    "company_si": "ලංකා කෘෂි සැපයුම් (පුද්) සමාගම",
    "contact": "info@lankaagri.lk | +94 77 234 5678",
    "color_po": "#7c3aed", "color_dn": "#ea6c0a", "color_inv": "#2252b5", "color_rec": "#16a34a",
    "counterparty_lines": ["කොළඹ සුපර් මාර්ට්"],
    "items": [
        ("සුදු සහල් මලු (කි.ග්‍රෑ. 25)", 40, 4250),
        ("රතු පරිප්පු මලු (කි.ග්‍රෑ. 10)", 60, 2100),
        ("සීනි මලු (කි.ග්‍රෑ. 25)", 20, 5400),
        ("තේ කොළ පැකට්ට (ග්‍රෑ. 400)", 100, 850),
    ],
    "po_no": "PO-2026-S01", "dn_no": "DN-2026-S01", "inv_no": "INV-2026-S01", "rec_no": "REC-2026-S01",
    "delivery_loc": "නො. 45, ගාලු පාර, කොළඹ 06",
    "authorised_by": "කළමනාකරු, කොළඹ සුපර් මාර්ට්",
    "bank_line": "වාණිජ බැංකුව | ගිණුම: 8801234567 | ශාඛාව: කොළඹ 06",
}

BI_STORY = {
    "company_en": "Ceylon Spice Traders (Pvt) Ltd",
    "company_lines": ["Ceylon Spice Traders (Pvt) Ltd", "සිලෝන් කුළුබඩු වෙළෙන්දෝ"],
    "company_si": "සිලෝන් කුළුබඩු වෙළෙන්දෝ",
    "contact": "sales@ceylonspice.lk | +94 76 345 6789",
    "color_po": "#7c3aed", "color_dn": "#ea6c0a", "color_inv": "#2252b5", "color_rec": "#16a34a",
    "counterparty_lines": ["Highland Hotels Group", "හයිලන්ඩ් හෝටල් සමූහය"],
    "items": [
        ("Ceylon Cinnamon Sticks 1kg / ලංකා කුරුඳු කූරු", 30, 3800),
        ("Black Pepper Whole 1kg / කළු ගම්මිරිස්", 25, 2600),
        ("Cardamom Pods 500g / එනසාල්", 15, 4200),
        ("Cloves 500g / කරාබුනැටි", 20, 3100),
    ],
    "po_no": "PO-2026-B01", "dn_no": "DN-2026-B01", "inv_no": "INV-2026-B01", "rec_no": "REC-2026-B01",
    "delivery_loc": "Kandy Road Warehouse, Kadawatha / කඩවත ගබඩාව",
    "authorised_by": "Procurement Manager / මිලදී ගැනීමේ කළමනාකරු",
    "bank_line": "Commercial Bank | Acc: 8809988776 | Branch: Kandy / ශාඛාව",
}


def money(x):
    return f"{x:,.2f}"


# ════════════════════════════════════════════════════════════════════════════
# Document generators (parameterised by label-dict L, story data S, prefix)
# ════════════════════════════════════════════════════════════════════════════

def gen_po(L, S, prefix):
    bilingual = prefix == "bi"
    img, d = new_page()
    color = S["color_po"]
    header_block(d, "Purchase Order" if bilingual else "මිලදී ගැනීමේ ඇණවුම",
                 S["po_no"], DATES[0].strftime("%d %b %Y"), color,
                 S["company_en"], S["company_si"], S["contact"])

    y = 135
    text(d, (50, y), L["supplier"], 10, bold=True, color="#888888")
    text(d, (420, y), L["ordered_by"], 10, bold=True, color="#888888")
    y += 18
    y_after_left = stacked(d, 50, y, S["company_lines"])
    y_after_right = stacked(d, 420, y, S["counterparty_lines"])
    y = max(y_after_left, y_after_right) + 4
    required = (DATES[0] + timedelta(days=7)).strftime("%d %b %Y")
    text(d, (50, y), f"{L['required_by']}: {required}", 11, color=color)
    text(d, (420, y), S["authorised_by"], 11, color="#555555")
    y += 24
    hline(d, y, color="#dddddd", width=2); y += 18

    hy = col_header(d, 50, y, *HEAD["description"], bilingual)
    col_header(d, 480, y, *HEAD["qty"], bilingual, anchor="ra")
    col_header(d, 610, y, *HEAD["unit_price"], bilingual, anchor="ra")
    col_header(d, 744, y, *HEAD["amount"], bilingual, anchor="ra")
    y += hy; hline(d, y); y += 12

    total = 0
    for desc, qty, price in S["items"]:
        amt = qty * price; total += amt
        text(d, (50, y), desc, 12)
        text(d, (480, y), str(qty), 12, anchor="ra")
        text(d, (610, y), money(price), 12, anchor="ra")
        text(d, (744, y), money(amt), 12, anchor="ra")
        y += 26; hline(d, y, color="#eeeeee"); y += 10

    y += 8; hline(d, y, color=color, width=2); y += 16
    text(d, (600, y), L["order_total"], 12, bold=True, anchor="ra")
    text(d, (744, y), money(total), 16, bold=True, color=color, anchor="ra")
    y += 40

    d.rectangle([(50, y), (744, y + 60)], fill="#f5f3ff", outline="#ddd6fe")
    text(d, (397, y + 12), f"{S['delivery_loc']}", 10, color="#5b21b6", anchor="ma")
    text(d, (397, y + 32), L["notes_po"], 10, color="#5b21b6", anchor="ma")

    fname = os.path.join(OUT_DIR, f"{prefix}_po_01_{S['po_no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")


def gen_dn(L, S, prefix):
    bilingual = prefix == "bi"
    img, d = new_page()
    color = S["color_dn"]
    header_block(d, "Delivery Note" if bilingual else "බෙදාහැරීමේ සටහන",
                 S["dn_no"], DATES[1].strftime("%d %b %Y"), color,
                 S["company_en"], S["company_si"], S["contact"])

    y = 135
    text(d, (50, y), L["delivered_by"], 10, bold=True, color="#888888")
    text(d, (420, y), L["received_by"], 10, bold=True, color="#888888")
    y += 18
    y_after_left = stacked(d, 50, y, S["company_lines"])
    y_after_right = stacked(d, 420, y, S["counterparty_lines"])
    y = max(y_after_left, y_after_right) + 2
    text(d, (50, y), f"{L['po_ref']}: {S['po_no']}", 11, color=color)
    text(d, (420, y), S["delivery_loc"], 11, color="#555555")
    y += 16
    text(d, (420, y), f"{L['delivery_date']}: {DATES[1].strftime('%d %b %Y')}", 11, color="#555555")
    y += 24; hline(d, y, color="#dddddd", width=2); y += 18

    hy = col_header(d, 50, y, *HEAD["description"], bilingual)
    col_header(d, 470, y, *HEAD["qty"], bilingual, anchor="ra")
    col_header(d, 560, y, *HEAD["unit"], bilingual, anchor="ra")
    col_header(d, 744, y, *HEAD["condition"], bilingual, anchor="ra")
    y += hy; hline(d, y); y += 12

    for desc, qty, _price in S["items"]:
        text(d, (50, y), desc, 12)
        text(d, (470, y), str(qty), 12, anchor="ra")
        text(d, (560, y), "kg" if "kg" in desc.lower() or "කි.ග්‍රෑ" in desc else "pcs", 12, anchor="ra")
        text(d, (744, y), L["good"], 11, color="#16a34a", anchor="ra")
        y += 26; hline(d, y, color="#eeeeee"); y += 10

    y += 16; hline(d, y, color=color, width=2); y += 20

    for lx, label in [(50, L["delivered_by"]), (420, L["received_by"])]:
        d.rectangle([(lx, y), (lx + 290, y + 80)], outline="#dddddd")
        text(d, (lx + 10, y + 10), label, 10, bold=True, color="#555555")
        text(d, (lx + 10, y + 55), f"{L['name']}: _______________", 10, color="#999999")
        text(d, (lx + 10, y + 70), f"{L['signature']}: ____________", 10, color="#999999")
    y += 100

    d.rectangle([(50, y), (744, y + 40)], fill="#fff7ed", outline="#fed7aa")
    text(d, (397, y + 12), L["notes_dn"], 10, color="#c2410c", anchor="ma")

    fname = os.path.join(OUT_DIR, f"{prefix}_dn_01_{S['dn_no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")


def gen_invoice(L, S, prefix):
    bilingual = prefix == "bi"
    img, d = new_page()
    color = S["color_inv"]
    header_block(d, "Invoice" if bilingual else "ඉන්වොයිසය",
                 S["inv_no"], DATES[2].strftime("%d %b %Y"), color,
                 S["company_en"], S["company_si"], S["contact"])

    y = 135
    text(d, (50, y), L["billed_to"], 10, bold=True, color="#888888")
    text(d, (420, y), L["billed_from"], 10, bold=True, color="#888888")
    y += 18
    y_after_left = stacked(d, 50, y, S["counterparty_lines"])
    y_after_right = stacked(d, 420, y, S["company_lines"])
    y = max(y_after_left, y_after_right) + 2
    due = (DATES[2] + timedelta(days=30)).strftime("%d %b %Y")
    text(d, (50, y), f"{L['due_date']}: {due}", 11, color="#dc2626")
    text(d, (420, y), f"{L['po_ref']}: {S['po_no']}", 11, color="#555555")
    y += 24; hline(d, y, color="#dddddd", width=2); y += 18

    hy = col_header(d, 50, y, *HEAD["description"], bilingual)
    col_header(d, 520, y, *HEAD["qty"], bilingual, anchor="ra")
    col_header(d, 630, y, *HEAD["unit_price"], bilingual, anchor="ra")
    col_header(d, 744, y, *HEAD["amount"], bilingual, anchor="ra")
    y += hy; hline(d, y); y += 12

    subtotal = 0
    for desc, qty, price in S["items"]:
        amt = qty * price; subtotal += amt
        text(d, (50, y), desc, 12)
        text(d, (520, y), str(qty), 12, anchor="ra")
        text(d, (630, y), money(price), 12, anchor="ra")
        text(d, (744, y), money(amt), 12, anchor="ra")
        y += 26; hline(d, y, color="#eeeeee"); y += 10

    y += 8; hline(d, y, color="#aaaaaa"); y += 14
    vat = round(subtotal * 0.15, 2)
    total = subtotal + vat
    text(d, (600, y), L["subtotal"], 11, color="#666666", anchor="ra")
    text(d, (744, y), money(subtotal), 11, anchor="ra")
    y += 20
    text(d, (600, y), L["tax"], 11, color="#666666", anchor="ra")
    text(d, (744, y), money(vat), 11, anchor="ra")
    y += 18
    hline(d, y, color=color, width=2); y += 16
    text(d, (600, y), L["total"], 13, bold=True, anchor="ra")
    text(d, (744, y), money(total), 16, bold=True, color=color, anchor="ra")
    y += 40

    d.rectangle([(50, y), (744, y + 45)], fill="#eff6ff", outline="#bfdbfe")
    text(d, (397, y + 12), S["bank_line"], 10, color="#1e40af", anchor="ma")
    text(d, (397, y + 30), L["bank_note"], 10, color="#1e40af", anchor="ma")

    fname = os.path.join(OUT_DIR, f"{prefix}_invoice_01_{S['inv_no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")


def gen_receipt(L, S, prefix):
    bilingual = prefix == "bi"
    img, d = new_page()
    color = S["color_rec"]
    header_block(d, "Receipt" if bilingual else "රිසිට්පත",
                 S["rec_no"], DATES[3].strftime("%d %b %Y"), color,
                 S["company_en"], S["company_si"], S["contact"])

    y = 135
    text(d, (50, y), L["received_from"], 11, color="#666666"); y += 18
    y = stacked(d, 50, y, S["counterparty_lines"], size0=15)
    y += 4
    text(d, (50, y), f"{L['po_ref']}: {S['po_no']}  |  {S['inv_no']}", 11, color="#666666"); y += 18
    hline(d, y); y += 16

    hy = col_header(d, 50, y, *HEAD["description"], bilingual)
    col_header(d, 540, y, *HEAD["qty"], bilingual, anchor="ra")
    col_header(d, 640, y, *HEAD["unit_price"], bilingual, anchor="ra")
    col_header(d, 744, y, *HEAD["amount"], bilingual, anchor="ra")
    y += hy; hline(d, y); y += 12

    total = 0
    for desc, qty, price in S["items"]:
        amt = qty * price; total += amt
        text(d, (50, y), desc, 12)
        text(d, (540, y), str(qty), 12, anchor="ra")
        text(d, (640, y), money(price), 12, anchor="ra")
        text(d, (744, y), money(amt), 12, anchor="ra")
        y += 26; hline(d, y, color="#eeeeee"); y += 10

    vat = round(total * 0.15, 2)
    grand = total + vat
    y += 8; hline(d, y, color="#aaaaaa"); y += 14
    text(d, (600, y), L["subtotal"], 11, color="#666666", anchor="ra")
    text(d, (744, y), money(total), 11, anchor="ra")
    y += 20
    text(d, (600, y), L["tax"], 11, color="#666666", anchor="ra")
    text(d, (744, y), money(vat), 11, anchor="ra")
    y += 18
    hline(d, y, color="#333333", width=2); y += 16
    text(d, (600, y), L["total"], 13, bold=True, anchor="ra")
    text(d, (744, y), money(grand), 16, bold=True, color=color, anchor="ra")
    y += 40

    d.rectangle([(50, y), (744, y + 50)], fill="#f0fdf4", outline="#bbf7d0")
    text(d, (397, y + 14), L["thanks"], 11, color="#166534", anchor="ma")
    text(d, (397, y + 34), f"{S['rec_no']}  ·  {S['company_lines'][0]}", 10, color="#166534", anchor="ma")

    fname = os.path.join(OUT_DIR, f"{prefix}_receipt_01_{S['rec_no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")


if __name__ == "__main__":
    print("Generating Sinhala-only set...")
    gen_po(L_SI, SI_STORY, "si")
    gen_dn(L_SI, SI_STORY, "si")
    gen_invoice(L_SI, SI_STORY, "si")
    gen_receipt(L_SI, SI_STORY, "si")

    print("Generating English+Sinhala bilingual set...")
    gen_po(L_BI, BI_STORY, "bi")
    gen_dn(L_BI, BI_STORY, "bi")
    gen_invoice(L_BI, BI_STORY, "bi")
    gen_receipt(L_BI, BI_STORY, "bi")

    print(f"\nDone. 8 documents saved to: {os.path.abspath(OUT_DIR)}")
