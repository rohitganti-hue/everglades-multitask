"""Tests for the canonical-path helpers (scripts/paths.py)."""
import tempfile
from pathlib import Path

import paths as paths_mod


def test_all_canonical_paths_return_correct_relative_locations():
    """Lock the canonical CLI layout against accidental drift."""
    draft = Path("/tmp/fake-draft")
    assert paths_mod.problem_md(draft) == draft / "problem.md"
    assert paths_mod.config_yaml(draft) == draft / "config.yaml"
    assert paths_mod.requirements_txt(draft) == draft / "requirements.txt"
    assert paths_mod.oracle_setup(draft) == draft / "oracle" / "setup.py"
    assert paths_mod.simulation_dir(draft) == draft / "simulation"
    assert paths_mod.main_py(draft) == draft / "solution" / "main.py"
    assert paths_mod.shortcut_py(draft) == draft / "solution" / "shortcut.py"
    assert paths_mod.grading_guide(draft) == draft / "grader" / "grading_guide.md"
    assert paths_mod.expected_json(draft) == draft / "golden" / "expected.json"
    assert paths_mod.reasoning_trap(draft) == draft / "reasoning_trap.md"
    assert paths_mod.state_md(draft) == draft / "STATE.md"
    assert paths_mod.brief_md(draft) == draft / "BRIEF.md"
    assert paths_mod.runs_dir(draft) == draft / "runs"


def test_detect_direction_inverse_via_oracle_setup():
    with tempfile.TemporaryDirectory() as d:
        draft = Path(d)
        (draft / "oracle").mkdir()
        (draft / "oracle" / "setup.py").write_text("# oracle\n")
        assert paths_mod.detect_direction(draft) == "inverse"


def test_detect_direction_forward_via_simulation():
    with tempfile.TemporaryDirectory() as d:
        draft = Path(d)
        (draft / "simulation").mkdir()
        (draft / "simulation" / "case.foam").write_text("")
        assert paths_mod.detect_direction(draft) == "forward"


def test_detect_direction_from_config_yaml_when_no_files():
    with tempfile.TemporaryDirectory() as d:
        draft = Path(d)
        (draft / "config.yaml").write_text("direction: forward\nsimulator: ngspice\n")
        assert paths_mod.detect_direction(draft) == "forward"


def test_detect_direction_from_config_yaml_with_inline_comment():
    """Regression test for the v0.2 bug — inline comment broke direction detection."""
    with tempfile.TemporaryDirectory() as d:
        draft = Path(d)
        (draft / "config.yaml").write_text("direction: inverse  # or forward\n")
        assert paths_mod.detect_direction(draft) == "inverse"


def test_detect_direction_unknown_when_nothing_set():
    with tempfile.TemporaryDirectory() as d:
        draft = Path(d)
        assert paths_mod.detect_direction(draft) == "unknown"
