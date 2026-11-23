#!/usr/bin/env python3
"""Build a deterministic Article Finder skill archive."""
from __future__ import annotations

import argparse
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = "article-finder"
INCLUDE = ("SKILL.md", "VERSION", "README.md", "LICENSE", "NOTICE", "CHANGELOG.md", "index.html", "app.js", "styles.css", ".github/workflows/tests.yml", "vercel.json", "requirements.txt", "api", "references", "scripts", "skills", "tests", "examples")
EXCLUDE_DIRS = {"__pycache__", "dist", ".git", ".github", "tools", "pdfs"}
EXCLUDE_FILES = {"test_pack_skill.py"}
EXCLUDE_SUFFIXES = {".pyc", ".pdf", ".skill"}
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def collect() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE:
        path = ROOT / name
        if path.is_symlink():
            raise ValueError(f"Refusing to package symlink: {path.relative_to(ROOT)}")
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in sorted(path.rglob("*")):
            relative = child.relative_to(ROOT)
            if child.is_symlink():
                raise ValueError(f"Refusing to package symlink: {relative.as_posix()}")
            if not child.is_file():
                continue
            if EXCLUDE_DIRS & set(relative.parts):
                continue
            if relative.parent.name == "tests" and child.name in EXCLUDE_FILES:
                continue
            if child.suffix.lower() in EXCLUDE_SUFFIXES:
                continue
            files.append(child)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack the skill archive deterministically.")
    parser.add_argument("--out", default=str(ROOT / "dist" / "article-finder.skill"))
    args = parser.parse_args()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    files = collect()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.comment = b""
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            source_mode = path.stat().st_mode
            file_mode = 0o755 if source_mode & stat.S_IXUSR else 0o644
            info = zipfile.ZipInfo(f"{SKILL}/{relative}", date_time=FIXED_ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | file_mode) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    print(f"{target}: {len(files)} files, {target.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
