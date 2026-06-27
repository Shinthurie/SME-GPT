"""
Generate 20 sample AIESEC financial documents as PNG images.
  5 Receipts, 5 Invoices, 5 Purchase Orders, 5 Delivery Notes
Output: backend/test_documents/
"""

import os
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "test_documents")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 794, 1123   # A4 at 96 dpi

# ── fonts ────────────────────────────────────────────────────────────────────
def _font(size=16, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            pass
    return ImageFont.load_default()

def new_page():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    return img, d

def hline(d, y, x1=50, x2=744, color="#cccccc", width=1):
    d.line([(x1, y), (x2, y)], fill=color, width=width)

def text(d, xy, txt, size=14, bold=False, color="#1a1a1a", anchor="la"):
    d.text(xy, str(txt), font=_font(size, bold), fill=color, anchor=anchor)

def header_block(d, doc_type, doc_no, doc_date, color):
    # coloured top bar
    d.rectangle([(0, 0), (W, 90)], fill=color)
    text(d, (50, 18), "AIESEC", 26, bold=True, color="white")
    text(d, (50, 52), "University of Moratuwa | Sri Lanka", 12, color="#ffffffcc")
    text(d, (W-50, 28), doc_type.upper(), 20, bold=True, color="white", anchor="ra")
    text(d, (W-50, 58), f"No: {doc_no}", 12, color="#ffffffdd", anchor="ra")

    # sub-header strip
    d.rectangle([(0, 90), (W, 115)], fill="#f3f4f6")
    text(d, (50, 97), f"Date: {doc_date}", 11, color="#444444")
    text(d, (W-50, 97), "info@aiesec.lk  |  +94 77 123 4567", 11, color="#444444", anchor="ra")
    hline(d, 115, color="#dddddd", width=2)

DATES = [date(2026, 1, 15), date(2026, 2, 3), date(2026, 3, 20),
         date(2026, 4, 8), date(2026, 5, 14)]

# ═══════════════════════════════════════════════════════════════════════════════
# RECEIPTS
# ═══════════════════════════════════════════════════════════════════════════════
receipts = [
    {
        "no": "REC-2026-001", "customer": "Pasindu Fernando", "items": [
            ("AIESEC Membership Fee – Q1 2026", 1, 2500),
            ("LC Leadership Conference Pass",   1, 1500),
        ]
    },
    {
        "no": "REC-2026-002", "customer": "Nethmi Perera", "items": [
            ("Global Volunteer Programme Fee",  1, 5000),
            ("Induction Kit (T-shirt + Badge)", 1,  950),
        ]
    },
    {
        "no": "REC-2026-003", "customer": "Kasun Rajapaksa", "items": [
            ("AIESEC Membership Fee – Q2 2026", 1, 2500),
            ("Exchange Participant Training",   1, 3000),
            ("Accommodation – 2 nights",        2, 1800),
        ]
    },
    {
        "no": "REC-2026-004", "customer": "Shehani Wijesinghe", "items": [
            ("LEAD Programme Registration",     1, 4500),
            ("Study Materials",                 1,  750),
        ]
    },
    {
        "no": "REC-2026-005", "customer": "Dilshan Madusanka", "items": [
            ("Annual Membership Renewal 2026",  1, 2500),
            ("National Congress Ticket",        1, 3500),
            ("Transport Levy",                  1,  500),
        ]
    },
]

COLOR_RECEIPT = "#16a34a"
for i, r in enumerate(receipts, 1):
    img, d = new_page()
    header_block(d, "Receipt", r["no"], DATES[i-1].strftime("%d %b %Y"), COLOR_RECEIPT)

    y = 135
    text(d, (50, y), "Received From:", 11, color="#666666"); y += 18
    text(d, (50, y), r["customer"], 16, bold=True); y += 28
    hline(d, y); y += 18

    # items header
    text(d, (50,  y), "Description",  11, bold=True, color="#555555")
    text(d, (560, y), "Qty",  11, bold=True, color="#555555", anchor="ra")
    text(d, (650, y), "Unit Price",  11, bold=True, color="#555555", anchor="ra")
    text(d, (744, y), "Amount (LKR)", 11, bold=True, color="#555555", anchor="ra")
    y += 14; hline(d, y); y += 12

    total = 0
    for desc, qty, price in r["items"]:
        amt = qty * price
        total += amt
        text(d, (50,  y), desc,  13)
        text(d, (560, y), str(qty), 13, anchor="ra")
        text(d, (650, y), f"{price:,.2f}", 13, anchor="ra")
        text(d, (744, y), f"{amt:,.2f}", 13, anchor="ra")
        y += 24
        hline(d, y, color="#eeeeee"); y += 10

    y += 10
    hline(d, y, color="#333333", width=2); y += 16
    text(d, (600, y), "TOTAL (LKR)", 13, bold=True)
    text(d, (744, y), f"{total:,.2f}", 16, bold=True, color=COLOR_RECEIPT, anchor="ra")
    y += 35

    d.rectangle([(50, y), (744, y+50)], fill="#f0fdf4", outline="#bbf7d0")
    text(d, (397, y+15), f"Payment received. Thank you, {r['customer'].split()[0]}!", 12, color="#166534", anchor="ma")
    text(d, (397, y+35), f"Receipt No: {r['no']}  |  AIESEC UoM", 10, color="#166534", anchor="ma")

    fname = os.path.join(OUT_DIR, f"receipt_{i:02d}_{r['no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")

# ═══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ═══════════════════════════════════════════════════════════════════════════════
invoices = [
    {
        "no": "INV-2026-001", "client": "Virtusa (Pvt) Ltd", "items": [
            ("Corporate Partnership – Platinum Tier",   1, 150000),
            ("AIESEC Brand Logo on Event Materials",    1,  15000),
            ("3× Social Media Mentions (Facebook/IG)",  3,   5000),
        ]
    },
    {
        "no": "INV-2026-002", "client": "WSO2 Inc.", "items": [
            ("Tech Summit Sponsorship Package",  1, 80000),
            ("Exhibition Booth (2m × 2m)",       1, 20000),
            ("Speaker Slot – 30 Minutes",        1, 10000),
        ]
    },
    {
        "no": "INV-2026-003", "client": "Hemas Holdings PLC", "items": [
            ("Corporate Bronze Sponsorship",     1, 50000),
            ("Career Fair Participation",        1, 15000),
            ("Brochure Insert (500 pcs)",        500,   80),
        ]
    },
    {
        "no": "INV-2026-004", "client": "MAS Holdings Ltd", "items": [
            ("Global Talent Recruitment Drive",  1, 120000),
            ("Campus Presentation Session",      2,  10000),
            ("Merchandise Bundle",               1,   8500),
        ]
    },
    {
        "no": "INV-2026-005", "client": "Commercial Bank of Ceylon", "items": [
            ("Financial Literacy Workshop",      1, 35000),
            ("Digital Banner at Venue",          1,  5000),
            ("Post-event Summary Report",        1,  8000),
        ]
    },
]

COLOR_INVOICE = "#2252b5"
for i, inv in enumerate(invoices, 1):
    img, d = new_page()
    due = (DATES[i-1] + timedelta(days=30)).strftime("%d %b %Y")
    header_block(d, "Invoice", inv["no"], DATES[i-1].strftime("%d %b %Y"), COLOR_INVOICE)

    y = 135
    # Two-column bill to/from
    text(d, (50,  y), "BILLED TO", 10, bold=True, color="#888888");
    text(d, (420, y), "BILLED FROM", 10, bold=True, color="#888888")
    y += 16
    text(d, (50,  y), inv["client"], 15, bold=True)
    text(d, (420, y), "AIESEC in Sri Lanka", 15, bold=True)
    y += 20
    text(d, (50,  y), "Colombo, Sri Lanka", 11, color="#555555")
    text(d, (420, y), "University of Moratuwa, Katubedda", 11, color="#555555")
    y += 16
    text(d, (420, y), f"Due Date: {due}", 11, color="#dc2626")
    y += 20; hline(d, y, color="#dddddd", width=2); y += 18

    text(d, (50,  y), "Description",   11, bold=True, color="#555555")
    text(d, (540, y), "Qty",           11, bold=True, color="#555555", anchor="ra")
    text(d, (640, y), "Unit Price",    11, bold=True, color="#555555", anchor="ra")
    text(d, (744, y), "Amount (LKR)",  11, bold=True, color="#555555", anchor="ra")
    y += 14; hline(d, y); y += 12

    subtotal = 0
    for desc, qty, price in inv["items"]:
        amt = qty * price; subtotal += amt
        text(d, (50,  y), desc, 13)
        text(d, (540, y), str(qty), 13, anchor="ra")
        text(d, (640, y), f"{price:,.2f}", 13, anchor="ra")
        text(d, (744, y), f"{amt:,.2f}", 13, anchor="ra")
        y += 24; hline(d, y, color="#eeeeee"); y += 10

    y += 10; hline(d, y, color="#aaaaaa"); y += 14
    vat = round(subtotal * 0.15, 2)
    total = subtotal + vat
    for label, val in [("Subtotal", subtotal), ("VAT (15%)", vat)]:
        text(d, (600, y), label, 12, color="#555555")
        text(d, (744, y), f"{val:,.2f}", 12, anchor="ra")
        y += 22
    hline(d, y, color="#2252b5", width=2); y += 14
    text(d, (600, y), "TOTAL (LKR)", 14, bold=True)
    text(d, (744, y), f"{total:,.2f}", 17, bold=True, color=COLOR_INVOICE, anchor="ra")
    y += 40

    d.rectangle([(50, y), (744, y+45)], fill="#eff6ff", outline="#bfdbfe")
    text(d, (397, y+12), "Please transfer to: Commercial Bank | Acc: 1234567890 | Branch: UoM", 10, color="#1e40af", anchor="ma")
    text(d, (397, y+30), f"Reference: {inv['no']}  |  AIESEC UoM", 10, color="#1e40af", anchor="ma")

    fname = os.path.join(OUT_DIR, f"invoice_{i:02d}_{inv['no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")

# ═══════════════════════════════════════════════════════════════════════════════
# PURCHASE ORDERS
# ═══════════════════════════════════════════════════════════════════════════════
pos = [
    {
        "no": "PO-2026-001", "supplier": "Classic Printers (Pvt) Ltd", "items": [
            ("A4 Event Brochures – Full Colour (4 pages)",  500,  45),
            ("Roll-up Banner 85cm × 200cm",                   4, 3500),
            ("Table Tent Cards (double-sided)",             200,  18),
        ]
    },
    {
        "no": "PO-2026-002", "supplier": "Future Events Lanka", "items": [
            ("Venue Hire – Grand Ballroom (6 hrs)",           1, 75000),
            ("PA System + Microphones",                       1, 15000),
            ("Stage Lighting Package",                        1, 12000),
            ("Projector & Screen (HDMI)",                     2,  4500),
        ]
    },
    {
        "no": "PO-2026-003", "supplier": "Lanka Beverage Supplies", "items": [
            ("Mineral Water Bottles 500ml",                 100,    55),
            ("Fruit Juice Cartons 200ml",                   100,    75),
            ("Disposable Cups (pack of 50)",                 10,   350),
        ]
    },
    {
        "no": "PO-2026-004", "supplier": "TechRent LK", "items": [
            ("Laptop for Presenter (i7, 1-day hire)",         3,  2500),
            ("Wireless Clicker/Presenter",                    3,   500),
            ("HDMI Cables 3m",                                5,   450),
        ]
    },
    {
        "no": "PO-2026-005", "supplier": "Colombo Hospitality Supplies", "items": [
            ("Name Badge Holders (pack of 100)",              2,  1200),
            ("Lanyards – Blue Printed",                     200,   120),
            ("Notebooks A5 (branded)",                      150,   280),
            ("Ballpoint Pens (branded, box of 50)",           4,   850),
        ]
    },
]

COLOR_PO = "#7c3aed"
for i, po in enumerate(pos, 1):
    img, d = new_page()
    delivery_date = (DATES[i-1] + timedelta(days=7)).strftime("%d %b %Y")
    header_block(d, "Purchase Order", po["no"], DATES[i-1].strftime("%d %b %Y"), COLOR_PO)

    y = 135
    text(d, (50,  y), "SUPPLIER", 10, bold=True, color="#888888")
    text(d, (420, y), "ORDERED BY", 10, bold=True, color="#888888")
    y += 16
    text(d, (50,  y), po["supplier"], 15, bold=True)
    text(d, (420, y), "AIESEC – University of Moratuwa", 14, bold=True)
    y += 20
    text(d, (420, y), f"Required by: {delivery_date}", 11, color="#7c3aed")
    text(d, (420, y+18), "Authorised by: President, AIESEC UoM", 11, color="#555555")
    y += 45; hline(d, y, color="#dddddd", width=2); y += 18

    text(d, (50,  y), "Item Description",  11, bold=True, color="#555555")
    text(d, (500, y), "Qty",               11, bold=True, color="#555555", anchor="ra")
    text(d, (620, y), "Unit Price (LKR)",  11, bold=True, color="#555555", anchor="ra")
    text(d, (744, y), "Total (LKR)",       11, bold=True, color="#555555", anchor="ra")
    y += 14; hline(d, y); y += 12

    total = 0
    for desc, qty, price in po["items"]:
        amt = qty * price; total += amt
        text(d, (50,  y), desc, 13)
        text(d, (500, y), str(qty), 13, anchor="ra")
        text(d, (620, y), f"{price:,.2f}", 13, anchor="ra")
        text(d, (744, y), f"{amt:,.2f}", 13, anchor="ra")
        y += 26; hline(d, y, color="#eeeeee"); y += 10

    y += 10; hline(d, y, color="#7c3aed", width=2); y += 14
    text(d, (600, y), "ORDER TOTAL (LKR)", 14, bold=True)
    text(d, (744, y), f"{total:,.2f}", 17, bold=True, color=COLOR_PO, anchor="ra")
    y += 40

    d.rectangle([(50, y), (744, y+60)], fill="#f5f3ff", outline="#ddd6fe")
    text(d, (397, y+10), "Delivery Instructions: Please deliver to AIESEC Room, Faculty of IT Building,", 10, color="#5b21b6", anchor="ma")
    text(d, (397, y+26), "University of Moratuwa, Katubedda 10400. Contact: +94 77 123 4567", 10, color="#5b21b6", anchor="ma")
    text(d, (397, y+44), f"PO Ref: {po['no']}  |  This PO is valid for 30 days from issue date.", 10, color="#5b21b6", anchor="ma")

    fname = os.path.join(OUT_DIR, f"po_{i:02d}_{po['no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")

# ═══════════════════════════════════════════════════════════════════════════════
# DELIVERY NOTES
# ═══════════════════════════════════════════════════════════════════════════════
dns = [
    {
        "no": "DN-2026-001", "po": "PO-2026-001", "supplier": "Classic Printers (Pvt) Ltd", "items": [
            ("A4 Event Brochures – Full Colour (4 pages)",    500, "pcs",  "✓ Good"),
            ("Roll-up Banner 85cm × 200cm",                     4, "pcs",  "✓ Good"),
            ("Table Tent Cards (double-sided)",               200, "pcs",  "✓ Good"),
        ]
    },
    {
        "no": "DN-2026-002", "po": "PO-2026-002", "supplier": "Future Events Lanka", "items": [
            ("Venue Setup Confirmation",                         1, "unit", "✓ Ready"),
            ("PA System Installed",                             1, "set",  "✓ Good"),
            ("Stage Lighting",                                  1, "set",  "✓ Good"),
            ("Projector & Screen",                              2, "unit", "✓ Good"),
        ]
    },
    {
        "no": "DN-2026-003", "po": "PO-2026-003", "supplier": "Lanka Beverage Supplies", "items": [
            ("Mineral Water Bottles 500ml",                   100, "btl",  "✓ Good"),
            ("Fruit Juice Cartons 200ml",                     100, "pcs",  "✓ Good"),
            ("Disposable Cups (pack of 50)",                   10, "pack", "✓ Good"),
        ]
    },
    {
        "no": "DN-2026-004", "po": "PO-2026-004", "supplier": "TechRent LK", "items": [
            ("Laptop for Presenter (i7)",                       3, "unit", "✓ Good"),
            ("Wireless Clicker/Presenter",                      3, "unit", "1 minor scratch"),
            ("HDMI Cables 3m",                                  5, "pcs",  "✓ Good"),
        ]
    },
    {
        "no": "DN-2026-005", "po": "PO-2026-005", "supplier": "Colombo Hospitality Supplies", "items": [
            ("Name Badge Holders (pack of 100)",                2, "pack", "✓ Good"),
            ("Lanyards – Blue Printed",                       200, "pcs",  "✓ Good"),
            ("Notebooks A5 (branded)",                        150, "pcs",  "✓ Good"),
            ("Ballpoint Pens (branded, box of 50)",             4, "box",  "✓ Good"),
        ]
    },
]

COLOR_DN = "#ea6c0a"
for i, dn in enumerate(dns, 1):
    img, d = new_page()
    header_block(d, "Delivery Note", dn["no"], DATES[i-1].strftime("%d %b %Y"), COLOR_DN)

    y = 135
    text(d, (50,  y), "DELIVERED BY", 10, bold=True, color="#888888")
    text(d, (420, y), "RECEIVED BY", 10, bold=True, color="#888888")
    y += 16
    text(d, (50,  y), dn["supplier"], 15, bold=True)
    text(d, (420, y), "AIESEC – University of Moratuwa", 14, bold=True)
    y += 20
    text(d, (50,  y), f"PO Reference: {dn['po']}", 11, color="#ea6c0a")
    text(d, (420, y), "Delivery Location: Faculty of IT, UoM", 11, color="#555555")
    y += 16
    text(d, (420, y), f"Delivery Date: {DATES[i-1].strftime('%d %b %Y')}", 11, color="#555555")
    y += 25; hline(d, y, color="#dddddd", width=2); y += 18

    text(d, (50,  y), "Item Description",  11, bold=True, color="#555555")
    text(d, (490, y), "Qty",               11, bold=True, color="#555555", anchor="ra")
    text(d, (560, y), "Unit",              11, bold=True, color="#555555", anchor="ra")
    text(d, (744, y), "Condition",         11, bold=True, color="#555555", anchor="ra")
    y += 14; hline(d, y); y += 12

    for desc, qty, unit, cond in dn["items"]:
        cond_color = "#16a34a" if "✓" in cond else "#dc2626"
        text(d, (50,  y), desc, 13)
        text(d, (490, y), str(qty), 13, anchor="ra")
        text(d, (560, y), unit, 13, anchor="ra")
        text(d, (744, y), cond, 12, color=cond_color, anchor="ra")
        y += 26; hline(d, y, color="#eeeeee"); y += 10

    y += 20
    hline(d, y, color="#ea6c0a", width=2); y += 20

    # Signature boxes
    for lx, label in [(50, "Delivered By"), (420, "Received By (AIESEC)")]:
        d.rectangle([(lx, y), (lx+290, y+80)], outline="#dddddd")
        text(d, (lx+10, y+10), label, 10, bold=True, color="#555555")
        text(d, (lx+10, y+55), "Name: _______________________", 10, color="#999999")
        text(d, (lx+10, y+70), "Signature: ____________________", 10, color="#999999")

    y += 100
    d.rectangle([(50, y), (744, y+40)], fill="#fff7ed", outline="#fed7aa")
    text(d, (397, y+12), f"DN: {dn['no']}  |  All items inspected on receipt. Report damage within 24 hours.", 10, color="#c2410c", anchor="ma")

    fname = os.path.join(OUT_DIR, f"dn_{i:02d}_{dn['no']}.png")
    img.save(fname, "PNG", dpi=(150, 150))
    print(f"  OK {fname}")

print(f"\n✅  20 documents saved to: {os.path.abspath(OUT_DIR)}")
