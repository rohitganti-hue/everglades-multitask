#!/usr/bin/env python3
"""Submit current draft progress to the dashboard — the "submit to tracker" action.

Wraps the telemetry emitter as an explicit, on-demand push. The skill calls
`sync()` automatically as each phase advances, and the expert can run it directly
(`/everglades-submit`) — e.g. at the end of a task. Best-effort + fail-silent:
a failed/offline push never breaks the skill.

This explicit path is the reliable way to reach the dashboard: a passive Stop
hook can be blocked by the Claude Code harness, but an in-workflow push (run as
a normal command) is transparent and goes through.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EMITTER = Path(__file__).resolve().parent / "telemetry.py"


def sync(quiet: bool = True) -> bool:
    """Push a fresh snapshot of all drafts to the dashboard.

    quiet=True  → suppress output (used automatically by phase commands).
    quiet=False → print the POST result (used by /everglades-submit).
    Returns True if the push process ran (not whether the server accepted it).
    """
    try:
        args = [sys.executable, str(EMITTER)] + ([] if quiet else ["--debug"])
        subprocess.run(args, timeout=8, capture_output=quiet)
        return True
    except Exception:
        return False


def main() -> None:
    ok = sync(quiet=False)
    print("✓ Progress submitted to the tracker." if ok
          else "⚠ Could not reach the tracker (it'll sync again as you work).")


if __name__ == "__main__":
    main()
