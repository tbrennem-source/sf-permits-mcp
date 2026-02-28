# Sprint 69 Scenario Review

_Reviewed: 2026-02-26_
_Scenarios reviewed: 18_
_Accepted: 10, Merged: 3, Rejected: 4, Deferred: 1_

---

## ACCEPT (10)

### 1. Anonymous visitor sees live data counts on landing page
**Disposition:** ACCEPT — core landing page behavior, testable, user-visible.
**Section:** PUBLIC SEARCH & DISCOVERY

### 2. Landing page search bar submits to /search endpoint
**Disposition:** ACCEPT — fundamental navigation, testable.
**Section:** PUBLIC SEARCH & DISCOVERY

### 3. Landing page renders correctly on mobile (375px)
**Disposition:** ACCEPT — mobile usability is a core requirement. Good edge cases.
**Section:** MOBILE & RESPONSIVE

### 4. Technical visitor reads methodology page
**Disposition:** ACCEPT — methodology transparency is a key differentiator. Reworded to remove word count (implementation detail).
**Section:** PUBLIC SEARCH & DISCOVERY

### 5. Visitor navigates to about-data page
**Disposition:** ACCEPT — data inventory visibility. Good coverage of pipeline schedule.
**Section:** PUBLIC SEARCH & DISCOVERY

### 6. Tim shares demo URL in Zoom call
**Disposition:** ACCEPT — admin-facing but core use case. Good "everything visible on load" criterion.
**Section:** ADMIN & OPERATIONS

### 7. Anonymous search shows routing progress
**Disposition:** ACCEPT — the marquee Sprint 69 feature. Core anonymous intelligence.
**Section:** PUBLIC SEARCH & DISCOVERY

### 8. Intelligence panel loads asynchronously
**Disposition:** ACCEPT — progressive enhancement behavior. Good degradation edge case.
**Section:** PUBLIC SEARCH & DISCOVERY

### 9. Anonymous visitor sees entity names but not full network
**Disposition:** ACCEPT — free vs gated split is a product decision. Well-specified boundary.
**Section:** PUBLIC SEARCH & DISCOVERY

### 10. Search results degrade gracefully on intel timeout
**Disposition:** ACCEPT — resilience behavior. Critical for production reliability.
**Section:** PUBLIC SEARCH & DISCOVERY

---

## MERGE (3)

### 11. Design system CSS loads without breaking existing authenticated pages
**Disposition:** MERGE into existing scenario about CSS backward compatibility (if one exists), or fold into a general "new features don't break existing pages" scenario.
**Reason:** Valid behavior but narrow — applies to any CSS change, not just Sprint 69.

### 12. Search engine indexes methodology and about-data
**Disposition:** MERGE into robots.txt scenario below. Both are about search engine behavior.

### 13. Mobile search results expandable intelligence
**Disposition:** MERGE into "Anonymous search shows routing progress" (#7) as a mobile edge case.
**Reason:** Same user, same goal, just a viewport variant.

---

## REJECT (4)

### 14. /api/stats returns cached data counts
**Disposition:** REJECT — implementation detail. The user-visible outcome is "landing page shows numbers" (#1), not the JSON API contract.
**Reason:** API response shape is testable via pytest, not a behavioral scenario.

### 15. Portfolio brief contains accurate project statistics
**Disposition:** REJECT — internal document quality, not user-facing behavior.
**Reason:** Portfolio brief accuracy is validated at review time, not as a runtime scenario.

### 16. Model release probes cover all capability categories
**Disposition:** REJECT — internal process artifact, not user behavior.
**Reason:** Probe coverage is a development practice, not a product guarantee.

### 17. PWA manifest enables add-to-homescreen
**Disposition:** REJECT — placeholder icons make this non-functional currently.
**Reason:** Deferred until real icons ship (Chief #303). Revisit then.

---

## DEFER (1)

### 18. robots.txt allows public pages while blocking admin routes
**Disposition:** DEFER — valid but needs verification against actual search engine behavior.
**Reason:** robots.txt is deployed but we haven't verified Google Search Console indexing. Accept after production verification.

---

## Summary

| Classification | Count | Notes |
|---------------|-------|-------|
| ACCEPT | 10 | Added to scenario-design-guide.md |
| MERGE | 3 | Folded into existing/accepted scenarios |
| REJECT | 4 | API contracts, internal docs, placeholder features |
| DEFER | 1 | robots.txt — verify after prod indexing |
