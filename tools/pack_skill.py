#!/usr/bin/env python3
"""Pack the skill into dist/article-finder.skill.

Usage:
    python3 tools/pack_skill.py [--out dist/article-finder.skill]

The archive keeps the `article-finder/` root folder so it can be unpacked
straight into a skills directory. Byte-code, the build output and any fetched
PDF are never included: the tests are shipped, the papers are not.
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = "article-finder"
INCLUDE = ("SKILL.md", "VERSION", "README.md", "LICENSE", "NOTICE", "references", "scripts", "skills", "tests", "examples")
EXCLUDE_DIRS = {"__pycache__", "dist", ".git", ".github", "tools", "pdfs"}
EXCLUDE_SUFFIXES = {".pyc", ".pdf", ".skill"}


def collect() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE:
        path = ROOT / name
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            if EXCLUDE_DIRS & set(child.relative_to(ROOT).parts):
                continue
            if child.suffix in EXCLUDE_SUFFIXES:
                continue
            files.append(child)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack the skill archive.")
    parser.add_argument("--out", default=str(ROOT / "dist" / "article-finder.skill"))
    args = parser.parse_args()

    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    files = collect()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, f"{SKILL}/{path.relative_to(ROOT).as_posix()}")
    size = target.stat().st_size
    print(f"{target}: {len(files)} files, {size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
