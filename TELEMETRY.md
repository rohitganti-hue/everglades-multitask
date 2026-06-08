# Skill-usage telemetry (opt-in)

`scripts/telemetry.py` emits a per-expert snapshot of skill usage to the Everglades phase
dashboard, so leads can see how many tasks an expert is iterating on, which one is active,
and where each draft sits in the cycle.

**It is opt-in and metadata-only.** It reports phase, artifact-presence sub-steps, preview
pass rates, counts, and timestamps. It **never** sends task content — no `problem.md` text,
no oracle/solution code, no answers. If no token + URL are configured, it does nothing.

It's also non-blocking: stdlib-only, ≤1.5s, and it can never raise — a failed/offline POST
is swallowed so it can't slow or break a Claude Code session.

---

## 1. Get your token

Your lead issues you a personal token (looks like `eg_live_xxx`) and the dashboard ingest
URL. The token identifies you to the dashboard; don't share it.

## 2. Configure it (pick one)

**A — config file (recommended).** Add two keys to `~/.everglades/config.json`:

```json
{
  "domain_code": "EG-1",
  "telemetry_url": "https://<your-dashboard>.vercel.app/api/ingest",
  "telemetry_token": "eg_live_xxxxxxxxxxxx"
}
```

**B — environment variables (override the config file).** Put these in your shell profile
(`~/.zshrc`) or the hook command:

```bash
export EVERGLADES_TELEMETRY_URL="https://<your-dashboard>.vercel.app/api/ingest"
export EVERGLADES_TELEMETRY_TOKEN="eg_live_xxxxxxxxxxxx"
```

## 3. Wire the Stop hook

So it fires automatically at the end of each Claude turn, add this to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/skills/everglades-multitask/scripts/telemetry.py" }
        ]
      }
    ]
  }
}
```

(If you used environment variables in option B and your hook shell doesn't load your profile,
inline them in the command: `EVERGLADES_TELEMETRY_URL=… EVERGLADES_TELEMETRY_TOKEN=… python3 …/telemetry.py`.)

## 4. Verify

```bash
# Print exactly what would be sent (no network):
python3 ~/.claude/skills/everglades-multitask/scripts/telemetry.py --dry-run

# POST once and show the result/errors:
python3 ~/.claude/skills/everglades-multitask/scripts/telemetry.py --debug
```

---

## What gets sent (schema v1)

```jsonc
{
  "schema_version": 1,
  "ts": 1780433680,                  // unix seconds
  "expert_label": "EG-1",            // human hint only; the token is the real identity
  "domain_code": "EG-1",
  "rollup": {
    "total_drafts_present": 3,
    "iterating": 2,                  // drafts present and not yet exported
    "exported": 1,                   // reached EXPORTED / MANIFEST written ("chose to upload")
    "active_draft": "draft-b",       // most-recently-touched non-exported draft
    "sibling_mode": true             // a _shared/ dir exists → Workflow B in play
  },
  "drafts": [
    {
      "draft_id": "draft-b",
      "domain": "EG-3",
      "direction": "inverse",
      "phase": "CALIBRATED",         // canonical state from STATE.md (same as /everglades-status)
      "steps": {                     // artifact-presence sub-steps (finer than phase)
        "brief": true, "answer_locked": true, "jobs": true, "scaffolded": true,
        "verified": true, "shortcut_failed": true, "prompt_written": false,
        "previewed": false, "exported": false
      },
      "preview_pass_rate": "2/8",    // from runs/preview_*.json, or null
      "last_activity": 1780433679.94 // max file mtime in the draft
    }
  ]
}
```

`draft_id` is the local folder name — not the task content. **"discarded" is computed on the
dashboard** by diffing snapshots over time (a draft that disappears without ever exporting);
the emitter only reports the drafts present right now.

## Config / env reference

| Setting | Env var | config.json key | Default |
|---|---|---|---|
| Ingest URL | `EVERGLADES_TELEMETRY_URL` | `telemetry_url` | unset → no-op |
| Token | `EVERGLADES_TELEMETRY_TOKEN` | `telemetry_token` | unset → no-op |
| Drafts dir | `EVERGLADES_DRAFTS_ROOT` | — | `~/everglades-drafts` |

Env vars win over `config.json`. With neither URL nor token set, telemetry is a silent no-op.
