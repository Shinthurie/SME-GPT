"use client";
// IT-42: Quick Cash Entry + IT-43: Auto-Crop Scanner — floating action button

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getStoredLanguage } from "@/lib/i18n";
import { addNotification } from "@/lib/notifications";
import { resolveBackendUrl } from "@/lib/backendUrl";

const BACKEND_URL = resolveBackendUrl();

const CASH_CATEGORIES = [
  { key: "transport",  icon: "directions_car",  en: "Transport",  si: "ප‍ොදු",       color: "#2252b5" },
  { key: "food",       icon: "restaurant",       en: "Food",       si: "ආහාර",        color: "#16a34a" },
  { key: "supplies",   icon: "inventory_2",      en: "Supplies",   si: "ද්‍රව්‍ය",   color: "#7c3aed" },
  { key: "utilities",  icon: "bolt",             en: "Utilities",  si: "විදුලිය",     color: "#ea6c0a" },
  { key: "services",   icon: "build",            en: "Services",   si: "සේවා",        color: "#0891b2" },
  { key: "rent",       icon: "home",             en: "Rent",       si: "කුලිය",       color: "#d97706" },
  { key: "marketing",  icon: "campaign",         en: "Marketing",  si: "අලෙවිකරණය",  color: "#dc2626" },
  { key: "other",      icon: "more_horiz",       en: "Other",      si: "වෙනත්",       color: "#64748b" },
];

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

// ── Quick Cash Entry Sheet ───────────────────────────────────────────────────
function QuickCashSheet({ onClose }: { onClose: () => void }) {
  const lang = getStoredLanguage();
  const [cat, setCat]       = useState<typeof CASH_CATEGORIES[0] | null>(null);
  const [amount, setAmount] = useState("");
  const [note, setNote]     = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!cat || !amount) return;
    setSaving(true);
    const token = getToken();
    try {
      const res = await fetch(`${BACKEND_URL}/documents/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          document_type:      "receipt",
          supplier_name:      cat.en,
          currency:           "LKR",
          items:              [{ description: note || cat.en, quantity: 1, unit_price: parseFloat(amount), line_total: parseFloat(amount) }],
          notes:              `quick-entry:${cat.key}${note ? " — " + note : ""}`,
          flow_type_override: "cash_outflow",
          force_save:         false,
        }),
      });
      const data = await res.json();
      if (data.success) {
        addNotification({ type: "success", title: lang === "si" ? "ගෙවීම සටහන් විය" : "Cash entry saved", message: `${data.document_id} · LKR ${parseFloat(amount).toLocaleString()}` });
        onClose();
      }
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" style={{ background: "rgba(0,0,0,0.4)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-[480px] rounded-t-3xl p-6 shadow-2xl" style={{ background: "var(--surface)" }}>
        <p className="mb-4 text-[17px] font-extrabold text-[var(--text-1)]">
          {lang === "si" ? "ඉක්මන් ගෙවීම" : "Quick Cash Entry"}
        </p>

        {/* Category grid */}
        <div className="mb-4 grid grid-cols-4 gap-2">
          {CASH_CATEGORIES.map(c => (
            <button key={c.key} onClick={() => setCat(c)}
              className="flex flex-col items-center gap-1 rounded-xl py-3 transition"
              style={cat?.key === c.key
                ? { background: c.color, color: "#fff" }
                : { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
              <span className="material-symbols-outlined text-[22px]">{c.icon}</span>
              <span className="text-[9px] font-bold">{lang === "si" ? c.si : c.en}</span>
            </button>
          ))}
        </div>

        {/* Amount */}
        <div className="mb-3 flex items-center gap-2 rounded-xl border px-4 py-3"
          style={{ borderColor: cat ? cat.color : "var(--border)", boxShadow: cat ? `0 0 0 2px ${cat.color}20` : "none" }}>
          <span className="text-[14px] font-bold text-[var(--text-3)]">LKR</span>
          <input type="number" value={amount} onChange={e => setAmount(e.target.value)}
            placeholder="0.00" autoFocus
            className="flex-1 bg-transparent text-[22px] font-extrabold text-[var(--text-1)] outline-none" />
        </div>

        <input value={note} onChange={e => setNote(e.target.value)}
          placeholder={lang === "si" ? "සටහන (විකල්ප)" : "Note (optional)"}
          className="mb-4 w-full rounded-xl border px-4 py-2.5 text-[13px] text-[var(--text-1)] outline-none"
          style={{ background: "var(--bg)", borderColor: "var(--border)" }} />

        <button onClick={save} disabled={!cat || !amount || saving}
          className="flex w-full items-center justify-center gap-2 rounded-2xl py-4 text-[15px] font-bold text-white transition disabled:opacity-50"
          style={{ background: cat ? cat.color : "#64748b" }}>
          {saving
            ? <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
            : <span className="material-symbols-outlined text-[18px]">save</span>}
          {lang === "si" ? "සුරකින්න" : "Save"}
        </button>
      </div>
    </div>
  );
}

// ── Auto-Crop Scanner Sheet ──────────────────────────────────────────────────
function ScannerSheet({ onClose }: { onClose: () => void }) {
  const lang = getStoredLanguage();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [captured, setCaptured] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const handleCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const canvas = canvasRef.current!;
      // Auto-scale: max 1600px wide keeping aspect ratio
      const maxW = 1600;
      const scale = img.width > maxW ? maxW / img.width : 1;
      canvas.width  = Math.round(img.width  * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
      setCaptured(canvas.toDataURL("image/jpeg", 0.92));
    };
    img.src = url;
  };

  const upload = async () => {
    if (!captured || !canvasRef.current) return;
    setUploading(true);
    const token = getToken();
    try {
      // Convert canvas to blob and upload as FormData
      canvasRef.current.toBlob(async (blob) => {
        if (!blob) return;
        const fd = new FormData();
        fd.append("file", blob, "scan.jpg");
        fd.append("doc_type_hint", "");
        const res = await fetch(`${BACKEND_URL}/process-document`, {
          method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd,
        });
        const data = await res.json();
        if (data.session_id) {
          onClose();
          router.push(`/analysis/${data.session_id}`);
        }
        setUploading(false);
      }, "image/jpeg", 0.92);
    } catch { setUploading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-[480px] rounded-t-3xl p-6 shadow-2xl" style={{ background: "var(--surface)" }}>
        <p className="mb-4 text-[17px] font-extrabold text-[var(--text-1)]">
          {lang === "si" ? "ලේඛනය ස්කෑන් කරන්න" : "Scan Document"}
        </p>

        <canvas ref={canvasRef} className="hidden" />

        {!captured ? (
          <>
            <button onClick={() => fileRef.current?.click()}
              className="flex w-full flex-col items-center justify-center gap-3 rounded-2xl py-12 transition hover:opacity-80"
              style={{ background: "var(--bg)", border: "2px dashed var(--border)" }}>
              <span className="material-symbols-outlined text-[48px]" style={{ color: "var(--brand-mid)" }}>photo_camera</span>
              <p className="text-[14px] font-semibold text-[var(--text-2)]">
                {lang === "si" ? "ක‍ැමරාව විවෘත කරන්න" : "Take photo or choose image"}
              </p>
              <p className="text-[11px] text-[var(--text-3)]">
                {lang === "si" ? "ලේඛනය ස්වයංක‍ීයව ගෙනෙනු ඇත" : "Auto-scales to 1600px for OCR"}
              </p>
            </button>
            {/* No `capture` attribute: it would force the camera and contradict
                the "or choose image" label. Without it, mobile shows the native
                sheet (camera + photo library), honouring both options. */}
            <input ref={fileRef} type="file" accept="image/*"
              className="hidden" onChange={handleCapture} />
          </>
        ) : (
          <>
            <img src={captured} alt="Preview" className="mb-4 w-full rounded-xl object-contain"
              style={{ maxHeight: 280, background: "#000" }} />
            <div className="flex gap-3">
              <button onClick={() => { setCaptured(null); setTimeout(() => fileRef.current?.click(), 50); }}
                className="flex-1 rounded-xl py-3 text-[13px] font-semibold transition hover:opacity-80"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
                {lang === "si" ? "නැවත ගන්න" : "Retake"}
              </button>
              <button onClick={upload} disabled={uploading}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl py-3 text-[13px] font-bold text-white transition disabled:opacity-60"
                style={{ background: "var(--brand-mid)" }}>
                {uploading
                  ? <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
                  : <span className="material-symbols-outlined text-[16px]">upload</span>}
                {lang === "si" ? "OCR කරන්න" : "Scan & Process"}
              </button>
            </div>
            {/* No `capture` attribute: it would force the camera and contradict
                the "or choose image" label. Without it, mobile shows the native
                sheet (camera + photo library), honouring both options. */}
            <input ref={fileRef} type="file" accept="image/*"
              className="hidden" onChange={handleCapture} />
          </>
        )}
      </div>
    </div>
  );
}

// ── Floating Action Button ───────────────────────────────────────────────────
export default function QuickActions() {
  const lang = getStoredLanguage();
  const [open, setOpen]     = useState(false);
  const [sheet, setSheet]   = useState<"cash"|"scan"|null>(null);

  return (
    <>
      {sheet === "cash" && <QuickCashSheet onClose={() => setSheet(null)} />}
      {sheet === "scan" && <ScannerSheet  onClose={() => setSheet(null)} />}

      {/* Fan-out menu */}
      {open && (
        <div className="fixed bottom-24 right-4 z-40 flex flex-col items-end gap-2">
          <button onClick={() => { setOpen(false); setSheet("scan"); }}
            className="flex items-center gap-2 rounded-2xl px-4 py-3 shadow-lg text-white text-[13px] font-bold transition hover:opacity-90"
            style={{ background: "#2252b5" }}>
            <span className="material-symbols-outlined text-[18px]">document_scanner</span>
            {lang === "si" ? "ස්කෑන්" : "Scan Doc"}
          </button>
          <button onClick={() => { setOpen(false); setSheet("cash"); }}
            className="flex items-center gap-2 rounded-2xl px-4 py-3 shadow-lg text-white text-[13px] font-bold transition hover:opacity-90"
            style={{ background: "#16a34a" }}>
            <span className="material-symbols-outlined text-[18px]">payments</span>
            {lang === "si" ? "ඉක්මන් ගෙවීම" : "Quick Cash"}
          </button>
        </div>
      )}

      {/* FAB */}
      <button
        onClick={() => setOpen(o => !o)}
        className="fixed bottom-[88px] right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full shadow-xl text-white transition hover:opacity-90 active:scale-95"
        style={{ background: open ? "#64748b" : "var(--brand-mid)" }}
        aria-label="Quick actions">
        <span className="material-symbols-outlined text-[26px]">{open ? "close" : "add"}</span>
      </button>
    </>
  );
}
