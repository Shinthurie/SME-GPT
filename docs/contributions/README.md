# Research Contribution Division — SME-GPT

Each member owns a coherent slice of the pipeline and can explain it end-to-end from their file.

| Member | Owns | File |
|---|---|---|
| **Ashfak N. A. M.** | OCR engine + selection · **C1** OCR post-correction · **RAG** (embeddings + pgvector + hybrid scope) · **C4** relationship index | [ashfak-ocr-rag.md](ashfak-ocr-rag.md) |
| **Shinthurie M.** | OCR **preprocessing** (image standardisation, P/M variants, deskew) · **C2** layout-aware spatial serialization | [shinthurie-preprocessing-spatial.md](shinthurie-preprocessing-spatial.md) |
| **R. Sobatharsan** | **C3** neuro-symbolic arithmetic QA (PAL) · **UI/UX** (bilingual frontend, provenance presentation) | [sobatharsan-pal-uiux.md](sobatharsan-pal-uiux.md) |

## The four research components (C1–C4), mapped

| Component | Owner | Theme |
|---|---|---|
| C1 — Semantic OCR Post-Correction | Ashfak | clean the text, never change a number |
| C2 — Layout-Aware Spatial Serialization | Shinthurie | rebuild table structure from tokens |
| C3 — Neuro-Symbolic Arithmetic QA (PAL) | Sobatharsan | LLM plans, code computes |
| C4 — Multi-Tenant Relationship Index | Ashfak | link PO ↔ invoice for retrieval |

## Pipeline at a glance (who does what, in order)

```
Scan/PDF
  └─ Shinthurie: standardise + P/M variants + deskew
       └─ Ashfak: Surya OCR + best-version selection
            └─ Ashfak: C1 post-correction (numeric safeguard)
                 └─ Shinthurie: C2 spatial serialization → provenance chunks
                      └─ (stored: Postgres + pgvector)

Question
  └─ Ashfak: C4 graph expansion + RAG retrieval → scoped docs
       └─ Sobatharsan: C3 PAL (plan → validate → compute → phrase)
            └─ Sobatharsan: UI/UX renders answer + evidence, bilingual
```

**Shared thread across all four:** the LLM is kept away from the facts — it corrects text but can't change numbers (C1), it never invents table structure (C2), it plans but never computes (C3). Correctness by construction.
