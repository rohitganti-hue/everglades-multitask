"""Config loader. ~/.everglades/config.json holds the Anthropic key (optional)
+ the expert's domain code (used to pick anchor examples for scaffolding).

The skill is LOCAL-ONLY: no RLS API key, no Taiga API key. After local
iteration the expert copy-pastes drafts into the RLS web UI manually.
"""
import json
import os
import sys
from pathlib import Path

def _eg_home() -> Path:
    """Home base for the skill's config + drafts. EVERGLADES_HOME overrides ~
    (used to run multiple expert profiles / tests on one machine)."""
    return Path(os.environ.get("EVERGLADES_HOME") or Path.home())


CONFIG_PATH = _eg_home() / ".everglades" / "config.json"


def load(*, require_anthropic: bool = False, require_telemetry: bool = False):
    """Load ~/.everglades/config.json.

    Holds `domain_code`, optional `anthropic_api_key`, and the telemetry creds
    (`telemetry_token` + `telemetry_url`). `require_anthropic` is enforced by
    preview.py. `require_telemetry` is enforced by the always-on entry points so
    an expert must insert their token before doing any work.
    """
    cfg = {"domain_code": "EG-1", "anthropic_api_key": None}
    if CONFIG_PATH.exists():
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

    if require_telemetry:
        tok = os.environ.get("EVERGLADES_TELEMETRY_TOKEN") or cfg.get("telemetry_token")
        url = os.environ.get("EVERGLADES_TELEMETRY_URL") or cfg.get("telemetry_url")
        if not (tok and url):
            print(
                "\n⛔ Telemetry token required before you can start work.\n"
                "   Run:  python3 scripts/setup.py   and paste the token your lead sent you.\n"
                "   (Saved to ~/.everglades/config.json as telemetry_token + telemetry_url.)\n",
                file=sys.stderr,
            )
            sys.exit(3)

    return cfg


def save(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


# The six Everglades domains (code → official name). Used as a label so the
# scaffolder picks the right anchor example. The skill is local-only — it makes
# NO RLS API calls, so no world_id (or other internal RLS identifier) is stored.
DOMAINS = {
    "EG-1": "Bioinformatics and Systems Biology",
    "EG-2": "Computational Chemistry",
    "EG-3": "Physics",
    "EG-4": "Electrical Engineering",
    "EG-5": "Mechanical and Structural Engineering",
    "EG-6": "Applied Statistics and Mathematics",
}
DOMAIN_CODES = tuple(DOMAINS)  # ("EG-1", … "EG-6") — for validation / back-compat


def workspace_root():
    """The expert's draft workspace."""
    return _eg_home() / "everglades-drafts"
