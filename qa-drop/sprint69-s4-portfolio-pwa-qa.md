# Sprint 69 Session 4: Portfolio + PWA QA Script

## Pre-requisites
- Dev server running at localhost:5000
- All docs written to docs/ directory
- manifest.json and icons in web/static/

## Checks

### 1. Portfolio Brief Content
- [ ] docs/portfolio-brief.md exists
- [ ] Contains "Tim Brenneman"
- [ ] Contains real numbers (3,327 tests, 29 tools, etc.)
- [ ] Word count > 500
- PASS: All present / FAIL: Any missing

### 2. LinkedIn Update Structure
- [ ] docs/linkedin-update.md exists
- [ ] Has "## Headline" section
- [ ] Has "## About" section
- [ ] Has Experience section with bullet points
- PASS: All sections present / FAIL: Missing sections

### 3. Model Release Probes
- [ ] docs/model-release-probes.md exists
- [ ] Has >10 probe entries (### Probe N.N)
- [ ] Covers all 6 categories
- PASS: All present / FAIL: Any missing

### 4. Manifest JSON Validity
- [ ] web/static/manifest.json exists
- [ ] Valid JSON parseable
- [ ] theme_color is #22D3EE
- PASS: Valid / FAIL: Parse error or wrong color

### 5. robots.txt Route (Browser)
- [ ] Navigate to /robots.txt
- [ ] Returns 200
- [ ] Contains "Disallow: /admin/"
- [ ] Contains "Allow: /"
- [ ] Contains "Sitemap:"
- PASS: All present / FAIL: 404 or missing directives

### 6. Manifest Served (Browser)
- [ ] Navigate to /static/manifest.json
- [ ] Returns 200
- [ ] Valid JSON response
- PASS: Accessible / FAIL: 404 or invalid

### 7. Portfolio Brief Test Count Accuracy
- [ ] Run pytest --co -q to get actual test count
- [ ] Read docs/portfolio-brief.md
- [ ] Verify test count mentioned matches actual (within ±50)
- PASS: Accurate / FAIL: More than 50 off

### 8. Portfolio Brief Entity Resolution Mention
- [ ] Read docs/portfolio-brief.md
- [ ] Contains "entity resolution"
- [ ] Contains "1.8M contacts" or similar
- PASS: Present / FAIL: Missing

### 9. dforge README Behavioral Scenarios
- [ ] docs/dforge-public-readme.md exists
- [ ] Contains "behavioral scenario" (case insensitive)
- [ ] Contains "Black Box"
- PASS: Present / FAIL: Missing

### 10. Icon Files Exist
- [ ] web/static/icon-192.png exists and is a valid PNG
- [ ] web/static/icon-512.png exists and is a valid PNG
- PASS: Both present / FAIL: Missing or invalid
