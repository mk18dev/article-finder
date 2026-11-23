# Phase 6 — Legal Full-text Retrieval & Network Security Test Matrix

**Scope:** CLI-only open-access PDF retrieval. This matrix maps the Phase 6 acceptance gates to implementation and regression evidence. Network tests are deterministic and mocked; they prove local policy behavior, not the availability or policy of live providers.

| Gate | Required behavior | Implementation | Regression evidence |
|---|---|---|---|
| PH6-01 | HTTPS-only, valid TLS, port 443, no URL credentials | `scripts/http_util.py:validate_remote_url`, `_open` | `test_rejects_http`, `test_rejects_credentials`, `test_rejects_nonstandard_port`, `test_tls_context_requires_certificate_and_hostname_verification` |
| PH6-02 | Every DNS answer must be public; mixed public/private answers fail closed | `_resolve_public_addresses` | `test_blocks_private_dns_result`, `test_blocks_mixed_public_and_private_dns_results`, IPv4-mapped IPv6 tests |
| PH6-03 | Pin the validated destination IP at connect time; preserve original host for SNI; block rebinding | `_PinnedHTTPSConnection`, `_PinnedHTTPSHandler` | `test_pinned_connection_uses_validated_ip_and_original_tls_hostname`, `test_pinned_connection_falls_back_only_to_validated_addresses`, `test_dns_rebinding_between_preflight_and_connect_is_blocked` |
| PH6-04 | Revalidate each redirect; block HTTP, loopback, private and reserved destinations | `_SafeRedirectHandler` | `test_revalidates_redirect_destinations`, `test_https_redirect_to_private_dns_is_blocked` |
| PH6-05 | Ignore ambient proxy variables | `ProxyHandler({})` in `_open` | `test_ambient_proxy_environment_is_not_used` |
| PH6-06 | Bounded timeout, retry count, transient retry policy and 80 MiB cap | `TIMEOUT`, `RETRIES`, `fetch_response`, `_read_capped` | `test_fetch_response_retries_transient_timeout_and_keeps_metadata`, `test_fetch_response_retries_http_429_and_503`, `test_response_size_is_capped` |
| PH6-07 | Do not trust HTTP 200 or Content-Type; require PDF signature and minimum size; support HTML-to-PDF links | `looks_like_pdf`, `pdf_links`, `download_one` | `test_html_error_page_rejected`, `test_tiny_pdf_rejected`, `test_html_body_is_rejected_even_with_pdf_content_type`, resolver-chain tests |
| PH6-08 | Record provider, requested URL, final URL, UTC time and outcome | `RetrievalAttempt`, `fetch_response`, `report` | `test_download_records_provider_source_final_url_and_utc_time`, `test_report_records_retrieval_provenance` |
| PH6-09 | Keep PDF retrieval out of public Web/API routes | `scripts/web_api.py` action allowlist; CLI entrypoint only | API dispatch accepts only `discover_sources`, `verify_sources`, `check_draft`; no `fetch_pdf` import or action |
| PH6-10 | No unauthorized full-text providers or routes; require explicit OA metadata where available | Provider chain limited to OpenAlex OA locations, Unpaywall OA locations, Semantic Scholar open-access PDFs, CORE records marked open access and arXiv; licensed fallback routes only | `test_non_oa_openalex_location_is_not_a_candidate`, `test_unknown_openalex_oa_status_fails_closed`, `test_core_requires_explicit_open_access_and_download_url`, `test_unauthorized_full_text_hosts_are_not_linked_in_policy_docs` |

## Operational limits

- Provider lookups are best-effort. A provider outage does not convert a missing copy into an approval; it leaves the source without a downloadable OA candidate.
- A successful mocked test does not establish live provider uptime or a real publisher's access policy.
- Paywalled papers remain on legitimate routes: publisher/library access, author repository/preprint, or an author request.
- PDF signature and size checks establish a plausible PDF payload, not scholarly correctness, completeness, malware absence, or a valid/retracted article version.
- Retrieval remains a local CLI workflow; no arbitrary-URL or PDF download endpoint is exposed publicly.
