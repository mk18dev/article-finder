#!/usr/bin/env python3
"""Validate and optionally extract an Article Finder skill archive safely."""
from __future__ import annotations

import argparse
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = "article-finder/"
REQUIRED = {
    "article-finder/SKILL.md",
    "article-finder/VERSION",
    "article-finder/README.md",
    "article-finder/requirements.txt",
}
FORBIDDEN_SUFFIXES = {".pdf", ".pyc", ".skill"}


def validate(archive_path: Path) -> list[str]:
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise ValueError("Archive contains duplicate paths")
        if not REQUIRED.issubset(names):
            raise ValueError(f"Archive is missing required paths: {sorted(REQUIRED - set(names))}")
        for item in infos:
            name = item.filename
            path = PurePosixPath(name)
            if not name.startswith(ROOT) or path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError(f"Unsafe archive path: {name!r}")
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                raise ValueError(f"Forbidden file type in archive: {name!r}")
            if any(part in {"__pycache__", ".git", "dist", "tools"} for part in path.parts):
                raise ValueError(f"Build-only path in archive: {name!r}")
            mode = item.external_attr >> 16
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                raise ValueError(f"Non-regular archive entry: {name!r}")
        version = archive.read("article-finder/VERSION").decode("utf-8").strip()
        if version != "1.1.0":
            raise ValueError(f"Expected package version 1.1.0, found {version!r}")
        return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--extract-to", type=Path)
    args = parser.parse_args()
    names = validate(args.archive)
    if args.extract_to:
        destination = args.extract_to.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.archive) as archive:
            for item in archive.infolist():
                target = (destination / PurePosixPath(item.filename)).resolve()
                if destination not in target.parents:
                    raise ValueError(f"Archive entry escapes destination: {item.filename!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
                mode = item.external_attr >> 16
                target.chmod(stat.S_IMODE(mode))
    print(f"Validated {len(names)} regular files for Article Finder 1.1.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
