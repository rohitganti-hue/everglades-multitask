"""Local main.py vs oracle.py verifier.

Runs the draft's main.py with the draft's oracle.py importable, captures the
final-stdout-line as the submitted answer, compares to expected.json.

CLI:
  python3 verify.py <draft_dir>
  python3 verify.py <draft_dir> --shortcut    # run shortcut.py instead (expects FAIL)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def check_answer(submitted, expected: dict) -> bool:
    target = expected.get("answer")
    tol = expected.get("tolerance", 0)
    try:
        s = float(submitted)
        t = float(target)
        if tol == 0:
            return s == t
        return abs(s - t) <= abs(t) * tol if t != 0 else abs(s) <= tol
    except (TypeError, ValueError):
        pass
    if isinstance(submitted, str) and isinstance(target, str):
        return submitted.strip().lower() == target.strip().lower()
    return submitted == target


def verify(draft_dir: Path, *, shortcut: bool = False) -> dict:
    script_name = "shortcut.py" if shortcut else "main.py"
    script = draft_dir / script_name
    if not script.exists():
        return {"error": f"missing {script_name}", "passed": False}
    expected_path = draft_dir / "expected.json"
    if not expected_path.exists():
        return {"error": "missing expected.json", "passed": False}
    expected = json.loads(expected_path.read_text())

    # Run the script with draft_dir on PYTHONPATH so it can `import oracle`
    env_path = str(draft_dir)
    try:
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(draft_dir),
            env={"PYTHONPATH": env_path, "PATH": "/usr/bin:/bin:/usr/local/bin"},
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout (>10 min)", "passed": False}

    stdout = r.stdout.strip()
    stderr = r.stderr.strip()
    # Last non-empty stdout line is the submitted answer
    submitted = None
    for line in reversed(stdout.splitlines()):
        if line.strip():
            submitted = line.strip()
            break
    passed = submitted is not None and check_answer(submitted, expected)
    result = {
        "script": script_name,
        "exit_code": r.returncode,
        "submitted": submitted,
        "expected": expected.get("answer"),
        "tolerance": expected.get("tolerance"),
        "passed": passed,
        "stderr_tail": stderr[-2000:] if stderr else "",
        "ran_at": datetime.utcnow().isoformat() + "Z",
    }
    # Save
    runs_dir = draft_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    kind = "shortcut" if shortcut else "verify"
    (runs_dir / f"{kind}_{ts}.json").write_text(json.dumps(result, default=str, indent=2))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("draft", help="Draft directory")
    p.add_argument("--shortcut", action="store_true", help="Run shortcut.py (expects FAIL)")
    args = p.parse_args()
    draft = Path(args.draft).expanduser().resolve()
    result = verify(draft, shortcut=args.shortcut)
    # Verdict
    expect_pass = not args.shortcut
    correct = result["passed"] == expect_pass
    sym = "✓" if correct else "✗"
    label = "verify" if not args.shortcut else "shortcut (expects FAIL)"
    print(f"\n{sym} {label}: {draft.name}")
    print(f"   submitted: {result.get('submitted')}")
    print(f"   expected:  {result.get('expected')} (±{result.get('tolerance', 0)})")
    print(f"   passed:    {result.get('passed')}  (expected: {expect_pass})")
    if result.get("stderr_tail"):
        print(f"   stderr (tail):\n{result['stderr_tail'][-800:]}")
    sys.exit(0 if correct else 1)


if __name__ == "__main__":
    main()
