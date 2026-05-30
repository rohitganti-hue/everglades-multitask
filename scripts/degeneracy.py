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
    """Dynamic-import oracle/setup.py for cross-sibling testing.

    Returns the module on success, or None if the import fails (e.g., missing
    deps). The caller treats None as "could not evaluate" rather than silently
    skipping.
    """
    op = paths.oracle_setup(draft_dir)
    if not op.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            f"oracle_setup_{draft_dir.name}", op
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Some oracles export handle_query instead of query_oracle
        if not hasattr(mod, "query_oracle") and hasattr(mod, "handle_query"):
            mod.query_oracle = mod.handle_query
        return mod if hasattr(mod, "query_oracle") else None
    except Exception:
        return None


def load_main(draft_dir: Path):
    """Dynamic-import solution/main.py.

    Returns the module on success, or None if it can't be loaded.
    """
    mp = paths.main_py(draft_dir)
    if not mp.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            f"main_{draft_dir.name}", mp
        )
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

    # 2. Cross-oracle solvability.
    # The previous version silently `continue`-d when a sibling's main.py
    # lacked `solve()` or an oracle failed to import, which could make the
    # check pass vacuously (printed "siblings orthogonal" with zero pairs
    # evaluated). Now we emit a warning per skipped pair and an explicit
    # rule-no-pairs-evaluated finding if NO pair could be evaluated.
    expected_per = {}
    for s in siblings:
        ep = paths.expected_json(s)
        if ep.exists():
            expected_per[s.name] = json.loads(ep.read_text())

    pairs_evaluated = 0
    pairs_skipped = []
    for i, si in enumerate(siblings):
        for j, sj in enumerate(siblings):
            if i == j:
                continue
            mi = load_main(si)
            mj_oracle = load_oracle(sj)
            if mi is None:
                pairs_skipped.append((si.name, sj.name, "main.py failed to load"))
                continue
            if not hasattr(mi, "solve"):
                pairs_skipped.append((si.name, sj.name,
                                       f"{si.name}/solution/main.py has no solve() function"))
                continue
            if mj_oracle is None:
                pairs_skipped.append((si.name, sj.name,
                                       f"{sj.name}/oracle/setup.py failed to load"))
                continue
            try:
                result = mi.solve(mj_oracle.query_oracle)
            except Exception as e:
                pairs_skipped.append((si.name, sj.name, f"solve() raised: {e!r}"))
                continue
            pairs_evaluated += 1
            if check_answer(result, expected_per.get(sj.name, {})):
                findings.append({
                    "severity": "error",
                    "rule": "cross-oracle-solvable",
                    "msg": (
                        f"{si.name}'s solution/main.py solves {sj.name}'s oracle/setup.py. "
                        f"Siblings are not orthogonal — they share too much structure."
                    ),
                })

    # Surface skipped pairs so vacuous passes can't sneak through silently.
    for src, dst, reason in pairs_skipped:
        findings.append({
            "severity": "warn",
            "rule": "pair-not-evaluated",
            "msg": f"{src} → {dst}: {reason}",
        })

    # Hard fail if we couldn't evaluate ANY pair — the check is meaningless.
    if pairs_evaluated == 0 and len(siblings) > 1:
        findings.append({
            "severity": "error",
            "rule": "no-pairs-evaluated",
            "msg": (
                "Cross-oracle degeneracy check evaluated ZERO pairs. The check "
                "is vacuous. Make sure each sibling's solution/main.py defines "
                "`solve(query_oracle)` and oracle/setup.py imports cleanly."
            ),
        })

    return {
        "findings": findings,
        "siblings": [s.name for s in siblings],
        "pairs_evaluated": pairs_evaluated,
        "pairs_skipped": len(pairs_skipped),
    }


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
