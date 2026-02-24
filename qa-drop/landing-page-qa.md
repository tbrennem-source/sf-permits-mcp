# QA Script: Landing Page + Public Address Lookup (Session C)

## Prerequisites
- App running locally or accessible at production URL
- No login session (use incognito/private browser window)

## Test Steps

### 1. Landing page renders for anonymous users
- [ ] Open `/` in a browser with no session
- [ ] PASS: Page shows "San Francisco Building Permit Intelligence" hero
- [ ] PASS: Search box is visible with placeholder text
- [ ] PASS: 6 feature cards visible (Address Lookup, Property Reports, Morning Brief, Plan Analysis, Entity Network, Fee & Timeline)
- [ ] PASS: Stats section shows 1.1M+, 3.9M+, 671K+, 1M+
- [ ] PASS: "Sign in" and "Get started free" buttons visible in header

### 2. Landing page search form works
- [ ] Type "1455 Market St" in the search box and submit
- [ ] PASS: Browser navigates to `/search?q=1455+Market+St`
- [ ] PASS: Results page loads with permit data

### 3. Public search results show locked premium cards
- [ ] On the `/search?q=1455+Market+St` results page
- [ ] PASS: Basic permit results are visible (not blurred/locked)
- [ ] PASS: "Property Report" locked card visible with "Sign up free to unlock" CTA
- [ ] PASS: "Watch & Get Alerts" locked card visible
- [ ] PASS: "AI Project Analysis" locked card visible
- [ ] PASS: CTAs link to `/auth/login`

### 4. Empty search redirects to home
- [ ] Navigate to `/search` (no query parameter)
- [ ] PASS: Redirected to `/`

### 5. Authenticated users see full app on home page
- [ ] Log in via `/auth/login`
- [ ] Navigate to `/`
- [ ] PASS: Full app visible (Analyze Project form, neighborhoods, etc.)
- [ ] PASS: NOT showing landing page hero text

### 6. Authenticated users redirect from /search to /?q=
- [ ] While logged in, navigate to `/search?q=test`
- [ ] PASS: Redirected to `/?q=test`

### 7. Premium routes require login
- [ ] Log out
- [ ] Navigate to `/brief` — PASS: redirected to `/auth/login`
- [ ] Navigate to `/portfolio` — PASS: redirected to `/auth/login`
- [ ] Navigate to `/account` — PASS: redirected to `/auth/login`
- [ ] Navigate to `/consultants` — PASS: redirected to `/auth/login`
- [ ] Navigate to `/account/analyses` — PASS: redirected to `/auth/login`

### 8. Public routes remain accessible
- [ ] Navigate to `/health` — PASS: returns 200 with JSON
- [ ] Navigate to `/auth/login` — PASS: login page loads
- [ ] Navigate to `/search?q=test` — PASS: search results page loads

### 9. Mobile responsiveness
- [ ] Resize browser to 375px width
- [ ] PASS: Landing page search box stacks vertically
- [ ] PASS: Feature cards stack to single column
- [ ] PASS: Stats grid becomes 2x2
- [ ] PASS: Touch targets are at least 48px

### 10. No-results handling
- [ ] Search for a nonsensical address: `/search?q=99999+Nonexistent+Blvd`
- [ ] PASS: No-results message shown, not a server error

### 11. Rate limiting on /search
- [ ] Rapidly submit 20+ searches in quick succession
- [ ] PASS: Rate limit message appears (429 status)
