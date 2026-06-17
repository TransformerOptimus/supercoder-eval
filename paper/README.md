# Paper — SuperCoder Context Engine Eval

LaTeX sources for the eval paper, in **IEEE conference two-column format**
(`\documentclass[conference]{IEEEtran}`). Co-located with the release
artifacts under `../data/`, `../scoring/`, `../analysis/`.

## Build

```bash
# One-shot build
make

# Continuous build on save (uses latexmk -pvc)
make watch

# Clean build artifacts
make clean
```

Output: `main.pdf`.

Requires `latexmk` (BasicTeX/MacTeX/TeX Live) plus the packages listed at
the top of `main.tex`. `IEEEtran.cls` is checked in alongside `main.tex`,
so no `tlmgr install ieeetran` is required. If your install lacks
`titlesec` or `sttools` (used by the preamble), run
`tlmgr install titlesec sttools` once.

## Layout

```
paper/
├── main.tex                  Root document. \documentclass[conference]{IEEEtran}.
├── IEEEtran.cls              IEEE conference class file (vendored for self-contained builds).
├── sections/                 One file per outline section.
│   ├── 00_abstract.tex
│   ├── 01_introduction.tex
│   ├── 02_related_work.tex
│   ├── 03_system.tex
│   ├── 04_experimental_design.tex
│   ├── 05_integrity.tex
│   ├── 06_results.tex
│   ├── 07_discussion.tex
│   └── 08_appendices.tex     (Not included in the build; see main.tex.)
├── figures/                  Generated figures (inline TikZ — no PDF/PNG assets).
├── tables/                   Standalone table files for \input.
├── appendix/                 Released-artifact SQL queries.
├── references.bib            Bibliography. Cite-key list at top.
├── Makefile                  Build helpers.
└── README.md                 This file.
```

## Conventions

- Tables use `booktabs` (`\toprule`, `\midrule`, `\bottomrule` — never `\hline`).
- Section labels follow `\label{sec:slug}` (e.g. `\label{sec:results}`).
- Citations: `\citep{key}` for parenthetical, `\citet{key}` for textual.
  `natbib` is loaded with `[numbers,sort&compress]` so the rendered form is
  `[1]` and `Author et al.\ [1]`, matching IEEE house style.
- Add entries to `references.bib` as you cite them; keep the cite-key list at
  the top of that file current.

## Format

For camera-ready submission to an IEEE venue, swap the `natbib` citation
calls to plain `\cite{}` and switch `\bibliographystyle` to `IEEEtran` if
the venue requires the IEEEtran-bst format. The current `unsrtnat` style
renders identically (numeric, ordered by appearance) for arXiv / draft
circulation.
