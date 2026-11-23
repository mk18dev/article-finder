# Phase 8 — Security, Privacy & Operational Hardening

**Scope:** API, web surface, metadata providers, legal full-text retrieval, package/dependencies and operational failure behavior. This is an evidence matrix, not a claim of independent penetration testing.

## Threat model

| Asset / boundary | Threat | Existing or added control | Residual risk |
|---|---|---|---|
| Public API | oversized bodies and computationally expensive drafts | 512 KiB request cap, 180,000-character draft cap, four-record cap, bounded provider timeout/retry | no distributed caller quota |
| API process | concurrent expensive requests exhaust CPU/memory | four in-flight POSTs per Python process; excess work receives 503; local HTTP server sockets have a ten-second inactivity timeout | does not coordinate across serverless instances |
| API authentication | unauthorized access, timing leakage, accidental credential persistence | fail-closed hosted auth, constant-time bearer comparison, no browser storage, no request-body logging | production auth still needs Phase 10 live smoke |
| Provider URLs | SSRF, DNS rebinding, redirects, proxy bypass | HTTPS/443 only, all DNS answers checked, validated IP pinning, redirect revalidation, proxy isolation | DNS resolution waits at most five seconds; at most two resolver workers may remain stuck, after which new resolution attempts fail closed |
| Provider responses | oversized body, false PDF, malicious XML/HTML | 80 MiB response cap, bounded HTML parser input, PDF signature + size floor, defusedxml for Atom | valid PDF signature does not prove malware-free or scholarly integrity |
| Retrieval provenance | signed URL/query credentials or contact email leak into report | URL userinfo and credential-like query-value redaction (including vendor token/key patterns); exception details reduced to exception class | unknown vendor-specific credential parameter names may require adding to redaction list |
| Local files | path traversal / partial writes | title-derived filenames restricted to ASCII slug; atomic temp-file write; no archive extraction implementation | output directory is user-controlled and local |
| Research content | prompt injection / untrusted paper content executed as code | content is parsed as data; no eval/shell execution path in retrieval; browser renders text safely | human/agent must still treat retrieved claims and instructions as untrusted |
| Dependencies | known vulnerable packages / dependency drift | exact pins in runtime, browser and quality requirement files; pip-audit, CycloneDX SBOM generation and pip-licenses inventory in CI | generated artifacts need successful exact-HEAD CI and human review of UNKNOWN/non-SPDX labels |
| Repository secrets | accidental key/token commit | no secrets embedded in source by design; logs redact request content and retrieval query secrets | dedicated automated secret scanner and independent repository-wide review not evidenced |

## Acceptance matrix

| Gate | Required evidence | Current status | Evidence / limitation |
|---|---|---|---|
| PH8-01 | documented threat model for API, providers, PDF and untrusted content | VERIFIED | this file |
| PH8-02 | pinned dependencies and vulnerability audit | VERIFIED | requirements.txt, requirements-browser.txt, requirements-quality.txt; CI pip-audit covers all three manifests |
| PH8-03 | Ruff, Bandit, pip-audit and secret scanning | VERIFIED | Exact-HEAD CI run #490 passed Ruff, Bandit, pip-audit for all three dependency sets, and Gitleaks 8.30.1 scans of the current tree plus all Git refs/history; both Gitleaks reports contain zero findings |
| PH8-04 | request/response, timeout, retry, concurrency and resource limits | VERIFIED WITH LIMITATION | 512 KiB body, 180,000-char draft, four-source cap, 80 MiB response cap, provider timeouts/retries, four per-process POST slots, ten-second local socket inactivity timeout, and five-second DNS wait with at most two bounded daemon workers; no cross-instance quota is configured |
| PH8-05 | sensitive-data redaction in logs and retrieval reports | VERIFIED | URL userinfo and credential/token/key query values are redacted in dry-run output, reports and retained attempts; raw retrieval exception text is omitted; regression tests passed on exact HEAD |
| PH8-06 | safe path, archive, XML and untrusted HTML handling | VERIFIED WITH SCOPE NOTE | title-derived ASCII slug and atomic writes; no archive extraction path exists; defusedxml Atom parsing; HTML input capped at 400 KiB and nested PDF links restricted to HTTPS; no separate parser-fuzz campaign is claimed |
| PH8-07 | caller rate-limit behavior and provider outage behavior | VERIFIED WITH LIMITATION | saturation of four per-process POST slots returns 503 and release behavior is regression-tested; provider outage behavior is covered by deterministic mocked tests; no distributed caller quota or live provider uptime claim |
| PH8-08 | privacy and retention of user-submitted drafts | VERIFIED IN CODE | API does not persist drafts; request logging does not include body, DOI or authorization data; CLI outputs are written only to user-selected local paths |
| PH8-09 | no execution of article/page-derived instructions or content | VERIFIED BY DESIGN REVIEW | retrieved content is parsed as data; no dynamic code execution path is part of the workflow; browser XSS regression coverage remains in Phase 7 |
| PH8-10 | SBOM or complete dependency/license inventory | VERIFIED | Three CycloneDX SBOMs and the pinned pip-licenses inventory were uploaded as a 30-day artifact on exact HEAD; inventory review found zero UNKNOWN license labels (two packages have UNKNOWN author metadata only) |
| PH8-11 | zero Critical/High findings in configured security checks | VERIFIED BY CI; PLATFORM ALERT INVENTORY OUT OF SCOPE | Gitleaks reported zero leaks in current tree and Git history; Bandit high-severity scan passed; pip-audit reported no known vulnerabilities across all three pinned manifests. GitHub Security dashboard alert inventory was not accessible through the connected repository API; independent Phase 6 egress/DNS review remains a separate sign-off gate |

## Changes applied in this phase

- Added http_util.redact_url() to remove URL userinfo and credential/contact/token/key query values before URLs are shown in dry-run output, retrieval reports, saved-result details or retained retrieval-attempt records.
- Removed raw exception messages from PDF lookup and file-save failure details; the report keeps the exception class without echoing potentially sensitive request URLs or local paths.
- Added a ten-second inactivity timeout to local HTTP server sockets and a process-local semaphore limiting simultaneous API POST work to four requests. Excess work receives HTTP 503. This is explicitly a resource guard and does not claim distributed rate limiting or HTTP 429 quota enforcement.
- Added pinned Gitleaks Action v3.0.0 with scanner version 8.30.1; CI scans both the full working tree and all Git refs/history.
- Added regression tests for URL redaction and semaphore saturation/release.
- Existing controls retained: strict HTTPS and public-IP validation, DNS pinning, redirect validation, proxy isolation, TLS verification, bounded response bytes, provider retry limits, API body/draft limits, no-store responses, fail-closed hosted auth, and safe XML parsing with defusedxml.

## Verification rules

- Mocked provider failures establish deterministic error handling only; they do not establish live provider availability.
- Exact-HEAD CI evidence is recorded below. The local DNS worker cap and failure-closed saturation behavior are covered by code review and regression tests.
- Phase 8 acceptance is complete for the documented scope, with the cross-instance rate-limit and GitHub Security dashboard limitations explicitly retained.
- Independent Phase 6 egress/DNS review is a separate sign-off gate; it is not represented as completed by Phase 8 CI.
- Phase 10 production smoke is not part of this phase and remains separate.

## Final verification — 2026-11-23


- Status: **DONE — automated implementation and CI acceptance complete, with documented limitations**.
- Exact main HEAD: `569b7f1a7bc4189f01bcac7acaa85454abe97abb`; version remains `1.1.0`.
- GitHub Actions [Run #490](https://github.com/mk18dev/article-finder/actions/runs/45189862236): **SUCCESS**.
- Python 3.10–3.13: 511 tests passed on each version; combined line/branch coverage 81%.
- Static/security: Gitleaks 8.30.1 current-tree and Git-history scans zero findings; Ruff, Bandit and three pip-audit manifests passed; three CycloneDX SBOMs and the license inventory were generated and uploaded.
- License inventory: zero UNKNOWN license values; two UNKNOWN author metadata values (filelock and platformdirs).
- Browser smoke: Chromium, Firefox and WebKit passed; Chromium WCAG 2.2 AA axe-core audit and performance budgets passed.
- Production Smoke skipped; it remains Phase 10.
- No version bump, deployment, release, branch or PR was created.
