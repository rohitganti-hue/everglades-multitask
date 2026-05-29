#!/usr/bin/env python3
"""First-run setup wizard for the everglades-multitask skill.

The skill is LOCAL-ONLY: builds + calibrates drafts on disk, then the expert
copy-pastes into the RLS web UI. We only ask for:
  - Anthropic API key (OPTIONAL — for /everglades-preview)
  - Domain code (lets the scaffolder pick the right anchor example)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config import CONFIG_PATH, DOMAIN_WORLDS, save, workspace_root


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
    print(
        "This skill is LOCAL-ONLY. It scaffolds + calibrates Everglades inverse\n"
        "and forward task drafts on your machine. When a draft is ready, you\n"
        "copy-paste it into the RLS web UI (https://studio.mercor.com/) and\n"
        "click 'magic-star → STEM Software Runner' there to launch Taiga.\n"
        "No RLS API key needed.\n"
    )
    existing = {}
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open() as f:
                existing = json.load(f)
            print(f"Existing config at {CONFIG_PATH} will be updated.\n")
        except Exception:
            existing = {}

    print("Anthropic API key — OPTIONAL. Only used by /everglades-preview (the")
    print("proxy eval: Opus 4.7 × 8 attempts via tool-use against your local")
    print("oracle.py). Press Enter to skip; everything else still works.")
    anthropic_key = prompt(
        "Anthropic API key (starts with sk-ant-..., or blank to skip)",
        default=existing.get("anthropic_api_key", ""),
        secret=True,
    )

    print("\nWhich domain are you working in?")
    for code in DOMAIN_WORLDS:
        print(f"  {code}")
    domain_code = prompt(
        "Domain code (e.g. EG-1, EG-7)",
        default=existing.get("domain_code", "EG-1"),
    )
    if domain_code not in DOMAIN_WORLDS:
        print(f"Unknown domain {domain_code!r}; falling back to EG-1.")
        domain_code = "EG-1"

    cfg = {
        "anthropic_api_key": anthropic_key or None,
        "domain_code": domain_code,
        "preview_model": existing.get("preview_model", "claude-opus-4-7"),
        "preview_attempts": existing.get("preview_attempts", 8),
    }
    save(cfg)
    print(f"\n✓ Config written to {CONFIG_PATH} (mode 600)")
    if not anthropic_key:
        print("  (Anthropic key skipped — /everglades-preview will be disabled.)")
    workspace_root().mkdir(parents=True, exist_ok=True)
    print(f"✓ Draft workspace: {workspace_root()}")
    print("\nReady. In Claude Code, run /everglades-status to begin.\n")


if __name__ == "__main__":
    main()
