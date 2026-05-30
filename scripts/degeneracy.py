"""Cross-sibling degeneracy check (Workflow B).

Reads from canonical Everglades CLI paths (oracle/setup.py, solution/main.py).

For a sibling set, run each sibling's solution/main.py against the OTHER
siblings' oracle/setup.py modules. If any cross-pair returns within tolerance,
the siblings collapse into each other.

Also: token-level similarity check on reasoning_trap.md across siblings.

CLI:
  python3 degeneracy.py <sibling_dir1> <sibling_dir2> [...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

import paths
from grading import check_answer  # single shared grader — see scripts/grading.py


def load_oracle(draft_dir: Path):
    spec = importlib.util.spec_from_file_location(
        f"oracle_setup_{draft_dir.name}", paths.oracle_setup(draft_dir)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_main(draft_dir: Path):
    """Dynamic-import solution/main.py. Falls back gracefully if it doesn't
    define `solve(query_oracle)`."""
    spec = importlib.util.spec_from_file_location(
        f"main_{draft_dir.name}", paths.main_py(draft_dir)
    )
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def shingle(text: str, n: int = 5) -> set:
    words = re.findall(r"\w+", text.lower())
    return set(tuple(words[i : i + n]) for i in range(len(words) - n + 1))


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def check_siblings(siblings: list[Path]) -> dict:
    findings = []

    # 1. Lexical similarity on reasoning_trap.md
    traps = {}
    for s in siblings:
        rt = paths.reasoning_trap(s)
        if rt.exists():
            traps[s.name] = shingle(rt.read_text())
    names = list(traps.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            sim = jaccard(traps[names[i]], traps[names[j]])
            if sim > 0.5:
                findings.append({
                    "severity": "warn" if sim < 0.8 else "error",
                    "rule": "trap-overlap",
                    "msg": (
                        f"reasoning_trap.md overlap between {names[i]} and {names[j]}: "
                        f"{sim:.0%} Jaccard. Likely sibling collapse."
                    ),
                })

    # 2. Cross-oracle solvability
    expected_per = {}
    for s in siblings:
        ep = paths.expected_json(s)
        if ep.exists():
            expected_per[s.name] = json.loads(ep.read_text())

    for i, si in enumerate(siblings):
        for j, sj in enumerate(siblings):
            if i == j:
                continue
            mi = load_main(si)
            if mi is None or not hasattr(mi, "solve"):
                continue
            mj_oracle = load_oracle(sj)
            try:
                result = mi.solve(mj_oracle.query_oracle)
            except Exception:
                continue
            if check_answer(result, expected_per.get(sj.name, {})):
                findings.append({
                    "severity": "error",
                    "rule": "cross-oracle-solvable",
                    "msg": (
                        f"{si.name}'s solution/main.py solves {sj.name}'s oracle/setup.py. "
                        f"Siblings are not orthogonal — they share too much structure."
                    ),
                })

    return {"findings": findings, "siblings": [s.name for s in siblings]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("siblings", nargs="+")
    args = p.parse_args()
    siblings = [Path(s).expanduser().resolve() for s in args.siblings]
    out = check_siblings(siblings)
    findings = out["findings"]
    if not findings:
        print(f"✓ siblings orthogonal: {', '.join(out['siblings'])}")
        sys.exit(0)
    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]
    sym = "✗" if errors else "⚠"
    print(f"\n{sym} degeneracy check: {len(errors)} errors, {len(warns)} warnings\n")
    for f in errors + warns:
        s = {"error": "ERR ", "warn": "WARN"}[f["severity"]]
        print(f"  [{s}] {f['rule']}: {f['msg']}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
