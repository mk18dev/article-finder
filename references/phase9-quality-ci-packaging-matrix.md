# Phase 9 — Quality Engineering, CI & Reproducible Packaging

**Scope:** `mk18dev/article-finder`, branch `main`, target version `1.1.0`.
**Acceptance rule:** every required job must pass on the same commit SHA. Production Smoke is an intentionally separate manual Phase 10 gate.

| Gate | Requirement | Enforcement / evidence |
|---|---|---|
| PH9-01 | Python compatibility | Required test matrix on Python 3.10, 3.11, 3.12 and 3.13 |
| PH9-02 | Test coverage | Unit, integration, contract and regression suite on every Python version; branch coverage must remain at least 80% |
| PH9-03 | Offline core suite | Main test suite uses deterministic fixtures, mocks and local loopback servers; no live provider call is an acceptance dependency |
| PH9-04 | Browser reproducibility | Playwright pinned in requirements-browser.txt; Chromium, Firefox and WebKit smoke jobs required |
| PH9-05 | Static/security | Pinned Ruff, Bandit, pip-audit and Gitleaks; SBOM and license inventory generated |
| PH9-06 | Artifact provenance | Test/coverage, browser, security and package artifacts are retained for 30 days and named with the exact commit SHA (Python/browser matrix dimension where relevant) |
| PH9-07 | Deterministic packaging | Two clean builds in the same pinned Python 3.12 environment must be byte-for-byte identical |
| PH9-08 | Archive integrity | Unique relative paths only; regular files only; normalized permissions; no symlinks, traversal, PDFs, bytecode, build output or build tooling |
| PH9-09 | Consumer installation | Archive is validated and extracted into a clean consumer skills directory; the installed copy is compiled and its packaged test suite is executed |
| PH9-10 | Workflow safety | Push-to-main CI required; Production Smoke remains manual, key-protected and separate; no continue-on-error or hidden required-test skips |
| PH9-11 | SHA-bound acceptance | All required jobs and artifacts identify the same immutable commit SHA; failed or cancelled runs do not count as acceptance |

## Threshold decision

The master plan requires an enforced coverage threshold but does not set its numeric value. The current pre-change exact-SHA baseline reports 81% combined line/branch coverage. This phase sets a **minimum 80%** threshold as a non-regression floor; it is not a claim that 80% coverage proves correctness. Raising the threshold requires a later evidence-backed change.

## Known limits

- The workflow's normal test suite uses mocked providers and local loopback HTTP fixtures. Live provider availability/access policy is not tested by this suite.
- Production Smoke is deliberately skipped on push events and is not a Phase 9 blocker; it remains a manual Phase 10 post-deployment gate.
- This workflow does not configure branch protection/rulesets. Repository policy changes are outside the current phase and require separate authorization.
