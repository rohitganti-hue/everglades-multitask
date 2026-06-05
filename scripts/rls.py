#!/usr/bin/env python3
"""Record an expert's self-reported RLS linkage for a finalized draft.

The skill is local-only and can't see RLS. Once a draft is READY and the expert
has pasted it into the RLS web UI, they record *which* RLS task it became and its
status here. The telemetry emitter then reports it, so the dashboard shows the
On-RLS / Approved funnel per expert.

Privacy: this stores ONLY an RLS task identifier + a status — never task content
(no problem.md, oracle/solution code, or answers).

Usage:
  python3 rls.py <draft> --task-id <RLS_TASK_ID_OR_LINK>   # link it (status defaults to submitted)
  python3 rls.py <draft> --status approved                 # update status later (approval lands days after upload)
  python3 rls.py <draft> --show                            # print current linkage
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from config import workspace_root

STATUSES = ("submitted", "in_review", "approved", "rejected")


def rls_path(draft_dir: Path) -> Path:
    return draft_dir / "rls.json"


def _load(draft_dir: Path) -> dict:
    try:
        return json.loads(rls_path(draft_dir).read_text())
    except Exception:
        return {}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Record self-reported RLS linkage for a draft")
    ap.add_argument("draft", help="draft id (folder name under the workspace)")
    ap.add_argument("--task-id", dest="task_id", default=None, help="RLS task id or link")
    ap.add_argument("--status", choices=STATUSES, default=None, help="submitted | in_review | approved | rejected")
    ap.add_argument("--show", action="store_true", help="print current linkage and exit")
    args = ap.parse_args(argv)

    draft_dir = workspace_root() / args.draft
    if not draft_dir.is_dir():
        print(f"No such draft: {draft_dir}")
        raise SystemExit(1)

    data = _load(draft_dir)

    if args.show and not (args.task_id or args.status):
        print(json.dumps(data, indent=2) if data else "(no RLS linkage recorded yet)")
        return

    if args.task_id:
        data["rls_task_id"] = args.task_id.strip()
        data.setdefault("status", "submitted")
    if args.status:
        data["status"] = args.status

    if not data.get("rls_task_id"):
        print("Provide --task-id (the RLS task id/link) the first time you link this draft.")
        raise SystemExit(1)

    data["updated"] = int(time.time())
    rls_path(draft_dir).write_text(json.dumps(data, indent=2))
    print(f"✓ RLS linkage for {args.draft}: {data['rls_task_id']} · {data.get('status')}")


if __name__ == "__main__":
    main()
