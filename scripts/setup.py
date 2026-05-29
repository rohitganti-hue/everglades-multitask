#!/usr/bin/env python3
"""First-run setup wizard for the everglades-multitask skill.

Writes ~/.everglades/config.json with the expert's RLS key, Anthropic key,
and assigned domain world.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config import CONFIG_PATH, DOMAIN_WORLDS, save, workspace_root, tasks_root


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


def main():
    print("=== Everglades Multitask Skill — First-Run Setup ===\n")
    existing = {}
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open() as f:
                existing = json.load(f)
            print(f"Existing config at {CONFIG_PATH} will be updated.\n")
        except Exception:
            existing = {}

    rls_key = prompt(
        "RLS API key (starts with rls-sk-...)",
        default=existing.get("rls_api_key"),
        secret=True,
    )
    print(
        "\nAnthropic API key (OPTIONAL — only needed for /everglades-preview).\n"
        "If you skip preview, you can push drafts straight to RLS and let the\n"
        "real Taiga 16-model eval be your only signal. Press Enter to skip."
    )
    anthropic_key = prompt(
        "Anthropic API key (starts with sk-ant-..., or blank to skip)",
        default=existing.get("anthropic_api_key", ""),
        secret=True,
    )

    print("\nWhich domain world are you primarily working in?")
    for code, wid in DOMAIN_WORLDS.items():
        print(f"  {code:8s}  {wid}")
    domain_code = prompt(
        "Domain code (e.g. EG-1, EG-7)",
        default=existing.get("domain_code", "EG-1"),
    )
    if domain_code not in DOMAIN_WORLDS:
        print(f"Unknown domain {domain_code}; falling back to EG-1.")
        domain_code = "EG-1"
    world_id = DOMAIN_WORLDS[domain_code]

    expert_id = prompt(
        "Your RLS expert/user ID (optional, helps filter your tasks)",
        default=existing.get("expert_id", ""),
    )

    cfg = {
        "rls_api_key": rls_key,
        "anthropic_api_key": anthropic_key or None,
        "domain_code": domain_code,
        "world_id": world_id,
        "expert_id": expert_id or None,
        "preview_model": existing.get("preview_model", "claude-opus-4-7"),
        "preview_attempts": existing.get("preview_attempts", 8),
    }
    save(cfg)
    print(f"\n✓ Config written to {CONFIG_PATH} (mode 600)")
    if not anthropic_key:
        print("  (Anthropic key skipped — /everglades-preview will be disabled.)")
    workspace_root().mkdir(parents=True, exist_ok=True)
    tasks_root().mkdir(parents=True, exist_ok=True)
    print(f"✓ Draft workspace: {workspace_root()}")
    print(f"✓ Pushed-task workspace: {tasks_root()}")
    print("\nReady. In Claude Code, run /everglades-status to begin.\n")


if __name__ == "__main__":
    main()
