# HIGH_RISK Compound Signal Validation Report

**Date:** 2026-02-23
**Data source:** Local DuckDB (sf_permits.duckdb) — 1.1M permits, 3.9M addenda, 509K violations, 671K inspections
**Spec validated:** severity-scoring-v2.md (5-tier model, HIGH_RISK compound signals)

---

## Signal Counts (individual)

| Signal | Properties | % of Total (165,853) | Assessment |
|---|---|---|---|
| Active holds | 301 | 0.18% | Tight — real signal |
| Open NOVs | 6,119 | 3.69% | Moderate — real signal |
| Expired uninspected | 357 | 0.22% | Tight — real signal |
| Stale with activity | 9,758 | 5.88% | **Noisy — needs tightening** |

## HIGH_RISK Candidates (compound)

**Total properties with 2+ AT_RISK signal types: 1,149 (0.69%)**

This is in the sweet spot — roughly **1 in 145 properties** has compound risk.

### By Pattern

| Pattern | Count | % of HIGH_RISK |
|---|---|---|
| nov + stale_with_activity | 948 | 82.5% |
| expired_uninspected + stale_with_activity | 50 | 4.4% |
| hold + stale_with_activity | 46 | 4.0% |
| expired_uninspected + nov | 43 | 3.7% |
| hold + nov | 32 | 2.8% |
| expired_uninspected + nov + stale_with_activity | 22 | 1.9% |
| hold + nov + stale_with_activity | 7 | 0.6% |
| hold + expired + nov + stale (all 4) | 1 | 0.1% |

### By signal count

| Signals | Properties |
|---|---|
| 2 types | 1,119 |
| 3 types | 29 |
| 4 types | 1 |

### Enrichment over random chance

| Pattern | Expected | Actual | Enrichment |
|---|---|---|---|
| hold + nov | 11.1 | 32 | **2.9x** |
| hold + stale_with_activity | 17.7 | 46 | **2.6x** |
| nov + expired_uninspected | 13.2 | 43 | **3.3x** |
| nov + stale_with_activity | 360.0 | 948 | **2.6x** |
| expired + stale | 21.0 | 50 | **2.4x** |
| hold + expired_uninspected | 0.6 | 0 | **0.0x** ← impossible |

All real patterns show **2.4-3.3x enrichment** — confirming these represent genuine correlation, not statistical noise. Properties with one problem tend to have others.

### HIGH_RISK by neighborhood (top 10)

| Neighborhood | Properties | Notes |
|---|---|---|
| Mission | 97 | Older stock, high enforcement activity |
| Tenderloin | 83 | SROs, hotels, high violation density |
| Bayview Hunters Point | 54 | |
| Nob Hill | 50 | |
| Financial District/South Beach | 47 | Commercial projects |
| South of Market | 45 | |
| West of Twin Peaks | 44 | |
| Hayes Valley | 42 | |
| Sunset/Parkside | 42 | |
| Russian Hill | 40 | |

---

## Top 10 HIGH_RISK Properties

### #1: 1281 8th Ave (1742/014) — Inner Sunset — **4 SIGNALS**
**Signals:** hold + nov + expired_uninspected + stale_with_activity

The only property with all 4 signal types. Fire-damaged 24-unit residential building with a $4.3M rehab permit (202412317573) currently in plan review. **Five** reviewers have issued comments (BLDG, MECH, SFFD, SFPUC stations). Five active NOVs from 2019-2023. An expired soft-story retrofit permit had 7 inspections but no final. A stale ADU legalization permit from 2017 remains in "issued" status.

**Assessment:** Textbook HIGH_RISK. An expediter would absolutely prioritize this property. The compound signals tell a coherent story of a fire-damaged multi-unit building in a complex rehab with enforcement pressure on multiple fronts.

### #2-6: 3-Signal Properties (nov + expired_uninspected + stale_with_activity)
- **1321 Columbus** (Russian Hill) — multi-permit renovation, 2 NOVs, 2 expired permits with 4-5 inspections each
- **821 Lombard** (Russian Hill) — apartment remodel, open NOV, expired permits with 8-9 inspections
- **1445 Leavenworth** (Russian Hill) — multiple unit remodels, 3 active NOVs, stale permits
- **570 O'Farrell** (Tenderloin) — hotel/restaurant with HCO violations, 9 NOVs, restaurant permit expired
- **61 Taylor** (Tenderloin) — **14 active NOVs** (mold, elevator, fire code), 9 stale permits, 2 expired uninspected

### #7-8: 3-Signal Properties (hold + nov + stale_with_activity)
- **2417 Green** (Pacific Heights) — horizontal addition stalled at CPB since 2022, open NOV
- **2050 Van Ness** (Russian Hill) — multiple stalled permits at CPB, 2 NOVs from 2013

### #9-10: 2-Signal Properties (hold + nov)
- **2154 Taylor** (Russian Hill) — ADU/soft-story with DPW holds (tree spacing, street improvements), active soft-story NOV
- **1210 Polk** (Nob Hill) — nuisance designation, 4 NOVs, expired permits

---

## Sample Deep Dives

### 1281 8th Ave — Fire-damaged multi-unit building (4 signals)
**The story:** A 24-unit residential building suffered a fire. The owner pulled multiple permits: soft-story retrofit, ADU legalization, soft demo of damaged units. The soft-story permit expired after 7 inspections but before final. The ADU legalization has been in "issued" status since 2021. Now a $4.3M full rehab is in plan review with holds at every station. Five NOVs remain open from 2019-2023.
**Would an expediter care?** Absolutely. This is a complex, multi-agency project with active enforcement and significant financial exposure.

### 134 Tiffany (Bernal Heights) — Chronic code violator (3 signals)
**The story:** 30 active NOVs including a nuisance designation. Multiple expired permits with inspections but no final. The owner just filed a $340K "recommencement" permit in 2025 to finish work under older expired permits. Active complaints from tenants about construction noise, broken kitchen, inadequate heating. A pattern spanning years.
**Would an expediter care?** Yes — this is a property owner who needs professional help navigating the enforcement debt accumulated over years of incomplete work.

### 3431 20th St (Mission) — Active construction with deep compliance debt (3 signals)
**The story:** 32 active NOVs. A $280K recommencement permit was filed Feb 2026. Ongoing complaints about leaks, rodents, egress obstruction. Active construction (rough frame, insulation inspections as recent as Aug 2025) alongside unresolved violations.
**Would an expediter care?** Yes — this is a property where work IS happening but the compliance burden is enormous.

### 2154 Taylor (Russian Hill) — Blocked project with enforcement (2 signals: hold + nov)
**The story:** An ADU addition and soft-story retrofit (permit from 2019) has holds at DPW-BUF (tree spacing) and DPW-BSM (street improvements). An active NOV for soft-story compliance creates enforcement pressure. The permit has been in review for 7+ years.
**Would an expediter care?** Yes — this is the classic "blocked at agency" + "enforcement clock ticking" compound that demands professional intervention.

### 2083 San Jose (Outer Mission) — Chronic unpermitted work (2 signals: nov + expired)
**The story:** Open NOVs from 2008 (illegal extension) and 2014 (fire damage). Multiple permits pulled to address violations — all expired before completion. Neighbor complaints about unpermitted construction. A pattern suggesting the owner is repeatedly attempting work without finishing the permit process.
**Would an expediter care?** Yes, though this may need an attorney too — the enforcement history is deep.

---

## Data Quality Issues Identified

### 1. `stale_with_activity` is too noisy at 5.88%

**Root cause:** 12,480 of 14,391 stale permits (87%) are OTC alterations (type 8). These are low-complexity permits where DBI routinely issues them, work gets done, but the permit is never formally closed. The inspection data confirms activity occurred, but "issued" is likely just an unclosed administrative state.

**Recommended tightening:** 2-7 year window + require 2+ real inspections:

| Variant | Properties | % of total |
|---|---|---|
| Current (2yr+, 1+ insp) | 9,758 | 5.88% |
| 2yr+, 2+ inspections | 6,008 | 3.62% |
| **2-7yr, 2+ inspections** | **3,147** | **1.90%** |
| 2-10yr, 2+ insp, non-OTC only | 1,003 | 0.60% |

With the recommended filter (2-7yr, 2+ insp), HIGH_RISK drops from 1,149 → **535 properties (0.32%)**, still healthy. The `nov + stale_with_activity` pattern drops from 948 to 386, making the pattern distribution more balanced.

### 2. `hold + expired_uninspected` is logically impossible

This pattern shows 0 overlap because holds only apply to active permits (issued/filed/approved) while expired_uninspected applies to expired permits. **Remove this compound pattern from the spec.** A hold on one permit and an expired uninspected permit at the same property IS captured — it just shows up as `hold + expired_uninspected + [other]`, which requires a NOV or stale signal to trigger anyway.

### 3. Addenda stall detection includes old data artifacts

The "stalled at station" detection (no result, no finish_date) captures 2,222 permits including records from the 1980s-90s at the CPB station. These are clearly data import artifacts, not real holds. The 2020+ recency filter used in this analysis is essential and should be hardcoded into the signal detection logic.

### 4. Hold detection: "Issued Comments" vs "stalled" are different signals

Station-level "Issued Comments" (88 permits, 80 properties) = reviewer explicitly sent comments back. This is a real, actionable hold with a specific station and reviewer.

"Stalled" (254 recent permits, 231 properties) = routing record with no result and no finish, arrived 30+ days ago. This is a softer signal — could be awaiting assignment, or simply a data lag.

**Recommendation:** Weight "Issued Comments" higher than generic stall in the severity model.

---

## Validation Verdict

| Question | Answer |
|---|---|
| Do compound patterns exist at meaningful rates? | **Yes** — 0.69% (1,149 properties), or 0.32% with tightened stale filter |
| Do they represent real risk? | **Yes** — 2.4-3.3x enrichment over random; all deep dives show genuine distress |
| Any patterns that are data artifacts? | `hold + expired_uninspected` is logically impossible; `stale_with_activity` needs tightening |
| Would an expediter care about these properties? | **Yes** — every deep dive property tells a coherent story of real compliance risk |
| Is the model ready for Amy validation? | **Yes, with the three refinements above** |

### Recommended spec changes before Amy review

1. **Remove** `hold + expired_uninspected` pattern (logically impossible)
2. **Tighten** `stale_with_activity`: 2-7yr window + 2+ real inspections (reduces from 5.88% to 1.90%)
3. **Split** hold detection into `hold_comments` (Issued Comments) and `hold_stalled` (no result/finish), with `hold_comments` weighted higher
4. **Hardcode** addenda recency filter (2020+) into hold/stall detection
5. **Add** `hold_stalled` as `behind` severity rather than `at_risk` (softer signal)
