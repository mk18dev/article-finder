---
name: article-finder-ci-cd-release
description: Gate Article Finder releases on the complete test matrix, package integrity, version consistency, and explicit production authorization.
---

# CI/CD and Release Skill — Article Finder 1.1.0

Use `.github/workflows/tests.yml`, `tools/pack_skill.py`, and `VERSION`.

- Run the full suite on Python 3.10, 3.11, 3.12, and 3.13.
- Run JavaScript syntax checks, version-consistency tests, and package-content validation.
- Build the skill archive and inspect its manifest; never package PDFs, caches, credentials, or deployment secrets.
- Keep every version reference aligned with canonical `VERSION` and the changelog.
- A failed or skipped required job is not a green release gate.
- Do not deploy, promote, or assign production aliases while any CI/CD gate is pending or failed.
- Production smoke tests remain manual and require explicit user authorization after the CI matrix is fully green.
- Report the exact commit SHA, run URL, test count, package size, and deployment state.

A successful build is not a production release. Never infer deployment success from a green unit-test matrix.
