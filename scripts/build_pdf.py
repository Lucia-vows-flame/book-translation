#!/usr/bin/env python3
"""Build a PDF directly from translated Markdown through Typst and bookly."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


DEFAULT_BOOKLY_VERSION = "5.1.1"
DEFAULT_FONTS = {
    "body": "Noto Serif CJK SC",
    "heading": "Noto Sans CJK SC",
    "math": "New Computer Modern Math",
    "raw": "DejaVu Sans Mono",
}


@dataclass
class Document:
    source: Path
    relative: str
    title: str
    body: str
    metadata: dict[str, str]


def typst_string(value: str) -> str:
    """Return a Typst string literal without relying on markup escaping."""

    return json.dumps(value, ensure_ascii=False)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        return {}, text
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_(). -]+):\s*(.*)$", line)
        if match:
            metadata[match.group(1).strip().lower()] = match.group(2).strip().strip("\"'")
    return metadata, "\n".join(lines[end + 1 :])


def first_heading(body: str) -> str | None:
    match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


class PdfBuilder:
    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        config_path: Path | None,
        title: str | None,
        author: str | None,
        language: str,
        typst: str,
        include_index: bool,
        source_output: Path | None,
    ) -> None:
        self.input_path = input_path.resolve()
        self.output_path = output_path.resolve()
        self.language = language
        self.typst = typst
        self.include_index = include_index
        self.source_output = source_output.resolve() if source_output else None
        self.warnings: list[str] = []
        self.asset_map: dict[Path, str] = {}
        self.config = self._read_config(config_path)
        self.documents = self._collect_documents()
        inferred_title = self.documents[0].metadata.get("title") if self.documents else None
        self.title = title or inferred_title or self.input_path.stem
        self.author = author or self._infer_author()

    @staticmethod
    def _read_config(path: Path | None) -> dict[str, object]:
        if path is None:
            return {
                "template": {"name": "bookly", "version": DEFAULT_BOOKLY_VERSION},
                "fonts": dict(DEFAULT_FONTS),
                "font_paths": [],
            }
        data = json.loads(path.read_text(encoding="utf-8"))
        template = data.get("template", {})
        if template.get("name", "bookly") != "bookly":
            raise ValueError("PDF adapter currently supports the bookly template only")
        return data

    def _collect_documents(self) -> list[Document]:
        if self.input_path.is_file():
            paths = [self.input_path]
            root = self.input_path.parent
        elif self.input_path.is_dir():
            root = self.input_path
            paths = sorted(
                (
                    p
                    for p in root.rglob("*.md")
                    if not any(part.startswith(".") for part in p.relative_to(root).parts)
                ),
                key=lambda p: natural_key(p.relative_to(root).as_posix()),
            )
            if not self.include_index:
                paths = [p for p in paths if p != root / "index.md"]
        else:
            raise FileNotFoundError(f"Markdown input does not exist: {self.input_path}")

        documents: list[Document] = []
        for source in paths:
            metadata, body = parse_frontmatter(source.read_text(encoding="utf-8"))
            title = first_heading(body) or metadata.get("title") or source.stem
            documents.append(Document(source, source.relative_to(root).as_posix(), title, body, metadata))
        return documents

    def _infer_author(self) -> str:
        for document in self.documents:
            for key in ("author", "authors", "author(s)"):
                if document.metadata.get(key):
                    return document.metadata[key]
        return ""

    def _root(self) -> Path:
        return self.input_path.parent if self.input_path.is_file() else self.input_path

    def _resolve_asset(self, document: Document, reference: str, workdir: Path) -> str | None:
        reference = unquote(reference.strip())
        split = urlsplit(reference)
        if split.scheme or split.netloc:
            self.warnings.append(f"External image kept as a link: {reference}")
            return None
        path = Path(split.path)
        candidates = [(document.source.parent / path).resolve(), (self._root() / path).resolve()]
        if path.name:
            candidates.append((self._root() / "assets" / path.name).resolve())
        source = next((candidate for candidate in candidates if candidate.is_file()), None)
        if source is None:
            self.warnings.append(f"Missing local image: {reference} in {document.relative}")
            return None
        if source in self.asset_map:
            return self.asset_map[source]
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.name).strip("-") or "asset"
        target = f"assets/{digest}-{safe_name}"
        destination = workdir / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        self.asset_map[source] = target
        return target

    def _render_inline(self, text: str, document: Document, workdir: Path) -> str:
        """Convert common Markdown inline constructs to safe Typst expressions."""

        pattern = re.compile(
            r"!\[([^]]*)\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)"
            r"|\[([^]]+)\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)"
            r"|`([^`]+)`"
            r"|\$\$([^$]+)\$\$"
            r"|\$([^$\n]+)\$"
            r"|\*\*([^*]+)\*\*"
            r"|__([^_]+)__"
            r"|\*([^*]+)\*"
            r"|_([^_]+)_"
            r"|<br\s*/?>",
            flags=re.IGNORECASE | re.DOTALL,
        )
        pieces: list[str] = []
        cursor = 0

        def plain(value: str) -> str:
            return f"#text({typst_string(value)})" if value else ""

        for match in pattern.finditer(text):
            pieces.append(plain(text[cursor : match.start()]))
            groups = match.groups()
            if groups[0] is not None:
                alt, reference = groups[0], groups[1]
                asset = self._resolve_asset(document, reference, workdir)
                if asset:
                    pieces.append(f"#cb_inline_image({typst_string(asset)})")
                else:
                    pieces.append(
                        f"#link({typst_string(reference)})[#text({typst_string('[图片链接: ' + alt + ']')})]"
                    )
            elif groups[2] is not None:
                pieces.append(f"#link({typst_string(groups[3])})[{self._render_inline(groups[2], document, workdir)}]")
            elif groups[4] is not None:
                pieces.append(f"#cb_inline_code({typst_string(groups[4])})")
            elif groups[5] is not None:
                pieces.append(f"#cb_display_math[${groups[5]}$]")
            elif groups[6] is not None:
                pieces.append(f"${groups[6]}$")
            elif groups[7] is not None or groups[8] is not None:
                pieces.append(f"#strong[{plain(groups[7] or groups[8])}]")
            elif groups[9] is not None or groups[10] is not None:
                pieces.append(f"#emph[{plain(groups[9] or groups[10])}]")
            else:
                pieces.append("#linebreak()")
            cursor = match.end()
        pieces.append(plain(text[cursor:]))
        return "".join(pieces)

    def _render_table(self, lines: list[str], document: Document, workdir: Path) -> str:
        rows: list[list[str]] = []
        for line in lines:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            rows.append(cells)
        if not rows:
            return ""
        columns = max(len(row) for row in rows)
        def render_row(row: list[str]) -> str:
            row = row + [""] * (columns - len(row))
            return ", ".join(f"[{self._render_inline(cell, document, workdir)}]" for cell in row)

        header = render_row(rows[0])
        body = ", ".join(render_row(row) for row in rows[1:])
        return (
            f"#cb_table(columns: {columns}, header: ({header}), "
            f"body: ({body}))"
        )

    def _render_blocks(self, body: str, document: Document, workdir: Path, skip_title: bool = False) -> str:
        lines = body.splitlines()
        output: list[str] = []
        paragraph: list[str] = []
        index = 0

        def flush() -> None:
            if paragraph:
                joined = " ".join(item.strip() for item in paragraph)
                output.append(self._render_inline(joined, document, workdir))
                # Keep adjacent Markdown paragraphs separate in the generated source.
                output.append("\n#parbreak()\n")
                paragraph.clear()

        skipped = not skip_title
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped:
                flush()
                index += 1
                continue
            fence = re.match(r"^\s*(```+|~~~+)\s*(.*)$", line)
            if fence:
                flush()
                marker, language = fence.group(1), fence.group(2).strip()
                index += 1
                code: list[str] = []
                while index < len(lines) and not lines[index].strip().startswith(marker[0] * len(marker)):
                    code.append(lines[index])
                    index += 1
                if index < len(lines):
                    index += 1
                lang = f", language: {typst_string(language)}" if language else ""
                output.append(f"#cb_code({typst_string(chr(10).join(code))}{lang})\n")
                continue
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
            if heading:
                flush()
                title = heading.group(2)
                if not skipped and len(heading.group(1)) == 1:
                    skipped = True
                else:
                    skipped = True
                    output.append("=" * len(heading.group(1)) + " " + self._render_inline(title, document, workdir) + "\n")
                index += 1
                continue
            if stripped.startswith(">"):
                flush()
                quote: list[str] = []
                while index < len(lines) and (lines[index].strip().startswith(">") or not lines[index].strip()):
                    value = lines[index].strip()
                    quote.append(value[1:].lstrip() if value.startswith(">") else "")
                    index += 1
                inner = self._render_blocks("\n".join(quote), document, workdir)
                output.append(f"#cb_quote[{inner}]\n")
                continue
            if stripped.startswith("{% hint"):
                flush()
                index += 1
                callout: list[str] = []
                while index < len(lines) and not lines[index].strip().startswith("{% endhint"):
                    callout.append(lines[index])
                    index += 1
                if index < len(lines):
                    index += 1
                inner = self._render_blocks("\n".join(callout), document, workdir)
                output.append(f"#cb_hint[{inner}]\n")
                continue
            if stripped == "<details>":
                flush()
                detail: list[str] = []
                index += 1
                while index < len(lines) and lines[index].strip() != "</details>":
                    detail.append(lines[index])
                    index += 1
                if index < len(lines):
                    index += 1
                output.append(f"#cb_details[{self._render_blocks(chr(10).join(detail), document, workdir)}]\n")
                continue
            if stripped.startswith("<img "):
                flush()
                match = re.search(r"src=[\"']([^\"']+)[\"']", stripped, flags=re.IGNORECASE)
                alt = re.search(r"alt=[\"']([^\"']*)[\"']", stripped, flags=re.IGNORECASE)
                if match:
                    reference = match.group(1)
                    asset = self._resolve_asset(document, reference, workdir)
                    if asset:
                        caption = alt.group(1) if alt else ""
                        figure = f"#cb_image({typst_string(asset)}"
                        if caption:
                            figure += f", caption: [{self._render_inline(caption, document, workdir)}]"
                        output.append(figure + ")\n")
                    else:
                        output.append(f"#link({typst_string(reference)})[#text(\"[图片链接]\")]\n")
                index += 1
                continue
            if "|" in stripped and index + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
                flush()
                table_lines = [line, lines[index + 1]]
                index += 2
                while index < len(lines) and "|" in lines[index] and lines[index].strip():
                    table_lines.append(lines[index])
                    index += 1
                output.append(self._render_table(table_lines, document, workdir) + "\n")
                continue
            list_item = re.match(r"^\s*([-*+] |\d+[.] )(.*)$", line)
            if list_item:
                flush()
                ordered = bool(re.match(r"^\s*\d+[.] ", line))
                marker = "+" if ordered else "-"
                items: list[str] = []
                while index < len(lines):
                    item = re.match(r"^\s*(?:[-*+] |\d+[.] )(.*)$", lines[index])
                    if not item:
                        break
                    items.append(item.group(1))
                    index += 1
                output.extend(f"{marker} {self._render_inline(item, document, workdir)}\n" for item in items)
                continue
            if re.fullmatch(r"\s*(?:\*\s*){3,}|\s*(?:-\s*){3,}", line):
                flush()
                output.append("#cb_rule()\n")
                index += 1
                continue
            if stripped.startswith("<") and stripped.endswith(">"):
                self.warnings.append(f"Unconverted HTML block in {document.relative}: {stripped[:80]}")
                paragraph.append(re.sub(r"<[^>]+>", "", stripped))
            else:
                paragraph.append(line)
            index += 1
        flush()
        return "".join(output)

    def _document_source(self, document: Document, workdir: Path) -> str:
        body = document.body
        return self._render_blocks(body, document, workdir, skip_title=bool(first_heading(body)))

    def _layout_source(self) -> str:
        template = self.config.get("template", {})
        version = template.get("version", DEFAULT_BOOKLY_VERSION)
        fonts = dict(DEFAULT_FONTS)
        fonts.update(self.config.get("fonts", {}))
        typst_lang = self.language.split("-", 1)[0]
        return "\n".join(
            [
            f'#import "@preview/bookly:{version}": *',
            "",
            "#let cb_layout(body) = {",
            "  show: bookly.with(",
            f"    title: {typst_string(self.title)},",
            f"    author: {typst_string(self.author)},",
            "    theme: classic,",
            f"    lang: {typst_string(typst_lang)},",
            "    title-page: none,",
            "    fonts: (",
            f"      body: {typst_string(fonts['body'])},",
            f"      math: {typst_string(fonts['math'])},",
            f"      raw: {typst_string(fonts['raw'])},",
            "    ),",
            '    config-options: (open-right: false, paper-size: "a4", par-indent: false,),',
            "  )",
            f'  show heading: it => {{ set text(font: {typst_string(fonts["heading"])}); it }}',
            "  show: main-matter",
            "  body",
            "}",
            "#let cb_tableofcontents() = tableofcontents",
            "",
            "// Semantic components used by generated content files.",
            "#let cb_inline_code(value) = raw(value)",
            "#let cb_code(value, language: none) = if language == none {",
            "  raw(block: true, value)",
            "} else {",
            "  raw(block: true, lang: language, value)",
            "}",
            "#let cb_display_math(body) = align(center, body)",
            "#let cb_inline_image(path) = image(path, width: 100%)",
            "#let cb_image(path, caption: none) = if caption == none {",
            "  figure(image(path, width: 100%))",
            "} else {",
            "  figure(image(path, width: 100%), caption: caption)",
            "}",
            "#let cb_quote(body) = block(fill: luma(96%), inset: 8pt, radius: 2pt, body)",
            '#let cb_hint(body) = block(stroke: (left: 2pt + rgb("#c1002a")), inset: 8pt, body)',
            "#let cb_details(body) = block(stroke: 0.5pt + luma(65%), inset: 8pt, body)",
            "#let cb_rule() = line(length: 100%)",
            "#let cb_table(columns: 1, header: (), body: ()) = table(",
            "  columns: columns,",
            "  stroke: 0.5pt + luma(60%),",
            "  inset: 4pt,",
            "  table.header(..header),",
            "  ..body,",
            ")",
            "",
            ]
        )

    def _content_source(self, document: Document, workdir: Path) -> str:
        return "\n".join(
            [
                (
                    '#import "../layout.typ": '
                    "cb_inline_code, cb_code, cb_display_math, cb_inline_image, "
                    "cb_image, cb_quote, cb_hint, cb_details, cb_rule, cb_table"
                ),
                "",
                f"= {self._render_inline(document.title, document, workdir)}",
                self._document_source(document, workdir),
                "",
            ]
        )

    def _main_source(self) -> str:
        chunks = [
            '#import "layout.typ": cb_layout, cb_tableofcontents',
            "#show: cb_layout",
            "#cb_tableofcontents()",
            "",
        ]
        for index in range(1, len(self.documents) + 1):
            chunks.append(f'#include "content/chapter-{index:04d}.typ"')
        return "\n".join(chunks) + "\n"

    def _write_source_tree(self, root: Path) -> Path:
        content_dir = root / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        (root / "layout.typ").write_text(self._layout_source(), encoding="utf-8")
        for index, document in enumerate(self.documents, start=1):
            (content_dir / f"chapter-{index:04d}.typ").write_text(
                self._content_source(document, root), encoding="utf-8"
            )
        main = root / "main.typ"
        main.write_text(self._main_source(), encoding="utf-8")
        return main

    def build(self) -> dict[str, object]:
        if not self.documents:
            raise ValueError("No Markdown documents found")
        executable = shutil.which(self.typst) if not Path(self.typst).is_file() else self.typst
        if executable is None:
            raise FileNotFoundError(f"Typst executable not found: {self.typst}")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="codex-pdf-") as directory:
            workdir = Path(directory)
            source = self._write_source_tree(workdir)
            if self.source_output:
                self.source_output.mkdir(parents=True, exist_ok=True)
                shutil.copytree(workdir, self.source_output, dirs_exist_ok=True)
            env = os.environ.copy()
            font_paths = [str(item) for item in self.config.get("font_paths", [])]
            if font_paths:
                env["TYPST_FONT_PATHS"] = os.pathsep.join(font_paths + ([env["TYPST_FONT_PATHS"]] if env.get("TYPST_FONT_PATHS") else []))
            result = subprocess.run(
                [executable, "compile", str(source), str(self.output_path)],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 or not self.output_path.is_file() or self.output_path.stat().st_size == 0:
                diagnostic = (result.stderr or result.stdout).strip()
                raise RuntimeError(diagnostic or "Typst compilation failed")
        typst_info = self.config.get("typst", {})
        if not isinstance(typst_info, dict):
            typst_info = {}
        typst_info = dict(typst_info)
        typst_info["executable"] = executable
        return {
            "status": "ok",
            "output": str(self.output_path),
            "title": self.title,
            "author": self.author,
            "documents": len(self.documents),
            "template": self.config.get("template", {"name": "bookly", "version": DEFAULT_BOOKLY_VERSION}),
            "typst": typst_info,
            "warnings": list(dict.fromkeys(self.warnings)),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown file or directory")
    parser.add_argument("output", type=Path, help="Output PDF path")
    parser.add_argument("--config", type=Path, help="Environment config from check_typst_env.py")
    parser.add_argument("--title", help="Book title")
    parser.add_argument("--author", help="Book author")
    parser.add_argument("--language", default="zh-CN", help="BCP-47 language tag (default: zh-CN)")
    parser.add_argument("--typst", default="typst", help="Typst executable (default: typst)")
    parser.add_argument("--include-index", action="store_true", help="Include index.md for directory inputs")
    parser.add_argument(
        "--typst-source",
        type=Path,
        help="Keep the generated Typst source tree in this directory",
    )
    parser.add_argument("--report", type=Path, help="Write a JSON build report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, object]
    try:
        report = PdfBuilder(
            args.input,
            args.output,
            args.config,
            args.title,
            args.author,
            args.language,
            args.typst,
            args.include_index,
            args.typst_source,
        ).build()
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        report = {"status": "error", "error": str(error)}
        print(f"PDF build failed: {error}", file=sys.stderr)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built PDF: {args.output}")
    print(f"Documents: {report['documents']}; warnings: {len(report['warnings'])}")
    for warning in report["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
