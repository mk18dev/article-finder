# Phase 6 — Legal Full-text Retrieval & Network Security Test Matrix

**Scope:** CLI-only open-access PDF retrieval. This matrix maps the Phase 6 acceptance gates to implementation and regression evidence. Network tests are deterministic and mocked; they prove local policy behavior, not the availability or policy of live providers. DNS resolution is bounded to a five-second caller wait with at most two stuck daemon workers per process; saturation fails closed.

**Formal status:** DONE — implementation and exact-HEAD CI verified; the independent egress/DNS review gate is closed by explicit project-owner risk acceptance (not by independent review).

| Gate | Required behavior | Implementation | Regression evidence |
|---|---|---|---|
| PH6-01 | HTTPS-only, valid TLS, port 443, no URL credentials | `scripts/http_util.py:validate_remote_url`, `_open` | `test_rejects_http`, `test_rejects_credentials`, `test_rejects_nonstandard_port`, `test_tls_context_requires_certificate_and_hostname_verification` |
| PH6-02 | Every DNS answer must be globally reachable; mixed public/private, reserved, multicast and ORCHIDv2 special-purpose answers fail closed | `_resolve_public_addresses` | `test_blocks_private_dns_result`, `test_blocks_mixed_public_and_private_dns_results`, `test_blocks_reserved_ipv6_nat64_result`, `test_blocks_ipv6_multicast_even_when_global`, `test_blocks_orchidv2_ipv6_identifier_range`, IPv4-mapped IPv6 tests |
| PH6-03 | Pin the validated destination IP at connect time; preserve original host for SNI; block rebinding | `_PinnedHTTPSConnection`, `_PinnedHTTPSHandler` | `test_pinned_connection_uses_validated_ip_and_original_tls_hostname`, `test_pinned_connection_falls_back_only_to_validated_addresses`, `test_dns_rebinding_between_preflight_and_connect_is_blocked` |
| PH6-04 | Revalidate each redirect; block HTTP, loopback, private and reserved destinations | `_SafeRedirectHandler` | `test_revalidates_redirect_destinations`, `test_https_redirect_to_private_dns_is_blocked` |
| PH6-05 | Ignore ambient proxy variables | `ProxyHandler({})` in `_open` | `test_ambient_proxy_environment_is_not_used` |
| PH6-06 | Bounded DNS wait, network timeout, retry count, transient retry policy and 80 MiB cap | `DNS_TIMEOUT=5`, two-slot bounded resolver workers, `TIMEOUT`, `RETRIES`, `fetch_response`, `_read_capped` | `test_fetch_response_retries_transient_timeout_and_keeps_metadata`, `test_fetch_response_retries_http_429_and_503`, `test_response_size_is_capped` |
| PH6-07 | Do not trust HTTP 200 or Content-Type; require PDF signature and minimum size; support HTML-to-PDF links | `looks_like_pdf`, `pdf_links`, `download_one` | `test_html_error_page_rejected`, `test_tiny_pdf_rejected`, `test_html_body_is_rejected_even_with_pdf_content_type`, resolver-chain tests |
| PH6-08 | Record provider, requested URL, final URL, UTC time and outcome | `RetrievalAttempt`, `fetch_response`, `report` | `test_download_records_provider_source_final_url_and_utc_time`, `test_report_records_retrieval_provenance` |
| PH6-09 | Keep PDF retrieval out of public Web/API routes | `scripts/web_api.py` action allowlist; CLI entrypoint only | API dispatch accepts only `discover_sources`, `verify_sources`, `check_draft`; no `fetch_pdf` import or action; `test_fetch_pdf_action_is_not_exposed` |
| PH6-10 | No unauthorized full-text providers or routes; require explicit OA metadata where available | Provider chain limited to OpenAlex OA locations, Unpaywall OA locations, Semantic Scholar open-access PDFs, CORE records marked open access and arXiv; licensed fallback routes only | `test_non_oa_openalex_location_is_not_a_candidate`, `test_unknown_openalex_oa_status_fails_closed`, `test_core_requires_explicit_open_access_and_download_url`, `test_unauthorized_full_text_hosts_are_not_linked_in_policy_docs` |

## Operational limits

- Provider lookups are best-effort. A provider outage does not convert a missing copy into an approval; it leaves the source without a downloadable OA candidate.
- A successful mocked test does not establish live provider uptime or a real publisher's access policy.
- Paywalled papers remain on legitimate routes: publisher/library access, author repository/preprint, or an author request.
- PDF signature and size checks establish a plausible PDF payload, not scholarly correctness, completeness, malware absence, or a valid/retracted article version.
- Retrieval remains a local CLI workflow; no arbitrary-URL or PDF download endpoint is exposed publicly.


## Final CI verification — 2026-11-23

- Repository: `mk18dev/article-finder`; branch: `main`; target version: `1.1.0`.
- Exact HEAD: `569b7f1a7bc4189f01bcac7acaa85454abe97abb`.
- Exact-HEAD workflow: [Run #490](https://github.com/mk18dev/article-finder/actions/runs/45189862236) — SUCCESS.
- Python 3.10, 3.11, 3.12 and 3.13 each passed 511 tests; combined line/branch coverage: 81%.
- Static quality/security workflow passed: Gitleaks 8.30.1 current-tree and all-ref history scans (zero findings), Ruff, Bandit, and pip-audit for runtime/browser/quality manifests (no known vulnerabilities).
- Chromium, Firefox and WebKit browser smoke passed. Chromium axe-core WCAG 2.2 AA audit and performance budgets passed.
- Production Smoke was skipped by design; it remains a Phase 10 post-deployment gate.
- Code and CI acceptance are complete. The independent egress/DNS review was not performed; on 2026-11-23 the project owner explicitly accepted this residual risk and waived that review as a Phase 6 closure gate. This is an owner risk-acceptance decision, not an independent security sign-off. No live provider uptime or production deployment is claimed.


## Formal closure — owner risk acceptance (2026-11-23)

- **Decision:** The project owner explicitly approved closing Phase 6 without an independent network-egress/DNS reviewer.
- **Disposition:** The independent-review acceptance gate is waived by the owner. Phase 6 is formally **DONE — RISK ACCEPTED**, based on completed implementation and exact-HEAD automated CI evidence.
- **What this does not mean:** No independent external review, live network-egress assessment, live DNS-rebinding exercise, provider uptime/access-policy test, or Production Smoke is claimed. Deterministic mocked tests and CI do not prove those external properties.
- **Residual risk retained:** A defect in network-egress/DNS controls may remain undiscovered by the automated test suite. The owner accepts that residual risk for this project milestone.
- **Evidence baseline:** main HEAD `3b0170d90a111bc5f6024379813249f76a36553b`; GitHub Actions [Run #492](https://github.com/mk18dev/article-finder/actions/runs/45190359893) SUCCESS; 511 tests passed on each of Python 3.10–3.13; 81% combined line/branch coverage.
- **Project constraints preserved:** branch `main`; target version `1.1.0`; no deployment, release, tag, version bump, branch, or PR created as part of this risk-acceptance closure.
