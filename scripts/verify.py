"""Local main.py vs oracle/setup.py verifier.

Runs the draft's solution/main.py with the draft directory on PYTHONPATH so
it can `from oracle.setup import query_oracle`. Captures the final-stdout-line
as the submitted answer, compares to golden/expected.json.

This matches the master Everglades CLI layout exactly.

CLI:
  python3 verify.py <draft_dir>
  python3 verify.py <draft_dir> --shortcut    # run solution/shortcut.py instead (expects FAIL)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import paths


from grading import check_answer  # noqa: F401 — re-exported for back-compat


def verify(draft_dir: Path, *, shortcut: bool = False) -> dict:
    script = paths.shortcut_py(draft_dir) if shortcut else paths.main_py(draft_dir)
    if not script.exists():
        return {"error": f"missing {script.relative_to(draft_dir)}", "passed": False}
    expected_path = paths.expected_json(draft_dir)
    if not expected_path.exists():
        return {"error": f"missing {expected_path.relative_to(draft_dir)}", "passed": False}
    expected = json.loads(expected_path.read_text())

    # Run the script with draft_dir on PYTHONPATH so `from oracle.setup import ...` works
    try:
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(draft_dir),
            env={"PYTHONPATH": str(draft_dir), "PATH": "/usr/bin:/bin:/usr/local/bin"},
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout (>10 min)", "passed": False}

    stdout = r.stdout.strip()
    stderr = r.stderr.strip()
    submitted = None
    for line in reversed(stdout.splitlines()):
        if line.strip():
            submitted = line.strip()
            break
    passed = submitted is not None and check_answer(submitted, expected)
    result = {
        "script": str(script.relative_to(draft_dir)),
        "exit_code": r.returncode,
        "submitted": submitted,
        "expected": expected.get("answer"),
        "tolerance": expected.get("tolerance"),
        "passed": passed,
        "stderr_tail": stderr[-2000:] if stderr else "",
        "ran_at": datetime.utcnow().isoformat() + "Z",
    }
    runs = paths.runs_dir(draft_dir)
    runs.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    kind = "shortcut" if shortcut else "verify"
    (runs / f"{kind}_{ts}.json").write_text(json.dumps(result, default=str, indent=2))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("draft", help="Draft directory")
    p.add_argument("--shortcut", action="store_true", help="Run solution/shortcut.py (expects FAIL)")
    args = p.parse_args()
    draft = Path(args.draft).expanduser().resolve()
    result = verify(draft, shortcut=args.shortcut)
    expect_pass = not args.shortcut
    correct = result.get("passed") == expect_pass
    sym = "✓" if correct else "✗"
    label = "verify" if not args.shortcut else "shortcut (expects FAIL)"
    print(f"\n{sym} {label}: {draft.name}")
    print(f"   script:    {result.get('script', '?')}")
    print(f"   submitted: {result.get('submitted')}")
    print(f"   expected:  {result.get('expected')} (±{result.get('tolerance', 0)})")
    print(f"   passed:    {result.get('passed')}  (expected: {expect_pass})")
    if result.get("stderr_tail"):
        print(f"   stderr (tail):\n{result['stderr_tail'][-800:]}")
    sys.exit(0 if correct else 1)


if __name__ == "__main__":
    main()
