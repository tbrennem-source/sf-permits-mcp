# SF DBI Building Permit Addenda & Routing Data Exploration Report

**Dataset**: `87xy-gk8d` on data.sfgov.org
**Total Records**: **3,920,710**
**Unique Permits**: **1,062,924**
**Average routing rows per permit**: ~3.7

## 1. Station Distribution (Top 15)

| Rank | Station | Count | % of Total | Description |
|---|---|---|---|---|
| 1 | **CPB** | 1,096,858 | 28.0% | Central Permit Bureau |
| 2 | **BLDG** | 415,665 | 10.6% | Building review |
| 3 | **CP-ZOC** | 337,405 | 8.6% | Planning - Zoning |
| 4 | **SFFD** | 311,262 | 7.9% | Fire Department |
| 5 | **INTAKE** | 272,247 | 6.9% | Intake processing |
| 6 | **CNT-PC** | 231,273 | 5.9% | Counter - Plan Check |
| 7 | **HIS** | 152,706 | 3.9% | Historic Preservation |
| 8 | **MECH** | 139,633 | 3.6% | Mechanical review |
| 9 | **DPW-BSM** | 134,540 | 3.4% | DPW - Bureau of Street Mapping |
| 10 | **BID-INSP** | 122,970 | 3.1% | Building Inspection Div |
| 11 | **SFPUC** | 89,744 | 2.3% | Public Utilities Commission |
| 12 | **PAD-PC** | 79,916 | 2.0% | PAD Plan Check |
| 13 | **PAD-MECH** | 73,763 | 1.9% | PAD Mechanical |
| 14 | **PPC** | 58,311 | 1.5% | Planning - PPC |
| 15 | **ONE-STOP** | 50,496 | 1.3% | One-Stop counter |

**Key finding**: CPB alone handles 28% of all routing. Top 5 stations = 62% of records.

## 2. Review Results Distribution

| Review Result | Count | % of Total |
|---|---|---|
| **(NULL/empty)** | **3,553,260** | **90.6%** |
| Approved | 167,683 | 4.3% |
| Administrative | 144,313 | 3.7% |
| Issued Comments | 38,926 | 1.0% |
| Not Applicable | 11,324 | 0.3% |
| Approved-Stipulated | 3,760 | 0.1% |
| In Progress | 1,166 | <0.1% |
| Denied | 278 | <0.1% |

**Critical finding**: 90.6% have NO review_results value. Only ~367K records (9.4%) carry explicit outcomes. Denial rate is 0.007%.

## 3. Station Velocity (Avg Days: Arrive→Finish, Last 90 Days)

| Station | Avg Days | Record Count | Interpretation |
|---|---|---|---|
| **INTAKE** | 0.002 | 5,317 | Near-instant (automated) |
| **HIS** | 0.004 | 1,316 | Near-instant (quick screening) |
| **BID-INSP** | 2.8 | 614 | Fast turnaround |
| **SFPUC** | 2.9 | 1,713 | ~3 business days |
| **DPW-BSM** | 3.1 | 966 | ~3 business days |
| **BLDG** | 3.2 | 5,334 | ~3 business days |
| **MECH-E** | 3.5 | 1,109 | ~3-4 business days |
| **MECH** | 4.5 | 2,235 | ~4-5 business days |
| **CPB** | 4.5 | 6,262 | ~4-5 business days |
| **CP-ZOC** | 6.4 | 3,174 | ~6 business days |
| **PAD-STR** | 13.3 | 705 | ~2 weeks |
| **DPW-BUF** | 16.3 | 384 | ~2-3 weeks |
| **SFFD** | 23.7 | 3,800 | **~3-4 weeks** |
| **PERMIT-CTR** | 32.8 | 611 | **~1 month** |
| **PPC** | **174.0** | 545 | **~6 months** |

**Critical findings**:
- INTAKE/HIS are pass-through (near-zero days)
- Core stations (BLDG, CPB, MECH) average 3-5 business days
- **SFFD is a bottleneck at 24 days**
- **PPC is the biggest bottleneck at 174 days** (discretionary/environmental review)

## 4. Addenda Number Distribution

| Addenda # | Count | % of Total | Cumulative |
|---|---|---|---|
| **0** (original) | **3,723,141** | **94.96%** | 94.96% |
| 1 | 141,815 | 3.62% | 98.58% |
| 2 | 20,704 | 0.53% | 99.11% |
| 3 | 12,328 | 0.31% | 99.42% |
| 4-9 | 18,845 | 0.48% | 99.90% |
| 10-31 | 3,907 | 0.10% | 100.00% |

**Key**: 95% are original routing (addenda #0). Most revised permits only need 1 revision.

## 5. Department Distribution

| Department | Count | % |
|---|---|---|
| **DBI** | 2,954,526 | 75.4% |
| **CPC** (Planning) | 372,906 | 9.5% |
| **SFFD** | 312,044 | 8.0% |
| **DPW** | 140,038 | 3.6% |
| **PUC** | 90,050 | 2.3% |
| **DPH** (Health) | 29,329 | 0.7% |
| Others | 22,817 | 0.5% |

## 6. Hold Descriptions

**34.4% of records have hold descriptions** (1,349,454 rows).
Hold descriptions are free-text and highly inconsistent. OTC (Over-The-Counter) is a major workflow pattern. "log out/no work done" entries (32K+) represent pass-through routing.

## 7. Top Reviewers

| Rank | Reviewer | Count |
|---|---|---|
| - | (NULL/empty) | 655,080 |
| 1 | BUFKA SUSAN | 76,582 |
| 2 | SHAWL HAREGGEWAIN | 67,227 |
| 3 | CHUNG JANCE | 64,804 |
| 4 | SHEK KATHY | 49,277 |
| 5 | YU ZHANG REN | 46,618 |

## 8. Key Ratios

- **3.7 routing rows per permit** average
- **5% of rows are actual revisions** (addenda >= 1)
- **9.4% of rows have explicit review outcomes**
- **34% of rows have hold descriptions** (mostly free-text)
- **75% of routing is DBI-internal**, 25% external departments
- **Denial rate: 0.007%** (278 of 3.9M)

## Feature Implications

1. **Station Velocity Dashboard** — velocity data is extremely actionable ("SFFD typically takes 3-4 weeks")
2. **Bottleneck Alerts** — SFFD (24d), PERMIT-CTR (33d), PPC (174d)
3. **Addenda Predictor** — predict revision likelihood from project type + station patterns
4. **OTC Detection** — identify streamlined OTC vs full plan review paths
5. **Reviewer Workload Patterns** — turnaround by reviewer (privacy considerations)

## Data Quality Notes

- 90.6% null review_results (most rows are intermediate steps)
- Hold descriptions need NLP normalization for structured use
- ~8 records with impossible dates (1721, 2205) — filter to 1990-2027
- Dataset refreshes continuously via SODA despite data_as_of showing 2025-06-23
