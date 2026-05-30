"""Unified status — purely local. Walks ~/everglades-drafts/ and reports
each draft's STATE.md + recent runs/.

No RLS API calls. The skill is local-only.

CLI:
  python3 status.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config import DOMAIN_WORLDS, load as load_config, workspace_root
import paths as paths_mod
from yaml_io import load_yaml


def parse_state_md(p: Path) -> dict:
    if not p.exists():
        return {}
    text = p.read_text()
    out = {}
    for line in text.splitlines():
        if line.startswith("state:"):
            out["state"] = line.split(":", 1)[1].strip()
        elif line.startswith("name:"):
            out["name"] = line.split(":", 1)[1].strip()
    return out


def parse_config_yaml(p: Path) -> dict:
    """Parse a draft's config.yaml using a real YAML parser.

    The previous hand-rolled parser broke on inline comments
    (e.g. `direction: inverse  # or forward` pushed
    `"inverse  # or forward"` into the directionality field).
    """
    return load_yaml(p)


def latest_run(draft: Path, kind: str):
    runs = paths_mod.runs_dir(draft)
    if not runs.exists():
        return None
    matches = sorted(runs.glob(f"{kind}_*.json"))
    if not matches:
        return None
    try:
        return json.loads(matches[-1].read_text())
    except Exception:
        return None


def list_drafts() -> list[dict]:
    root = workspace_root()
    drafts = []
    if not root.exists():
        return drafts
    for d in sorted(root.iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            state = parse_state_md(paths_mod.state_md(d))
            cfg = parse_config_yaml(paths_mod.config_yaml(d))
            direction = paths_mod.detect_direction(d)
            preview = latest_run(d, "preview")
            preview_summary = (
                f"{preview.get('passes', '?')}/{preview.get('attempts', '?')}"
                if preview else "—"
            )
            drafts.append({
                "draft": d.name,
                "name": state.get("name") or cfg.get("name", ""),
                "state": state.get("state", "BRIEFED"),
                "direction": direction if direction != "unknown" else cfg.get("direction", "?"),
                "preview": preview_summary,
            })
    return drafts


from state_machine import next_action


def main():
    cfg = load_config()
    print(f"\nEverglades workspace — domain {cfg.get('domain_code', 'EG-1')} (local-only)\n")
    drafts = list_drafts()
    if not drafts:
        print("No drafts yet. /everglades-ideate <N> to start.\n")
        return
    print(f"{'draft':35s}  {'state':14s}  {'dir':8s}  {'preview':10s}")
    print("-" * 75)
    for d in drafts:
        print(f"{d['draft']:35s}  {d['state']:14s}  {d['direction']:8s}  {d['preview']:10s}")
    print()
    # Suggest next move using the single-source state machine
    in_progress = [d for d in drafts if d["state"] not in ("EXPORTED",)]
    if in_progress:
        next_d = in_progress[0]
        cmd = next_action(next_d["state"])
        print(f"Suggested next move: {cmd}  →  {next_d['draft']}")
    else:
        print("All drafts exported. /everglades-ideate <N> to start another batch.")


if __name__ == "__main__":
    main()
