"""Tests for the leak-checker (scripts/lint.py).

Catches the rules at the heart of the Designing-Tasks-That-Challenge-LLMs
guide: Strategy 1 (method-name leaks), Strategy 2 (canonical targets),
strategy hints, and the oracle-as-grader / missing-budget anti-patterns.
"""
import tempfile
from pathlib import Path

from lint import lint_problem, lint_oracle


def _problem(text: str) -> list:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(text)
        p = Path(f.name)
    try:
        return lint_problem(p)
    finally:
        p.unlink()


def _oracle(text: str) -> list:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(text)
        p = Path(f.name)
    try:
        return lint_oracle(p)
    finally:
        p.unlink()


def test_lint_problem_catches_method_name_leak():
    findings = _problem("Use DMRG with bond dimension 100. Call submit_answer.")
    assert any(f["rule"] == "strategy-1-method-name-leak" for f in findings)


def test_lint_problem_catches_canonical_target():
    findings = _problem("Identify formaldehyde's n→π* transition. submit_answer.")
    assert any(f["rule"] == "strategy-2-canonical-target" for f in findings)


def test_lint_problem_flags_missing_submit_answer():
    findings = _problem("Determine the bare quark mass.")
    assert any(f["rule"] == "missing-submit-answer" and f["severity"] == "error"
               for f in findings)


def test_lint_problem_clean_passes():
    findings = _problem(
        "Determine the modulation depth and spatial frequency of the "
        "transmission line. Call submit_answer with two comma-separated floats."
    )
    errors = [f for f in findings if f["severity"] == "error"]
    assert not errors


def test_lint_oracle_catches_grader_pattern():
    src = """
def query_oracle(mode, params):
    if mode == "check_topology":
        return {"correct": True}
"""
    findings = _oracle(src)
    assert any(f["rule"] == "oracle-is-grader" for f in findings)


def test_lint_oracle_warns_missing_budget():
    src = """
def query_oracle(mode, params):
    return {"observation": [1, 2, 3]}
"""
    findings = _oracle(src)
    assert any(f["rule"] == "no-budget" for f in findings)


def test_lint_oracle_warns_missing_help_mode():
    src = """
_BUDGET = 30
def query_oracle(mode, params):
    return {"observation": [1, 2, 3]}
"""
    findings = _oracle(src)
    assert any(f["rule"] == "no-help-mode" for f in findings)


def test_lint_oracle_clean_passes():
    src = '''
_BUDGET = 30
def query_oracle(mode, params):
    if mode == "help":
        return {"modes": ["a", "b"]}
    return {"observation": [1, 2, 3]}
'''
    findings = _oracle(src)
    errors = [f for f in findings if f["severity"] == "error"]
    assert not errors
