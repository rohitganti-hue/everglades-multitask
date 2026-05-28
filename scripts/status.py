"""Unified status — drafts + pushed tasks + in-revision tasks.

Reads ~/everglades-drafts/*/STATE.md and ~/everglades-drafts/*/meta.yml for
drafts; GETs the expert's owned tasks from RLS for live state.

CLI:
  python3 status.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config import load as load_config, workspace_root, DOMAIN_WORLDS
from rls import list_tasks


def parse_state_md(p: Path) -> dict:
    if not p.exists():
        return {}
    text = p.read_text()
    out = {}
    for line in text.splitlines():
        if line.startswith("state:"):
            out["state"] = line.split(":", 1)[1].strip()
        elif line.startswith("task_id:"):
            out["task_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("name:"):
            out["name"] = line.split(":", 1)[1].strip()
    return out


def parse_meta(p: Path) -> dict:
    if not p.exists():
        return {}
    text = p.read_text()
    out = {}
    for line in text.splitlines():
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def list_drafts() -> list[dict]:
    root = workspace_root()
    drafts = []
    if not root.exists():
        return drafts
    for d in sorted(root.iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            state = parse_state_md(d / "STATE.md")
            meta = parse_meta(d / "meta.yml")
            drafts.append({
                "draft": d.name,
                "name": state.get("name") or meta.get("name", ""),
                "state": state.get("state", "BRIEFED"),
                "task_id": meta.get("rls_task_id"),
                "directionality": meta.get("directionality", "?"),
            })
    return drafts


def list_my_owned_tasks() -> list[dict]:
    cfg = load_config()
    wid = cfg["world_id"]
    expert = cfg.get("expert_id")
    tasks = list_tasks(wid, owned_by=expert) if expert else list_tasks(wid)
    return tasks


STATUS_LEGEND = {
    "ce5f656b-6b79-4913-b0ba-37df93dc9eb1": "Approved",
    "done": "QC Approved",
    "submitted": "Awaiting Review",
    "in_review": "In Review",
    "in_progress": "Pending",
    "needs_edits": "In Revision",
    "draft": "Unclaimed",
}


def main():
    cfg = load_config()
    print(f"\nEverglades workspace — domain {cfg.get('domain_code','?')} ({cfg['world_id']})\n")

    drafts = list_drafts()
    if drafts:
        print("Local drafts:")
        for d in drafts:
            tid = d["task_id"] or "(not yet pushed)"
            print(f"  {d['draft']:35s}  state={d['state']:14s}  dir={d['directionality']:8s}  rls={tid}")
        print()

    rls_tasks = list_my_owned_tasks()
    if rls_tasks:
        print(f"RLS tasks ({len(rls_tasks)}):")
        for t in rls_tasks:
            sid = t.get("task_status_id", "?")
            sname = STATUS_LEGEND.get(sid, sid[:12])
            tname = t.get("task_name", "?")
            tid = t.get("task_id", "")
            print(f"  {tname:30s}  {sname:18s}  {tid}")
        print()

    # Suggest next move
    print("Suggested next move:")
    revisions = [t for t in rls_tasks if t.get("task_status_id") == "needs_edits"]
    if revisions:
        print(f"  → {len(revisions)} task(s) in revision. /everglades-inbox")
        return
    in_progress = [d for d in drafts if d["state"] not in ("READY", "PUSHED")]
    if in_progress:
        next_d = in_progress[0]
        next_cmd = {
            "BRIEFED": "/everglades-lock",
            "LOCKED": "/everglades-jobs",
            "JOBS": "/everglades-scaffold",
            "SCAFFOLDED": "/everglades-verify",
            "CALIBRATED": "/everglades-preview",
        }.get(next_d["state"], "/everglades-step")
        print(f"  → {next_cmd} {next_d['draft']}")
    elif any(d["state"] == "READY" for d in drafts):
        print("  → /everglades-push-all")
    else:
        print("  → /everglades-ideate <N>  or  /everglades-ideate-siblings")


if __name__ == "__main__":
    main()
