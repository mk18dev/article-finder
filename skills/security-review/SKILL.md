---
name: article-finder-security-review
description: Review Article Finder API, network boundaries, DOI handling, secrets, request limits, and safe file operations.
---

# Security Review Skill — Article Finder 1.1.0

Review `scripts/http_util.py`, `scripts/web_api.py`, `scripts/serve.py`, `api/index.py`, and `vercel.json`.

- Allowlist remote hosts and HTTPS schemes; reject arbitrary user-supplied fetch URLs and private-network destinations.
- Bound request bodies, batch sizes, timeouts, retries, and response sizes.
- Treat API keys as secrets: never log, persist in browser storage, or expose them in static assets.
- Use constant-time comparison for bearer credentials and explicit same-origin/CSRF boundaries.
- Keep PDF downloads local and separate from public API URL fetching.
- Return sanitized errors; never leak stack traces, environment values, filesystem paths, or credentials.
- Record public API mode explicitly. If `ARTICLE_FINDER_API_KEY` is unset on Vercel, the API fails closed unless `ARTICLE_FINDER_PUBLIC_MODE=1` is explicitly set. Local development is public by default.

Output: findings with severity, affected file/line, reproducible test, and smallest safe fix.
