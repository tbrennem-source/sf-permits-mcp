# Sprint 69 S3 — Content Pages QA Script

## Setup
1. Start dev server: `python -c "from web.app import app; app.run(port=5099, debug=False)"` in background
2. Wait for server ready on http://localhost:5099
3. Run Playwright checks below

## Playwright Checks

### 1. /methodology — 200 response
- Navigate to `http://localhost:5099/methodology`
- **PASS**: Status 200
- Screenshot: `qa-results/screenshots/sprint69-s3/methodology-desktop.png` (1440px)
- Screenshot: `qa-results/screenshots/sprint69-s3/methodology-mobile.png` (375px)

### 2. /methodology — Entity Resolution heading
- On /methodology page
- **PASS**: h2 or h3 containing "Entity Resolution" is visible

### 3. /methodology — Timeline Estimation heading
- On /methodology page
- **PASS**: h2 or h3 containing "Timeline Estimation" is visible

### 4. /methodology — Data provenance table
- On /methodology page
- Find `<table>` with "Building Permits" in a row
- **PASS**: Table has 5+ rows in tbody

### 5. /methodology — Substantial content (>2000 words)
- Get text content of the page body
- Count words
- **PASS**: Word count > 2000

### 6. /about-data — 200 response
- Navigate to `http://localhost:5099/about-data`
- **PASS**: Status 200
- Screenshot: `qa-results/screenshots/sprint69-s3/about-data-desktop.png` (1440px)
- Screenshot: `qa-results/screenshots/sprint69-s3/about-data-mobile.png` (375px)

### 7. /about-data — Data inventory section
- On /about-data page
- **PASS**: Text "Data Inventory" visible AND "Building Permits" visible

### 8. /about-data — Nightly pipeline section
- On /about-data page
- **PASS**: Text "Nightly Pipeline" or "Pipeline" visible

### 9. /demo — 200 response
- Navigate to `http://localhost:5099/demo`
- **PASS**: Status 200
- Screenshot: `qa-results/screenshots/sprint69-s3/demo-desktop.png` (1440px)

### 10. /demo — noindex meta tag
- On /demo page
- **PASS**: `meta[name="robots"][content="noindex"]` exists

### 11. /demo — Permit data renders
- On /demo page
- **PASS**: "Permit History" text visible AND "Property Intelligence" visible

### 12. /demo — Annotation callouts visible
- On /demo page
- **PASS**: At least one element with class "callout" is visible

### 13. /demo — Obsidian design tokens
- Check page source for `--bg-deep` and `--signal-cyan`
- **PASS**: Both CSS variables present in page source

## Teardown
- Kill dev server process
