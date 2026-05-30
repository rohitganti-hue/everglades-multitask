"""Tests for the verify.py answer-extraction contract.

Locks the sentinel-line behavior that unified verify + preview answer
extraction (#12 in the code review).
"""
from verify import extract_submitted


def test_sentinel_line_extracted():
    stdout = "doing the math\nsome intermediate\nEVERGLADES_SUBMIT_ANSWER: 1.04\n"
    assert extract_submitted(stdout) == "1.04"


def test_sentinel_with_trailing_print():
    # main.py emits sentinel + a plain final line — sentinel still wins
    stdout = "...\nEVERGLADES_SUBMIT_ANSWER: DIS3\nDIS3\n"
    assert extract_submitted(stdout) == "DIS3"


def test_sentinel_in_middle_of_output():
    # Even if main.py prints more stuff after the sentinel, we still pick it
    stdout = (
        "step 1: hello\n"
        "EVERGLADES_SUBMIT_ANSWER: 0.873, 1.524, -0.387\n"
        "elapsed: 0.42s\n"
    )
    assert extract_submitted(stdout) == "0.873, 1.524, -0.387"


def test_fallback_to_last_line_when_no_sentinel():
    # Legacy main.py without sentinel — fall back to last non-empty line
    stdout = "computing...\n1.04\n"
    assert extract_submitted(stdout) == "1.04"


def test_fallback_skips_trailing_empty_lines():
    stdout = "computing...\n42\n\n\n"
    assert extract_submitted(stdout) == "42"


def test_empty_stdout_returns_none():
    assert extract_submitted("") is None
    assert extract_submitted("   \n  \n") is None


def test_sentinel_with_whitespace():
    stdout = "   EVERGLADES_SUBMIT_ANSWER:   spaced answer   \n"
    assert extract_submitted(stdout) == "spaced answer"
