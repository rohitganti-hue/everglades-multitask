# everglades-multitask

A Claude Code skill that lets Project Everglades experts construct, calibrate, and ship 3–5 inverse or forward scientific reasoning tasks in parallel — driven entirely from Claude Code, with the real Taiga 16-model eval as the final destination.

**What it gives you:**

- **Workflow A** — start with N distinct ideas *in your configured domain*, scaffold N drafts in parallel, batch preview, batch push to RLS, batch dispatch Taiga
- **Workflow B** — start with one idea, expand to 2–3 orthogonal siblings with a degeneracy check
- **Workflow C** — N tasks back from review; aggregate feedback, detect cross-task patterns, batch resubmit

> **Same-domain default.** Experts generally work in their assigned domain (EG-1 expert ships EG-1 tasks). The skill is single-domain per session: drafts share an anchor-example pool, tool families, and degeneracy-check semantics within a domain. To work in a different domain, re-run `scripts/setup.py` with the new domain code — don't mix in a single session.
- **Preview eval** — Opus 4.7 × 8 attempts via Anthropic API + tool-use, runs against your local `oracle.py`. ~90s vs ~40 min for a real Taiga 16-model run
- **Opinionated state machine** — every draft has a `STATE.md`; skill won't let you skip a Playbook step
- **Lint** — leak-checker for `problem.md` (method names, canonical targets, strategy hints) and `oracle.py` (judgment-style modes, missing budget)

## Install

```bash
git clone https://github.com/rohitganti-hue/everglades-multitask.git ~/.claude/skills/everglades-multitask
cd ~/.claude/skills/everglades-multitask
pip install anthropic numpy
python3 scripts/setup.py    # first-run wizard
```

Then in Claude Code:

```
/everglades-status
```

That's it. The skill auto-loads on Everglades-related prompts.

## Quickstart — Workflow A

(Example assumes you're configured as an EG-1 expert.)

```
> /everglades-ideate 3

Skill: Paste your 3 briefs (one per line). All in your configured domain (EG-1).

You:
  1) ATAC-seq, ALS iPSC subtype-specific signal vs covariates
  2) Single-cell biomarker, AD PBMC PANEL_B vs PANEL_A trap
  3) RNA velocity inverse, colorectal cancer reversion candidate

Skill: scaffolds 3 drafts at ~/everglades-drafts/{2026-05-28-atac, ...},
       walks Playbook Steps 1-4 across all 3 round-robin.

After ~25 min, all 3 drafts SCAFFOLDED.

> /everglades-preview-batch

  ATAC-seq:        2/8 ✓ IN RANGE
  PK 2-comp:       5/8 ✗ TOO EASY · urine mode leaks k10
  RNA velocity:    0/8 ✗ check main.py · 6/8 errored on tool call

Iterate the weak ones. Re-preview. Then:

> /everglades-push-all
> /everglades-eval-all
# (Taiga 16-model runs dispatched in parallel; ~50 min wall-clock)

> /everglades-submit task-a task-b
```

3 tasks shipped in one session.

## Repository layout

```
everglades-multitask/
├── SKILL.md                         # Skill entry point (Claude reads this)
├── README.md                        # This file
├── reference/                       # Compressed playbook + strategies + anchor examples
│   ├── playbook.md
│   ├── oracle-design.md
│   ├── strategies.md
│   ├── forward-task-guide.md
│   ├── anchor-examples-summary.md
│   └── field-map.json
├── scripts/                         # Python tooling
│   ├── setup.py                     # First-run wizard
│   ├── config.py                    # ~/.everglades/config.json loader
│   ├── field_map.py
│   ├── rls.py                       # RLS API client (list, get, patch, upload, dispatch)
│   ├── preview.py                   # Anthropic API preview eval (asyncio batch)
│   ├── verify.py                    # main.py vs oracle.py
│   ├── lint.py                      # leak checker
│   ├── degeneracy.py                # cross-sibling degeneracy
│   └── status.py
├── templates/
│   ├── inverse-task/                # oracle.py / main.py / shortcut.py / etc. scaffolds
│   └── forward-task/
└── examples/
    └── example-walkthrough.md       # Real anonymized walkthrough on approved EG-1 tasks
```

## Config

The skill stores credentials in `~/.everglades/config.json` (mode 600):

```json
{
  "rls_api_key": "rls-sk-...",
  "anthropic_api_key": "sk-ant-...",
  "domain_code": "EG-1",
  "world_id": "world_95d559681bc0411db772f38393216250",
  "expert_id": "user_...",
  "preview_model": "claude-opus-4-7",
  "preview_attempts": 8
}
```

Setup wizard prompts for each. Re-run `python3 scripts/setup.py` to update.

## Anatomy of a draft

Matches the **canonical Everglades CLI task structure** (per master instructions + `Mercor-Intelligence/stem-software` repo) — drafts are interchangeable with the GitHub CLI sandbox.

```
~/everglades-drafts/2026-05-28-rna-velocity/
├── problem.md                  # What the model sees — YOU write, last
├── config.yaml                 # domain, sub_domain, direction, simulator
├── requirements.txt            # Python deps (RLS: Required Packages)
├── oracle/
│   └── setup.py                # HIDDEN system — skill helps scaffold (RLS: Oracle File)
├── grader/
│   └── grading_guide.md        # Near-miss table — YOU write (RLS: Grading Guidance)
├── golden/
│   └── expected.json           # Golden answer + tolerance (RLS: Golden Response + Tolerance)
├── solution/
│   ├── main.py                 # Reference solve — skill helps scaffold (RLS: Verification Code)
│   └── shortcut.py             # Naive solver — skill-local, NOT uploaded
├── reasoning_trap.md           # The naive trap — YOU write (RLS: Reasoning Trap field)
├── BRIEF.md                    # Your idea in your words — skill workflow state
├── STATE.md                    # Playbook step + decisions — skill workflow state
└── runs/
    ├── verify_<ts>.json
    ├── shortcut_<ts>.json
    ├── preview_<ts>.json
    └── taiga_<run_id>.json     # after push + eval
```

**Forward tasks** swap `oracle/setup.py` for a `simulation/` directory of model-visible input files.

### File → RLS field mapping (on push)

| Canonical file | RLS field |
|---|---|
| `oracle/setup.py` | Oracle File (file upload) |
| `solution/main.py` | Verification Code (file upload) |
| `golden/expected.json` | Golden Response + Tolerance |
| `grader/grading_guide.md` | Grading Guidance |
| `problem.md` | User Prompt |
| `config.yaml` (parsed) | Domain, Subdomain, Directionality, Required Tool |
| `requirements.txt` | Required Packages |
| `reasoning_trap.md` | Reasoning Trap |

**AI Use Policy:** The skill helps scaffold `oracle/setup.py`, `solution/main.py`, and `solution/shortcut.py`. The skill does NOT write `problem.md`, `reasoning_trap.md`, `grader/grading_guide.md`, or your explanation. **You own the science.**

## Preview eval — how it works

The `preview` command launches N parallel Anthropic API calls (default: Opus 4.7 × 8 attempts), each with tool-use access to `query_oracle` and `submit_answer`. The `query_oracle` tool routes calls to your local `oracle.py`. The `submit_answer` tool compares to `expected.json` within tolerance.

Pass rate interpretation:

- **0/8** — check `main.py`; likely broken
- **1–2/8** — IN RANGE; dispatch to Taiga
- **3–4/8** — BORDERLINE; harden once
- **5+/8** — TOO EASY; transcript_analyzer suggests which strategy to apply

Roughly **90 seconds wall-clock** with `--attempts 8`, vs ~40 minutes for a real Taiga 16-model run.

## Example walkthrough

See [`examples/example-walkthrough.md`](examples/example-walkthrough.md) for a real anonymized walkthrough drawn from an EG-1 bioinformatics expert's actual May 4–8 sprint — including the duplicate task pair (`xm0vffa1` + `w49sa943`) that the degeneracy check would have caught at scaffold time.

## Status

⚠️ **v0.1 — work in progress.** Two RLS API endpoints are probed dynamically (file upload + Taiga dispatch) and may need adjustment as the RLS API surface stabilizes. The preview eval, lint, verify, and degeneracy checks are stable.

## License

Internal use only. Not for redistribution outside Mercor.
