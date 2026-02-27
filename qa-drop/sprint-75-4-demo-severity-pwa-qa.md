# QA Script: Sprint 75-4 — Demo Severity + PWA Polish

Self-contained. No setup required. All steps use pytest or browser.

---

## CLI Steps (pytest — no browser needed)

**1. Sprint 75-4 unit tests pass**
```
source .venv/bin/activate
pytest tests/test_sprint_75_4.py -v
```
PASS: 24 tests pass, 0 failures
FAIL: Any test fails

**2. Manifest.json has maskable purpose**
```
python3 -c "
import json
m = json.load(open('web/static/manifest.json'))
icons = m['icons']
assert all('maskable' in i.get('purpose','') for i in icons), 'No maskable'
assert all('any' in i.get('purpose','') for i in icons), 'No any'
print('PASS: purpose fields correct')
"
```
PASS: prints PASS
FAIL: assertion error

**3. sitemap.xml contains /demo**
```
python3 -c "
from web.app import app
with app.test_client() as c:
    r = c.get('/sitemap.xml')
    assert b'/demo' in r.data, '/demo missing from sitemap'
    print('PASS: /demo in sitemap')
"
```
PASS: prints PASS
FAIL: assertion error

**4. Cache TTL is 15 min (not 1 hour)**
```
python3 -c "
from web.routes_misc import _DEMO_CACHE_TTL
assert _DEMO_CACHE_TTL == 900, f'TTL is {_DEMO_CACHE_TTL}, expected 900'
print('PASS: TTL = 900s')
"
```
PASS: prints PASS
FAIL: wrong value

**5. Demo route returns 200**
```
python3 -c "
from web.app import app
with app.test_client() as c:
    r = c.get('/demo')
    assert r.status_code == 200, f'Got {r.status_code}'
    print('PASS: /demo 200')
"
```
PASS: prints PASS
FAIL: non-200 status

---

## Browser Steps (Playwright — staging URL required)

Replace `BASE_URL` with staging URL.

**6. /demo renders severity badge when active permits exist**
- Navigate to /demo
- PASS: `.severity-pill` element visible in hero section
- FAIL: no severity badge visible

**7. Permit table has Severity column**
- Navigate to /demo
- PASS: "Severity" column header visible in permit history table
- FAIL: no Severity column

**8. Severity pill colors match design system**
- Navigate to /demo
- PASS: CRITICAL shows in red-toned pill, GREEN shows in green-toned pill (visual check)
- FAIL: all pills same color

**9. PWA installable (Chrome)**
- Open /demo in Chrome
- Open DevTools → Application → Manifest
- PASS: Manifest loaded, "Installability: Installable" shown, purpose includes "maskable"
- FAIL: Manifest errors or missing maskable

**10. /demo linked from footer (verify discoverability)**
- Navigate to /demo
- PASS: Footer has links to /methodology and /about-data (existing links still present)
- FAIL: footer links missing
