"""Shared answer-grading logic.

Previously duplicated identically in verify.py and preview.py — two copies
could drift independently, and neither handled list/tuple answers element-wise
even though Strategy 5 of the Designing-Tasks-That-Challenge-LLMs page
explicitly promotes compositional tuple answers (e.g., 6-tuple orbital
elements, 4-tuple AAH parameters).

This module is the single source of truth for answer comparison. Both
verify.py (subprocess-stdout extraction) and preview.py (Anthropic
submit_answer extraction) call check_answer() here.

Handles:
  - Numeric scalars with relative tolerance (`tol` is a fractional rate;
    `tol=0` means exact equality)
  - Strings (case-insensitive, whitespace-stripped)
  - Sequences (lists / tuples / comma-separated strings parsed as numbers
    when both submitted and expected look numeric; element-wise tolerance)
  - JSON / structured equality as the fallback
"""
from __future__ import annotations

import re
from typing import Any


def _coerce_numeric_sequence(value: Any) -> list[float] | None:
    """If value is a sequence of numbers (or a comma-separated string of them),
    return a list[float]. Otherwise None.
    """
    # Already a sequence of numbers?
    if isinstance(value, (list, tuple)):
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return None
    # Comma-separated numeric string?
    if isinstance(value, str):
        # Strip whitespace, surrounding brackets/quotes
        s = value.strip().strip("[]()").strip()
        if not s:
            return None
        # Try comma-separated
        parts = [p.strip() for p in re.split(r"[,\s]+", s) if p.strip()]
        if len(parts) < 2:
            return None  # single number, handle as scalar elsewhere
        try:
            return [float(p) for p in parts]
        except ValueError:
            return None
    return None


def check_answer(submitted: Any, expected: dict) -> bool:
    """Compare a submitted answer to the expected dict.

    expected: {"answer": <value>, "tolerance": <float>, ...}
      - tolerance is RELATIVE (fraction): 0.05 = 5%. 0 means exact.

    Decision order:
      1. Both look numeric → scalar numeric comparison with tolerance
      2. Both look like sequences → element-wise numeric comparison
      3. Both are strings → case-insensitive whitespace-stripped equality
      4. Fallback → exact structural equality (`==`)
    """
    target = expected.get("answer")
    tol = expected.get("tolerance", 0) or 0

    # 1. Scalar numeric path
    try:
        s = float(submitted)
        t = float(target)
        return _numeric_eq(s, t, tol)
    except (TypeError, ValueError):
        pass

    # 2. Sequence path — try parsing both as numeric sequences
    s_seq = _coerce_numeric_sequence(submitted)
    t_seq = _coerce_numeric_sequence(target)
    if s_seq is not None and t_seq is not None:
        if len(s_seq) != len(t_seq):
            return False
        return all(_numeric_eq(s, t, tol) for s, t in zip(s_seq, t_seq))

    # 3. String path
    if isinstance(submitted, str) and isinstance(target, str):
        return submitted.strip().lower() == target.strip().lower()

    # 4. Fallback
    return submitted == target


def _numeric_eq(s: float, t: float, tol: float) -> bool:
    if tol == 0:
        return s == t
    if t == 0:
        return abs(s) <= tol  # absolute fall-back when target is 0
    return abs(s - t) <= abs(t) * tol
