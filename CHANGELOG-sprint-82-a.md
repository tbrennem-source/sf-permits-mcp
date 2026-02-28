## Sprint 82-A — Register 4 intelligence tools in MCP server (30→34 tools)

### Changed
- `src/server.py`: Registered 4 Phase 9 intelligence tools built in QS8/Sprint 80:
  - `predict_next_stations` (from `src.tools.predict_next_stations`) — What's Next station predictor; uses historical transition probabilities and velocity estimates
  - `diagnose_stuck_permit` (from `src.tools.stuck_permit`) — Stuck permit intervention playbook; diagnoses dwell time, revision backlog, inter-agency holds
  - `simulate_what_if` (from `src.tools.what_if_simulator`) — Side-by-side project variation comparison (timeline, fees, review path, revision risk)
  - `calculate_delay_cost` (from `src.tools.cost_of_delay`) — Financial cost of permit processing delays with carrying cost and revision risk
- Tool count: 30 → 34
- Phase label: Phase 9 (permit intelligence — station prediction, stuck permits, simulation, delay cost)

### Tests
- `pytest -k "server"`: 1 passed
- `python -c "from src.server import mcp"`: import succeeds, all 34 tools registered
