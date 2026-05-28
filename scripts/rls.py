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
  python3 rls.py push-file <task_id> --field oracle_file --path ./oracle/setup.py
  python3 rls.py push-draft <draft_dir> --task <task_id>    # uploads from canonical paths
  python3 rls.py dispatch-runner <task_id>
  python3 rls.py transition <task_id> --edge submit_for_review

This is intentionally a thin wrapper. The skill's higher-level commands compose
multiple calls (e.g., /everglades-push = create + push-file × N + patch × M).

CANONICAL-PATH MAPPING (file -> RLS field):
  oracle/setup.py            -> oracle_file        (inverse only)
  solution/main.py           -> verification_code
  golden/expected.json       -> Golden Response + Tolerance (parsed)
  grader/grading_guide.md    -> grading_guidance
  problem.md                 -> User Prompt
  config.yaml                -> Domain + Subdomain + Directionality + Required Tool (parsed)
  reasoning_trap.md          -> reasoning_trap
  requirements.txt           -> packages
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
import paths as paths_mod


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
    """DEPRECATED — the skill no longer programmatically dispatches Taiga.

    After /everglades-push, the expert opens the RLS task URL and clicks
    the magic-star → STEM Software Runner in the RLS UI. This is intentional:
      - RLS UI shows live Taiga progress nicely
      - The dispatch is a single click (≈30s for a batch of 3)
      - Avoids reverse-engineering the magic-star endpoint

    This function is kept as a stub for future use if Mercor exposes a clean
    public RLS API for triggering the 16-model runner. For now, prints a
    pointer to the RLS UI URL.
    """
    print(
        f"\n→ Open https://studio.mercor.com/task/{task_id}\n"
        f"  Click magic-star → {runner_name}\n"
        f"  Then run /everglades-status to poll, or /everglades-results {task_id}\n",
        file=sys.stderr,
    )
    return {"action": "manual_dispatch", "task_id": task_id, "ui_url": f"https://studio.mercor.com/task/{task_id}"}


def push_draft(draft_dir: Path, *, task_id: str) -> dict:
    """Upload a draft's canonical files to its RLS task.

    Maps the master CLI layout to RLS custom fields exactly:
      oracle/setup.py            -> oracle_file
      solution/main.py           -> verification_code
      grader/grading_guide.md    -> grading_guidance
      problem.md                 -> user prompt (passed via custom_fields)
      reasoning_trap.md          -> reasoning_trap
      requirements.txt           -> packages
      golden/expected.json       -> Golden Response + Tolerance (parsed)
      config.yaml                -> Domain + Subdomain + Directionality + Required Tool (parsed)
    """
    results = {}

    # 1. File uploads
    if paths_mod.oracle_setup(draft_dir).exists():
        s3 = upload_file(paths_mod.oracle_setup(draft_dir))
        if s3:
            patch_task(task_id, custom_fields={"oracle_file": [{"file_s3_url": s3}]})
            results["oracle_file"] = s3
    if paths_mod.main_py(draft_dir).exists():
        s3 = upload_file(paths_mod.main_py(draft_dir))
        if s3:
            patch_task(task_id, custom_fields={"verification_code": [{"file_s3_url": s3}]})
            results["verification_code"] = s3

    # 2. Text field PATCHes
    text_fields = {}
    if paths_mod.problem_md(draft_dir).exists():
        # User prompt is a special field — handled via task_prompt_messages on RLS
        text_fields["_prompt"] = paths_mod.problem_md(draft_dir).read_text()
    if paths_mod.grading_guide(draft_dir).exists():
        text_fields["grading_guidance"] = paths_mod.grading_guide(draft_dir).read_text()
    if paths_mod.reasoning_trap(draft_dir).exists():
        text_fields["reasoning_trap"] = paths_mod.reasoning_trap(draft_dir).read_text()
    if paths_mod.requirements_txt(draft_dir).exists():
        text_fields["packages"] = paths_mod.requirements_txt(draft_dir).read_text()

    # 3. Parse config.yaml
    cfg_path = paths_mod.config_yaml(draft_dir)
    if cfg_path.exists():
        for line in cfg_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = [x.strip() for x in line.split(":", 1)]
            v = v.strip('"').strip("'")
            if k == "domain": text_fields["domain"] = v
            elif k in ("sub_domain", "subdomain"): text_fields["subdomain"] = v
            elif k in ("direction", "directionality"): text_fields["directionality"] = v.capitalize()
            elif k == "simulator": text_fields["tool"] = v

    # 4. Parse golden/expected.json
    exp_path = paths_mod.expected_json(draft_dir)
    if exp_path.exists():
        try:
            exp = json.loads(exp_path.read_text())
            if exp.get("tolerance") is not None:
                text_fields["tolerance"] = exp["tolerance"]
            # Golden Response value is set via a separate API; not a custom_field
            # TODO: confirm API endpoint for setting golden response per RLS docs
            results["golden_answer_pending"] = str(exp.get("answer"))
        except Exception as e:
            results["expected_json_parse_error"] = str(e)

    # Drop the special _prompt key — it's set via a different mechanism
    prompt_text = text_fields.pop("_prompt", None)
    if prompt_text:
        results["prompt_pending"] = "User Prompt is set via task_prompt_messages, not custom_fields. TODO."

    if text_fields:
        patch_task(task_id, custom_fields=text_fields)
        results.update({k: "PATCHed" for k in text_fields})

    return results


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

    s = sub.add_parser("push-draft", help="Upload a draft's canonical files + custom_fields to its RLS task")
    s.add_argument("draft_dir")
    s.add_argument("--task", required=True, help="RLS task_id")

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
        # Prints the magic-star instructions; doesn't actually call any API.
        print(json.dumps(dispatch_runner(args.task_id), default=str, indent=2))
    elif args.cmd == "transition":
        print(json.dumps(transition(args.task_id, args.edge), default=str, indent=2))
    elif args.cmd == "create-task":
        wid = DOMAIN_WORLDS.get(args.world, args.world)
        print(json.dumps(create_task(wid, task_name=args.name), default=str, indent=2))
    elif args.cmd == "push-draft":
        print(json.dumps(push_draft(Path(args.draft_dir).expanduser().resolve(), task_id=args.task), default=str, indent=2))
    elif args.cmd == "results":
        print(json.dumps(fetch_run_results(args.task_id), default=str, indent=2))


if __name__ == "__main__":
    main()
