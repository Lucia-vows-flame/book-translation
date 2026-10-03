# Markdown Knowledge-Base Translation Checklist

## Text

- The translation preserves source meaning, qualifications, numbers, dates, names, quotations, and examples.
- The Chinese prose is natural and technically precise rather than mechanically literal.
- Body text was authored by the agent from the source and context; no translation service, API, local translation model, or browser translation generated it.
- Terms, proper names, API names, chapter titles, punctuation, and capitalization are consistent with the glossary and style sheet.
- No OCR remnants, broken words, accidental line-wraps, duplicated paragraphs, or untranslated body passages remain.
- For bilingual notes, every translated prose block has the corresponding source block in the required order.

## Markdown Structure

- Frontmatter matches the existing knowledge-base convention.
- File names, directory placement, heading hierarchy, chapter order, and anchors are correct.
- Code fences are balanced and their language labels are preserved.
- Lists, tables, callouts, quotations, notes, quizzes, captions, and warnings retain their source order and semantics.
- Every source correction preserves the original passage and adds one adjacent semantic repair Tip block containing the issue, corrected content, and explanation; corrected code or formulas remain inside that block.
- Markdown renders without stray syntax, malformed links, or escaped characters leaking into visible text.
- Internal links resolve from the final note location, including links in tables of contents and cross-references.

## Images and Other Media

- Every required image is present at the expected local path and is readable.
- Image position, alt text, caption, and source URL record are preserved.
- Crops contain only the intended figure, table, formula, or illustration and are not blank or cut off.
- External-image policy has been followed; failed downloads are documented.
- Videos and interactive content are represented by clear links when they cannot be stored locally.

## Source Coverage

- Every source page or chapter in scope has a target note or an explicit omission record.
- Source and target counts for headings, code blocks, images, tables, notes, and links are explainable.
- `book-map.json`, `page-map.json`, or `segments.jsonl` entries point to real source and target files when those sidecars are used.
- Spot checks cover the opening, chapter boundaries, technical examples, quizzes, notes, and the final section.

## Handoff

- The final response identifies the Markdown output location and validation performed.
- Known source limitations, unavailable assets, and intentionally preserved links are listed plainly.

## Optional Publication Outputs

Run only the sections for outputs selected by the user. These checks are additive; they do not replace the core translation checks above.

### PDF via Typst

- The Markdown-to-Typst adaptation preserves source order, headings, code, formulas, tables, captions, notes, and links.
- The selected Typst template is available, compiles successfully, and embeds the required fonts, including Chinese fonts when needed.
- Images resolve from local assets at usable resolution and are not stretched, blank, clipped, or displaced.
- Tables, formulas, code blocks, callouts, footnotes, and long headings do not overflow or disappear at page boundaries.
- Repair blocks use the PDF hint/tip component, retain the original passage, and keep prose plus corrected code together in the same block.
- The table of contents, page numbering, bookmarks, hyperlinks, and metadata are present and correct where requested.
- The generated PDF opens successfully and representative pages have passed visual inspection.

### EPUB

- The EPUB package has the required structure and opens in an EPUB validator or reader.
- `mimetype`, package metadata, manifest, spine, navigation, and chapter order are valid and consistent.
- Every chapter, image, stylesheet, font, and other referenced resource is present at the expected path.
- Internal chapter links, anchors, table-of-contents entries, and external links behave as intended.
- Code blocks, formulas, tables, callouts, captions, and bilingual paragraph order remain readable in a reflowable layout.
- Repair blocks use the EPUB-local tip/repair `aside` template, retain the original passage, and keep corrected code or formulas inside the aside.
- The generated EPUB opens in a reader and representative chapters have passed visual or structural inspection.
