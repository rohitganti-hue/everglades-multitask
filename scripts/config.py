"""Config loader. ~/.everglades/config.json holds RLS + Anthropic creds + world id."""
import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".everglades" / "config.json"


def load():
    if not CONFIG_PATH.exists():
        print(
            f"Config not found at {CONFIG_PATH}.\n"
            "Run: python3 ~/.claude/skills/everglades-multitask/scripts/setup.py",
            file=sys.stderr,
        )
        sys.exit(2)
    with CONFIG_PATH.open() as f:
        cfg = json.load(f)
    required = ["rls_api_key", "anthropic_api_key", "world_id"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        print(f"Config missing keys: {missing}. Re-run setup.py.", file=sys.stderr)
        sys.exit(2)
    return cfg


def save(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


# Hard-coded — these never change for the STEM Software campaign.
CAMPAIGN_ID = "camp_591445dee0d942d6827f724012d2f684"
COMPANY_ID = "comp_2fa4115109d741cd94a3c409ed89e61f"
RLS_BASE = "https://api.studio.mercor.com"

# Approved/done status IDs across worlds
APPROVED_STATUSES = {
    "ce5f656b-6b79-4913-b0ba-37df93dc9eb1",
    "done",
}

# Per-domain world IDs
DOMAIN_WORLDS = {
    "Samples": "world_73b237efc96b4b4fbf736105946cbcb2",
    "EG-1": "world_95d559681bc0411db772f38393216250",
    "EG-2": "world_3a65693c950c42a9bf77ca7ada00d92e",
    "EG-3": "world_2f339a331c2b4e42af45b616e948b577",
    "EG-4": "world_c103da8ca544493c9c9ebeb12fff4235",
    "EG-5": "world_87f397299fe44817b9750c7aa72e4dd2",
    "EG-6": "world_a7697c54b3dd42c2bd9dc45c1580f260",
    "EG-7": "world_f359f5689aaa46ff952b67239580b7c3",
    "EG-8": "world_2e47c25ea4af477999cfe545fa279837",
    "EG-9": "world_71cbe60f81ec43d79cacef9fa764ba19",
}


def workspace_root():
    """The expert's draft + task workspace."""
    return Path.home() / "everglades-drafts"


def tasks_root():
    return Path.home() / "everglades-tasks"


def assert_same_domain(brief_domain_code: str | None) -> None:
    """Enforce same-domain default. If a brief specifies a domain that doesn't
    match the configured one, refuse and direct the expert to re-run setup.

    The skill is single-domain per session — drafts in a session must share
    a world_id so scaffolding, anchor examples, degeneracy checks, and
    cross-task feedback patterns all work cleanly.
    """
    if not brief_domain_code:
        return  # Brief didn't specify — default to configured
    cfg = load()
    configured = cfg.get("domain_code")
    if configured and brief_domain_code != configured:
        print(
            f"\n⚠ Domain mismatch:\n"
            f"   configured domain: {configured}\n"
            f"   brief domain:      {brief_domain_code}\n\n"
            f"The skill is single-domain per session. Either:\n"
            f"  (a) Update the brief to use {configured} (your configured domain), or\n"
            f"  (b) Re-run `python3 scripts/setup.py` with domain_code={brief_domain_code}\n"
            f"      to switch your active domain.\n\n"
            f"Don't mix domains in a single session — scaffolding, anchor examples,\n"
            f"and degeneracy checks only work within a domain.",
            file=sys.stderr,
        )
        sys.exit(3)
