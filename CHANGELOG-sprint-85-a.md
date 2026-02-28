# Sprint 85-A — Intelligence API Endpoints

## Added

### 4 New JSON API Endpoints (web/routes_api.py)

**GET /api/predict-next/<permit_number>**
- Calls `predict_next_stations(permit_number)` and returns markdown as JSON
- Requires authenticated session; returns 401 if unauthenticated
- Response: `{"permit_number": str, "result": str}`

**GET /api/stuck-permit/<permit_number>**
- Calls `diagnose_stuck_permit(permit_number)` and returns markdown playbook as JSON
- Requires authenticated session; returns 401 if unauthenticated
- Response: `{"permit_number": str, "result": str}`

**POST /api/what-if**
- Accepts JSON body: `{base_description, variations?}`
- Calls `simulate_what_if(base_description, variations)` and returns comparison table as JSON
- Validates: base_description required and non-empty; variations must be a list
- Requires authenticated session; returns 401 if unauthenticated
- Response: `{"result": str}`

**POST /api/delay-cost**
- Accepts JSON body: `{permit_type, monthly_carrying_cost, neighborhood?, triggers?}`
- Calls `calculate_delay_cost(permit_type, monthly_carrying_cost, ...)` and returns cost breakdown as JSON
- Validates: permit_type required; monthly_carrying_cost required, numeric, > 0; triggers must be a list if provided
- Requires authenticated session; returns 401 if unauthenticated
- Response: `{"result": str}`

### Tests (tests/test_api_intelligence.py)
- 26 tests across 4 endpoint groups
- Auth gate tests (401 on unauthenticated access)
- Input validation tests (400 on missing/invalid fields)
- Happy-path tests with mocked tool responses
- Error handling tests (500 on tool exception)
- Method enforcement (405 on GET to POST-only endpoints)
