#!/usr/bin/env python3
"""First-run setup wizard for the everglades-multitask skill.

The FIRST thing it asks is the dashboard access token (required) — the expert
can't start work without it. Then the domain, then the optional Anthropic key.
It also wires the telemetry hook and sends an initial snapshot so the expert
shows on the dashboard immediately.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config import CONFIG_PATH, DOMAIN_CODES, DOMAINS, save, workspace_root, _eg_home


def prompt(label: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    if secret:
        try:
            import getpass
            val = getpass.getpass(f"{label}{suffix}: ")
        except Exception:
            val = input(f"{label}{suffix}: ")
    else:
        val = input(f"{label}{suffix}: ")
    val = val.strip()
    if not val and default is not None:
        return default
    return val


def wire_stop_hook() -> None:
    """Install the telemetry Stop hook into ~/.claude/settings.json so usage also
    reports at the end of each turn (best-effort — some environments block it, which
    is why the skill ALSO syncs explicitly as each phase advances). Idempotent.
    """
    settings = _eg_home() / ".claude" / "settings.json"
    cmd = "python3 ~/.claude/skills/everglades-multitask/scripts/telemetry.py"
    try:
        settings.parent.mkdir(parents=True, exist_ok=True)
        cfg = {}
        if settings.exists() and settings.stat().st_size:
            cfg = json.loads(settings.read_text())
        stop = cfg.setdefault("hooks", {}).setdefault("Stop", [])
        already = any(
            isinstance(h, dict) and h.get("command") == cmd
            for entry in stop
            if isinstance(entry, dict)
            for h in (entry.get("hooks") or [])
        )
        if not already:
            stop.append({"hooks": [{"type": "command", "command": cmd}]})
            settings.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass  # never let hook-wiring break setup; the per-phase sync covers it


def main():
    print("=== Everglades Multitask Skill — First-Run Setup ===\n")
    print(
        "This skill is LOCAL-ONLY. It scaffolds + calibrates Everglades task drafts\n"
        "on your machine; when one is ready you paste it into the RLS web UI. Your\n"
        "progress is reported to the team dashboard as you work.\n"
    )
    existing = {}
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open() as f:
                existing = json.load(f)
            print(f"Existing config at {CONFIG_PATH} will be updated.\n")
        except Exception:
            existing = {}

    # 1) Dashboard access token — FIRST and REQUIRED.
    print("Dashboard access token — REQUIRED. Your lead sent you a personal token")
    print("(eg_live_...) so your task progress shows on the team dashboard. You")
    print("cannot start work without it.")
    default_url = existing.get("telemetry_url", "https://everglades-phase-dashboard.vercel.app/api/ingest")
    telemetry_token = prompt("Dashboard access token (eg_live_...)", default=existing.get("telemetry_token") or None, secret=True)
    while not telemetry_token:
        print("  Required — paste the eg_live_... token your lead sent you.")
        telemetry_token = prompt("Dashboard access token (eg_live_...)", secret=True)
    telemetry_url = prompt("Dashboard URL", default=default_url)

    # 2) Domain.
    print("\nWhich domain are you working in?")
    for code, name in DOMAINS.items():
        print(f"  {code} — {name}")
    domain_code = prompt("Domain code (e.g. EG-1, EG-3)", default=existing.get("domain_code", "EG-1"))
    if domain_code not in DOMAIN_CODES:
        print(f"Unknown domain {domain_code!r}; falling back to EG-1.")
        domain_code = "EG-1"

    # 3) Anthropic key — OPTIONAL.
    print("\nAnthropic API key — OPTIONAL. Only used by /everglades-preview (the proxy")
    print("eval). Press Enter to skip; everything else still works.")
    anthropic_key = prompt(
        "Anthropic API key (starts with sk-ant-..., or blank to skip)",
        default=existing.get("anthropic_api_key", ""),
        secret=True,
    )

    cfg = {
        "anthropic_api_key": anthropic_key or None,
        "domain_code": domain_code,
        "telemetry_token": telemetry_token,
        "telemetry_url": telemetry_url,
        "preview_model": existing.get("preview_model", "claude-opus-4-7"),
        "preview_attempts": existing.get("preview_attempts", 8),
    }
    save(cfg)
    print(f"\n✓ Config written to {CONFIG_PATH} (mode 600)")
    if not anthropic_key:
        print("  (Anthropic key skipped — /everglades-preview will be disabled.)")
    workspace_root().mkdir(parents=True, exist_ok=True)
    print(f"✓ Draft workspace: {workspace_root()}")

    wire_stop_hook()

    # Send an initial snapshot so the expert shows on the dashboard right away.
    try:
        from tracker import sync
        print("\nSending an initial snapshot to the dashboard…")
        sync(quiet=False)
    except Exception:
        pass

    print("\nReady. In Claude Code, run /everglades-status to begin.\n")


if __name__ == "__main__":
    main()
