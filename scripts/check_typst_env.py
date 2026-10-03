#!/usr/bin/env python3
"""Check and describe the Typst environment used by the PDF adapter."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


DEFAULT_BOOKLY_VERSION = "5.1.1"
DEFAULT_FONTS = {
    "body": "Noto Serif CJK SC",
    "heading": "Noto Sans CJK SC",
    "math": "New Computer Modern Math",
    "raw": "DejaVu Sans Mono",
}


def run(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, env=env, check=False)


def typst_version(executable: str) -> str | None:
    result = run([executable, "--version"])
    if result.returncode != 0:
        return None
    match = re.search(r"\bTypst\s+(\S+)", result.stdout, flags=re.IGNORECASE)
    return match.group(1) if match else result.stdout.strip().splitlines()[0]


def discovered_fonts(executable: str, font_paths: list[Path]) -> tuple[set[str], str | None]:
    env = os.environ.copy()
    if font_paths:
        separator = os.pathsep
        existing = env.get("TYPST_FONT_PATHS", "")
        env["TYPST_FONT_PATHS"] = separator.join(str(path) for path in font_paths) + (
            separator + existing if existing else ""
        )
    result = run([executable, "fonts"], env=env)
    if result.returncode != 0:
        return set(), result.stderr.strip() or result.stdout.strip()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}, None


def probe_document(version: str, fonts: dict[str, str]) -> str:
    def typst_string(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    return f'''#import "@preview/bookly:{version}": *

#show: bookly.with(
  title: "Typst environment probe",
  author: "codex-book-translation",
  theme: classic,
  lang: "zh",
  fonts: (
    body: {typst_string(fonts["body"])},
    math: {typst_string(fonts["math"])},
    raw: {typst_string(fonts["raw"])},
  ),
  title-page: none,
  config-options: (open-right: false,),
)

= Probe

#text(font: {typst_string(fonts["heading"])})[中文标题字体检查]

中文 English $x^2 + y^2$

```java
class Probe {{}}
```
'''


def compile_probe(executable: str, version: str, fonts: dict[str, str], font_paths: list[Path]) -> tuple[bool, str]:
    env = os.environ.copy()
    if font_paths:
        separator = os.pathsep
        existing = env.get("TYPST_FONT_PATHS", "")
        env["TYPST_FONT_PATHS"] = separator.join(str(path) for path in font_paths) + (
            separator + existing if existing else ""
        )
    with tempfile.TemporaryDirectory(prefix="codex-typst-probe-") as directory:
        root = Path(directory)
        source = root / "probe.typ"
        output = root / "probe.pdf"
        source.write_text(probe_document(version, fonts), encoding="utf-8")
        result = run([executable, "compile", str(source), str(output)], env=env)
        if result.returncode == 0 and output.is_file() and output.stat().st_size > 0:
            return True, str(output)
        diagnostic = (result.stderr or result.stdout).strip()
        return False, diagnostic or "Typst probe compilation failed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--typst", default="typst", help="Typst executable (default: typst)")
    parser.add_argument("--bookly-version", default=DEFAULT_BOOKLY_VERSION)
    parser.add_argument("--font-path", action="append", type=Path, default=[])
    parser.add_argument("--body-font", default=DEFAULT_FONTS["body"])
    parser.add_argument("--heading-font", default=DEFAULT_FONTS["heading"])
    parser.add_argument("--math-font", default=DEFAULT_FONTS["math"])
    parser.add_argument("--raw-font", default=DEFAULT_FONTS["raw"])
    parser.add_argument("--skip-compile", action="store_true", help="Only inspect Typst and fonts")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this path")
    parser.add_argument("--config", type=Path, help="Write reusable PDF adapter configuration after a successful check")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fonts = {
        "body": args.body_font,
        "heading": args.heading_font,
        "math": args.math_font,
        "raw": args.raw_font,
    }
    report: dict[str, object] = {
        "status": "error",
        "template": {
            "name": "bookly",
            "version": args.bookly_version,
            "import": f"@preview/bookly:{args.bookly_version}",
        },
        "fonts": {name: {"requested": value, "available": False} for name, value in fonts.items()},
        "warnings": [],
        "errors": [],
    }

    executable = shutil.which(args.typst) if not Path(args.typst).is_file() else args.typst
    if executable is None:
        report["errors"] = [f"Typst executable not found: {args.typst}"]
    else:
        version = typst_version(executable)
        report["typst"] = {"executable": executable, "version": version}
        if version is None:
            report["errors"] = [f"Unable to read Typst version from: {executable}"]
        else:
            available, font_error = discovered_fonts(executable, args.font_path)
            for name, requested in fonts.items():
                report["fonts"][name]["available"] = requested in available  # type: ignore[index]
            missing = [name for name, requested in fonts.items() if requested not in available]
            if font_error:
                report["errors"] = [font_error]
            elif missing:
                report["warnings"] = [
                    "Requested fonts are unavailable: " + ", ".join(f"{name}={fonts[name]}" for name in missing)
                ]
            if not args.skip_compile:
                ok, diagnostic = compile_probe(executable, args.bookly_version, fonts, args.font_path)
                report["probe"] = {"compiled": ok, "diagnostic": diagnostic}
                if not ok:
                    report["errors"] = [diagnostic]
            else:
                report["probe"] = {"compiled": None, "diagnostic": "skipped"}

        if not report["errors"]:
            report["status"] = "ok"

    if args.config and report["status"] == "ok":
        typst_info = report.get("typst", {})
        config = {
            "template": report["template"],
            "fonts": fonts,
            "font_paths": [str(path) for path in args.font_path],
            "typst": typst_info,
        }
        args.config.parent.mkdir(parents=True, exist_ok=True)
        args.config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
