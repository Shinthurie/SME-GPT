# Figures

Put publication figures here as **vector PDF** (or high-res PNG for screenshots).

The manuscript currently renders two **starter Mermaid diagrams** inline
(`fig-architecture`, `fig-pal`) so it builds with no external assets. When you have
polished versions, either:

- replace the Mermaid blocks in `paper.qmd` with `![caption](figures/architecture.pdf){#fig-architecture}`, or
- keep Mermaid and just refine the diagram code.

Suggested figures to add:
- `architecture.pdf` — end-to-end pipeline (polished).
- `pal.pdf` — Plan→Validate→Execute→Answer loop (polished).
- `example.png` — an anonymised Sinhala/English document → extracted JSON → QA answer with provenance (a qualitative walk-through reviewers love).

See `../README.md` §5 for how to make clean vector figures (draw.io, Excalidraw, Mermaid, TikZ)
and the rules (vector, captioned, referenced, colour-blind-safe, PII-redacted).
