# QS4-C Obsidian Design Migration — QA Script

## Setup
- Start local dev server on port 5099
- Use Playwright headless Chromium
- Save screenshots to qa-results/screenshots/qs4-c/

## Checks

1. [NEW] GET / (landing) → login → GET /index uses same font family — PASS/FAIL
2. [NEW] index.html has JetBrains Mono headings — PASS/FAIL
3. [NEW] brief.html has JetBrains Mono headings — PASS/FAIL
4. [NEW] brief.html health indicators use signal-green/amber/red — PASS/FAIL
5. [NEW] Nav renders correctly on index page — PASS/FAIL
6. [NEW] Nav renders correctly on brief page — PASS/FAIL
7. [NEW] Screenshot /index at 375px — no horizontal scroll — PASS/FAIL
8. [NEW] Screenshot /index at 1440px — PASS/FAIL
9. [NEW] Screenshot /brief at 375px — PASS/FAIL
10. [NEW] Screenshot /brief at 1440px — PASS/FAIL
11. [NEW] PWA manifest link present on both pages — PASS/FAIL
