"""Check that everything is in place to run the triage workflow.

    python -m scripts.check_setup
"""
from __future__ import annotations

import sys

from src.preflight import run_checks


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    checks = run_checks()
    for c in checks:
        mark = "OK  " if c.ok else ("FAIL" if c.blocking else "WARN")
        print(f"[{mark}] {c.name}: {c.message}")
        if not c.ok and c.fix:
            print(f"       What to do: {c.fix}")
    bad = [c for c in checks if not c.ok and c.blocking]
    print("\nReady." if not bad else f"\n{len(bad)} problem(s) must be fixed before the workflow can run.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
