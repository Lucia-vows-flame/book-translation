#!/usr/bin/env python3
"""Build a reflowable EPUB 3 directly from translated Markdown notes."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import re
import sys
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET


EPUB_NS = "http://www.idpf.org/2007/ops"
DC_NS = "http://purl.org/dc/elements/1.1/"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
XML_NS = "http://www.w3.org/XML/1998/namespace"
MIMETYPE = "application/epub+zip"


@dataclass
class Document:
    source: Path
    relative: str
    title: str
    body: str
    metadata: dict[str, str]
    chapter_name: str = ""


class EpubBuilder:
    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        title: str | None,
        author: str | None,
        language: str,
        identifier: str | None,
        include_index: bool,
    ) -> None:
        self.input_path = input_path.resolve()
        self.output_path = output_path.resolve()
        self.language = language
        self.include_index = include_index
        self.warnings: list[str] = []
        self.asset_map: dict[Path, str] = {}
        self.asset_bytes: dict[str, bytes] = {}
        self.documents = self._collect_documents()
        inferred_title = self.documents[0].metadata.get("title") if self.documents else None
        self.title = title or inferred_title or (self.input_path.stem if self.input_path.is_file() else self.input_path.name)
        self.author = author or self._infer_author()
        self.identifier = identifier or "urn:uuid:" + str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"codex-book-translation:{self.input_path}:{self.title}")
        )
        for index, document in enumerate(self.documents, start=1):
            document.chapter_name = f"chapter-{index:04d}.xhtml"

    def _infer_author(self) -> str:
        for document in self.documents:
            for key in ("author", "authors", "author(s)"):
                if document.metadata.get(key):
                    return document.metadata[key]
        return ""

    def _collect_documents(self) -> list[Document]:
        if self.input_path.is_file():
            paths = [self.input_path]
            root = self.input_path.parent
        elif self.input_path.is_dir():
            root = self.input_path
            paths = sorted(
                (p for p in root.rglob("*.md") if not any(part.startswith(".") for part in p.relative_to(root).parts)),
                key=lambda p: self._natural_key(p.relative_to(root).as_posix()),
            )
            index = root / "index.md"
            if index.exists() and not self.include_index:
                paths = [p for p in paths if p != index]
        else:
            raise FileNotFoundError(f"Markdown input does not exist: {self.input_path}")

        documents: list[Document] = []
        for source in paths:
            metadata, body = parse_frontmatter(source.read_text(encoding="utf-8"))
            title = first_heading(body) or metadata.get("title") or source.stem
            relative = source.relative_to(root).as_posix()
            documents.append(Document(source, relative, title, body, metadata))
        return documents

    @staticmethod
    def _natural_key(value: str) -> list[object]:
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]

    def _document_lookup(self) -> dict[str, Document]:
        lookup: dict[str, Document] = {}
        for document in self.documents:
            key = document.relative.lower()
            lookup[key] = document
            lookup[Path(key).name] = document
        return lookup

    def _resolve_document(self, current: Document, target: str) -> tuple[Document | None, str]:
        target = unquote(target.strip())
        split = urlsplit(target)
        fragment = split.fragment
        path = split.path
        if not path or split.scheme or path.startswith("/"):
            return None, fragment
        lookup = self._document_lookup()
        root = self.input_path.parent if self.input_path.is_file() else self.input_path
        candidate = (current.source.parent / path).resolve()
        candidates = [candidate]
        candidates.append((root / path).resolve())
        if not path.lower().endswith(".md"):
            candidates.extend([(Path(str(item) + ".md")).resolve() for item in list(candidates)])
        for item in candidates:
            try:
                relative = item.relative_to(root).as_posix().lower()
            except ValueError:
                continue
            if relative in lookup:
                return lookup[relative], fragment
        basename = Path(path).name.lower()
        return lookup.get(basename), fragment

    def _resolve_asset(self, document: Document, reference: str) -> str | None:
        reference = unquote(reference.strip())
        split = urlsplit(reference)
        if split.scheme or split.netloc:
            self.warnings.append(f"External image kept as a link: {reference}")
            return None
        path = Path(split.path)
        root = self.input_path.parent if self.input_path.is_file() else self.input_path
        candidates = [(document.source.parent / path).resolve(), (root / path).resolve()]
        if path.name:
            candidates.append((root / "assets" / path.name).resolve())
        source = next((candidate for candidate in candidates if candidate.is_file()), None)
        if source is None:
            self.warnings.append(f"Missing local image: {reference} in {document.relative}")
            return None
        if source in self.asset_map:
            return "../" + self.asset_map[source]
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.name).strip("-") or "asset"
        package_path = f"assets/{digest}-{safe_name}"
        self.asset_map[source] = package_path
        self.asset_bytes[package_path] = source.read_bytes()
        return "../" + package_path

    def _token(self, tokens: dict[str, str], value: str) -> str:
        # Keep placeholders in the XML-safe ASCII range.  NUL-delimited
        # placeholders can leak into math expressions and make XHTML invalid.
        key = f"CODEXTOKEN{len(tokens)}END"
        tokens[key] = value
        return key

    def _link_markup(self, document: Document, label: str, target: str, tokens: dict[str, str]) -> str:
        if target.startswith(("http://", "https://", "mailto:")):
            href = html.escape(target, quote=True)
        else:
            linked, fragment = self._resolve_document(document, target)
            if linked is None:
                href = html.escape(target, quote=True)
            else:
                href = linked.chapter_name
                if fragment:
                    href += "#" + slugify(fragment)
        return self._token(tokens, f'<a href="{href}">{self._inline_text(label, document, tokens)}</a>')

    def _inline_text(self, text: str, document: Document, tokens: dict[str, str]) -> str:
        return self._inline_markup(text, document, tokens)

    def _inline_markup(
        self,
        text: str,
        document: Document,
        tokens: dict[str, str] | None = None,
    ) -> str:
        tokens = {} if tokens is None else tokens

        def raw_math(match: re.Match[str]) -> str:
            return self._token(tokens, f'<span class="math">{html.escape(match.group(1))}</span>')

        def raw_break(match: re.Match[str]) -> str:
            return self._token(tokens, "<br />")

        # A small amount of inline HTML is emitted by the translated notes.
        # Protect the known presentation tags before escaping ordinary text.
        text = re.sub(
            r'<span\s+class=["\']math["\']>(.*?)</span>',
            raw_math,
            text,
            flags=re.I | re.S,
        )
        text = re.sub(r"<br\s*/?>", raw_break, text, flags=re.I)

        def image(match: re.Match[str]) -> str:
            alt = html.escape(match.group(1), quote=True)
            src = self._resolve_asset(document, match.group(2))
            if src is None:
                return self._token(tokens, f'<a href="{html.escape(match.group(2), quote=True)}">[External or missing image: {alt}]</a>')
            return self._token(tokens, f'<img src="{src}" alt="{alt}" />')

        text = re.sub(r"!\[([^]]*)\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)", image, text)

        def markdown_link(match: re.Match[str]) -> str:
            return self._link_markup(document, match.group(1), match.group(2), tokens)

        text = re.sub(r"\[([^]]+)\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)", markdown_link, text)

        def wiki_link(match: re.Match[str]) -> str:
            target = match.group(1)
            label = match.group(2) or Path(target.split("#", 1)[0]).stem
            if target.startswith("#"):
                return self._token(tokens, f'<a href="{html.escape(target, quote=True)}">{html.escape(label)}</a>')
            return self._link_markup(document, label, target, tokens)

        text = re.sub(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]", wiki_link, text)

        def math(match: re.Match[str]) -> str:
            return self._token(tokens, f'<span class="math">{html.escape(match.group(0))}</span>')

        # Protect formulas before code spans so backticks embedded in a
        # formula cannot introduce a placeholder into the formula itself.
        text = re.sub(r"\$\$[^$]+\$\$|\$[^$\n]+\$", math, text)

        def code(match: re.Match[str]) -> str:
            return self._token(tokens, f"<code>{html.escape(match.group(1))}</code>")

        text = re.sub(r"`([^`]+)`", code, text)
        text = html.escape(text, quote=False)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
        text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
        for key, value in tokens.items():
            text = text.replace(html.escape(key), value)
        return text

    def _rewrite_raw_html(self, raw: str, document: Document) -> str:
        def image(match: re.Match[str]) -> str:
            src = self._resolve_asset(document, match.group(3))
            if src is None:
                return match.group(0)
            return f'{match.group(1)}src={match.group(2)}{src}{match.group(2)}'

        raw = re.sub(r"(\s)src=(['\"])([^'\"]+)\2", image, raw)
        raw = re.sub(r"(<img\b[^>]*?)(?<!/)>", r"\1 />", raw, flags=re.I)
        raw = re.sub(r"<br\s*>", "<br />", raw, flags=re.I)
        raw = re.sub(r"<hr\s*>", "<hr />", raw, flags=re.I)
        return raw

    def _render_details(self, lines: list[str], document: Document) -> str:
        """Render a GitBook/Markdown details block without swallowing Markdown."""
        content = list(lines)
        summary_start = next(
            (index for index, value in enumerate(content) if value.strip().lower().startswith("<summary")),
            None,
        )
        summary_html = ""
        if summary_start is not None:
            summary_end = summary_start
            while summary_end < len(content) and "</summary>" not in content[summary_end].lower():
                summary_end += 1
            if summary_end < len(content):
                summary_text = "\n".join(content[summary_start:summary_end + 1])
                match = re.search(r"<summary(?:\s[^>]*)?>(.*?)</summary>", summary_text, flags=re.I | re.S)
                if match:
                    summary_html = f"<summary>{self._inline_markup(match.group(1).strip(), document)}</summary>"
                del content[summary_start:summary_end + 1]
        body = self._render_body("\n".join(content), document)
        return "<details>\n" + (summary_html + "\n" if summary_html else "") + body + "\n</details>"

    @staticmethod
    def _repair_title(lines: list[str]) -> tuple[str, list[str]]:
        """Extract a repair label from the first bold line of a hint body."""
        remaining = list(lines)
        for index, line in enumerate(remaining):
            value = line.strip()
            if not value:
                continue
            match = re.fullmatch(r"\*\*(修复块|兼容性修复块|repair|compatibility repair)\*\*", value, flags=re.I)
            if match:
                del remaining[index]
                return match.group(1), remaining
            break
        return "", remaining

    @staticmethod
    def _is_repair_title(title: str) -> bool:
        return bool(re.search(r"修复块|兼容性修复块|repair|correction|fix", title, flags=re.I))

    def _render_tip(self, lines: list[str], document: Document, title: str, repair: bool, style: str = "tip") -> str:
        title, content = self._repair_title(lines) if not title else (title, lines)
        repair = repair or self._is_repair_title(title)
        class_name = "tip repair-block" if repair else style
        title_html = ""
        if title:
            title_html = f'<p class="tip-title">{self._inline_markup(title, document)}</p>\n'
        body = self._render_body("\n".join(content), document)
        return f'<aside class="{class_name}">\n{title_html}{body}\n</aside>'

    def _render_table(self, lines: list[str], document: Document) -> str:
        rows = []
        for line in lines:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            rows.append(cells)
        if not rows:
            return ""
        output = ["<table>", "<thead>", "<tr>"]
        for cell in rows[0]:
            output.append(f"<th>{self._inline_markup(cell, document)}</th>")
        output.extend(["</tr>", "</thead>"])
        if len(rows) > 1:
            output.append("<tbody>")
            for row in rows[1:]:
                output.append("<tr>")
                for cell in row:
                    output.append(f"<td>{self._inline_markup(cell, document)}</td>")
                output.append("</tr>")
            output.append("</tbody>")
        output.append("</table>")
        return "\n".join(output)

    def _render_body(self, body: str, document: Document) -> str:
        lines = body.splitlines()
        output: list[str] = []
        paragraph: list[str] = []
        index = 0

        def flush_paragraph() -> None:
            if paragraph:
                text = " ".join(item.strip() for item in paragraph)
                text = text.replace("\\\\", "<br />")
                output.append(f"<p>{self._inline_markup(text, document)}</p>")
                paragraph.clear()

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                index += 1
                continue
            if stripped.startswith("```"):
                flush_paragraph()
                language = stripped[3:].strip()
                index += 1
                code_lines = []
                while index < len(lines) and not lines[index].strip().startswith("```"):
                    code_lines.append(lines[index])
                    index += 1
                if index < len(lines):
                    index += 1
                class_attr = f' class="language-{html.escape(language, quote=True)}"' if language else ""
                output.append(f"<pre><code{class_attr}>{html.escape(chr(10).join(code_lines))}</code></pre>")
                continue
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
            if heading:
                flush_paragraph()
                level = len(heading.group(1))
                title = heading.group(2)
                output.append(f'<h{level} id="{html.escape(slugify(title), quote=True)}">{self._inline_markup(title, document)}</h{level}>')
                index += 1
                continue
            if stripped.startswith(">"):
                flush_paragraph()
                tip_match = re.match(r"^>\s*\[!TIP\]\s*(.*?)\s*$", stripped, flags=re.I)
                if tip_match:
                    title = tip_match.group(1).strip() or "提示"
                    index += 1
                    tip_lines: list[str] = []
                    while index < len(lines):
                        current = lines[index]
                        if not current.strip():
                            tip_lines.append("")
                            index += 1
                            continue
                        if not current.strip().startswith(">"):
                            break
                        value = current.strip()
                        if tip_lines and re.match(r"^>\s*\[!TIP\]", value, flags=re.I):
                            break
                        tip_lines.append(value[1:].lstrip())
                        index += 1
                    output.append(self._render_tip(tip_lines, document, title, self._is_repair_title(title)))
                    continue
                quote_lines = []
                while index < len(lines) and (lines[index].strip().startswith(">") or not lines[index].strip()):
                    value = lines[index].strip()
                    # A repair TIP may immediately follow a regular quote.
                    # Leave it for the outer loop so it becomes its own aside.
                    if quote_lines and re.match(r"^>\s*\[!TIP\]", value, flags=re.I):
                        break
                    quote_lines.append(value[1:].lstrip() if value.startswith(">") else "")
                    index += 1
                output.append(f"<blockquote>\n{self._render_body(chr(10).join(quote_lines), document)}\n</blockquote>")
                continue
            if stripped.startswith("{% hint"):
                flush_paragraph()
                style_match = re.search(r"style\s*=\s*[\"']([^\"']+)[\"']", stripped, flags=re.I)
                hint_style = style_match.group(1).lower() if style_match else "info"
                index += 1
                callout = []
                while index < len(lines) and not lines[index].strip().startswith("{% endhint"):
                    callout.append(lines[index])
                    index += 1
                if index < len(lines):
                    index += 1
                title, callout = self._repair_title(callout)
                repair = self._is_repair_title(title)
                target_style = "tip" if hint_style in {"info", "success", "tip"} else "callout"
                output.append(self._render_tip(callout, document, title, repair, target_style))
                continue
            if stripped.startswith("<details>"):
                flush_paragraph()
                detail = []
                index += 1
                while index < len(lines):
                    current = lines[index].strip()
                    if current == "</details>":
                        index += 1
                        break
                    detail.append(lines[index])
                    index += 1
                output.append(self._render_details(detail, document))
                continue
            if stripped.startswith("<figure") or stripped.startswith("<pre"):
                flush_paragraph()
                raw_lines = [line]
                closing = "</figure>" if stripped.startswith("<figure") else "</pre>"
                index += 1
                while closing not in raw_lines[-1] and index < len(lines):
                    raw_lines.append(lines[index])
                    index += 1
                output.append(self._rewrite_raw_html(chr(10).join(raw_lines), document))
                continue
            if stripped.startswith("<img "):
                flush_paragraph()
                output.append(self._rewrite_raw_html(stripped, document))
                index += 1
                continue
            if "|" in stripped and index + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
                flush_paragraph()
                table_lines = [line, lines[index + 1]]
                index += 2
                while index < len(lines) and "|" in lines[index] and lines[index].strip():
                    table_lines.append(lines[index])
                    index += 1
                output.append(self._render_table(table_lines, document))
                continue
            if re.match(r"^\s*(?:[-*+]\s+|\d+[.]\s+)", line):
                flush_paragraph()
                ordered = bool(re.match(r"^\s*\d+[.]\s+", line))
                tag = "ol" if ordered else "ul"
                items = []
                while index < len(lines):
                    item = re.match(r"^\s*(?:[-*+]\s+|\d+[.]\s+)(.*)$", lines[index])
                    if not item:
                        break
                    items.append(item.group(1))
                    index += 1
                output.append(f"<{tag}>" + "".join(f"<li>{self._inline_markup(item, document)}</li>" for item in items) + f"</{tag}>")
                continue
            if re.fullmatch(r"\s*(?:\*\s*){3,}|\s*(?:-\s*){3,}", line):
                flush_paragraph()
                output.append("<hr />")
                index += 1
                continue
            paragraph.append(line)
            index += 1
        flush_paragraph()
        return "\n".join(output)

    def _render_document(self, document: Document) -> str:
        title = self._inline_markup(document.title, document)
        body = self._render_body(document.body, document)
        return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="{EPUB_NS}" xml:lang="{html.escape(self.language, quote=True)}" lang="{html.escape(self.language, quote=True)}">
<head><title>{title}</title><link rel="stylesheet" type="text/css" href="../styles.css" /></head>
<body>{body}</body>
</html>
'''

    def _nav(self) -> str:
        items = "\n".join(
            f'<li><a href="text/{document.chapter_name}">{html.escape(document.title)}</a></li>'
            for document in self.documents
        )
        return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="{EPUB_NS}" xml:lang="{html.escape(self.language, quote=True)}" lang="{html.escape(self.language, quote=True)}">
<head><title>{html.escape(self.title)}</title></head>
<body><nav epub:type="toc" id="toc"><h1>{html.escape(self.title)}</h1><ol>{items}</ol></nav></body>
</html>
'''

    def _opf(self) -> str:
        modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest = [
            '<item id="css" href="styles.css" media-type="text/css"/>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        ]
        spine = []
        for index, document in enumerate(self.documents, start=1):
            item_id = f"chapter-{index:04d}"
            manifest.append(f'<item id="{item_id}" href="text/{document.chapter_name}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{item_id}"/>')
        for index, (path, data) in enumerate(sorted(self.asset_bytes.items()), start=1):
            media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
            manifest.append(f'<item id="asset-{index}" href="{html.escape(path, quote=True)}" media-type="{media_type}"/>')
        author = f'<dc:creator>{html.escape(self.author)}</dc:creator>' if self.author else ""
        return f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0">
<metadata xmlns:dc="{DC_NS}" xmlns:dcterms="http://purl.org/dc/terms/">
<dc:identifier id="book-id">{html.escape(self.identifier)}</dc:identifier>
<dc:title>{html.escape(self.title)}</dc:title>
{author}
<dc:language>{html.escape(self.language)}</dc:language>
<meta property="dcterms:modified">{modified}</meta>
</metadata>
<manifest>{"".join(manifest)}</manifest>
<spine>{"".join(spine)}</spine>
</package>
'''

    def _container(self) -> str:
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="{CONTAINER_NS}"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>
'''

    def build(self) -> dict[str, object]:
        if not self.documents:
            raise ValueError("No Markdown documents found")
        for document in self.documents:
            for reference in image_references(document.body):
                self._resolve_asset(document, reference)
        entries: dict[str, bytes] = {
            "mimetype": MIMETYPE.encode("ascii"),
            "META-INF/container.xml": self._container().encode("utf-8"),
            "OEBPS/content.opf": self._opf().encode("utf-8"),
            "OEBPS/nav.xhtml": self._nav().encode("utf-8"),
            "OEBPS/styles.css": DEFAULT_CSS.encode("utf-8"),
        }
        for document in self.documents:
            entries[f"OEBPS/text/{document.chapter_name}"] = self._render_document(document).encode("utf-8")
        for path, data in self.asset_bytes.items():
            entries[f"OEBPS/{path}"] = data
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.output_path, "w") as archive:
            for name in ["mimetype"] + sorted(key for key in entries if key != "mimetype"):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, entries[name])
        report = {
            "output": str(self.output_path),
            "title": self.title,
            "author": self.author,
            "language": self.language,
            "documents": len(self.documents),
            "assets": len(self.asset_bytes),
            "warnings": list(dict.fromkeys(self.warnings)),
        }
        validate_epub(self.output_path)
        return report


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        return {}, text
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_(). -]+):\s*(.*)$", line)
        if match:
            value = match.group(2).strip().strip("\"'")
            metadata[match.group(1).strip().lower()] = value
    return metadata, "\n".join(lines[end + 1 :])


def first_heading(body: str) -> str | None:
    match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def image_references(body: str) -> list[str]:
    references = re.findall(r"!\[[^]]*\]\(([^)\s]+)", body)
    references.extend(re.findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)", body, flags=re.I))
    return list(dict.fromkeys(references))


def slugify(value: str) -> str:
    value = re.sub(r"[`*_~]", "", value).strip().lower()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "section"


def validate_epub(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names or names[0] != "mimetype" or archive.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
            raise ValueError("Invalid EPUB: mimetype must be the first uncompressed entry")
        if archive.read("mimetype") != MIMETYPE.encode("ascii"):
            raise ValueError("Invalid EPUB mimetype contents")
        required = {"META-INF/container.xml", "OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/styles.css"}
        missing = required - set(names)
        if missing:
            raise ValueError(f"Invalid EPUB: missing {sorted(missing)}")
        for name in names:
            if name.endswith((".xhtml", ".opf", ".xml")):
                ET.fromstring(archive.read(name))
        opf_root = ET.fromstring(archive.read("OEBPS/content.opf"))
        manifest = {item.attrib.get("href") for item in opf_root.findall("{http://www.idpf.org/2007/opf}manifest/{http://www.idpf.org/2007/opf}item")}
        for href in manifest:
            if href and f"OEBPS/{href}" not in names:
                raise ValueError(f"Invalid EPUB: manifest resource is missing: {href}")


DEFAULT_CSS = """body { font-family: serif; line-height: 1.5; margin: 5%; }
h1, h2, h3, h4, h5, h6 { line-height: 1.2; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f2f2f2; padding: 0.8em; }
code { font-family: monospace; }
blockquote { margin: 1em 0; padding-left: 1em; border-left: 0.2em solid #999; }
img { max-width: 100%; height: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #999; padding: 0.35em; vertical-align: top; }
.callout { border-left: 0.25em solid #777; padding: 0.5em 1em; }
.tip { margin: 1em 0; padding: 0.7em 1em; border-left: 0.25em solid #3d7f5f; background: #eef7f1; }
.tip.repair-block { border-left-color: #b36b16; background: #fff7e6; }
.tip-title { margin: 0 0 0.45em; font-weight: bold; }
.tip pre { background: rgba(255, 255, 255, 0.65); }
.math { font-family: monospace; white-space: pre-wrap; }
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown file or directory")
    parser.add_argument("output", type=Path, help="Output EPUB path")
    parser.add_argument("--title", help="Book title")
    parser.add_argument("--author", help="Book author")
    parser.add_argument("--language", default="zh-CN", help="BCP-47 language tag (default: zh-CN)")
    parser.add_argument("--identifier", help="Stable publication identifier")
    parser.add_argument("--include-index", action="store_true", help="Include index.md as a chapter when input is a directory")
    parser.add_argument("--report", type=Path, help="Write a JSON build report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = EpubBuilder(
            args.input,
            args.output,
            args.title,
            args.author,
            args.language,
            args.identifier,
            args.include_index,
        ).build()
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"EPUB build failed: {error}", file=sys.stderr)
        return 1
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built EPUB: {args.output}")
    print(f"Documents: {report['documents']}; assets: {report['assets']}; warnings: {len(report['warnings'])}")
    for warning in report["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
