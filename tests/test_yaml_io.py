"""Unit tests for the YAML parser (scripts/yaml_io.py).

Regression test for the v0.2 bug where the hand-rolled parser pushed
"inverse  # or forward" into the directionality field when the template
shipped `direction: inverse  # or forward`.
"""
import tempfile
from pathlib import Path

from yaml_io import load_yaml, dump_yaml


def _tmpfile(text: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(text)
    f.close()
    return Path(f.name)


def test_inline_comment_is_stripped():
    # The exact failure mode from the code review: inline comments
    # on the same line as a value used to leak into the parsed value.
    p = _tmpfile("direction: inverse  # or forward\nsimulator: ngspice\n")
    try:
        data = load_yaml(p)
        assert data["direction"] == "inverse"
        assert data["simulator"] == "ngspice"
    finally:
        p.unlink()


def test_missing_file_returns_empty():
    assert load_yaml(Path("/nonexistent/path/config.yaml")) == {}


def test_empty_file_returns_empty():
    p = _tmpfile("")
    try:
        assert load_yaml(p) == {}
    finally:
        p.unlink()


def test_quoted_values():
    p = _tmpfile('name: "Task with: special chars"\nfoo: \'bar\'\n')
    try:
        data = load_yaml(p)
        assert data["name"] == "Task with: special chars"
        assert data["foo"] == "bar"
    finally:
        p.unlink()


def test_nested_values():
    p = _tmpfile("config:\n  domain: EG-1\n  direction: inverse\n")
    try:
        data = load_yaml(p)
        assert isinstance(data["config"], dict)
        assert data["config"]["domain"] == "EG-1"
    finally:
        p.unlink()


def test_dump_roundtrip():
    src = {"domain": "EG-1", "direction": "inverse", "tolerance": 0.05}
    p = _tmpfile("")
    try:
        dump_yaml(src, p)
        assert load_yaml(p) == src
    finally:
        p.unlink()
