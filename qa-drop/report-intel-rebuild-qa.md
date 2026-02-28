# QA Script: Report Page — Property Intel Rebuild

**Feature:** Rebuild `web/templates/report.html` from `property-intel.html` mockup
**Date:** 2026-02-27
**Sprint:** report-intel-rebuild

---

## Setup

1. Start the dev server: `source .venv/bin/activate && python -m web.app &`
2. Navigate to a property report with known data, e.g. `/report/3582/035`
3. If rate-limited, wait 1 minute or use a different IP

---

## 1. Page Load

- [ ] Navigate to `/report/{block}/{lot}` for a block/lot with permit data
- **PASS:** Page returns HTTP 200 with content
- **FAIL:** 500 error or blank page

## 2. Property Header

- [ ] Page shows property address in the header
- [ ] Address has accent color styling (not plain white)
- [ ] Block, Lot chips visible in the property-meta row
- **PASS:** Header renders with address and at least 2 chips
- **FAIL:** Missing address or chips absent

## 3. Intel Grid

- [ ] Three intel cards visible below the header
- [ ] First card shows total permit count (clickable, links to #section-permits)
- [ ] Second card shows complaint count (clickable, links to #section-complaints)
- [ ] Third card shows risk factors count (clickable, links to #section-risks)
- [ ] Cards with zero counts show "0" not empty
- [ ] Cards with > 0 complaints/risks show danger styling
- **PASS:** All three cards render with numeric values
- **FAIL:** Cards missing, empty, or template error

## 4. Actions Needed

- [ ] If risk_assessment has high/moderate items, "Needs attention" section appears
- [ ] Each action item has a colored dot and description
- [ ] Hovering action item reveals arrow CTA
- **PASS:** Actions section renders for properties with risks
- **FAIL:** Section missing when risks exist

## 5. CTA Row

- [ ] "Ask AI about this property" ghost-cta links to `/search?q={address}`
- [ ] If consultant signal is non-cold, "Find a consultant" CTA appears
- **PASS:** At least one CTA visible
- **FAIL:** Empty CTA row

## 6. Permit List

- [ ] Permits listed with permit number, description, status badge, date
- [ ] Permit number is a clickable link (external DBI link)
- [ ] Status badge color matches status (green=issued, amber=filed, red=expired)
- [ ] Clicking a permit item expands its details panel
- **PASS:** Permits list renders; clicking expands contacts/routing/inspections
- **FAIL:** Permit list empty for known-data property, or expand fails

## 7. Routing Progress Section

- [ ] If any permit has routing data (total > 0), routing section appears below permit list
- [ ] Shows progress bar with correct percentage
- [ ] Stalled stations shown with amber "Xd stalled" text
- [ ] Pending stations shown with "Pending" text
- **PASS:** Routing section renders for permits with routing data
- **FAIL:** Missing for permits that should have routing

## 8. Risk Assessment Section

- [ ] Section labeled "Risk assessment" appears
- [ ] Each risk item has severity chip (high/moderate/low/clear)
- [ ] Risk items use left-border color coding (red=high, amber=moderate, blue=low)
- [ ] "No known risks" shown when risk_assessment is empty
- **PASS:** Risk items render correctly or clean state shown
- **FAIL:** Template error or missing risks for known-risk property

## 9. Complaints & Violations

- [ ] Section shows complaint count in data-row
- [ ] Each complaint has a status chip and date
- [ ] "No complaints on file" shown when empty
- [ ] Violations shown separately with own count
- **PASS:** Complaints and violations render; empty state works
- **FAIL:** Missing section or data

## 10. Entity Network (Project Team)

- [ ] "Project team" section visible
- [ ] Each entity row shows name, role, and permit count
- [ ] Entity rows are clickable links to entity search
- [ ] "No contacts on file" shown when no contacts
- **PASS:** Team entities render for permit with contacts
- **FAIL:** Section missing or empty despite contacts in permits

## 11. Property Profile

- [ ] Property profile section shows zoning, assessed value, year built, etc.
- [ ] Zoning links to planning code
- [ ] "—" shown for unavailable fields
- **PASS:** Profile renders with available data
- **FAIL:** Section completely empty for property with known profile

## 12. Zoning & Regulatory Context

- [ ] If property has zoning, zoning section renders
- [ ] Zoning-specific copy appears (e.g. "RH-1 Residential House" for RH-1 zones)
- **PASS:** Zoning note renders for property with zoning code
- **FAIL:** Missing section for zoned property

## 13. Consultant Recommendation

- [ ] If consultant_signal is not "cold", callout box appears
- [ ] Signal-appropriate styling applied (warm/recommended/strongly_recommended/essential)
- [ ] "Find a consultant" link present
- [ ] Cold signal = section absent
- **PASS:** Callout renders with correct signal styling
- **FAIL:** Missing for non-cold signal properties

## 14. Owner Mode

- [ ] Visiting `/report/{block}/{lot}?owner=1` when logged in activates owner mode
- [ ] Owner banner appears at top
- [ ] Remediation roadmap section renders if roadmap data present
- **PASS:** Owner banner and roadmap visible
- **FAIL:** Banner missing on owner=1 request

## 15. Share Modal

- [ ] When logged in, "Share" button appears in nav
- [ ] Clicking "Share" opens the share modal
- [ ] Modal has email input and optional message textarea
- [ ] ESC key closes modal
- **PASS:** Modal opens and can be dismissed
- **FAIL:** Button missing or modal doesn't open

## 16. Navigation Search Bar

- [ ] Nav shows a search input bar with property address pre-filled
- [ ] Submitting search navigates to `/search?q={value}`
- **PASS:** Search bar visible in nav with pre-filled address
- **FAIL:** Nav search missing

## 17. Scroll Reveal Animation

- [ ] Sections fade in as user scrolls down
- [ ] No flash of invisible content (FOIC) on initial load
- **PASS:** Sections animate in on scroll
- **FAIL:** All sections invisible or no animation

## 18. Error State

- [ ] Navigate to `/report/0000/000` (non-existent parcel)
- **PASS:** Error message shown ("No data found..." or similar), not 500
- **FAIL:** Unhandled exception or blank page

## 19. Mobile Responsive

- [ ] At 375px viewport, intel grid collapses to 2 columns then 1 column at 480px
- [ ] Nav search bar hides on mobile
- [ ] Permit list readable on mobile
- **PASS:** Page usable on mobile, no horizontal overflow
- **FAIL:** Layout broken at mobile sizes

## 20. Design Token Compliance

- [ ] Run: `python scripts/design_lint.py --files web/templates/report.html --quiet`
- **PASS:** Score 5/5 (0 violations)
- **FAIL:** Score < 4/5 or inline hex colors detected
