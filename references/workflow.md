# Markdown-First Translation Workflow

Use this reference when the source is a GitBook, website, Markdown collection, HTML collection, or PDF and the requested deliverable includes Markdown notes, a Typst-rendered PDF, or an EPUB.

## Core Position

- Markdown notes are the final deliverable and the source of truth.
- The original source, not an extracted draft, determines meaning, order, and special content.
- Use page images only when they provide evidence about figures, tables, formulas, or layout that text extraction cannot preserve.
- Body text must be authored by the agent from the source and context; translation services, translation APIs, local translation models, and browser translation must not generate the prose.
- Keep structural inventories and optional alignment data separate from the notes so the final directory stays readable.

## Publication Target Selection

At the start of a job, ask the user to select one or more outputs: Markdown, PDF, and EPUB. Default to Markdown when no other target is requested. This records publication intent only; it does not alter source discovery, extraction, glossary creation, translation, bilingual pairing, or core validation.

The translated Markdown is the canonical content source. After it passes the core validation, run only the selected publication adapters independently. Read `publishing.md` for the target-specific workflow.

## Source-Specific Discovery

### GitBook and websites

1. Locate the canonical site, sitemap, sidebar, and page-level Markdown or data endpoints.
2. Save the page URL, retrieval date, title, and source identifier for every page.
3. Prefer deterministic Markdown or page data; consult rendered HTML for callouts, image placement, captions, embeds, and links that are missing from the Markdown.
4. Record unavailable images, videos, interactive widgets, and authentication boundaries as review items.

### Markdown and HTML collections

1. Inventory files and infer the source reading order from the existing index or navigation.
2. Parse headings, paragraphs, lists, tables, links, images, code fences, and block elements structurally.
3. Preserve source filenames or stable IDs in the mapping so each translated note can be audited.

### PDFs

1. Record the edition, page count, author, and copyright-page information.
2. Render pages with `scripts/render_pages.py` when layout or OCR quality matters.
3. Extract text as a working draft while retaining page anchors.
4. Crop only figures, tables, formulas, illustrations, or complex regions that cannot be represented reliably as Markdown.

## Working Artifacts

Use only the artifacts that add audit value:

- `book-map.json`: logical chapter order and source-to-target file mapping.
- `page-map.json`: optional page or screenshot evidence for visually complex sources.
- `segments.jsonl`: optional paragraph alignment for proofreading and progress tracking.
- `target-md/`: translation drafts or final Markdown notes.
- `assets/`: local images and other approved resources.
- `review/`: validation reports and unresolved-source records.

An existing knowledge base may use a different layout. Preserve it rather than copying the whole book into a second hierarchy.

## Translation Pass

1. Create the glossary and style sheet before a large batch.
2. Translate directly from the source and its surrounding context.
3. Keep paragraph boundaries aligned where practical.
4. For bilingual Chinese-English notes, place the complete Chinese paragraph first and the corresponding English source in a `>` blockquote immediately after it.
5. Keep headings and anchors stable unless the project explicitly defines a translated-heading policy.
6. Keep code, formulas, commands, identifiers, URLs, and image paths exact.
7. Preserve quizzes, choices, notes, captions, callouts, and warnings in their original order.

## Assets and Embeds

- Use stable local paths for images when the project requests local assets.
- Download reachable external images only when authorized, and retain a source URL record.
- Keep videos, interactive examples, and scripts as labeled links when they cannot be represented locally.
- Never replace a missing image with an invented illustration without explicit approval.
- Keep alt text and captions with the image; distinguish translated prose from technical labels.

## Validation Pass

For each batch and at the end, check:

- source order and chapter coverage;
- heading levels and balanced code fences;
- bilingual paragraph pairing, where applicable;
- code, formula, number, and identifier preservation;
- frontmatter and internal-link targets;
- local image existence and external-asset policy;
- list, table, callout, note, and caption placement; and
- untranslated or duplicated body text and extraction artifacts.

Finish with spot checks at chapter boundaries and in image-, table-, quiz-, and note-heavy sections. State every unresolved issue in the final report.

## Post-Translation Publishing

Run this stage only after the canonical Markdown and shared assets pass the core validation:

1. Publish Markdown notes using the existing knowledge-base path, frontmatter, and link conventions.
2. If selected, adapt the content to Typst, apply the chosen template, compile the PDF, and run PDF-specific checks.
3. If selected, build the EPUB directly from the Markdown or structural map, package its assets and navigation, and run EPUB-specific checks.

These branches share content and assets but never use another output format as an intermediate source. A later request for an unselected format should rerun only its adapter, not the translation.
