import unittest

from scripts.citation_crosswalk import audit, audit_apa, audit_ieee


class CitationCrosswalkTests(unittest.TestCase):
    def test_ieee_ranges_match_bibliography(self):
        text = "Prior studies support this claim [1], [2, 4-5]."
        refs = [{"number": n, "doi": f"10.1234/{n}"} for n in (1, 2, 4, 5)]
        result = audit_ieee(text, refs)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["unique_in_text_numbers"], [1, 2, 4, 5])

    def test_ieee_missing_bibliography_number_is_reported(self):
        result = audit_ieee("Evidence [1, 3].", [{"number": 1}])
        self.assertEqual(result["missing_bibliography_numbers"], [3])
        self.assertEqual(result["status"], "review")

    def test_ieee_uncited_reference_is_reported(self):
        result = audit_ieee("Evidence [1].", [{"number": 1}, {"number": 2}])
        self.assertEqual(result["uncited_bibliography_numbers"], [2])

    def test_ieee_unsafe_range_is_reported(self):
        result = audit_ieee("Evidence [1-999].", [{"number": 1}])
        self.assertTrue(result["malformed_citations"])

    def test_ieee_duplicate_doi_is_reported(self):
        refs = [{"number": 1, "doi": "10.1234/a"}, {"number": 2, "doi": "https://doi.org/10.1234/A"}]
        result = audit_ieee("Evidence [1, 2].", refs)
        self.assertEqual(len(result["duplicate_dois"]), 1)
        self.assertEqual(result["status"], "review")

    def test_apa_parenthetical_and_narrative_citations_match(self):
        text = "Prior work (Smith, 2020; Jones et al., 2021) and Smith (2020) support this."
        refs = [
            {"first_author": "Smith, J.", "year": 2020, "doi": "10.1234/smith"},
            {"authors": ["Jones, K.", "Lee, A."], "year": 2021, "doi": "10.1234/jones"},
        ]
        result = audit_apa(text, refs)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["in_text_citation_count"], 3)
        self.assertEqual(result["matched_reference_indices"], [1, 2])

    def test_apa_unmatched_in_text_citation_is_reported(self):
        result = audit_apa("Prior work (Unknown, 2022).", [{"first_author": "Smith", "year": 2020}])
        self.assertEqual(len(result["unmatched_in_text_citations"]), 1)
        self.assertEqual(result["status"], "review")

    def test_apa_uncited_reference_is_reported(self):
        result = audit_apa("Prior work (Smith, 2020).", [
            {"first_author": "Smith", "year": 2020},
            {"first_author": "Jones", "year": 2021},
        ])
        self.assertEqual(result["uncited_reference_indices"], [2])

    def test_apa_duplicate_author_year_is_reported(self):
        refs = [
            {"first_author": "Smith", "year": 2020, "doi": "10.1234/a"},
            {"first_author": "Smith", "year": 2020, "doi": "10.1234/b"},
        ]
        result = audit_apa("Prior work (Smith, 2020).", refs)
        self.assertEqual(len(result["duplicate_author_year_keys"]), 1)
        self.assertEqual(result["status"], "review")


    def test_ieee_reference_section_is_not_counted_as_in_text_citation(self):
        text = "No citations in the body.\n\nReferences\n[1] Smith, 2020."
        result = audit_ieee(text, [{"number": 1}])
        self.assertEqual(result["uncited_bibliography_numbers"], [1])
        self.assertEqual(result["status"], "review")

    def test_apa_reference_section_is_not_counted_as_in_text_citation(self):
        text = "No citations in the body.\n\nReferences\nSmith, J. (2020). Example title."
        result = audit_apa(text, [{"first_author": "Smith, J.", "year": 2020}])
        self.assertEqual(result["uncited_reference_indices"], [1])
        self.assertEqual(result["status"], "review")

    def test_malformed_ieee_bracket_is_reported(self):
        result = audit_ieee("Evidence [1;2].", [{"number": 1}, {"number": 2}])
        self.assertTrue(result["malformed_citations"])
        self.assertEqual(result["status"], "review")

    def test_malformed_apa_year_parenthetical_is_reported(self):
        result = audit_apa("The threshold was set (2020, p. 4).", [{"first_author": "Smith", "year": 2020}])
        self.assertTrue(result["malformed_citations"])
        self.assertEqual(result["status"], "review")

    def test_audit_accepts_wrapped_citations_input(self):
        result = audit("Citation [1].", {"citations": [{"number": 1}]}, "IEEE")
        self.assertEqual(result["status"], "pass")

    def test_invalid_reference_document_is_rejected(self):
        with self.assertRaises(ValueError):
            audit("Citation [1].", {"items": []}, "IEEE")

    def test_unsupported_style_is_rejected(self):
        with self.assertRaises(ValueError):
            audit("text", [], "Chicago")


    def test_persian_author_and_solar_year_are_matched(self):
        text = "پژوهش پیشین (رضایی، ۱۴۰۲) این نتیجه را تأیید می‌کند."
        refs = [{"first_author": "رضایی، علی", "year": "۱۴۰۲"}]
        result = audit_apa(text, refs)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["matched_reference_indices"], [1])

    def test_persian_ieee_digits_are_normalized(self):
        result = audit_ieee("شواهد پیشین [۱، ۲] را ببینید.", [{"number": 1}, {"number": 2}])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["unique_in_text_numbers"], [1, 2])

    def test_arabic_and_persian_author_variants_normalize_equally(self):
        text = "پژوهش پیشین (رضايي، ۱۴۰۲)."
        refs = [{"first_author": "رضایی، علی", "year": 1402}]
        result = audit_apa(text, refs)
        self.assertEqual(result["status"], "pass")


if __name__ == "__main__":
    unittest.main()
