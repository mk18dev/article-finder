"""Regression tests for scripts/check_ids.py. Run: python -m unittest discover tests"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_ids as ci


class IssnTests(unittest.TestCase):
    def test_valid_issn(self) -> None:
        self.assertTrue(ci.issn_valid("09241868"))
        self.assertTrue(ci.issn_valid("13845810"))

    def test_valid_issn_with_x_check_digit(self) -> None:
        self.assertTrue(ci.issn_valid("1573756X"))

    def test_invalid_checksum(self) -> None:
        self.assertFalse(ci.issn_valid("12345678"))

    def test_wrong_length(self) -> None:
        self.assertFalse(ci.issn_valid("1234567"))

    def test_letters_other_than_x(self) -> None:
        self.assertFalse(ci.issn_valid("1234567A"))


class IsbnTests(unittest.TestCase):
    def test_isbn10_with_x(self) -> None:
        self.assertTrue(ci.isbn10_valid("155404295X"))

    def test_isbn10_invalid(self) -> None:
        self.assertFalse(ci.isbn10_valid("1554042951"))

    def test_isbn13_valid(self) -> None:
        self.assertTrue(ci.isbn13_valid("9780262033848"))

    def test_isbn13_invalid(self) -> None:
        self.assertFalse(ci.isbn13_valid("9780262033849"))

    def test_real_mit_press_deep_learning_isbn(self) -> None:
        self.assertTrue(ci.isbn13_valid("9780262035613"))

    def test_real_kdd_2024_proceedings_isbn(self) -> None:
        self.assertTrue(ci.isbn13_valid("9798400704901"))


class ClassifyTests(unittest.TestCase):
    def test_classifies_by_length_after_clean(self) -> None:
        self.assertEqual(ci.clean("0924-1868"), "09241868")
        self.assertEqual(ci.clean("978-0-262-03384-8"), "9780262033848")


if __name__ == "__main__":
    unittest.main()
