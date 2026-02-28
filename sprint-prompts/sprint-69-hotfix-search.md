<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/sprint-69-hotfix-search.md and execute it" -->

# Sprint 69 Hotfix: Address Search Broken on Staging + Production

This is a **hotfix**, not a full sprint. Fix one bug, verify, ship.

## SETUP — Session Bootstrap

1. **Navigate to the main repo root:**
   ```
   cd /Users/timbrenneman/AIprojects/sf-permits-mcp
   ```
2. **Pull latest main:**
   ```
   git checkout main && git pull origin main
   ```
3. **Create your worktree:**
   Use EnterWorktree with name `hotfix-search`

If EnterWorktree fails because a worktree with that name already exists:
```
git worktree remove .claude/worktrees/hotfix-search --force 2>/dev/null; true
```

---

## THE BUG

**Symptom:** All address-based searches on `/search?q=<address>` return "Something went wrong. We couldn't complete your search right now." on BOTH staging and production.

**What works:** Permit number search (`/search?q=202401015555`), keyword search, `/lookup` POST endpoint, `/demo` page (pre-loaded data), `/api/stats`. The database is healthy (59 tables, 2M permits).

**What fails:** Any query that `classify_intent()` routes to the `search_address` intent path, causing `run_async(permit_lookup(street_number=..., street_name=...))` to throw.

**Code path:**
```
GET /search?q=1455+Market+St
  → web/routes_public.py:81 public_search()
  → line 93: classify_intent(query_str, NEIGHBORHOODS)
  → line 110-124: intent == "search_address" → permit_lookup(street_number, street_name)
  → line 109/119: run_async(permit_lookup(...))
  → EXCEPTION caught at line 131
  → "We couldn't complete your search right now"
```

---

## INVESTIGATION STEPS (do these FIRST, before writing any fix)

### Step 1: Check Railway logs for the actual exception

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
railway logs -n 200 2>&1 | grep -i "error\|exception\|traceback\|search failed" | head -40
```

If railway CLI isn't linked to the right service:
```bash
railway service link sfpermits-ai-staging
railway logs -n 200
```

Look for the actual exception type and traceback. This tells us whether it's:
- Connection pool exhaustion
- Event loop conflict in run_async
- Intent classifier returning bad entities
- SQL error in permit_lookup
- Timeout

### Step 2: Reproduce locally

```bash
source .venv/bin/activate
python -c "
from web.app import create_app
app = create_app()
with app.test_client() as c:
    resp = c.get('/search?q=1455+Market+St')
    print(f'Status: {resp.status_code}')
    if b'Something went wrong' in resp.data:
        print('BUG REPRODUCED LOCALLY')
    elif b'permit' in resp.data.lower():
        print('WORKS LOCALLY — Railway-specific issue')
    else:
        print('Unexpected response')
        print(resp.data[:500])
"
```

### Step 3: Test classify_intent output

```bash
python -c "
from src.tools.intent_router import classify
result = classify('1455 Market St', ['Mission', 'SoMa', 'Castro/Upper Market'])
print(f'Intent: {result.intent}')
print(f'Entities: {result.entities}')
# Expected: intent='search_address', entities={'street_number': '1455', 'street_name': 'Market St'}
"
```

### Step 4: Test permit_lookup directly

```bash
python -c "
import asyncio
from src.tools.permit_lookup import permit_lookup
result = asyncio.run(permit_lookup(street_number='1455', street_name='Market St'))
print(result[:500])
"
```

### Step 5: Test run_async specifically

```bash
python -c "
from web.helpers import run_async
from src.tools.permit_lookup import permit_lookup
try:
    result = run_async(permit_lookup(street_number='1455', street_name='Market St'))
    print('SUCCESS:', result[:200])
except Exception as e:
    print(f'FAILED: {type(e).__name__}: {e}')
"
```

---

## LIKELY ROOT CAUSES (ranked by probability)

### 1. run_async event loop conflict (MOST LIKELY)

`run_async()` in `web/helpers.py:140-150` tries to get an existing event loop. On Railway with gunicorn workers, the behavior depends on the worker type:
- **sync workers:** no event loop → `asyncio.run(coro)` works
- **gevent/eventlet workers:** may have a running loop → `ThreadPoolExecutor` path
- **The ThreadPoolExecutor path** calls `asyncio.run(coro)` in a new thread, which creates a NEW event loop. But `permit_lookup` calls `get_connection()` which may return a connection bound to the ORIGINAL thread's context.

**Fix:** Make `permit_lookup` synchronous. It only does DB queries — there's no actual async I/O. The `async def` signature is a FastMCP convention but the Flask web app doesn't need it.

Create a synchronous wrapper in `web/routes_public.py`:
```python
def _sync_permit_lookup(**kwargs):
    """Synchronous wrapper for permit_lookup — avoids run_async event loop issues."""
    from src.tools.permit_lookup import (
        get_connection, _lookup_by_number, _lookup_by_address,
        _lookup_by_block_lot, ...
    )
    # Call the internal functions directly, bypassing the async wrapper
```

Or simpler: just call `asyncio.run(permit_lookup(...))` directly instead of `run_async()`, since Flask sync routes don't have a running event loop.

### 2. classify_intent returns wrong entities

The intent classifier might be extracting `street_number=None` for "1455 Market St", causing `has_address=False` in permit_lookup. This would raise a different error though ("Please provide a permit number..."), not an exception.

**Fix:** Add logging before the permit_lookup call to see what entities were extracted.

### 3. DB connection pool exhaustion on Railway

Railway's Postgres may be hitting connection limits. The `/health` endpoint works because it uses a simple query, but `permit_lookup` does 5-10 queries in sequence.

**Fix:** Check if `get_connection()` is using a pool, and if the pool size is appropriate for Railway's connection limits.

---

## AFTER FIXING

### Test locally
```bash
pytest tests/ --ignore=tests/test_tools.py -q
python -c "
from web.app import create_app
app = create_app()
with app.test_client() as c:
    resp = c.get('/search?q=1455+Market+St')
    print(f'Status: {resp.status_code}')
    assert b'Something went wrong' not in resp.data, 'STILL BROKEN'
    print('FIXED')
"
```

### Test on staging
After pushing to main (auto-deploys to staging):
```bash
curl -s 'https://sfpermits-ai-staging-production.up.railway.app/search?q=1455+Market+St' | head -100
```

Should show permit results, not "Something went wrong."

### Write a regression test
Add to `tests/test_sprint69_hotfix.py`:
```python
def test_address_search_returns_results(client):
    """Regression: address search was returning 'Something went wrong'."""
    resp = client.get('/search?q=1455+Market+St')
    assert resp.status_code == 200
    assert b'Something went wrong' not in resp.data
```

### Commit and push
```
git add -A && git commit -m "fix: address search broken — [root cause description]"
git checkout main && git merge hotfix-search && git push origin main
```

### Verify staging, then promote to prod
```bash
# After staging auto-deploys:
curl -s 'https://sfpermits-ai-staging-production.up.railway.app/search?q=1455+Market+St' | grep -c 'permit'

# If results appear, promote:
git checkout prod && git merge main && git push origin prod
```

---

## DO NOT

- Do NOT refactor permit_lookup beyond what's needed to fix the bug
- Do NOT change the classify_intent logic unless it's the root cause
- Do NOT modify any Sprint 69 templates or CSS
- Do NOT add new features — this is a hotfix

## File Ownership
- `web/routes_public.py` (fix the search path)
- `web/helpers.py` (fix run_async if that's the cause)
- `src/tools/permit_lookup.py` (only if the bug is there)
- `tests/test_sprint69_hotfix.py` (regression test)
