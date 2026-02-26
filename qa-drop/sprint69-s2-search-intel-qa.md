# QA Script: Sprint 69-S2 — Search Intelligence + Anonymous Demo Path

## Prerequisites
- Flask dev server running on localhost:5099
- Python with playwright installed (`pip install playwright && playwright install chromium`)

## Test Steps

### 1. Start Flask test server
```python
import subprocess, time
proc = subprocess.Popen(["python", "-c",
    "from web.app import app; app.run(host='127.0.0.1', port=5099, debug=False)"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
```
**PASS:** Server starts without error

### 2. Navigate to /search?q=1455+Market+St — verify 200
```python
page.goto("http://127.0.0.1:5099/search?q=1455+Market+St")
assert page.url contains "search"
```
**PASS:** Page loads with 200 status, no error visible

### 3. Screenshot at 375px (mobile)
```python
page.set_viewport_size({"width": 375, "height": 812})
page.goto("http://127.0.0.1:5099/search?q=1455+Market+St")
page.screenshot(path="qa-results/screenshots/sprint69-s2/mobile-375.png", full_page=True)
```
**PASS:** Screenshot captured, no horizontal scroll, single column layout

### 4. Screenshot at 768px (tablet)
```python
page.set_viewport_size({"width": 768, "height": 1024})
page.goto("http://127.0.0.1:5099/search?q=1455+Market+St")
page.screenshot(path="qa-results/screenshots/sprint69-s2/tablet-768.png", full_page=True)
```
**PASS:** Screenshot captured, layout readable

### 5. Screenshot at 1440px (desktop)
```python
page.set_viewport_size({"width": 1440, "height": 900})
page.goto("http://127.0.0.1:5099/search?q=1455+Market+St")
page.screenshot(path="qa-results/screenshots/sprint69-s2/desktop-1440.png", full_page=True)
```
**PASS:** Screenshot captured, two-column layout visible (results left, intel right)

### 6. Verify permit result cards appear
```python
content = page.content()
assert "permit" in content.lower() or "Permit" in content
```
**PASS:** Permit data visible in results

### 7. Verify intelligence panel section exists
```python
# Desktop: intel column with HTMX loader or loaded content
assert page.locator(".intel-column").count() > 0 or page.locator("[hx-post='/lookup/intel-preview']").count() > 0
```
**PASS:** Intel panel container present (HTMX placeholder or loaded content)

### 8. POST to /lookup/intel-preview with block/lot — verify HTML fragment
```python
response = page.request.post("http://127.0.0.1:5099/lookup/intel-preview",
    form={"block": "3512", "lot": "001"})
assert response.status == 200
body = response.text()
assert "intel" in body.lower()
```
**PASS:** Returns HTML fragment with intel content

### 9. Verify no horizontal scroll at 375px
```python
page.set_viewport_size({"width": 375, "height": 812})
page.goto("http://127.0.0.1:5099/search?q=1455+Market+St")
scroll_width = page.evaluate("document.documentElement.scrollWidth")
viewport_width = page.evaluate("document.documentElement.clientWidth")
assert scroll_width <= viewport_width + 5  # 5px tolerance
```
**PASS:** No horizontal overflow at mobile viewport

### 10. Verify search bar is functional
```python
page.set_viewport_size({"width": 1440, "height": 900})
page.goto("http://127.0.0.1:5099/search?q=test")
input_el = page.locator("input[name='q']")
assert input_el.is_visible()
assert input_el.input_value() == "test"
```
**PASS:** Search bar visible and pre-filled with query

### 11. Verify "Sign up free" CTA appears
```python
page.goto("http://127.0.0.1:5099/search?q=1455+Market+St")
page.wait_for_timeout(3000)  # Let HTMX load intel
content = page.content()
assert "Sign up free" in content or "sign up free" in content.lower()
```
**PASS:** Signup CTA visible (in header, intel panel, or both)

### Cleanup
```python
proc.terminate()
```
