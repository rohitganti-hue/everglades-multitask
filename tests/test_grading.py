"""Unit tests for the shared grader (scripts/grading.py).

Covers the four decision paths: numeric scalar, sequence, string, structural.
The key regression we're preventing: Strategy-5 compositional tuple answers
(e.g., the AAH 4-tuple, the orbit-determination 6-tuple) previously fell
through to exact `==` with no element-wise tolerance.
"""
from grading import check_answer


# ────────────────────────────────────────────────────────────────────
# Scalar numeric
# ────────────────────────────────────────────────────────────────────

def test_scalar_exact_match():
    assert check_answer(1.0, {"answer": 1.0, "tolerance": 0})


def test_scalar_exact_mismatch():
    assert not check_answer(1.0, {"answer": 1.5, "tolerance": 0})


def test_scalar_within_relative_tolerance():
    # 5% tolerance, 0.04 deviation on 1.0 → within
    assert check_answer(1.04, {"answer": 1.0, "tolerance": 0.05})


def test_scalar_outside_relative_tolerance():
    # 5% tolerance, 0.06 deviation on 1.0 → outside
    assert not check_answer(1.06, {"answer": 1.0, "tolerance": 0.05})


def test_scalar_target_zero_uses_absolute():
    # Target is 0 → relative tolerance is degenerate; falls back to absolute
    assert check_answer(0.04, {"answer": 0, "tolerance": 0.05})
    assert not check_answer(0.1, {"answer": 0, "tolerance": 0.05})


def test_scalar_string_input_coerces():
    # Stdout from main.py is always a string; numeric coercion must work
    assert check_answer("1.04", {"answer": 1.0, "tolerance": 0.05})


# ────────────────────────────────────────────────────────────────────
# Strings
# ────────────────────────────────────────────────────────────────────

def test_string_exact():
    assert check_answer("DIS3", {"answer": "DIS3", "tolerance": 0})


def test_string_case_insensitive():
    assert check_answer("dis3", {"answer": "DIS3", "tolerance": 0})


def test_string_whitespace_stripped():
    assert check_answer("  DIS3 \n", {"answer": "DIS3", "tolerance": 0})


def test_string_mismatch():
    assert not check_answer("TRAF3", {"answer": "DIS3", "tolerance": 0})


# ────────────────────────────────────────────────────────────────────
# Sequences (the Strategy-5 regression test)
# ────────────────────────────────────────────────────────────────────

def test_tuple_exact():
    assert check_answer([0.873, 1.524, -0.387], {"answer": [0.873, 1.524, -0.387], "tolerance": 0})


def test_tuple_within_tolerance():
    # 1% relative tolerance, every element within
    submitted = [0.880, 1.530, -0.385]
    expected = {"answer": [0.873, 1.524, -0.387], "tolerance": 0.01}
    assert check_answer(submitted, expected)


def test_tuple_outside_tolerance_on_one_element():
    # 1% tolerance, one element off by 10% → reject
    submitted = [0.873, 1.524, -0.500]  # third element way off
    expected = {"answer": [0.873, 1.524, -0.387], "tolerance": 0.01}
    assert not check_answer(submitted, expected)


def test_tuple_different_length():
    assert not check_answer([1.0, 2.0], {"answer": [1.0, 2.0, 3.0], "tolerance": 0})


def test_csv_string_parses_as_sequence():
    # AAH flagship format: "m, b, phi, alpha" submitted as csv string
    submitted = "0.873, 1.524, -0.387, 0.193"
    expected = {"answer": "0.873, 1.524, -0.387, 0.193", "tolerance": 0}
    assert check_answer(submitted, expected)


def test_csv_string_within_tolerance():
    # All elements within 1% of target
    submitted = "0.876, 1.530, -0.385, 0.194"
    expected = {"answer": "0.873, 1.524, -0.387, 0.193", "tolerance": 0.01}
    assert check_answer(submitted, expected)


def test_csv_with_brackets():
    # Some main.py outputs include surrounding brackets
    submitted = "[0.873, 1.524, -0.387]"
    expected = {"answer": [0.873, 1.524, -0.387], "tolerance": 0}
    assert check_answer(submitted, expected)


def test_csv_outside_tolerance():
    submitted = "0.873, 1.524, -0.387, -1.474, 0.193, -2.775"
    # one element way off (last)
    expected = {"answer": "0.873, 1.524, -0.387, -1.474, 0.193, 1.000", "tolerance": 0.01}
    assert not check_answer(submitted, expected)


# ────────────────────────────────────────────────────────────────────
# Mixed / fallback
# ────────────────────────────────────────────────────────────────────

def test_dict_structural_equality():
    submitted = {"transcript": "TX_NOVA", "rule": "EJC75"}
    expected = {"answer": {"transcript": "TX_NOVA", "rule": "EJC75"}, "tolerance": 0}
    assert check_answer(submitted, expected)


def test_dict_structural_mismatch():
    submitted = {"transcript": "TX_NOVA", "rule": "EJC50"}
    expected = {"answer": {"transcript": "TX_NOVA", "rule": "EJC75"}, "tolerance": 0}
    assert not check_answer(submitted, expected)


def test_default_tolerance_zero_if_missing():
    assert check_answer(1.0, {"answer": 1.0})
    assert not check_answer(1.0001, {"answer": 1.0})


def test_tolerance_none_handled_as_zero():
    # In case golden/expected.json has explicit `"tolerance": null`
    assert check_answer(1.0, {"answer": 1.0, "tolerance": None})
    assert not check_answer(1.0001, {"answer": 1.0, "tolerance": None})
