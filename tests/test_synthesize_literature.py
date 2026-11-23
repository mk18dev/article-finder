import unittest

from scripts.synthesize_literature import render_markdown, synthesize, validate_bundle


def evidence(note="Reviewed source excerpt and relevant section"):
    return {"reviewed": True, "url": "https://publisher.example/paper", "note": note, "locator": "Results, p. 4"}


def bundle():
    return {
        "review_title": "Evidence on topic X",
        "studies": [
            {
                "study_id": "S1",
                "title": "Study One",
                "doi": "10.1234/one",
                "year": 2024,
                "theme": "Theme A",
                "study_design": "experiment",
                "population": "Adults",
                "method": "Randomized design",
                "outcome": "Outcome X",
                "direction": "positive",
                "finding_summary": "Reviewer-extracted finding one",
                "limitations": ["Small sample"],
                "review_status": "full_text",
                "extraction_evidence": evidence(),
                "quality_appraisal": {"rating": "moderate", "evidence": evidence()},
            },
            {
                "study_id": "S2",
                "title": "Study Two",
                "doi": "10.1234/two",
                "year": 2023,
                "theme": "Theme A",
                "study_design": "observational",
                "population": "Adults",
                "method": "Cohort design",
                "outcome": "Outcome X",
                "direction": "negative",
                "finding_summary": "Reviewer-extracted finding two",
                "limitations": ["Short follow-up"],
                "review_status": "abstract_only",
            },
        ],
        "claims": [
            {
                "claim_text": "The evidence is mixed for outcome X.",
                "study_ids": ["S1", "S2"],
                "source_evidence": [
                    {"study_id": "S1", "reviewed": True, "url": "https://publisher.example/paper",
                     "quote": "The study reports an observed improvement.", "locator": "Results, p. 4"}
                ],
            }
        ],
    }


class LiteratureSynthesisTests(unittest.TestCase):
    def test_theme_synthesis_preserves_conflicting_directions(self):
        result = synthesize(bundle())
        theme = result["themes"][0]
        self.assertTrue(theme["conflict_flag"])
        self.assertEqual(theme["direction_counts"], {"negative": 1, "positive": 1})
        self.assertEqual(theme["study_count"], 2)

    def test_claim_requires_excerpt_evidence_for_every_linked_study(self):
        result = synthesize(bundle())
        self.assertEqual(result["claim_map"][0]["status"], "pending")
        self.assertEqual(result["claim_map"][0]["evidence_linked_study_ids"], ["S1"])

    def test_full_text_status_requires_reviewed_source_evidence(self):
        data = bundle()
        data["studies"][0]["extraction_evidence"] = None
        self.assertTrue(any("full-text extraction requires" in error for error in validate_bundle(data)))

    def test_quality_rating_requires_evidence(self):
        data = bundle()
        data["studies"][0]["quality_appraisal"]["evidence"] = None
        self.assertTrue(any("quality rating requires reviewed evidence" in error for error in validate_bundle(data)))

    def test_unknown_claim_study_is_rejected(self):
        data = bundle()
        data["claims"][0]["study_ids"] = ["UNKNOWN"]
        self.assertTrue(any("unknown study IDs" in error for error in validate_bundle(data)))

    def test_markdown_reports_limitations_and_flags(self):
        output = render_markdown(synthesize(bundle()))
        self.assertIn("conflicting or mixed reported directions", output)
        self.assertIn("a DOI alone is not claim support", output)

    def test_duplicate_study_ids_are_rejected(self):
        data = bundle()
        data["studies"][1]["study_id"] = "S1"
        self.assertTrue(any("duplicate study_id" in error for error in validate_bundle(data)))

    def test_claim_evidence_requires_valid_https_origin_and_locator(self):
        for url, locator in (
            ("https://", "Results, p. 4"),
            ("http://publisher.example/paper", "Results, p. 4"),
            ("https://user@publisher.example/paper", "Results, p. 4"),
            ("https://publisher.example:444/paper", "Results, p. 4"),
            ("https://publisher.example/paper", ""),
        ):
            with self.subTest(url=url, locator=locator):
                data = bundle()
                data["claims"][0]["source_evidence"][0]["url"] = url
                data["claims"][0]["source_evidence"][0]["locator"] = locator
                self.assertTrue(any("reviewed HTTPS evidence" in error for error in validate_bundle(data)))

    def test_claim_evidence_must_be_unique_and_linked(self):
        data = bundle()
        data["claims"][0]["source_evidence"].append(dict(
            data["claims"][0]["source_evidence"][0], study_id="UNKNOWN"
        ))
        self.assertTrue(any("study_id must identify a study linked" in error for error in validate_bundle(data)))

        data = bundle()
        data["claims"][0]["source_evidence"].append(dict(data["claims"][0]["source_evidence"][0]))
        self.assertTrue(any("duplicate source evidence" in error for error in validate_bundle(data)))

    def test_claim_study_ids_must_be_unique(self):
        data = bundle()
        data["claims"][0]["study_ids"] = ["S1", "S1"]
        self.assertTrue(any("study_ids must not contain duplicates" in error for error in validate_bundle(data)))


if __name__ == "__main__":
    unittest.main()
