"""Shared YAML parser. Uses pyyaml.

Replaces the hand-rolled `split on first colon` parser that previously lived in
both status.py and (now-deleted) rls.py. The hand-rolled parser broke on inline
comments — e.g. `direction: inverse  # or forward` pushed
`"inverse  # or forward"` into the directionality field.

Pyyaml handles inline comments, quoting, lists, and nested dicts correctly.
"""
from __future__ import annotations
from pathlib import Path

try:
    import yaml
except ImportError as e:
    raise ImportError(
        "pyyaml is required. Install with: pip install pyyaml\n"
        "(or `pip install -r requirements.txt` from the skill repo root)"
    ) from e


def load_yaml(path: Path) -> dict:
    """Load a YAML file. Returns {} if file is missing or empty."""
    if not path.exists():
        return {}
    text = path.read_text()
    if not text.strip():
        return {}
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        return {"_raw": data}
    return data


def dump_yaml(data: dict, path: Path) -> None:
    """Write a dict to a YAML file."""
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
