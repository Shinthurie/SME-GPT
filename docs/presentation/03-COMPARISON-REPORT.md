# SME-GPT vs Existing Systems — Comparison Report

> How SME-GPT positions against paid and open-source alternatives. Written to be fair — we name where incumbents beat us, and where we genuinely win.

## The honest one-liner

**No single existing product does what SME-GPT does for a Sri Lankan SME:** bilingual (Sinhala/English) document extraction **+** natural-language financial Q&A **+** arithmetic that's correct by construction **+** at a price an SME can afford. Incumbents each cover *part* of this — we integrate the whole for a specific, underserved market.

---

## The landscape (who does what)

There is no direct one-to-one competitor. The market splits into three buckets:

### A. Document-OCR / data-extraction APIs (the "read the receipt" layer)
| Product | Type | Strengths | Gaps vs our use case |
|---|---|---|---|
| **Google Document AI** | Paid API | Best-in-class accuracy; invoice parser; supports Sinhala script OCR | No financial Q&A; per-page cost adds up; no SME app; you build everything around it |
| **AWS Textract / Azure Document Intelligence** | Paid API | Strong tables/forms extraction | Weak/again no Sinhala *semantics*; no query layer; enterprise-oriented |
| **Veryfi / Nanonets / Rossum / Mindee / Klippa** | Paid SaaS | Purpose-built receipt/invoice extraction, high accuracy | English/European-first; USD pricing; no Sinhala; no NL question answering |
| **Tesseract / PaddleOCR / docTR / EasyOCR / Surya** | Open source | Free, self-hostable; **Surya = strong Sinhala** | OCR only — no correction, no extraction-to-JSON, no Q&A, no app |
| **Donut / LayoutLMv3 / Nougat** | Open source models | Layout-aware extraction | Need ML expertise + training; no product; no Sinhala tuning |

### B. Accounting / bookkeeping software (the "store & report" layer)
| Product | Type | Strengths | Gaps vs our use case |
|---|---|---|---|
| **QuickBooks / Xero / Zoho Books / FreshBooks** | Paid SaaS | Mature accounting, bank feeds, tax, ecosystem | English-first UI; receipt OCR is add-on & English-centric; **no Sinhala**; no NL Q&A; monthly USD fees; overkill for a micro-SME |
| **Dext / Hubdoc** | Paid (bolt-on) | Receipt capture feeding accounting tools | English; no Sinhala; no conversational querying |
| **Wave** | Freemium | Free accounting | English-only; no Sinhala OCR; no NL Q&A |
| **Akaunting / ERPNext / Frappe Books / InvoicePlane** | Open source | Free, self-host accounting | Manual data entry; no OCR pipeline; no Sinhala AI; no NL Q&A |

### C. "Chat with your data" / LLM tools (the "ask questions" layer)
| Product | Type | Strengths | Gaps vs our use case |
|---|---|---|---|
| **ChatGPT / Claude (+ file upload)** | Paid | Great language understanding, some Sinhala | **LLM does the math → unreliable for finance**; no persistent tenant DB; no provenance; no structured pipeline; privacy concerns |
| **LangChain / LlamaIndex RAG apps** | Open source frameworks | Building blocks for RAG | Not a product; still let the LLM compute; you build correctness/tenancy/UI yourself |

---

## Head-to-head on the dimensions that matter for a Sri Lankan SME

| Capability | SME-GPT | Google/Veryfi (OCR APIs) | QuickBooks/Xero | ChatGPT + files | OSS (Tesseract/ERPNext) |
|---|---|---|---|---|---|
| **Sinhala documents** | ✅ end-to-end | 🟡 OCR only | ❌ | 🟡 unreliable | 🟡 OCR only (Surya) |
| **Handles messy phone photos** | ✅ (2-variant + correction) | ✅ | 🟡 | 🟡 | ❌ raw |
| **Structured extraction (invoice/receipt/PO/DN)** | ✅ | 🟡 generic | ✅ (manual/OCR) | 🟡 | ❌ |
| **Natural-language Q&A (si/en)** | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Arithmetic correctness** | ✅ deterministic (no LLM math) | n/a | ✅ | ❌ LLM math | n/a |
| **Provenance / cite the source** | ✅ (bbox roadmap) | 🟡 | ❌ | ❌ | ❌ |
| **Multi-tenant + RBAC + audit** | ✅ | n/a | ✅ | ❌ | 🟡 |
| **Affordable for micro-SME** | ✅ | 🟡 per-page | ❌ USD/mo | 🟡 | ✅ (but DIY) |
| **Turn-key product (not DIY)** | ✅ | ❌ | ✅ | 🟡 | ❌ |
| **Data-privacy / local option** | ✅ (Ollama tier) | ❌ | ❌ | ❌ | ✅ |

Legend: ✅ strong · 🟡 partial/indirect · ❌ absent

---

## Where incumbents genuinely beat us (say this — it builds credibility)

- **Raw OCR accuracy at scale:** Google Document AI / Veryfi are tuned on millions of docs. Our OCR is good but not yet at that level.
- **Ecosystem & integrations:** QuickBooks/Xero have bank feeds, tax filing, payroll, thousands of integrations. We don't (yet).
- **Maturity, support, compliance:** SOC 2, SLAs, 24/7 support, years of hardening. We're pre-GA.
- **Scale:** they serve millions of businesses; we're pilot-stage.

## Where SME-GPT wins (our defensible moat)

1. **The only integrated Sinhala-first pipeline** from photo → structured data → conversational answers. Competitors force you to stitch an OCR API + an accounting app + a chatbot yourself, and none speak Sinhala financially.
2. **Correct-by-construction arithmetic.** Unlike ChatGPT-over-receipts, our numbers come from a deterministic executor, not an LLM guess — critical for finance.
3. **Built for the actual market:** Sri Lankan SME document types, VAT, bilingual UI, mobile PWA, and pricing/privacy suited to small businesses.
4. **Provider-agnostic & privacy-flexible:** cloud LLM for speed *or* fully local (Ollama) for sensitive data — enterprise tools give you no such choice.
5. **Transparency:** provenance/derivation trace — the user can see *why* an answer is what it is.

---

## Positioning statement (use in the deck)

> "SME-GPT isn't trying to out-QuickBooks QuickBooks or out-OCR Google. It occupies a gap none of them serve: an affordable, Sinhala-and-English, ask-it-anything financial assistant for Sri Lankan small businesses — with the arithmetic guarantees finance demands. The incumbents are our components' *competitors*, not our product's."

## Suggested "build vs buy" answer if asked "why not just use Google Document AI + QuickBooks?"

"You could — but you'd pay per page to Google, monthly USD to QuickBooks, get an English-only experience your users can't read, still have no reliable natural-language Q&A, and have wired three vendors together yourself. We deliver one Sinhala-capable product at SME pricing, with arithmetic you can trust. For this market, integration *is* the innovation."
