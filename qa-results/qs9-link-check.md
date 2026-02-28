============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0 -- /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/python3.14
cachedir: .pytest_cache
rootdir: /Users/timbrenneman/AIprojects/sf-permits-mcp
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.3.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 7 items

tests/e2e/test_links.py::TestDeadLinkSpider::test_no_dead_links_anonymous PASSED [ 14%]
tests/e2e/test_links.py::TestDeadLinkSpider::test_no_dead_links_authenticated FAILED [ 28%]
tests/e2e/test_links.py::TestDeadLinkSpider::test_no_dead_links_admin FAILED [ 42%]
tests/e2e/test_links.py::TestDeadLinkSpider::test_no_slow_pages PASSED   [ 57%]
tests/e2e/test_links.py::TestSpiderCoverage::test_spider_visits_login PASSED [ 71%]
tests/e2e/test_links.py::TestSpiderCoverage::test_spider_visits_search PASSED [ 85%]
tests/e2e/test_links.py::TestSpiderCoverage::test_methodology_page_accessible PASSED [100%]

=================================== FAILURES ===================================
_____________ TestDeadLinkSpider.test_no_dead_links_authenticated ______________
tests/e2e/test_links.py:248: in test_no_dead_links_authenticated
    visited, errors, external, slow = _crawl(
tests/e2e/test_links.py:177: in _crawl
    rv = client.get(url, follow_redirects=True)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/werkzeug/test.py:1162: in get
    return self.open(*args, **kw)
           ^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/testing.py:235: in open
    response = super().open(
.venv/lib/python3.14/site-packages/werkzeug/test.py:1116: in open
    response_parts = self.run_wsgi_app(request.environ, buffered=buffered)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/werkzeug/test.py:988: in run_wsgi_app
    rv = run_wsgi_app(self.application, environ, buffered=buffered)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/werkzeug/test.py:1264: in run_wsgi_app
    app_rv = app(environ, start_response)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:1536: in __call__
    return self.wsgi_app(environ, start_response)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:1514: in wsgi_app
    response = self.handle_exception(e)
               ^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:1511: in wsgi_app
    response = self.full_dispatch_request()
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:919: in full_dispatch_request
    rv = self.handle_user_exception(e)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:917: in full_dispatch_request
    rv = self.dispatch_request()
         ^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:902: in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web/helpers.py:216: in decorated
    return f(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^
web/routes_auth.py:504: in account_prep
    checklists = get_user_checklists(g.user["user_id"])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web/permit_prep.py:330: in get_user_checklists
    rows = query(
src/db.py:286: in query
    result = conn.execute(sql, params).fetchall()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E   _duckdb.CatalogException: Catalog Error: Table with name prep_checklists does not exist!
E   Did you mean "page_cache"?
E   
E   LINE 1: ... checklist_id, permit_number, created_at, updated_at FROM prep_checklists WHERE user_id = ? ORDER BY updated_at DESC
E                                                                        ^
_________________ TestDeadLinkSpider.test_no_dead_links_admin __________________
tests/e2e/test_links.py:289: in test_no_dead_links_admin
    visited, errors, external, slow = _crawl(
tests/e2e/test_links.py:177: in _crawl
    rv = client.get(url, follow_redirects=True)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/werkzeug/test.py:1162: in get
    return self.open(*args, **kw)
           ^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/testing.py:235: in open
    response = super().open(
.venv/lib/python3.14/site-packages/werkzeug/test.py:1116: in open
    response_parts = self.run_wsgi_app(request.environ, buffered=buffered)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/werkzeug/test.py:988: in run_wsgi_app
    rv = run_wsgi_app(self.application, environ, buffered=buffered)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/werkzeug/test.py:1264: in run_wsgi_app
    app_rv = app(environ, start_response)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:1536: in __call__
    return self.wsgi_app(environ, start_response)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:1514: in wsgi_app
    response = self.handle_exception(e)
               ^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:1511: in wsgi_app
    response = self.full_dispatch_request()
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:919: in full_dispatch_request
    rv = self.handle_user_exception(e)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:917: in full_dispatch_request
    rv = self.dispatch_request()
         ^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.14/site-packages/flask/app.py:902: in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web/helpers.py:216: in decorated
    return f(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^
web/routes_auth.py:504: in account_prep
    checklists = get_user_checklists(g.user["user_id"])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web/permit_prep.py:330: in get_user_checklists
    rows = query(
src/db.py:286: in query
    result = conn.execute(sql, params).fetchall()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E   _duckdb.CatalogException: Catalog Error: Table with name prep_checklists does not exist!
E   Did you mean "page_cache"?
E   
E   LINE 1: ... checklist_id, permit_number, created_at, updated_at FROM prep_checklists WHERE user_id = ? ORDER BY updated_at DESC
E                                                                        ^
------------------------------ Captured log call -------------------------------
WARNING  web.pipeline_health:pipeline_health.py:291 Could not get cron history: Binder Error: Referenced column "lookback_days" not found in FROM clause!
Candidate bindings: "log_id", "job_type"

LINE 1: SELECT log_id, job_type, started_at, completed_at, status, lookback_days, soda_records, changes_inserted, inspections_...
                                                                   ^
=========================== short test summary info ============================
FAILED tests/e2e/test_links.py::TestDeadLinkSpider::test_no_dead_links_authenticated
FAILED tests/e2e/test_links.py::TestDeadLinkSpider::test_no_dead_links_admin
========================= 2 failed, 5 passed in 2.01s ==========================
