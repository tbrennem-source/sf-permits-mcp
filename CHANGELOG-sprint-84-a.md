## Sprint 84-A: DB Pool Tuning
- Increased DB_POOL_MIN from 2 to 5, DB_POOL_MAX from 20 to 50
- Added pool exhaustion warning at >80% utilization (configurable via DB_POOL_WARN_THRESHOLD)
- Documented pool env vars in ONBOARDING.md
