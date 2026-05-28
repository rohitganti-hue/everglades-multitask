"""RLS API client + CLI.

Wraps the read + write surface the skill needs:
  - list approved + claimable tasks in a world
  - GET a task (hydrated)
  - PATCH a task's custom_fields
  - upload a file (oracle.py / main.py) to the snapshots bucket
  - dispatch the 16-model STEM Software Runner
  - transition a task's status (submit-for-review, etc.)

CLI usage:
  python3 rls.py list-tasks --world EG-1
  python3 rls.py get-task <task_id>
  python3 rls.py patch-task <task_id> --field reasoning_trap --value "..."
  python3 rls.py push-file <task_id> --field oracle_file --path ./oracle.py
  python3 rls.py dispatch-runner <task_id>
  python3 rls.py transition <task_id> --edge submit_for_review

This is intentionally a thin wrapper. The skill's higher-level commands compose
multiple calls (e.g., /everglades-push = create + push-file × N + patch × M).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from config import (
    CAMPAIGN_ID,
    COMPANY_ID,
    DOMAIN_WORLDS,
    RLS_BASE,
    load as load_config,
)
from field_map import FIELD_MAP, semantic_to_field_id


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Campaign-Id": CAMPAIGN_ID,
        "X-Company-Id": COMPANY_ID,
        "User-Agent": "everglades-multitask/0.1",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, *, data=None, retry: int = 3):
    cfg = load_config()
    headers = _headers(cfg["rls_api_key"])
    url = RLS_BASE + path
    body = None
    if data is not None:
        body = json.dumps(data).encode()
    for attempt in range(retry):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read().decode()
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:300]
            if e.code in (429, 502, 503, 504) and attempt < retry - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"HTTP {e.code} {method} {path}: {err}", file=sys.stderr)
            return None
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"Error on {method} {path}: {e}", file=sys.stderr)
            return None
    return None


def list_tasks(world_id: str, *, status_filter: str | None = None, owned_by: str | None = None):
    r = _request("GET", f"/tasks/world/{world_id}?limit=500")
    if not r:
        return []
    tasks = r.get("tasks", r if isinstance(r, list) else [])
    if status_filter:
        tasks = [t for t in tasks if t.get("task_status_id") == status_filter]
    if owned_by:
        tasks = [t for t in tasks if t.get("owned_by") == owned_by]
    return tasks


def get_task(task_id: str):
    return _request("GET", f"/tasks/{task_id}")


def patch_task(task_id: str, *, custom_fields: dict | None = None, **fields):
    """PATCH a task. custom_fields maps semantic name -> value."""
    body = {}
    if fields:
        body.update(fields)
    if custom_fields:
        body["custom_fields"] = {}
        for semantic, value in custom_fields.items():
            fid = semantic_to_field_id(semantic)
            body["custom_fields"][fid] = value
    return _request("PATCH", f"/tasks/{task_id}", data=body)


def create_task(world_id: str, *, task_name: str | None = None):
    payload = {"world_id": world_id}
    if task_name:
        payload["task_name"] = task_name
    return _request("POST", "/tasks/", data=payload)


def transition(task_id: str, edge_id: str):
    return _request("POST", f"/tasks/{task_id}/transition", data={"edge_id": edge_id})


def upload_file(local_path: Path) -> str | None:
    """Upload a local file to RLS snapshots bucket. Returns s3:// URL or None.

    Probes the upload endpoint dynamically — the API exposes either
    `POST /files/upload-url` (presigned) or `POST /files` (multipart). We try
    presigned first.
    """
    # Step 1: ask for an upload URL.
    presign = _request(
        "POST",
        "/files/upload-url",
        data={"filename": local_path.name, "campaign_id": CAMPAIGN_ID},
    )
    if not presign or "upload_url" not in presign:
        print(
            "upload_file: /files/upload-url not available — TODO probe /files multipart fallback",
            file=sys.stderr,
        )
        return None
    upload_url = presign["upload_url"]
    s3_url = presign.get("s3_url") or presign.get("file_s3_url")
    # Step 2: PUT the file contents to the presigned URL.
    body = local_path.read_bytes()
    req = urllib.request.Request(upload_url, data=body, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
    except urllib.error.HTTPError as e:
        print(f"upload_file PUT failed: HTTP {e.code} {e.read().decode()[:200]}", file=sys.stderr)
        return None
    return s3_url


def dispatch_runner(task_id: str, *, runner_name: str = "STEM Software Runner"):
    """Dispatch the 16-model Taiga eval. Returns the run id or None.

    Probes the actual endpoint by trying the known patterns.
    """
    # Pattern A: /tasks/{id}/run-trajectory
    r = _request("POST", f"/tasks/{task_id}/run-trajectory", data={"runner": runner_name})
    if r and (r.get("run_id") or r.get("job_id")):
        return r
    # Pattern B: /trajectory-batches with task_id
    r = _request("POST", "/trajectory-batches", data={"task_id": task_id, "runner_name": runner_name})
    if r and (r.get("batch_id") or r.get("id")):
        return r
    print("dispatch_runner: neither known endpoint succeeded — probe RLS swagger.", file=sys.stderr)
    return None


def fetch_run_results(task_id: str) -> dict | None:
    """Fetch the latest 16-model run results from a task's submission history."""
    task = get_task(task_id)
    if not task:
        return None
    history = task.get("custom_fields", {}).get("taiga_submission_history")
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except Exception:
            return None
    if not isinstance(history, list) or not history:
        return None
    # Most recent first
    latest = history[-1]
    return latest


def main():
    p = argparse.ArgumentParser(description="RLS API client")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list-tasks")
    s.add_argument("--world", required=True, help="EG-1, EG-2, ... or full world_id")
    s.add_argument("--status", default=None, help="Filter by status_id (e.g. approved UUID)")
    s.add_argument("--owned-by", default=None)

    s = sub.add_parser("get-task")
    s.add_argument("task_id")

    s = sub.add_parser("patch-task")
    s.add_argument("task_id")
    s.add_argument("--field", required=True, help="semantic field name (e.g. reasoning_trap)")
    s.add_argument("--value", required=True)

    s = sub.add_parser("push-file")
    s.add_argument("task_id")
    s.add_argument("--field", required=True, help="oracle_file | verification_code | paper")
    s.add_argument("--path", required=True)

    s = sub.add_parser("dispatch-runner")
    s.add_argument("task_id")

    s = sub.add_parser("transition")
    s.add_argument("task_id")
    s.add_argument("--edge", required=True)

    s = sub.add_parser("create-task")
    s.add_argument("--world", required=True)
    s.add_argument("--name", default=None)

    s = sub.add_parser("results")
    s.add_argument("task_id")

    args = p.parse_args()

    if args.cmd == "list-tasks":
        wid = DOMAIN_WORLDS.get(args.world, args.world)
        tasks = list_tasks(wid, status_filter=args.status, owned_by=args.owned_by)
        print(json.dumps(tasks, default=str, indent=2))
    elif args.cmd == "get-task":
        print(json.dumps(get_task(args.task_id), default=str, indent=2))
    elif args.cmd == "patch-task":
        print(json.dumps(patch_task(args.task_id, custom_fields={args.field: args.value}), default=str, indent=2))
    elif args.cmd == "push-file":
        s3 = upload_file(Path(args.path))
        if s3:
            print(json.dumps(patch_task(args.task_id, custom_fields={args.field: [{"file_s3_url": s3}]}), default=str, indent=2))
    elif args.cmd == "dispatch-runner":
        print(json.dumps(dispatch_runner(args.task_id), default=str, indent=2))
    elif args.cmd == "transition":
        print(json.dumps(transition(args.task_id, args.edge), default=str, indent=2))
    elif args.cmd == "create-task":
        wid = DOMAIN_WORLDS.get(args.world, args.world)
        print(json.dumps(create_task(wid, task_name=args.name), default=str, indent=2))
    elif args.cmd == "results":
        print(json.dumps(fetch_run_results(args.task_id), default=str, indent=2))


if __name__ == "__main__":
    main()
