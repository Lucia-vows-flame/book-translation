# Codex Book Translation

This repository contains a Markdown-first Codex skill for translating books, textbooks, manuals, reports, and GitBook materials into maintainable knowledge-base notes.

The skill emphasizes:

- faithful, natural, agent-authored translation;
- optional Chinese-English paragraph alignment;
- preservation of headings, code, formulas, tables, notes, images, links, and source order;
- local asset handling and explicit reporting of unavailable media; and
- source-to-target structural and terminology checks.

The canonical deliverable is Markdown plus any approved local assets. When selected by the user, the same validated Markdown can also be published independently as a Typst-rendered PDF and/or an EPUB.

## Optional Dependencies

The skill itself is Markdown plus small helper scripts. Install these only when the source requires them:

- Python 3
- `PyMuPDF` / `fitz` for rendering PDF pages
- `Pillow` / `PIL` for cropping and validating images
- Typst CLI and the `bookly:5.1.1` template for PDF output; run `scripts/check_typst_env.py` before `scripts/build_pdf.py`
- The bundled `scripts/build_epub.py` uses only the Python standard library; an external EPUB reader or validator is optional for visual review

For a GitBook, HTML, or Markdown source, no PDF tool is required.

## Use

Invoke it explicitly in Codex:

```text
Use $codex-book-translation to translate this source into Markdown knowledge-base notes while preserving structure and source alignment.
```

The bundled scripts support PDF page rendering, figure/table cropping, contact sheets, and basic image validation. They do not translate prose automatically. Publication adapters consume the validated translated Markdown independently; no publication format is used as another format's intermediate source.
