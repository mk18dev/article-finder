# Phase 2 — Source Verification Engine test acceptance matrix

**Scope:** Article Finder 1.1.0, Mode 1, S1–S11.  
**Implementation:** `scripts/verify_source.py` and `scripts/tier_policy.py`.  
**Regression suite:** `tests/test_verify_source.py`, `tests/test_tier_policy.py`.

The matrix distinguishes:
- **Positive:** valid evidence produces the intended pass.
- **Negative:** explicit invalid or failed input is rejected, or remains non-approved where the gate is evidence-only.
- **Incomplete:** missing, malformed, stale, or unreviewed evidence stays pending.
- **Conflict:** two claims disagree; the deterministic source-of-truth rule wins or the result remains pending.

| Gate | Positive | Negative | Incomplete | Conflict / contradictory input |
|---|---|---|---|---|
| S1 Area | `test_s1_s2_s10_need_review_records` | `test_explicit_negative_judgements_reject_s1_s2_and_s10` | `test_missing_judgement_is_pending_even_when_label_exists`; `test_judgement_requires_url_and_note` | `test_positive_judgement_without_valid_review_is_pending` |
| S2 Subject | `test_s1_s2_s10_need_review_records` | `test_explicit_negative_judgements_reject_s1_s2_and_s10` | `test_missing_judgement_is_pending_even_when_label_exists` | `test_positive_judgement_without_valid_review_is_pending` |
| S3 Keyword | `test_search_evidence_allows_keyword_gate` | `test_invalid_keyword_pair_fails` | `test_missing_search_execution_is_pending`; `test_search_timestamp_must_include_timezone` | `test_search_doi_must_match_record`; `test_search_query_must_match_pair` |
| S4 Source Type | `test_supported_journal_type_passes_s4` | `test_unknown_crossref_type_is_rejected_at_s4`; `test_bachelors_thesis_is_rejected` | `test_thesis_without_degree_is_pending`; `test_thesis_degree_without_evidence_is_pending` | `test_crossref_book_chapter_overrides_conflicting_degree_claim` |
| S5 Publisher/Venue | `test_trusted_publisher_passes` | `test_book_s5_explicit_negative_review_fails` | `test_unknown_publisher_is_pending_not_failed`; `test_missing_publisher_is_pending` | `test_manual_s5_disagreement_cannot_override_crossref_publisher` |
| S6 Credibility | `test_verified_index_with_clear_blacklist_passes` | `test_blacklist_hit_hard_rejects_even_when_tier_is_high` | `test_missing_blacklist_checks_is_pending`; `test_stale_official_blacklist_list_is_pending` | `test_verified_blacklist_hit_is_not_masked_by_incomplete_other_checks`; title/year mismatch tests |
| S7 Identifiers | `test_valid_journal_issn_and_metadata_pass`; `test_book_needs_primary_book_and_valid_isbn` | `test_invalid_issn_fails`; `test_book_invalid_isbn_checksum_is_rejected_by_source_verification` | `test_missing_issn_is_pending`; `test_journal_missing_issue_is_pending` | `test_primary_book_false_overrides_valid_isbn_and_book_evidence` |
| S8 Specialization & Year | `test_recent_application_passes` | `test_old_application_fails`; `test_future_publication_year_fails` | `test_specialization_missing_is_pending`; `test_specialization_boolean_without_evidence_is_pending` | `test_old_application_fails_even_with_positive_specialization_evidence` |
| S9 Tier | `test_verified_tier_is_preserved`; `test_q1_quartile_computes_tier_a` | `test_declared_tier_mismatch_is_rejected` | `test_missing_declared_tier_stays_pending`; `test_tier_needs_reviewer_evidence` | `test_declared_tier_mismatch_is_rejected`; `test_unofficial_tier_evidence_host_keeps_tier_pending` |
| S10 Category | `test_s1_s2_s10_need_review_records` | `test_explicit_negative_judgements_reject_s1_s2_and_s10` | `test_missing_judgement_is_pending_even_when_label_exists` | `test_unknown_category_overrides_positive_s10_judgement` |
| S11 Extraction | `test_article_requires_abstract_intro_and_conclusion`; `test_methodology_requires_full_text` | `test_unreviewed_required_section_keeps_s11_pending` (not approved) | `test_abstract_alone_does_not_pass_s11`; `test_missing_reading_record_is_pending_even_with_abstract_metadata` | `test_unreviewed_required_section_keeps_s11_pending` |

## S6 source-type coverage

- Journal: three independent official ISSN blacklist checks plus at least one verified, title-matched, year-covered index record.
- Conference: Scopus, Web of Science/WoS, ISC or DBLP; DOAJ is not accepted as a proceedings index.
- Thesis: Irandoc or a verified institutional repository.
- Book: Google Books or a supported Amazon record, non-negative citation count and publisher verification.

## Interpretation limits

A passing test proves the code enforces the declared evidence contract; it does not prove that a reviewer actually inspected an external registry page. The reviewer attestation remains human-controlled. Production provider verification and the manual production smoke are separate release gates, not implied by this matrix.
