"""pytest fixtures shared across the test suite.

Makes `scripts/` importable as a top-level package so tests can
`from grading import check_answer`, `from yaml_io import load_yaml`, etc.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
