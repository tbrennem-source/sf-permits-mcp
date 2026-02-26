"""Sprint 57 Methodology Transparency QA — Steps 1-5 (tool-level checks).

Runs without a browser; uses Python directly.
"""
import sys
import os
import asyncio
from unittest.mock import patch, MagicMock

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

RESULTS = []


def record(step, name, status, notes=""):
    RESULTS.append((step, name, status, notes))
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{icon}] Step {step}: {name}" + (f" — {notes}" if notes else ""))


def make_mock_conn():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    return mock_conn


# ---------------------------------------------------------------------------
# STEPS 1-3: return_structured backward compat + methodology dict keys
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"tool", "headline", "formula_steps", "data_sources",
                 "sample_size", "data_freshness", "confidence", "coverage_gaps"}

TOOLS = [
    ("estimate_fees", "src.tools.estimate_fees", dict(permit_type="alterations", estimated_construction_cost=50000)),
    ("estimate_timeline", "src.tools.estimate_timeline", dict(permit_type="alterations")),
    ("predict_permits", "src.tools.predict_permits", dict(project_description="Kitchen remodel in SoMa")),
    ("required_documents", "src.tools.required_documents", dict(permit_forms=["Form 3/8"], review_path="in_house")),
    ("revision_risk", "src.tools.revision_risk", dict(permit_type="alterations")),
]


def run_tool(fn, **kwargs):
    return asyncio.run(fn(**kwargs))


print("\n=== STEP 1: return_structured=False returns str ===")

mock_conn = make_mock_conn()
patches = [
    patch("src.tools.estimate_fees.get_connection", return_value=mock_conn),
    patch("src.tools.estimate_timeline.get_connection", return_value=mock_conn),
    patch("src.tools.revision_risk.get_connection", return_value=mock_conn),
    patch("src.tools.estimate_fees.BACKEND", "duckdb"),
    patch("src.tools.estimate_timeline.BACKEND", "duckdb"),
    patch("src.tools.revision_risk.BACKEND", "duckdb"),
]
for p in patches:
    p.start()

all_str_ok = True
for tool_name, module_path, kwargs in TOOLS:
    try:
        module = __import__(module_path, fromlist=[tool_name])
        fn = getattr(module, tool_name)
        result = run_tool(fn, **kwargs)
        if isinstance(result, str):
            record(1, f"{tool_name} returns str", "PASS")
        else:
            record(1, f"{tool_name} returns str", "FAIL", f"Got {type(result).__name__}")
            all_str_ok = False
    except Exception as e:
        record(1, f"{tool_name} returns str", "FAIL", str(e))
        all_str_ok = False

print("\n=== STEP 2: return_structured=True returns (str, dict) tuple ===")

all_tuple_ok = True
for tool_name, module_path, kwargs in TOOLS:
    try:
        module = __import__(module_path, fromlist=[tool_name])
        fn = getattr(module, tool_name)
        result = run_tool(fn, return_structured=True, **kwargs)
        if isinstance(result, tuple) and len(result) == 2:
            md, meta = result
            if isinstance(md, str) and isinstance(meta, dict):
                record(2, f"{tool_name} returns (str, dict)", "PASS")
            else:
                record(2, f"{tool_name} returns (str, dict)", "FAIL",
                       f"md={type(md).__name__}, meta={type(meta).__name__}")
                all_tuple_ok = False
        else:
            record(2, f"{tool_name} returns (str, dict)", "FAIL",
                   f"Got {type(result).__name__}, len={len(result) if isinstance(result, tuple) else 'N/A'}")
            all_tuple_ok = False
    except Exception as e:
        record(2, f"{tool_name} returns (str, dict)", "FAIL", str(e))
        all_tuple_ok = False

print("\n=== STEP 3: Methodology dict has required keys ===")

all_keys_ok = True
for tool_name, module_path, kwargs in TOOLS:
    try:
        module = __import__(module_path, fromlist=[tool_name])
        fn = getattr(module, tool_name)
        result = run_tool(fn, return_structured=True, **kwargs)
        if isinstance(result, tuple):
            _, meta = result
            missing = REQUIRED_KEYS - meta.keys()
            if not missing:
                record(3, f"{tool_name} has all 8 keys", "PASS")
            else:
                record(3, f"{tool_name} has all 8 keys", "FAIL", f"Missing: {missing}")
                all_keys_ok = False
        else:
            record(3, f"{tool_name} has all 8 keys", "FAIL", "Not a tuple")
            all_keys_ok = False
    except Exception as e:
        record(3, f"{tool_name} has all 8 keys", "FAIL", str(e))
        all_keys_ok = False

for p in patches:
    p.stop()

# ---------------------------------------------------------------------------
# STEP 4: Fee estimate has Cost Revision Risk section (cost=50000)
# ---------------------------------------------------------------------------

print("\n=== STEP 4: Fee estimate includes Cost Revision Risk ===")

mock_conn2 = make_mock_conn()
with patch("src.tools.estimate_fees.get_connection", return_value=mock_conn2), \
     patch("src.tools.estimate_fees.BACKEND", "duckdb"):
    from src.tools.estimate_fees import estimate_fees
    result = asyncio.run(estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=50000,
    ))

has_revision_risk = "Cost Revision Risk" in result
has_ceiling = "ceiling" in result.lower()

if has_revision_risk and has_ceiling:
    record(4, "estimate_fees has Cost Revision Risk + ceiling", "PASS")
elif has_revision_risk:
    record(4, "estimate_fees has Cost Revision Risk (no ceiling)", "FAIL",
           "'ceiling' not found in output")
else:
    record(4, "estimate_fees has Cost Revision Risk", "FAIL",
           "'Cost Revision Risk' not in output")

# ---------------------------------------------------------------------------
# STEP 5: Coverage disclaimers in all tool outputs
# ---------------------------------------------------------------------------

print("\n=== STEP 5: Coverage disclaimers in all tool outputs ===")

mock_conn3 = make_mock_conn()
with patch("src.tools.estimate_fees.get_connection", return_value=mock_conn3), \
     patch("src.tools.estimate_timeline.get_connection", return_value=mock_conn3), \
     patch("src.tools.revision_risk.get_connection", return_value=mock_conn3), \
     patch("src.tools.estimate_fees.BACKEND", "duckdb"), \
     patch("src.tools.estimate_timeline.BACKEND", "duckdb"), \
     patch("src.tools.revision_risk.BACKEND", "duckdb"):

    all_coverage_ok = True
    for tool_name, module_path, kwargs in TOOLS:
        try:
            module = __import__(module_path, fromlist=[tool_name])
            fn = getattr(module, tool_name)
            result = run_tool(fn, **kwargs)
            if "## Data Coverage" in result:
                record(5, f"{tool_name} has '## Data Coverage'", "PASS")
            else:
                record(5, f"{tool_name} has '## Data Coverage'", "FAIL",
                       "'## Data Coverage' not found in output")
                all_coverage_ok = False
        except Exception as e:
            record(5, f"{tool_name} has '## Data Coverage'", "FAIL", str(e))
            all_coverage_ok = False

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
pass_count = sum(1 for _, _, s, _ in RESULTS if s == "PASS")
fail_count = sum(1 for _, _, s, _ in RESULTS if s == "FAIL")
print(f"PASS: {pass_count}  FAIL: {fail_count}  TOTAL: {len(RESULTS)}")

# Write structured results for the QA output file
import json
with open("/tmp/sprint57_step1to5_results.json", "w") as f:
    json.dump(RESULTS, f, indent=2)

print("\nResults saved to /tmp/sprint57_step1to5_results.json")

if fail_count > 0:
    sys.exit(1)
