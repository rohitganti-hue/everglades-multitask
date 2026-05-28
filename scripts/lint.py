"""Leak-checker for problem.md and oracle.py.

Catches:
  - Method-name leaks in problem.md (Strategy 1 violation)
  - Canonical-target tokens (Strategy 2 violation)
  - Judgment-style oracle modes (`check_*`, `validate_*`, `is_correct`)
  - Missing `submit_answer` instruction in prompt
  - Missing budget in oracle

CLI:
  python3 lint.py <draft_dir>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Method-name leaks (Strategy 1)
METHOD_NAMES = [
    "DMRG", "AlphaFold", "ΔSCF", "DeltaSCF", "Delta-SCF", "MOM constraint", "MOM",
    "Hartree-Fock", "Hartree Fock", "RHF", "UHF", "DFT", "TDDFT", "MP2", "CCSD",
    "Gaussian process", "ridge regression", "Lasso", "Bayesian optimization",
    "Gauss's method", "Lambert solver", "Kalman filter",
    "Smith-Waterman", "Needleman-Wunsch", "BLAST", "HMMER",
    "TauP", "depth phase", "Brune", "moment tensor",
    "PIMPLE", "SIMPLE", "icoFoam", "pimpleFoam",
    "Euler-Bernoulli", "Timoshenko", "Mindlin-Reissner",
    "Gell-Mann–Oakes–Renner", "GMOR", "Wilson loop",
    "MarkDuplicates", "GATK HaplotypeCaller",
]

# Canonical-target tokens (Strategy 2)
CANONICAL_TARGETS = [
    "formaldehyde", "H2CO", "methylene blue",
    "2D Ising", "Ising critical", "T_c = 2.269",
    "repressilator", "Elowitz-Leibler", "Lotka-Volterra",
    "Van der Pol",
    "1000 Genomes", "ENCODE", "GTEx",
    "Planck", "WMAP",
    "AK135", "IASP91",
]

# Strategy-hint phrases
STRATEGY_HINTS = [
    "start by", "first measure", "begin with", "the trick is",
    "the hint is", "best approach is", "you should use",
    "this measures the", "this is good for",
]

# Judgment-style oracle modes
JUDGMENT_PATTERNS = [
    r"\bcheck_\w+\b", r"\bvalidate_\w+\b", r"\bis_correct\w*\b",
    r"\bis_right\w*\b", r"\bclose_enough\b",
    r'"accepted"', r'"rejected"', r'"correct"',
]


def lint_problem(path: Path) -> list[dict]:
    findings = []
    if not path.exists():
        findings.append({"severity": "error", "msg": f"problem.md missing at {path}"})
        return findings
    text = path.read_text()
    lower = text.lower()

    # Strategy 1: method names
    for m in METHOD_NAMES:
        if re.search(rf"\b{re.escape(m)}\b", text, re.I):
            findings.append({
                "severity": "warn",
                "rule": "strategy-1-method-name-leak",
                "msg": f"problem.md mentions '{m}' — likely a method-name leak. Strategy 1 says describe operationally.",
            })

    # Strategy 2: canonical targets
    for t in CANONICAL_TARGETS:
        if re.search(rf"\b{re.escape(t)}\b", text, re.I):
            findings.append({
                "severity": "warn",
                "rule": "strategy-2-canonical-target",
                "msg": f"problem.md references '{t}' — canonical/textbook target. Model may retrieve the answer.",
            })

    # Strategy hints
    for h in STRATEGY_HINTS:
        if h in lower:
            findings.append({
                "severity": "info",
                "rule": "strategy-hint",
                "msg": f"problem.md contains '{h}' — review whether this hands over the solve path.",
            })

    # Required: submit_answer instruction
    if "submit_answer" not in text:
        findings.append({
            "severity": "error",
            "rule": "missing-submit-answer",
            "msg": "problem.md does NOT instruct the model to call `submit_answer`. Required.",
        })

    return findings


def lint_oracle(path: Path) -> list[dict]:
    findings = []
    if not path.exists():
        return findings  # forward tasks don't have an oracle
    text = path.read_text()

    # Judgment-style modes
    for pat in JUDGMENT_PATTERNS:
        for m in re.finditer(pat, text):
            findings.append({
                "severity": "error",
                "rule": "oracle-is-grader",
                "msg": f"oracle.py contains judgment-style pattern: {m.group(0)!r}. The oracle must return observations, not judgments.",
            })

    # Missing budget
    if "budget" not in text.lower():
        findings.append({
            "severity": "warn",
            "rule": "no-budget",
            "msg": "oracle.py has no query budget. Brute force may dominate; add a budget.",
        })

    # Missing help mode
    if '"help"' not in text and "'help'" not in text:
        findings.append({
            "severity": "warn",
            "rule": "no-help-mode",
            "msg": "oracle.py has no help mode. Add one that lists modes without recommending strategies.",
        })

    return findings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("draft")
    args = p.parse_args()
    draft = Path(args.draft).expanduser().resolve()

    findings = []
    findings += lint_problem(draft / "problem.md")
    findings += lint_oracle(draft / "oracle.py")

    if not findings:
        print(f"✓ lint clean: {draft.name}")
        sys.exit(0)

    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]
    infos = [f for f in findings if f["severity"] == "info"]
    sym = "✗" if errors else "⚠"
    print(f"\n{sym} lint: {draft.name}  ({len(errors)} errors, {len(warns)} warnings, {len(infos)} info)\n")
    for f in errors + warns + infos:
        s = {"error": "ERR ", "warn": "WARN", "info": "INFO"}[f["severity"]]
        print(f"  [{s}] {f.get('rule','?')}: {f['msg']}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
