# Publication Adapters

Read this reference after the canonical translated Markdown and shared assets pass the core translation checks. Publication targets are independent and may be selected in any combination.

## Canonical Source

The translated Markdown is the single content source for all outputs. Keep the source order, paragraph boundaries, code, formulas, identifiers, URLs, figures, captions, notes, bilingual pairing, and repair blocks intact. Publication adapters may normalize frontmatter, link syntax, and resource paths for their target, but must not retranslate or silently rewrite content.

Source corrections are additive. The original passage remains in place, followed by a semantic repair block containing the issue, corrected content, and explanation. The three adapters use independent visual templates for this same semantic block:

- Knowledge base: an Obsidian `[!TIP]` callout, with every line of the repair content (including fenced code) nested inside the callout.
- PDF: the Typst template's hint/tip component (the bundled adapter uses `cb_hint`), with the complete repair body passed as content rather than as a literal placeholder.
- EPUB: an XHTML `aside` with a repair/tip class and EPUB-local CSS; do not import Obsidian callout syntax or PDF layout rules into the EPUB.

The adapter may change the wrapper, colors, borders, spacing, and typography for its target, but it must not remove the original passage, omit the corrected content, or turn the repair block into an unstyled ordinary paragraph.

Do not use a generated PDF as EPUB input or a generated EPUB as PDF input. If the user later requests an output that was not selected, rerun only that adapter from the canonical Markdown and its asset manifest.

## Markdown

Use the existing knowledge-base hierarchy and conventions when Markdown is selected:

- Preserve the requested frontmatter, filenames, directory placement, and internal-link style.
- Copy or materialize approved local assets at the paths used by the notes.
- Validate links, image references, source coverage, and bilingual pairing before handoff.
- Validate that each repair is represented by one TIP callout, that the original and corrected content are both present, and that corrected code remains inside the callout.

Markdown may be selected alone and remains the required canonical artifact for every job.

## PDF via Typst

The default template is the pinned Typst Universe package `bookly:5.1.1`:
<https://typst.app/universe/package/bookly>. It is a book-oriented template with
front matter, chapters, appendices, outlines, figures, tables, code listings, equations,
and configurable language and fonts. A user-supplied template may override it for a
specific publication, but the translation workflow and canonical Markdown remain unchanged.

Before compiling, run the bundled environment check:

```bash
python3 scripts/check_typst_env.py \
  --config artifacts/typst-config.json \
  --report artifacts/typst-environment.json
```

The check verifies the Typst executable, enumerates configured fonts, and compiles a
small Chinese/English, math, and code probe through `bookly`. On success, `--config` writes
the pinned template and font choices for the PDF adapter to consume. It does not silently install
system fonts or mutate global Typst configuration. Use `--font-path` to add a project-local
font directory and the `--*-font` options to select its families. A successful check is a
precondition for the PDF adapter; warnings about optional fallback fonts must be reported.

The bundled adapter can then be invoked directly from the canonical Markdown:

```bash
python3 scripts/build_pdf.py \
  path/to/translated-markdown \
  artifacts/book.pdf \
  --config artifacts/typst-config.json \
  --typst-source artifacts/book-typst/ \
  --report artifacts/book-pdf-report.json
```

The adapter accepts one Markdown file or a directory, infers title and author from frontmatter,
copies local images into a temporary Typst workspace, and emits an explicit build report. When
`--typst-source` is supplied, it preserves a source tree containing `main.typ`, `layout.typ`,
`content/*.typ`, and local assets. The content files use semantic components exported by
`layout.typ`; concrete colors, borders, spacing, fonts, and page rules stay in that layout file.
It supports headings, paragraphs, bilingual blockquotes, links, images, formulas, fenced code,
lists, tables, GitBook hints, and details blocks. Unsupported HTML and unavailable images remain
warnings; they are never silently replaced with generated content.

Repair blocks must map to the PDF layout's hint/tip component (normally `cb_hint`). Keep the
original passage outside the component, place the complete repair body inside it, and inspect a
repair containing prose plus a fenced code block. Do not use a plain quote component as a
substitute when the source block is a repair tip.

1. Adapt the canonical Markdown into Typst content or a controlled Markdown-to-Typst intermediate representation.
2. Preserve chapter order, headings, paragraphs, code, formulas, tables, figures, captions, notes, callouts, and hyperlinks.
3. Resolve all images and fonts locally. Select fonts that cover the target language and required symbols.
4. Compile with the Typst CLI and fail the publication step on compilation errors.
5. Inspect the generated PDF at chapter boundaries and in pages containing figures, tables, formulas, code, long headings, and bilingual blocks.
6. Run the PDF section of `references/quality-checklist.md` and report template, font, or layout limitations.

The PDF branch must not change the canonical Markdown or feed its output into EPUB generation.

## EPUB

Build the EPUB directly from the canonical Markdown or a structural map derived from it.

The bundled standard-library script accepts one Markdown file or a directory of Markdown
notes. For example:

```bash
python3 scripts/build_epub.py \
  path/to/translated-markdown \
  artifacts/book.epub \
  --title "Book title" \
  --author "Author" \
  --report artifacts/book-epub-report.json
```

When a directory is supplied, files are read in natural path order and `index.md` is
treated as navigation metadata unless `--include-index` is specified. The script supports
frontmatter title/author inference, headings, paragraphs, lists, blockquotes, fenced code,
tables, callouts, details blocks, formulas, Markdown links/images, Obsidian wiki links,
local image packaging, and EPUB archive/XML validation. Missing local images and external
image references remain explicit warnings or links in the report; videos and interactive
embeds are kept as links because they are not converted into static EPUB media.

1. Split content into readable XHTML/HTML chapters without changing source order.
2. Generate package metadata, manifest, spine, navigation, and stylesheets.
3. Copy local images, fonts, and other approved resources into the package and rewrite only target-specific relative paths.
4. Preserve heading hierarchy, code blocks, formulas, tables, callouts, captions, notes, bilingual ordering, internal anchors, and external links.
5. Map repair blocks to the EPUB tip/repair `aside` template and its local stylesheet; retain the original passage and keep corrected code inside the aside.
6. Package the EPUB with the required `mimetype` and validate its archive and navigation structure.
7. Open the result in an EPUB reader or validator and inspect representative chapters, narrow layouts, images, formulas, code, repair tips, and links.
8. Run the EPUB section of `references/quality-checklist.md` and report known reader-specific limitations.

The EPUB branch must not use a PDF or screenshots as its content source. Interactive embeds that cannot be packaged locally remain labeled links.

## Failure and Rerun Rules

- A failure in one publication branch does not invalidate the other selected branches if the canonical Markdown and shared assets remain valid.
- Record missing templates, unavailable fonts, failed asset packaging, compile errors, malformed links, and validator failures in the review output.
- Fixing a publication issue should normally rerun only the affected adapter.
