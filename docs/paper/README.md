# SME-GPT Research Paper — Author Guide (read this fully)

This folder contains a ready-to-render research paper draft. This guide tells you
**exactly** how to produce a publication-quality PDF: tooling, formatting, fonts, figures,
tables, citations, venue templates, authorship ethics, and a submission checklist.

```
docs/paper/
├── paper.qmd        # the manuscript (Quarto Markdown) — edit this
├── references.bib   # bibliography (BibTeX) — verify every entry
├── README.md        # this guide
└── figures/         # put your figures here (create this folder)
```

---

## 0. TL;DR — from zero to a PDF

1. Install **Quarto** and a **LaTeX** distribution (see §1). Yes — Quarto is the right choice for this.
2. `cd docs/paper`
3. `quarto render paper.qmd --to pdf`
4. Open `paper.pdf`. Iterate.

Then: pick a venue template (§3), make the two figures (§5), fill the results table (§6),
verify citations (§4), run the checklist (§9).

---

## 1. Is Quarto the right tool? (Yes) — and setup

You were right: **Quarto** is an excellent, modern way to write papers. It's Markdown +
LaTeX under the hood, with first-class citations, cross-references, figures, and one-command
PDF/Word/HTML output. It's easier than raw LaTeX but produces the same publication-grade PDFs,
and most major venues (IEEE, ACM, Springer/LNCS, Elsevier) have Quarto templates.

**Install (Windows):**
- Quarto: download from <https://quarto.org/docs/get-started/> (or `winget install Quarto.Quarto`).
- LaTeX: the simplest path is Quarto's bundled TinyTeX — run once:
  ```powershell
  quarto install tinytex
  ```
  (Alternatively install MiKTeX. TinyTeX is smaller and Quarto-managed — recommended.)
- Verify: `quarto check`

**Recommended editor:** VS Code with the **Quarto** extension (live preview, `Ctrl+Shift+K`
to render). RStudio and Positron also support `.qmd`.

**Word instead of PDF?** Some supervisors want `.docx`. `quarto render paper.qmd --to docx`.
Formatting control is weaker; prefer PDF for camera-ready.

---

## 2. What's already in `paper.qmd`

A complete first draft: title, author block, abstract, keywords, and full sections
(Introduction, Related Work, System Overview, C1–C4, Implementation, Evaluation protocol,
Discussion/Limitations, Conclusion), with cross-references, one equation, two figure
placeholders, and a results table. It uses `references.bib` for citations. **The prose is a
genuine draft grounded in your `docs/components/*.md` — edit for your voice and add measured
results.**

---

## 3. Choosing a venue template (do this early — it sets page limits & style)

The default output is a clean generic article PDF. To match a specific venue, install its
Quarto extension **from inside `docs/paper/`** and change the `format:` in the YAML header.

| Venue | Command (run in `docs/paper/`) | Set `format:` to |
|---|---|---|
| **IEEE** (conf/journal) | `quarto add dpsdce/quarto-ieee` | `ieee-pdf` |
| **ACM** | `quarto use template quarto-journals/acm` | `acm-pdf` |
| **Springer LNCS** | `quarto add quarto-journals/lncs` *(or search "quarto lncs")* | as extension README says |
| **Elsevier** | `quarto use template quarto-journals/elsevier` | `elsevier-pdf` |
| Generic (default) | — | `pdf` (already set) |

> Each extension ships its own author/affiliation fields and title-page rules. When you add
> one, copy your author block into **its** expected schema (the extension README shows it).
> **Do the template switch before heavy formatting** — it changes fonts, columns, and length.

**Fonts:** you almost never set fonts manually — the venue template dictates them (IEEE:
Times, two-column, 10pt; ACM: Libertine; LNCS: Times-like). If you must (generic format),
add to the YAML `format: pdf:` block:
```yaml
    mainfont: "Times New Roman"   # requires the xelatex/lualatex engine:
    pdf-engine: xelatex
```

---

## 4. Citations & the bibliography

- Cite in text with `[@key]` → renders "[1]" or "(Author, Year)" per the venue style.
  Multiple: `[@gao2022pal; @lewis2020rag]`. In-text author: `@gao2022pal shows …`.
- All keys live in `references.bib`. **⚠️ VERIFY EVERY ENTRY** — some entries I generated from
  search results have `author = {others}` or a `VERIFY` note. Open each `arXiv:` / DOI link,
  confirm the author list, year, and venue, and fix the `.bib`. Wrong citations are the #1
  reviewer red flag.
- Citation *style* is controlled by the venue template (IEEE numeric, ACM, etc.). For a
  specific style file you can add `csl: some-style.csl` (get `.csl` files from
  <https://www.zotero.org/styles>).
- **Tip:** manage references in **Zotero**, then export a fresh `references.bib` — far less
  error-prone than hand-editing. Add new papers you cite as you write.

The current bibliography covers: PAL, Chain-of-Thought, Program-of-Thoughts, RAG, Multilingual
E5, LayoutLMv3, Donut, DocILE, a KIE survey, LLM post-OCR correction (3 papers), Sinhala/low-
resource OCR (2 papers), and Surya. Add: your dataset source, any Sinhala NLP/finance papers
specific to your claims, and the DeepSeek/Ollama/Llama model cards you actually used.

---

## 5. Figures (papers live or die on these)

Create `docs/paper/figures/` and produce **at least** the two referenced figures:

1. `architecture.pdf` — the end-to-end ingestion + query pipeline (@fig-architecture).
2. `pal.pdf` — the C3 Plan→Validate→Execute→Answer loop (@fig-pal).

**How to make clean vector figures (pick one):**
- **draw.io / diagrams.net** (free): design the boxes-and-arrows, `File → Export → PDF`
  (vector). Best balance of speed and quality.
- **Excalidraw** (hand-drawn look) → export **SVG/PDF**, not PNG.
- **Mermaid** (code-based, versionable): Quarto renders it natively — you can inline a diagram:
  ````markdown
  ```{mermaid}
  %%| label: fig-architecture
  %%| fig-cap: "End-to-end architecture."
  flowchart TB
    U[Upload] --> P[Preprocess] --> O[OCR] --> C1[C1: numeric-safe correction]
    C1 --> C2[C2: spatial serialization] --> IDX[C4 + vector index]
    Q[Question] --> S[Scope] --> R[Retrieve] --> PAL[C3: Plan→Validate→Execute→Answer] --> A[Answer + citations]
  ```
  ````
  (Replace the `![](figures/…pdf)` placeholders with a mermaid block if you prefer code-drawn.)
- **TikZ/LaTeX** (highest quality, steepest curve) — only if you're comfortable.

**Figure rules for publication:**
- **Vector (PDF/SVG), not PNG/JPG** for diagrams — they must stay crisp at print resolution.
- Screenshots (UI, sample document) may be **PNG at ≥300 DPI**; redact real PII.
- Every figure needs a caption ending with a period and is **referenced in the text**
  (`@fig-architecture`), never "the figure below".
- Readable fonts in figures (≈ the paper's font size); consistent colours; colour-blind-safe
  palette; don't rely on colour alone.
- Include a **qualitative example**: one real (anonymised) Sinhala/English document → its
  extracted JSON → a QA answer with provenance. Reviewers love a concrete walk-through.

---

## 6. Tables & results

- `@tbl-results` is a placeholder — **fill it with real measured numbers** before submission
  (CER, NAR, arithmetic accuracy, plan success rate, latency, cross-doc recall). See the
  Evaluation section and `docs/TESTING.md`.
- Use `booktalk`-style rules (already enabled via `booktabs`): top/mid/bottom rules only, no
  vertical lines.
- Report **how** you measured: dataset size, ground-truth source, train/test split, hardware,
  model versions, and averaging (mean ± std over N runs). Reproducibility is graded.
- If you lack a labelled Sinhala financial dataset, say so and report what you *can*
  (NAR = 0% is provable by construction; arithmetic accuracy on synthetic queries; a small
  hand-labelled sample for CER). Honest, scoped results beat inflated ones.

---

## 7. Structure & length (typical)

- **Conference:** 6–10 pages (venue-dependent), including references. IEEE/ACM double-column.
- **Order:** Abstract → Intro (problem + contributions bullet list) → Related Work → System/
  Method (your C1–C4) → Implementation → Evaluation → Discussion/Limitations → Conclusion →
  Acknowledgements → References.
- Put the **contributions as an explicit bulleted list** at the end of the Introduction
  (already drafted).
- **Abstract**: problem → gap → what you built → key idea → how you evaluate. ~200 words
  (already drafted).
- Include a **Limitations** paragraph (already drafted) — reviewers respect honesty; hiding
  the C1/C2 integration status would backfire.

---

## 8. Authorship — read before finalising the author list

You asked whether to include **L. V. A. U. Pushpakumara**, who "didn't contribute anything."

**The ethical standard** (used by IEEE, ACM, Springer, and most venues): authorship requires a
**substantial intellectual contribution** — to the design, implementation, analysis, or
writing — *and* involvement in drafting/revising *and* approval of the final version. Adding
someone who did none of these is **"gift/honorary authorship,"** which publication-ethics
bodies (e.g. COPE) classify as misconduct.

**Practical guidance:**
- If he genuinely contributed nothing intellectual: **do not list him as an author.** Thank him
  in the **Acknowledgements** instead (there's a commented placeholder in `paper.qmd`).
- If he did something minor but real (e.g. data collection, testing): a **Contributions
  statement** ("CRediT" taxonomy — Conceptualization, Software, Investigation, Writing, etc.)
  lets you credit each person accurately, and he can be an author for that specific role.
- **Caveat:** some universities require *all* group-project members as authors for coursework.
  If this is a course deliverable, check your supervisor's/faculty rules — they may override
  the general norm. When in doubt, **ask your supervisor** and get it in writing.

The draft currently lists three authors (Ashfak, Shinthurie, Sobatharsan) with a comment
marking where to decide on the fourth. Also confirm **author order** (usually contribution-based;
first author = lead) with your team and supervisor early — it causes disputes if left late.

Add ORCID iDs and correct affiliation/emails in the YAML before submission.

---

## 9. Pre-submission checklist

- [ ] Chose the venue and switched to its Quarto template; paper fits the page limit.
- [ ] Every `references.bib` entry verified (no `others`/`VERIFY` left); styles render correctly.
- [ ] Both figures are **vector**, captioned, and referenced; a qualitative example is included.
- [ ] `@tbl-results` filled with real numbers + measurement methodology described.
- [ ] Abstract, contributions list, and Limitations all present and accurate.
- [ ] Author list, order, affiliations, emails, ORCIDs correct; authorship ethics settled (§8).
- [ ] Any real document images anonymised (no PII / real company data).
- [ ] Ran a spell/grammar pass; consistent terminology (C1–C4, "SME-GPT", "flow_type").
- [ ] Anonymised version prepared if the venue is **double-blind** (remove names, self-cite in
      third person, strip identifying repo URLs).
- [ ] Reproducibility: model versions, hardware, dataset description, and (if allowed) a code link.
- [ ] `quarto render` produces a clean PDF with no unresolved `??` cross-references.

---

## 10. Suggested target venues (Sri Lanka / region + document-AI)

- **ICTer** (International Conference on Advances in ICT for Emerging Regions, Sri Lanka).
- **MERCon** (Moratuwa Engineering Research Conference).
- **IEEE region conferences** (e.g. ICIIS, ICIAfS) — good fit for an applied systems paper.
- **Workshops** at ICDAR / *CL venues on document analysis or low-resource NLP — strong fit for
  the OCR/Sinhala angle.
- Discuss with your supervisor: a **systems + low-resource-language** framing travels well.

---

*Questions this guide doesn't cover (e.g. rebuttal writing, camera-ready specifics) depend on
the venue — check its author kit once you've chosen one.*
