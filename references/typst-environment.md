# Typst PDF Environment

## Default Template

Use `@preview/bookly:5.1.1` as the default PDF template. Pin the version in generated
Typst sources so a later package release cannot silently change pagination or styling.
The official package page is <https://typst.app/universe/package/bookly> and the source
repository is <https://github.com/maucejo/bookly>.

The PDF adapter should expose a small configuration surface rather than leaking every
`bookly` option:

- book title, subtitle, authors, language, and date;
- paper size and theme;
- body, math, and raw/code font families;
- optional cover and local asset directory.

The adapter may use `bookly` features internally for front matter, chapter/part structure,
outlines, figures, tables, equations, code, and callout environments.

## Environment Check

Run the standard-library helper before PDF publication:

```bash
python3 scripts/check_typst_env.py \
  --config artifacts/typst-config.json \
  --report artifacts/typst-environment.json
```

The helper performs three checks:

1. Finds the Typst executable and records its version.
2. Lists fonts visible to Typst, including optional directories passed with `--font-path`.
3. Compiles a temporary probe importing the pinned `bookly` package and exercising Chinese,
   Latin text, a formula, and a fenced code block.

The helper reports missing font families as warnings and compilation or package-resolution
failures as errors. It never installs packages or fonts implicitly. Installation and any
project-local font setup remain explicit deployment steps. When the check succeeds, the
`--config` file records the selected template, fonts, font paths, and Typst executable for
the PDF adapter.

Use `scripts/build_pdf.py` for the independent PDF post-processing branch. Pass the generated
configuration with `--config`; use `--typst-source` when the generated Typst source tree should
be kept for inspection. That tree separates `main.typ`, `layout.typ`, and `content/*.typ`; the
adapter reads canonical Markdown directly and does not use an EPUB or another rendered format as
an intermediate.

The default font selection is intended for Linux environments with common CJK fonts:

```text
body:    Noto Serif CJK SC
heading: Noto Sans CJK SC
math:    New Computer Modern Math
raw:     DejaVu Sans Mono
```

Override these with `--body-font`, `--heading-font`, `--math-font`, and `--raw-font` when
the target environment supplies different families. `bookly` accepts body, math, and raw
font settings directly; the heading family is recorded by the environment report and may
be applied by the PDF adapter's heading show rules.

## Failure Policy

- Do not begin a full PDF build when the Typst probe cannot compile.
- Do not treat a missing optional font as a translation failure; record the fallback and
  inspect representative pages for missing glyphs.
- Keep the environment report beside the PDF build report for reproducibility.
