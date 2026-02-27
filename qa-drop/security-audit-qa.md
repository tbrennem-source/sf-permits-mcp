# QA Script: Security Audit Tooling (Sprint 74-3)

Self-contained. No credentials needed. Requires: Python venv active.

---

## 1. File Existence Checks

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
```

- [ ] `ls scripts/security_audit.py` → file exists
  PASS: exits 0
  FAIL: file missing

- [ ] `ls .bandit` → file exists
  PASS: exits 0
  FAIL: file missing

- [ ] `ls .github/workflows/security.yml` → file exists
  PASS: exits 0
  FAIL: file missing

---

## 2. Pytest Suite

```bash
source .venv/bin/activate
pytest tests/test_sprint_74_3.py -v
```

PASS: 29 passed, 0 failed
FAIL: any test failure

---

## 3. Script Import

```bash
source .venv/bin/activate
python -c "import importlib.util; spec = importlib.util.spec_from_file_location('sa', 'scripts/security_audit.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('OK:', [f for f in dir(m) if not f.startswith('_')])"
```

PASS: "OK:" printed, includes `main`, `run_bandit`, `run_pip_audit`, `build_report`
FAIL: ImportError or missing functions

---

## 4. Script Runs Without Tools Installed (graceful degradation)

```bash
source .venv/bin/activate
# Run with tools not on PATH by temporarily using a minimal PATH
PATH=/usr/bin:/bin python scripts/security_audit.py
```

PASS: Script completes without traceback, report written to `qa-results/security-audit-latest.md`, output contains "SKIPPED" lines for missing tools
FAIL: Python exception / traceback printed

---

## 5. Report File Created

```bash
source .venv/bin/activate
python scripts/security_audit.py
cat qa-results/security-audit-latest.md | head -20
```

PASS: Report starts with `# Security Audit Report`, contains `## Summary` section
FAIL: File missing or empty

---

## 6. .bandit Config Validation

```bash
grep -n "B101\|tests\|\[bandit\]" .bandit
```

PASS: Shows `[bandit]` section, `B101` in skips, `tests` in exclude_dirs
FAIL: Missing any of those lines

---

## 7. Workflow YAML Validity

```bash
source .venv/bin/activate
python -c "import yaml; d=yaml.safe_load(open('.github/workflows/security.yml')); print('Jobs:', list(d.get('jobs', {}).keys()))"
```

PASS: Prints "Jobs: ['security-audit']" (or similar job name)
FAIL: YAML parse error

---

## 8. Workflow Has Required Triggers

```bash
grep -E "cron|push:|0 6|main" .github/workflows/security.yml
```

PASS: Lines present for both schedule cron `0 6 * * 0` and `push:` with `main`
FAIL: Missing either trigger

---

## 9. Exit Code 1 on Mocked HIGH Issue

```bash
source .venv/bin/activate
python - << 'EOF'
import sys
from unittest.mock import patch

sys.path.insert(0, '.')
from scripts.security_audit import main

high_bandit = {
    "available": True,
    "issues": [{"severity": "HIGH", "confidence": "HIGH", "test_id": "B602",
                "test_name": "shell", "filename": "f.py", "line_number": 1,
                "issue_text": "shell=True", "code": ""}],
    "high_count": 1, "medium_count": 0, "low_count": 0, "raw": "", "error": None,
}
clean_pip = {"available": True, "vulnerabilities": [], "high_count": 0, "raw": "", "error": None}

with patch("scripts.security_audit.run_bandit", return_value=high_bandit), \
     patch("scripts.security_audit.run_pip_audit", return_value=clean_pip):
    rc = main()

print(f"Exit code: {rc}")
assert rc == 1, f"Expected 1, got {rc}"
print("PASS")
EOF
```

PASS: "Exit code: 1" and "PASS" printed
FAIL: Exit code != 1 or assertion error

---

## 10. Edge Case: Empty JSON from bandit

```bash
source .venv/bin/activate
python - << 'EOF'
from unittest.mock import patch
from scripts.security_audit import run_bandit
from pathlib import Path

with patch("scripts.security_audit.check_tool_available", return_value=True), \
     patch("scripts.security_audit.run_command", return_value=(1, "not-json!!!", "")):
    result = run_bandit(Path("."))

assert result["error"] is not None
assert "json" in result["error"].lower() or "parse" in result["error"].lower()
print("PASS: invalid JSON handled gracefully, error:", result["error"])
EOF
```

PASS: "PASS: invalid JSON handled gracefully" printed
FAIL: Exception raised or error is None
