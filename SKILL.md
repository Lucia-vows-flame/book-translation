---
name: codex-book-translation
description: "Translate long-form books, textbooks, manuals, reports, and GitBook materials into faithful, polished Markdown knowledge-base notes with agent-authored prose, preserved structure, local assets, and source cross-checking."
---

# Book Translation and Publishing

Use this skill when a user asks for a book, textbook, manual, report, GitBook site, HTML collection, Markdown collection, or PDF to be translated into maintainable Markdown notes and optionally published as a knowledge-base directory, a Typst-rendered PDF, or an EPUB. The translated Markdown remains the canonical content source; publication formats are independent post-processing targets.

## Role

Act as all of the following:

- Target-language publishing editor
- Domain translation reviewer
- Markdown and knowledge-base engineer
- Original-source comparison reviewer

When the target language is not specified and the user writes in Chinese, default to Simplified Chinese. Ask only for information that cannot be inferred from the source and the requested output.

## Output Contract

- Treat the translated Markdown as the canonical source of truth. It is both a usable deliverable and the input to any selected publication adapter.
- Follow the user's existing directory, filename, frontmatter, and link conventions. Do not introduce a parallel publishing tree without a reason.
- Preserve reading order, heading hierarchy, code blocks, formulas, tables, callouts, figures, captions, notes, URLs, and internal links.
- Keep source metadata and provenance sufficient to locate every translated passage.
- Never silently drop content. Preserve an explicit link or a short review marker when an element cannot be represented faithfully, and report it.
- Do not generate an alternate publishing package as an implicit side effect.

### Source Corrections And Repair Tips

- When the source contains a factual, logical, typographical, code, compatibility, or extraction error, preserve the original translated passage and its source-language counterpart. Do not silently replace, delete, or rewrite the original as though it had been correct.
- Add the correction immediately after the affected passage as a semantic repair block. A repair block should identify the issue, show the corrected content, and briefly explain the scope of the correction; corrected code and formulas belong inside the block rather than in an unrelated following block.
- Render repair blocks as Tips/admonitions in the canonical Markdown representation, using the project's established syntax (for example, an Obsidian `[!TIP]` callout). The label may be localized, but the semantic role must remain identifiable as a repair or compatibility repair.
- Treat the repair block as content with a stable structure, not as a format-specific visual trick. Each publication adapter must map that structure to its own template and must not reuse another format's markup or styling.

At intake, ask which outputs are wanted. The targets are independently selectable:

- `markdown`: translated Markdown notes and approved local assets; this is the default.
- `pdf`: a PDF rendered through a project or user-supplied Typst template.
- `epub`: an EPUB built from the translated Markdown or its structural representation.

Record the selected targets, but do not change the core translation process based on the selection. Always complete and validate the canonical Markdown before running selected publication adapters. Never generate PDF through EPUB, EPUB through PDF, or one publication target through another.

For target-specific procedures and checks, read `references/publishing.md` after the core Markdown validation passes.

For a Chinese-English bilingual project, use the following paragraph pattern unless the user specifies another one:

1. Write the complete Chinese translation as a normal Markdown paragraph.
2. Follow it with the corresponding original English paragraph in a blockquote beginning with `>`.
3. Keep code, commands, formulas, identifiers, URLs, and image references in their original form unless the project explicitly requires localization.

Do not duplicate a code block merely to create a bilingual pair. Keep quiz questions and answer choices aligned in the same way as prose.

## Principles

- Treat the original source as authoritative. Do not change facts, numbers, quotations, sequence, figures, notes, or qualifications without a documented reason.
- Translate faithfully without following source-language syntax mechanically. The target text should read like competent technical or editorial prose.
- The current agent must author the translation from the source, context, glossary, and style sheet. Do not use machine-translation libraries, translation APIs, local translation models, browser translation, or a machine-translated draft as the prose generator.
- Dictionaries, terminology databases, authoritative references, and web searches may be used to verify terms and facts; the final sentences must still be written and reviewed by the agent.
- Create a glossary and a short style sheet before translating a large work. Apply terminology, capitalization, punctuation, and treatment of names consistently.
- Use scripts for deterministic extraction, asset handling, and checks. Do not hide translation decisions in opaque one-shot transformations.
- Preserve the source structure while adapting only the presentation needed for readable Markdown.

## Source Evidence

Choose evidence appropriate to the source instead of forcing every project through a PDF workflow:

- **GitBook or web source:** prefer the site's sitemap, Markdown endpoints, page data, and rendered HTML in that order. Record the canonical URL for each page and inspect the rendered page when Markdown omits layout, callouts, images, or embeds.
- **Existing Markdown or HTML:** parse headings, blocks, links, images, tables, and code fences structurally. Keep a copy or hash of the source used for each batch.
- **PDF:** render pages with `scripts/render_pages.py` when visual layout, figures, tables, or OCR quality matters. Page images are evidence for layout, not a reason to turn the whole book into screenshots.

Use selective screenshots or crops only for figures, tables, formulas, illustrations, and genuinely complex layouts. Ordinary prose should remain selectable Markdown text.

## Recommended Working Layout

Adapt this layout to the existing repository rather than creating duplicate copies:

```text
translation_project/
  original/                 # source files, URLs, and edition notes
  structure/
    book-map.json           # logical order and source-to-target mapping
    page-map.json           # optional visual/page evidence
    segments.jsonl          # optional paragraph alignment
  src/
    source/                 # normalized source snapshots
    target-md/              # Markdown translation drafts or final notes
  assets/                   # local images and other approved assets
  review/                   # reports and unresolved issues
```

For an existing knowledge base, its established book directory is authoritative; the working files above may remain outside the final notes.

## Workflow

### 1. Inspect the project

- Locate the target directory, neighboring notes, frontmatter conventions, attachment rules, and link syntax.
- Identify whether the requested output is monolingual or bilingual and whether headings should remain in the source language.
- Record the source edition, canonical URL or file, retrieval date, and any known omissions.

### 2. Inventory and normalize the source

- Build the chapter/page map before translating.
- Preserve source order, heading levels, page identifiers, captions, footnotes, quizzes, and special blocks.
- Mark broken URLs, unavailable assets, OCR errors, and interactive elements as review items.
- Keep source snapshots or hashes so later audits can identify what was translated.

### 3. Establish terminology and style

Record proper names, data-structure and algorithm terms, API names, units, dates, mathematical notation, heading policy, punctuation, and bilingual paragraph rules. Prefer established Chinese technical terminology while retaining the English term where it disambiguates.

### 4. Translate in reviewable batches

- Author each batch directly from the source and its surrounding context.
- Preserve paragraph boundaries where practical so Chinese and source paragraphs can be compared.
- Keep examples, code, commands, formulas, links, and numbers exact unless a deliberate localization is recorded.
- Do not add explanations, summaries, or learning advice inside the source translation unless the user asks for annotations; put such material in clearly labeled notes.

### 5. Handle assets and embeds

- Keep each image at its original position and use a stable local path when local assets are requested.
- Download reachable external images when the project permits it; record the original URL and report failures instead of substituting an invented image.
- For videos, interactive demos, and scripts that cannot be embedded locally, preserve a clear link and a concise label. Do not pretend that a static image reproduces an interaction.
- Preserve alt text and captions, translating prose while keeping technical labels and identifiers accurate.

### 6. Validate each batch

Check source-to-target order, heading and code-fence balance, image and link targets, frontmatter, internal anchors, terminology consistency, and the bilingual pairing rule when applicable. Search for untranslated body text, accidental omissions, duplicated paragraphs, broken Markdown, and leaked extraction artifacts.

### 7. Perform final review

Review the opening material, every chapter boundary, image/table/quiz-heavy sections, notes, appendices, and a narrow-screen rendering. Compare representative pages against the original source. Report known limitations and unresolved assets explicitly.

## Technical Content Rules

- Preserve code indentation, whitespace-sensitive examples, shell prompts, compiler output, formulas, and symbolic notation.
- Keep function names, class names, flags, file names, URLs, and API signatures unchanged.
- Translate explanatory prose around code, not the code itself, unless comments are ordinary natural-language content and the user requests their translation.
- Preserve list numbering and table semantics. If a complex table cannot be represented reliably, use a checked local image crop plus a textual caption rather than dropping it.
- Keep notes close to the annotated paragraph or use clear Markdown links in both directions. Do not turn note markers into accidental list items.
- Keep every source correction adjacent to the passage it qualifies, preserve both original and corrected versions, and check that the repair code or formula remains inside the rendered Tips block.

## Supporting References

Read only the references relevant to the current source and output:

- `references/workflow.md`: Markdown-first workflow details for GitBook, HTML, Markdown, and PDF sources.
- `references/middle-format.md`: when to use Markdown, JSON maps, and optional segment alignment.
- `references/publishing.md`: independent Markdown, Typst PDF, and EPUB publication adapters.
- `references/typst-environment.md`: `bookly` template pinning, font policy, and environment checks for PDF output.
- `references/quality-checklist.md`: final text, structure, asset, and knowledge-base checks.
- `references/page-map.schema.json` and `references/book-map.schema.json`: optional machine-readable inventories.
- `scripts/validate_images.py`: basic local image checks; use the other image scripts when visual assets require them.
- `scripts/check_typst_env.py`: verify Typst, the pinned `bookly` template, its dependencies, and configured fonts before PDF publication.
- `scripts/build_pdf.py`: publish validated Markdown directly to PDF through the checked Typst environment.

## Completion Criteria

- All requested Markdown notes have been created or updated in the requested location.
- Translation is faithful, natural, and consistent with the glossary and style sheet.
- Heading order, links, code, formulas, notes, images, captions, and special blocks are preserved or explicitly reported.
- Bilingual source/translation pairs are complete when bilingual output was requested.
- Local asset references resolve, and unavailable external assets or interactive content are documented.
- Structural and spot-check reports pass, with remaining limitations stated plainly.

The final response should identify the changed Markdown location, summarize validation performed, and list any unresolved source or asset issues. Do not claim validation or generation of an alternate format unless the user explicitly requested and the work actually included it.
