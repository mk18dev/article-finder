"""Contract test for the source-verification to tier-policy adapter."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts import verify_source


class TierAdapterIntegrationTests(unittest.TestCase):
    def test_book_adapter_calls_supported_tier_policy_contract(self):
        work = SimpleNamespace(kind="book", publisher="")
        ok, computed, reason = verify_source.tier_verified(work, {}, {"S6": None, "S7": None})
        self.assertIsNone(ok)
        self.assertIsNone(computed)
        self.assertIn("Primary-book", reason)


if __name__ == "__main__":
    unittest.main()


class TimestampTypeGuardTests(unittest.TestCase):
    def test_non_string_review_timestamps_fail_closed(self):
        for value in (None, 0, [], {}, True):
            with self.subTest(value=value):
                self.assertFalse(verify_source._valid_search_timestamp(value))

