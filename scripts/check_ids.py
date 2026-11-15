#!/usr/bin/env python3
"""Offline checksum validation for ISSN, ISBN-10 and ISBN-13.

Usage:
    python3 check_ids.py 1384-5810 1573-756X 978-0-262-03384-8

Each argument is classified by its length (8 characters = ISSN, 10 = ISBN-10,
13 = ISBN-13, after removing hyphens and spaces) and printed as VALID or
INVALID. A valid checksum only proves the number is well-formed; it does not
prove the journal or book exists, so still confirm the identifier on SJR, the
publisher page or the Master Journal List.
"""
import sys


def clean(value: str) -> str:
    return value.replace("-", "").replace(" ", "").upper()


def issn_valid(s: str) -> bool:
    if len(s) != 8 or not s[:7].isdigit() or not (s[7].isdigit() or s[7] == "X"):
        return False
    total = sum(int(d) * w for d, w in zip(s[:7], range(8, 1, -1)))
    check = (11 - total % 11) % 11
    expected = "X" if check == 10 else str(check)
    return s[7] == expected


def isbn10_valid(s: str) -> bool:
    if len(s) != 10 or not s[:9].isdigit() or not (s[9].isdigit() or s[9] == "X"):
        return False
    total = sum(int(d) * w for d, w in zip(s[:9], range(10, 1, -1)))
    last = 10 if s[9] == "X" else int(s[9])
    return (total + last) % 11 == 0


def isbn13_valid(s: str) -> bool:
    if len(s) != 13 or not s.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(s[:12]))
    return (10 - total % 10) % 10 == int(s[12])


def classify(raw: str) -> tuple[str, bool]:
    s = clean(raw)
    if len(s) == 8:
        return "ISSN", issn_valid(s)
    if len(s) == 10:
        return "ISBN-10", isbn10_valid(s)
    if len(s) == 13:
        return "ISBN-13", isbn13_valid(s)
    return "unknown (expected 8, 10 or 13 characters)", False


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    bad = 0
    for raw in argv:
        kind, ok = classify(raw)
        print(f"{raw}\t{kind}\t{'VALID' if ok else 'INVALID'}")
        bad += 0 if ok else 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
