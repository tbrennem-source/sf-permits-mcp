# QA: Session 43 — Intent Router + Portfolio Health + What Changed

## Prerequisites
- Logged in as admin on https://sfpermits-ai-production.up.railway.app
- At least one watched property with an expired permit (e.g., 300 Howard St)

---

## Intent Router — Email Detection (Priority 0)

### 1. Kitchen remodel email → draft response
- [ ] On homepage, paste into search box: `Hi Amy, We're getting quotes for a kitchen remodel at our place on Noe Valley. Can you tell us what permits we'll need?`
- [ ] Click Go
- **PASS**: AI-generated response about kitchen remodel permits (draft_response mode). NOT a "Project Analysis" form or permit prediction table.

### 2. Complaint email → draft response
- [ ] Paste into search box:
```
Hi,
We just got a notice from DBI about a complaint on our property at 4521 Judah Street. We bought the house 18 months ago.
The notice mentions unpermitted work in the garage. We didn't do any work.
What should we do?
— Karen
```
- [ ] Click Go
- **PASS**: AI-generated response advising about the complaint. NOT a complaint search results table.

### 3. Short complaint search still works
- [ ] Type: `complaints at 4521 Judah Street`
- [ ] Click Go
- **PASS**: Shows complaint search results (table/cards), not an AI draft.

### 4. Short address search still works
- [ ] Type: `300 Howard St`
- [ ] Click Go
- **PASS**: Shows permit lookup results for 300 Howard, not an AI draft.

### 5. Explicit draft prefix
- [ ] Type: `draft: reply to client about their ADU project timeline`
- [ ] Click Go
- **PASS**: AI-generated draft response.

### 6. Short greeting does NOT trigger draft
- [ ] Type: `Hi Amy`
- [ ] Click Go
- **PASS**: Routes to general_question (short, no substance). Should NOT crash or show empty draft.

---

## Portfolio Health — Expired Permit Noise

### 7. Active site with expired permit → ON_TRACK
- [ ] Go to /portfolio
- [ ] Find a property with an expired permit AND recent activity (e.g., 300 Howard St, activity within 90d)
- **PASS**: Shows green ON_TRACK badge, NOT yellow BEHIND or red AT_RISK.

### 8. Active site health reason cleared
- [ ] Same property as #7
- **PASS**: No health_reason text shown (no "permit expired Xd ago" message).

### 9. Properties with real issues still flagged
- [ ] Check any property with open violations or routing holds
- **PASS**: Still shows AT_RISK with appropriate reason (violations, holds, expiring-soon, stalled filing).

---

## "What Changed" — Permit Detail Cards

### 10. Morning brief shows permit details
- [ ] Go to /brief (or /brief?lookback=7 for wider window)
- [ ] Look at "What Changed" section
- **PASS**: Cards show permit number, permit type, and current status badge (e.g., "ISSUED", "FILED"). NOT generic "3d ago · 1 active of 2" for properties with identifiable permit changes.

### 11. Status badges render correctly
- [ ] In "What Changed" section, check cards that show a current status
- **PASS**: Status badge is colored appropriately (green for complete, blue for issued, etc.). If old_status is known, shows "OLD → NEW" arrow. If only current status known, shows just the badge.

### 12. Fallback still works for unidentifiable activity
- [ ] If any property shows the generic "Activity Xd ago" card format
- **PASS**: Card still displays cleanly with activity badge, active/total permits count. No broken layout or missing data.

---

## Regression Checks

### 13. Brief summary count matches cards
- [ ] On /brief, compare the "X Changed" count in the summary bar with the number of cards in "What Changed"
- **PASS**: Count is consistent (or close — count is property-level, cards may be permit-level).

### 14. Portfolio page loads without errors
- [ ] Go to /portfolio
- **PASS**: Page loads, all property cards render with health badges. No 500 errors.

### 15. Email brief sends correctly
- [ ] Check most recent morning brief email (if available)
- **PASS**: Email renders without broken HTML. "What Changed" items show permit details.
