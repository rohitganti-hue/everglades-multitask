#!/usr/bin/env python3
"""telemetry.py — emit a per-expert skill-usage snapshot to the phase dashboard.

Consensual, OPT-IN product telemetry. It reports METADATA ONLY — per-draft phase,
artifact-presence sub-steps, preview pass rates, counts, timestamps. It NEVER
sends task content: no problem.md text, no oracle/solution code, no answers.

Designed to run as a Claude Code `Stop` hook (fires at the end of each turn), so
the dashboard reflects "as of the expert's last turn." It is deliberately:
  - stdlib-only (no numpy/pyyaml/anthropic import) so it can't fail on a missing dep,
  - fail-silent and non-blocking (≤5s, never raises) so it can't break a session,
  - a no-op unless a token + url are configured (opt-in).

Config (env wins over config.json):
  token : $EVERGLADES_TELEMETRY_TOKEN   else ~/.everglades/config.json "telemetry_token"
  url   : $EVERGLADES_TELEMETRY_URL     else ~/.everglades/config.json "telemetry_url"
  drafts: $EVERGLADES_DRAFTS_ROOT       else ~/everglades-drafts

CLI:
  python3 telemetry.py            # build snapshot + POST (silent; no-op if unconfigured)
  python3 telemetry.py --dry-run  # print the snapshot JSON, do NOT POST
  python3 telemetry.py --debug    # POST and print status/errors to stderr
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

SCHEMA_VERSION = 1


def _eg_home() -> Path:
    return Path(os.environ.get("EVERGLADES_HOME") or Path.home())


CONFIG_PATH = _eg_home() / ".everglades" / "config.json"


# --- config / paths (stdlib-only; no skill imports so the hook can't dep-fail) ---

def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def _drafts_root() -> Path:
    override = os.environ.get("EVERGLADES_DRAFTS_ROOT")
    if override:
        return Path(override).expanduser()
    return _eg_home() / "everglades-drafts"


# --- tiny parsers (mirror status.py, kept inline to stay dependency-free) ---

def _state_field(draft: Path) -> str:
    """Read the canonical phase from STATE.md's `state:` line (what status.py uses)."""
    p = draft / "STATE.md"
    try:
        for line in p.read_text().splitlines():
            if line.startswith("state:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "BRIEFED"


def _config_field(draft: Path, key: str):
    """Light line-parse of config.yaml (avoids a pyyaml dependency in the hook)."""
    p = draft / "config.yaml"
    try:
        for line in p.read_text().splitlines():
            if line.strip().startswith(f"{key}:"):
                val = line.split(":", 1)[1]
                return val.split("#", 1)[0].strip().strip('"\'') or None
    except Exception:
        pass
    return None


def _latest_run(draft: Path, kind: str):
    runs = draft / "runs"
    try:
        matches = sorted(runs.glob(f"{kind}_*.json"))
        if matches:
            return json.loads(matches[-1].read_text())
    except Exception:
        pass
    return None


def _nonempty(p: Path) -> bool:
    try:
        return p.exists() and p.stat().st_size > 0
    except OSError:
        return False


def _answer_locked(draft: Path) -> bool:
    p = draft / "golden" / "expected.json"
    try:
        ans = json.loads(p.read_text()).get("answer")
        return ans not in (None, "", [], {})
    except Exception:
        return False


def _run_passed(draft: Path, kind: str):
    r = _latest_run(draft, kind)
    if not r:
        return None
    for k in ("passed", "correct", "pass"):
        if k in r:
            return bool(r[k])
    return None


def _last_activity(draft: Path) -> float:
    latest = 0.0
    try:
        for sub in draft.rglob("*"):
            try:
                if sub.is_file():
                    latest = max(latest, sub.stat().st_mtime)
            except OSError:
                continue
    except OSError:
        pass
    try:
        return latest or draft.stat().st_mtime
    except OSError:
        return latest


def _direction(draft: Path) -> str:
    if (draft / "oracle" / "setup.py").exists():
        return "inverse"
    sim = draft / "simulation"
    try:
        if sim.exists() and any(sim.iterdir()):
            return "forward"
    except OSError:
        pass
    return (_config_field(draft, "direction") or "unknown").lower()


# --- snapshot construction ---

def build_draft_vector(draft: Path) -> dict:
    preview = _latest_run(draft, "preview")
    pass_rate = None
    if preview and preview.get("attempts"):
        pass_rate = f"{preview.get('passes', '?')}/{preview.get('attempts')}"

    scaffolded = (
        (draft / "oracle" / "setup.py").exists()
        and (draft / "solution" / "main.py").exists()
        and (draft / "solution" / "shortcut.py").exists()
    )
    shortcut_raw = _run_passed(draft, "shortcut")
    steps = {
        "brief": (draft / "BRIEF.md").exists(),
        "answer_locked": _answer_locked(draft),
        "jobs": _nonempty(draft / "grader" / "grading_guide.md"),
        "scaffolded": scaffolded,
        "verified": _run_passed(draft, "verify"),
        # shortcut MUST fail to be calibrated → "good" when the run did NOT pass
        "shortcut_failed": (shortcut_raw is False) if shortcut_raw is not None else None,
        "prompt_written": _nonempty(draft / "problem.md"),
        "previewed": preview is not None,
        "exported": (draft / "MANIFEST.md").exists(),
    }
    return {
        "draft_id": draft.name,
        "domain": _config_field(draft, "domain"),
        "direction": _direction(draft),
        "phase": _state_field(draft),
        "steps": steps,
        "preview_pass_rate": pass_rate,
        "last_activity": round(_last_activity(draft), 3),
    }


def build_snapshot(cfg: dict) -> dict:
    root = _drafts_root()
    drafts = []
    if root.exists():
        for d in sorted(root.iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                try:
                    drafts.append(build_draft_vector(d))
                except Exception:
                    continue  # one bad draft never sinks the snapshot

    exported = [d for d in drafts if d["steps"]["exported"] or d["phase"] == "EXPORTED"]
    iterating = [d for d in drafts if d not in exported]
    active = max(iterating or drafts, key=lambda d: d["last_activity"], default=None)

    return {
        "schema_version": SCHEMA_VERSION,
        "ts": int(time.time()),
        # the token identifies the expert server-side; this is just a human label
        "expert_label": cfg.get("expert_id") or cfg.get("email") or cfg.get("domain_code"),
        "domain_code": cfg.get("domain_code"),
        "rollup": {
            "total_drafts_present": len(drafts),
            "iterating": len(iterating),       # present and not yet exported
            "exported": len(exported),         # reached EXPORTED / MANIFEST written ("chose to upload")
            "active_draft": active["draft_id"] if active else None,
            "sibling_mode": (root / "_shared").exists(),  # Workflow B in play
        },
        # NOTE: "discarded" is derived SERVER-SIDE by diffing snapshots over time
        # (a draft that disappears without reaching EXPORTED). The emitter only
        # reports the drafts present right now — the history lives on the dashboard.
        "drafts": drafts,
    }


def _post(url: str, token: str, payload: dict, debug: bool) -> bool:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if debug:
                print(f"[telemetry] POST {resp.status}", file=sys.stderr)
            return True
    except Exception as e:  # noqa: BLE001 — never let telemetry break the session
        if debug:
            print(f"[telemetry] POST failed: {e}", file=sys.stderr)
        return False


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Everglades skill-usage telemetry emitter")
    p.add_argument("--dry-run", action="store_true", help="print the snapshot, don't POST")
    p.add_argument("--debug", action="store_true", help="print POST status/errors")
    args = p.parse_args(argv)

    try:
        cfg = _load_config()
        snapshot = build_snapshot(cfg)

        if args.dry_run:
            print(json.dumps(snapshot, indent=2))
            return

        token = os.environ.get("EVERGLADES_TELEMETRY_TOKEN") or cfg.get("telemetry_token")
        url = os.environ.get("EVERGLADES_TELEMETRY_URL") or cfg.get("telemetry_url")
        if not token or not url:
            if args.debug:
                print("[telemetry] no token/url configured — skipping (opt-in)", file=sys.stderr)
            return
        _post(url, token, snapshot, args.debug)
    except Exception as e:  # noqa: BLE001 — hard guarantee: never raise from a Stop hook
        if args.debug:
            print(f"[telemetry] error (swallowed): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
