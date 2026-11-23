# Phase 8 — Security, Privacy & Operational Hardening

**Scope:** API, web surface, metadata providers, legal full-text retrieval, package/dependencies and operational failure behavior. This is an evidence matrix, not a claim of independent penetration testing.

## Threat model

| Asset / boundary | Threat | Existing or added control | Residual risk |
|---|---|---|---|
| Public API | oversized bodies and computationally expensive drafts | 512 KiB request cap, 180,000-character draft cap, four-record cap, bounded provider timeout/retry | no distributed caller quota |
| API process | concurrent expensive requests exhaust CPU/memory | four in-flight POSTs per Python process; excess work receives 503 | does not coordinate across serverless instances |
| API authentication | unauthorized access, timing leakage, accidental credential persistence | fail-closed hosted auth, constant-time bearer comparison, no browser storage, no request-body logging | production auth still needs Phase 10 live smoke |
| Provider URLs | SSRF, DNS rebinding, redirects, proxy bypass | HTTPS/443 only, all DNS answers checked, validated IP pinning, redirect revalidation, proxy isolation | DNS resolution waits at most five seconds; at most two resolver workers may remain stuck, after which new resolution attempts fail closed |
| Provider responses | oversized body, false PDF, malicious XML/HTML | 80 MiB response cap, bounded HTML parser input, PDF signature + size floor, defusedxml for Atom | valid PDF signature does not prove malware-free or scholarly integrity |
| Retrieval provenance | signed URL/query credentials or contact email leak into report | URL userinfo and credential-like query-value redaction (including vendor token/key patterns); exception details reduced to exception class | unknown vendor-specific credential parameter names may require adding to redaction list |
| Local files | path traversal / partial writes | title-derived filenames restricted to ASCII slug; atomic temp-file write; no archive extraction implementation | output directory is user-controlled and local |
| Research content | prompt injection / untrusted paper content executed as code | content is parsed as data; no eval/shell execution path in retrieval; browser renders text safely | human/agent must still treat retrieved claims and instructions as untrusted |
| Dependencies | known vulnerable packages / dependency drift | exact pins in runtime, browser and quality requirement files; pip-audit in CI | no automated license inventory or generated SBOM in current workflow |
| Repository secrets | accidental key/token commit | no secrets embedded in source by design; logs redact request content and retrieval query secrets | dedicated automated secret scanner and independent repository-wide review not evidenced |

## Acceptance matrix

| Gate | Required evidence | Current status | Evidence / limitation |
|---|---|---|---|
| PH8-01 | documented threat model for API, providers, PDF and untrusted content | VERIFIED | this file |
| PH8-02 | pinned dependencies and vulnerability audit | VERIFIED | requirements.txt, requirements-browser.txt, requirements-quality.txt; CI pip-audit covers all three manifests |
| PH8-03 | Ruff, Bandit, pip-audit and secret scanning | CI PENDING | Ruff/Bandit/pip-audit plus pinned Gitleaks v2.3.9 with full-history checkout are configured; exact-SHA CI result is required before verification |
| PH8-04 | request/response, timeout, retry, concurrency and resource limits | PARTIAL | request/draft/count/body/response limits, four per-process POST slots, and five-second DNS wait with at most two bounded daemon workers; no distributed rate limiter |
| PH8-05 | sensitive-data redaction in logs and retrieval reports | VERIFIED IN CODE; CI PENDING | http_util.redact_url; retrieval errors omit exception text; regression tests cover common and vendor-specific token keys plus URL userinfo |
| PH8-06 | safe path, archive, XML and untrusted HTML handling | PARTIAL | no archive extraction path exists; title slug + atomic writes; defusedxml is pinned; HTML input is bounded and PDF links are HTTPS-filtered; further parser fuzzing not evidenced |
| PH8-07 | caller rate-limit behavior and provider outage behavior | PARTIAL | process capacity overflow returns 503; this is not a caller quota; provider outage is covered by deterministic mocked tests, not live uptime evidence |
| PH8-08 | privacy and retention of user-submitted drafts | VERIFIED IN CODE | API does not persist drafts; request logging does not include body, DOI or authorization data; CLI outputs are written only to user-selected local paths |
| PH8-09 | no execution of article/page-derived instructions or content | VERIFIED BY DESIGN REVIEW | retrieved content is parsed as data; no dynamic code execution path is part of the workflow; browser XSS regression coverage remains in Phase 7 |
| PH8-10 | SBOM or complete dependency/license inventory | CI PENDING / PARTIAL | three CycloneDX SBOMs (runtime, browser, quality) plus a pip-licenses 5.5.5 mixed-metadata license inventory are generated and uploaded as a 30-day CI artifact; CI verification and human review of UNKNOWN/non-SPDX labels remain required |
| PH8-11 | zero open Critical/High findings and independent security review | OPEN | no independent reviewer sign-off or dedicated secret-scan evidence is available; Phase 6 DNS/egress review remains a dependency |

## Changes applied in this phase

- Added http_util.redact_url() to remove URL userinfo and credential/contact/token/key query values before URLs are shown in dry-run output, retrieval reports or saved-result details.
- Removed raw exception messages from PDF lookup and file-save failure details; the report keeps the exception class without echoing potentially sensitive request URLs or local paths.
- Added a process-local semaphore limiting simultaneous API POST work to four requests. Excess work receives HTTP 503. This is explicitly a resource guard and does not claim distributed rate limiting or HTTP 429 quota enforcement.
- Added regression tests for URL redaction and semaphore saturation/release.
- Existing controls retained: strict HTTPS and public-IP validation, DNS pinning, redirect validation, proxy isolation, TLS verification, bounded response bytes, provider retry limits, API body/draft limits, no-store responses, fail-closed hosted auth, and safe XML parsing with defusedxml.

## Verification rules

- Mocked provider failures establish deterministic error handling only; they do not establish live provider availability.
- A green CI run on the exact main SHA is required before this matrix can be treated as verified.
- Phase 8 must remain IN PROGRESS / BLOCKED FOR ACCEPTANCE until Gitleaks, SBOM and license-inventory steps pass on the exact HEAD, the bounded DNS-worker failure mode is reviewed, and independent security review has evidence.
- Phase 10 production smoke is not part of this phase and remains separate.