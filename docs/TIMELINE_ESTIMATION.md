# Timeline Estimation Strategy

How sfpermits.ai estimates permit processing timelines from historical data.

## Models

### Station-Sum Model (Primary)

The primary timeline model sums median review times across individual DBI plan review stations.

**Data source:** `station_velocity_v2` table, computed from 3.9M+ addenda routing records.

**How it works:**
1. For a given permit type and triggers, determine the relevant review stations (e.g., BLDG, CP-ZOC, SFFD-HQ)
2. Look up each station's p50 (median) review duration from the velocity table
3. Sum the station p50 values for a sequential estimate
4. Report p25/p50/p75/p90 percentiles for the combined timeline

**Data scrub filters:**
- Exclude pre-2018 data (sparse, inconsistent)
- Exclude "Not Applicable" and "Administrative" review results (pass-throughs)
- Exclude NULL stations
- Deduplicate reassignment dupes (same permit+station+addenda_number -> latest finish_date)
- Separate initial review (addenda_number=0) from revision cycles (addenda_number>=1)
- Exclude durations < 0 or > 365 days (outliers)

**Period strategy:**
- `current`: Rolling 90-day window (primary for estimates)
- `baseline`: Rolling 365-day window (for trend comparison)
- If a station has < 30 samples in the 90-day window, automatically widens to 180 days

### Neighborhood Stratification (Sprint 66)

When a neighborhood is provided, the system tries neighborhood-specific velocity data first.

**Data source:** `station_velocity_v2_neighborhood` table, joining addenda with permits.

**How it works:**
1. Query the neighborhood velocity table for (station, neighborhood) combinations
2. If data exists (>= 10 samples per station-neighborhood pair), use it
3. If no neighborhood data exists, fall back to station-only baselines
4. Output indicates "Neighborhood-specific" when stratified data is used

This captures neighborhood-level variation in review times (e.g., some neighborhoods have more complex projects that take longer at certain stations).

### Aggregate Percentile Model (Fallback)

When no station velocity data is available, falls back to aggregate permit statistics.

**Data source:** `timeline_stats` table, computed from 1.1M+ historical permits.

**Filters:**
- 1-year recency window (issued >= CURRENT_DATE - 1 year)
- Excludes electrical, plumbing, and mechanical trade permits
- Progressive widening: if neighborhood+cost+type has < 10 samples, widens filters

## Delay Factors and Triggers

Certain project characteristics trigger additional delay estimates:

| Trigger | Impact | Related Stations |
|---------|--------|-----------------|
| `change_of_use` | +30 days minimum | Section 311 notification |
| `planning_review` | +2-6 weeks | CP-ZOC |
| `dph_review` | +2-4 weeks | HEALTH, HEALTH-FD |
| `fire_review` | +1-3 weeks | SFFD, SFFD-HQ |
| `historic` | +4-12 weeks | HIS |
| `ceqa` | +3-12 months | Environmental review |
| `multi_agency` | +1-2 weeks per agency | DPW-BSM, SFPUC |
| `conditional_use` | +3+ months | Planning Commission |

Triggers are mapped to station codes via `TRIGGER_STATION_MAP` in `estimate_timeline.py`.

## Trend Detection

### Station-Level Trends

Each station's current p50 is compared to its 365-day baseline:
- **> +15%**: Flagged as "slower" with upward arrow
- **< -15%**: Flagged as "faster" with downward arrow
- **Within +/-15%**: "Normal"

### Data Quality Trend Check

The `_check_velocity_trends()` DQ check (Sprint 66) compares all stations' current p50 values to their baselines and flags any station >15% slower. This surfaces in the Admin DQ dashboard as a warning.

## Confidence Levels

| Level | Criteria |
|-------|----------|
| **High** | Station-sum model with >= 100 total routing records |
| **Medium** | Station-sum < 100 samples, or aggregate model with >= 10 permits |
| **Low** | Knowledge-based estimates (no DB data), or < 10 permits |

## Cost of Delay (Sprint 60C)

When a `monthly_carrying_cost` is provided, the tool computes:
- Daily and weekly carrying costs
- Total carrying cost for p50, p75, and p90 scenarios
- Incremental cost of delay (p75 - p50 difference)

## Architecture

```
estimate_timeline()
  ├── _query_station_velocity_v2(stations, neighborhood)
  │     ├── _query_neighborhood_velocity()   # Sprint 66: try first
  │     └── station_velocity_v2 table        # fallback
  ├── _compute_station_sum()                 # Primary model
  ├── _query_station_baseline()              # For trend arrows
  ├── _query_timeline()                      # Fallback model
  ├── _query_trend()                         # Recent vs prior
  └── DELAY_FACTORS                          # Trigger-based delays
```

## Limitations

- Station-sum assumes sequential review, but some stations may review in parallel
- 90-day rolling window may miss seasonal patterns
- Neighborhood stratification requires >= 10 samples per station-neighborhood pair, which may not be available for less active neighborhoods
- Trade permits (electrical, plumbing, mechanical) are excluded and have different timelines
- Pre-2018 data is excluded entirely due to quality issues
- Self-reported cost data may be inaccurate, affecting cost bracket matching
