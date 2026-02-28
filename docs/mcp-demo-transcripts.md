# MCP Demo Transcripts

Pre-written conversation transcripts for the landing page animated demo section.
Used by web/templates/components/mcp_demo.html — use EXACT text from Demo 1, Demo 2, and Demo 6.

Demo rotation order on landing page: **Demo 2 → Demo 1 → Demo 6** (What-If leads, then Stuck, then Delay).

---

## Demo 2: What-If Scope Comparison

**Tool used:** `what_if_simulator`

---

**User:** What's the difference in timeline if I add a bathroom remodel to my kitchen permit?

**[Tool call: what_if_simulator]**

**Claude:**

Here's the comparison for your kitchen-only scope versus kitchen + bathroom + wall removal:

| | Kitchen Only | Kitchen + Bath + Wall |
|---|---|---|
| **Estimated Cost** | $45,000 | $185,000 |
| **Review Path** | OTC (Over Counter) | In-House |
| **Agencies** | 1 (DBI) | 7 (DBI, Planning, SFFD, DPH, SFPUC, DPW, Structural) |
| **Timeline (p50)** | ~2 weeks | 70 days |
| **Timeline (p75)** | ~3 weeks | 113 days |
| **DBI Fees** | $1,200 | $6,487 |
| **Plans Signed By** | Contractor OK | Licensed Architect required |
| **ADA Required** | No | Yes — path of travel |
| **Revision Risk** | Low | High (24.6%) |

**The wall removal is the trigger.** Removing a wall requires structural calculations, which pulls you from OTC into in-house review. That single change adds 7 agencies and ~56 days to your timeline.

**Strategy:** Consider splitting into two permits — kitchen first (OTC, issued in days), then wall + bath as a second permit. You can often start kitchen work while the second permit is in review.

---

## Demo 1: Stuck Permit Diagnosis

**Tool used:** `diagnose_stuck_permit`

---

**User:** Permit 202412237330 has been sitting for 7 months. Can you tell me what's going on?

**[Tool call: diagnose_stuck_permit]**

**Claude:**

**CRITICAL — 4 SIMULTANEOUS BLOCKS** on permit 202412237330 (Laundromat → Childcare Conversion, $200K)

This permit is stuck at 4 stations at once. That's rare and serious.

**Active blocks:**

| Station | Status | Reviewer | Issue |
|---|---|---|---|
| BLDG | 2nd round of comments | Jeff Ibarra | Occupancy load calc missing |
| MECH | Comments issued | Ray Chen | Ventilation design insufficient for childcare use |
| SFFD | Comments issued | M. Torres | Fire suppression plan incomplete |
| CP-ZOC | 223 days — no action | Wesley Wong | Change of use requires conditional use hearing |

**The real problem:** CP-ZOC (Planning's Zoning & Occupancy Change desk) has had this for 223 days without a final determination. The other 3 stations are waiting on CP-ZOC to clear before they'll issue final approvals.

**Intervention playbook:**

1. **Address BLDG + MECH + SFFD comments NOW** — respond to all 3 agencies in one resubmission. Don't wait for CP-ZOC to clear first.
2. **Call Planning (628-652-7600) about CP-ZOC. Ask for Wesley Wong.** This project needs a conditional use hearing scheduled — that's the blocker.
3. **Upload corrected sheets with revision clouds (EPR-025).** Each comment cycle without revision clouds adds 2-3 weeks to BLDG review.

**Timeline impact:** Each comment-response cycle adds 6-8 weeks. With 4 simultaneous blocks, you're looking at 4-6 months minimum if you start now.

---

## Demo 6: Cost of Delay

**Tool used:** `estimate_timeline`

---

**User:** My restaurant renovation has a $15,000/month carry cost. How much is this permit delay going to cost me?

**[Tool call: estimate_timeline]**

**Claude:**

With a $15,000/month carrying cost ($500/day), here's the financial exposure for your restaurant alteration permit:

| Scenario | Days | Carrying Cost |
|---|---|---|
| **Best case (p25)** | 35 days | $17,500 |
| **Typical (p50)** | 70 days | $35,000 |
| **Conservative (p75)** | 113 days | $56,500 |
| **Worst case (p90)** | 174 days | $87,000 |

**Probability-weighted expected cost: $41,375**

⚠️ **SFFD-HQ bottleneck alert:** SFFD-HQ is currently running 86% slower than baseline — average 34 days at this station vs. the typical 18. Restaurant permits route through SFFD-HQ for fire suppression review. If your plans have any suppression work, budget for the conservative (p75) scenario, not p50.

**Recommendation:** Budget for $56,500 in carrying costs (p75), not $35,000. If SFFD comments come back with corrections, you're looking at one additional cycle — add $21,000 to your contingency.

---

## Notes for Implementation

- **Demo 2** leads the rotation because the comparison table communicates value instantly — no explanation needed
- **Demo 1** follows with depth — shows the system knows WHO to call and what to say
- **Demo 6** closes with emotional hook — $500/day makes the value of speed visceral
- Tool call badge text: `what_if_simulator`, `diagnose_stuck_permit`, `estimate_timeline`
- Tables should render as pre-built HTML blocks (not typed character by character)
- Risk meters / gauges render as pre-built HTML (not typed)
