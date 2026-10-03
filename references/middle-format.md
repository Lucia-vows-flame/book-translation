# Intermediate Format Principles

## Conclusion

The translated Markdown is the editable canonical format and remains a valid final deliverable. When PDF or EPUB is selected, independent publication adapters consume this Markdown after core validation. Add structured sidecar files only when they improve traceability or validation:

- `book-map.json`: whole-work logical order and source-to-target mapping.
- `page-map.json`: page or screenshot evidence for visually complex sources.
- `segments.jsonl`: optional source/translation alignment.
- Markdown: translated notes, including headings, prose, code, links, images, tables, notes, and callouts.

## Why Sidecars Help

Markdown alone may not record:

- the source URL or page range for each note;
- exact figure coordinates or crop provenance;
- paragraph-level source alignment;
- multiple source files that form one logical chapter; or
- unresolved assets and review decisions.

Keep those details in small, readable sidecars rather than adding hidden metadata or duplicating the entire source.

## Recommended Practice

- Keep final note files in the existing knowledge-base hierarchy.
- Use stable source IDs and target paths in `book-map.json`.
- Use `segments.jsonl` only when paragraph-level review or progress tracking is useful.
- Store image crop information and original URLs beside the local asset record.
- Do not use one publication format as another's intermediate source. Inspect the canonical Markdown directly, and use the selected publication adapter plus its format-specific validator for PDF or EPUB spot checks.
