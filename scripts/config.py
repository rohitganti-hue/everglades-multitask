"""Config loader. ~/.everglades/config.json holds the Anthropic key (optional)
+ the expert's domain code (used to pick anchor examples for scaffolding).

The skill is LOCAL-ONLY: no RLS API key, no Taiga API key. After local
iteration the expert copy-pastes drafts into the RLS web UI manually.
"""
import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".everglades" / "config.json"


def load(*, require_anthropic: bool = False):
    """Load ~/.everglades/config.json.

    Only `anthropic_api_key` and `domain_code` may live here. `anthropic_api_key`
    is needed solely by /everglades-preview; pass require_anthropic=True from
    preview.py to enforce it, otherwise it's optional.
    """
    if not CONFIG_PATH.exists():
        # No config file is OK — the skill works with sensible defaults if the
        # expert never wants /everglades-preview.
        return {"domain_code": "EG-1", "anthropic_api_key": None}
    with CONFIG_PATH.open() as f:
        cfg = json.load(f)
    if require_anthropic and not cfg.get("anthropic_api_key"):
        print(
            "Anthropic API key not configured. The proxy/preview eval "
            "(/everglades-preview) needs it. Run setup.py to add one, or "
            "skip preview and copy-paste straight to the RLS UI.",
            file=sys.stderr,
        )
        sys.exit(2)
    return cfg


def save(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


# Domain code -> canonical RLS world_id mapping. Used purely as a label so the
# scaffolding picks the right anchor example. NO RLS API CALLS are made.
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
    """The expert's draft workspace."""
    return Path.home() / "everglades-drafts"
