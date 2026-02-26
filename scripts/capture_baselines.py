#!/usr/bin/env python3
"""Capture visual baselines for the current sprint.

Thin wrapper around visual_qa.py that sets up the right flags for
golden baseline capture. Run before each sprint to establish
regression baselines.

Usage:
    # Local (auto-start Flask not supported — start server first):
    python scripts/capture_baselines.py http://localhost:5001 sprint69

    # Against staging:
    TEST_LOGIN_SECRET=xxx python scripts/capture_baselines.py \
        https://sfpermits-ai-staging-production.up.railway.app sprint69

    # With journey recordings:
    TEST_LOGIN_SECRET=xxx python scripts/capture_baselines.py \
        https://sfpermits-ai-staging-production.up.railway.app sprint69 --journeys
"""

import os
import subprocess
import sys


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5001"
    sprint = sys.argv[2] if len(sys.argv) > 2 else "current"
    extra_args = sys.argv[3:] if len(sys.argv) > 3 else []

    secret = os.environ.get("TEST_LOGIN_SECRET", "")

    cmd = [
        sys.executable, "scripts/visual_qa.py",
        "--url", url,
        "--sprint", sprint,
        "--capture-goldens",
    ]
    cmd.extend(extra_args)

    env = os.environ.copy()
    if secret:
        env["TEST_LOGIN_SECRET"] = secret

    print(f"Capturing baselines for {sprint} against {url}")
    if not secret:
        print("  WARNING: TEST_LOGIN_SECRET not set — auth/admin pages will be skipped")
    print(f"  Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, env=env)

    if result.returncode == 0:
        print(f"\nBaselines saved to qa-results/baselines/{sprint}/")
        print("Next steps:")
        print(f"  1. Review screenshots in qa-results/screenshots/{sprint}/")
        print(f"  2. After sprint work, run: python scripts/visual_qa.py --url {url} --sprint {sprint}")
        print("  3. Review diffs for >5% pixel change")
    else:
        print(f"\nBaseline capture failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
