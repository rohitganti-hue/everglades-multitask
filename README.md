# everglades-multitask

A Claude Code skill that lets Project Everglades experts construct, calibrate, and iterate **3–5 inverse or forward scientific reasoning tasks in parallel, fully local**. When a draft is calibrated, the skill writes a MANIFEST mapping each file to its RLS form field — the expert opens the RLS web UI and copy-pastes from there. **No RLS or Taiga API key needed.**

**What it gives you:**

- **Workflow A** — N distinct task ideas in your domain, scaffolded in parallel, batch preview, batch export
- **Workflow B** — 1 idea → 2–3 orthogonal siblings with a degeneracy check
- **Preview eval** — Opus 4.7 × 8 attempts via Anthropic API + tool-use against your local `oracle/setup.py`. ~90s wall-clock per draft vs ~40 min for a real Taiga 16-model run. Optional — skip if you'd rather paste straight to RLS and let Taiga be your only signal.
- **Opinionated state machine** — every draft has a `STATE.md`; skill won't let you skip a Playbook step
- **Lint** — leak-checker for `problem.md` (method names, canonical targets, strategy hints) and `oracle/setup.py` (judgment-style modes, missing budget)
- **MANIFEST export** — single command writes a per-draft file-to-RLS-field mapping for clean copy-paste

> **Same-domain default.** Experts work in their assigned domain (EG-1 expert ships EG-1 tasks). The skill is single-domain per session: drafts share an anchor-example pool, tool families, and degeneracy-check semantics within a domain. To switch domains, re-run `scripts/setup.py`.

## Install

```bash
# 1. Clone the skill into Claude Code's skill directory
git clone https://github.com/rohitganti-hue/everglades-multitask ~/.claude/skills/everglades-multitask

# 2. Install Python dependencies
cd ~/.claude/skills/everglades-multitask
pip install -r requirements.txt

# 3. Run the first-run wizard
python3 scripts/setup.py
```

The wizard prompts for:

| Prompt | What to enter |
|---|---|
| Anthropic API key | **OPTIONAL** — only for `/everglades-preview`. Get one at <https://console.anthropic.com/> if you want the proxy eval; press Enter to skip. |
| Domain code | `EG-1` for Bioinformatics, `EG-2` for Comp Chemistry, etc. The scaffolder uses this to pick anchor examples. |

That's it. No RLS API key, no Taiga API key.

Then in Claude Code: `/everglades-status`.

## Quickstart — Workflow A

(Assumes you're configured as an EG-1 expert.)

```
> /everglades-ideate 3

Skill: Paste your 3 briefs (one per line). All in your configured domain (EG-1).

You:
  1) ATAC-seq, ALS iPSC subtype-specific signal vs covariates
  2) Single-cell biomarker, AD PBMC PANEL_B vs PANEL_A trap
  3) RNA velocity inverse, colorectal cancer reversion candidate

Skill: scaffolds 3 drafts in canonical CLI layout. Walks Playbook 1-4
       round-robin. Generates oracle/setup.py + solution/main.py +
       solution/shortcut.py for each.

> /everglades-preview-batch
  → ATAC-seq:        2/8 ✓ IN_RANGE
  → Single-cell-AD:  5/8 ✗ TOO_EASY (oracle leaks via module_score)
  → RNA velocity:    0/8 ✗ check main.py

# iterate the weak ones with skill's guidance, re-preview, then:

> /everglades-export draft-1
  Writes draft-1/MANIFEST.md.

# Skill says: "Open https://studio.mercor.com/, create a task in EG-1
#  world, and copy-paste from MANIFEST.md. Then click magic-star → STEM
#  Software Runner."

# Expert opens RLS UI, creates the task, pastes each file's contents into
# the matching form field, clicks magic-star. Taiga runs. ~30-50 min later
# results land. If ≤4/16 pass, the expert hits 'Submit for Review' in RLS.
```

The skill's job ends at `/everglades-export`. Everything after happens in the RLS web UI.

## Where your drafts live

All drafts are created under **`~/everglades-drafts/<draft-id>/`** — one folder per task. That's where you open `problem.md`, `reasoning_trap.md`, and `grader/grading_guide.md` to write your science. `/everglades-status` prints the path for each draft.

## Reduce permission prompts (lower AHT)

Claude Code asks before each script run and file edit; across a session those prompts add up. Cut them **safely** by allow-listing only this skill's operations in `~/.claude/settings.json` (don't use `--dangerously-skip-permissions` or a blanket `Bash(*)`):

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 ~/.claude/skills/everglades-multitask/scripts/*.py)",
      "Read(~/everglades-drafts/**)",
      "Edit(~/everglades-drafts/**)",
      "Write(~/everglades-drafts/**)"
    ]
  }
}
```

`~` expands and the file reloads live. Or pick **"Yes, don't ask again"** when prompted for a script. Run `/permissions` to review what's allowed.

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
│   └── anchor-examples-summary.md
├── scripts/                         # Python tooling — ALL LOCAL
│   ├── setup.py                     # First-run wizard
│   ├── config.py                    # ~/.everglades/config.json loader
│   ├── paths.py                     # Canonical-path helpers
│   ├── status.py                    # Walk drafts, show state + latest runs
│   ├── verify.py                    # solution/main.py vs oracle/setup.py
│   ├── preview.py                   # Anthropic API preview eval (Opus 4.7 × 8)
│   ├── lint.py                      # leak checker
│   ├── degeneracy.py                # cross-sibling degeneracy check
│   └── export.py                    # Write MANIFEST.md mapping files → RLS fields
├── templates/
│   ├── inverse-task/                # oracle/setup.py, solution/main.py, etc. scaffolds
│   └── forward-task/
└── examples/
    └── example-walkthrough.md       # Anonymized walkthrough on approved EG-1 tasks
```

## Anatomy of a draft

Matches the **canonical Everglades CLI task structure** (per master instructions + `Mercor-Intelligence/stem-software` repo). Drafts are bidirectionally compatible with the GitHub CLI sandbox.

```
~/everglades-drafts/2026-05-28-rna-velocity/
├── problem.md                  # What the model sees — YOU write, last
├── config.yaml                 # domain, sub_domain, direction, simulator
├── requirements.txt            # Python deps
├── oracle/
│   └── setup.py                # HIDDEN system — skill helps scaffold
├── grader/
│   └── grading_guide.md        # Near-miss table — YOU write
├── golden/
│   └── expected.json           # Golden answer + tolerance
├── solution/
│   ├── main.py                 # Reference solve — skill helps scaffold
│   └── shortcut.py             # Naive solver — skill-local
├── reasoning_trap.md           # The naive trap — YOU write
├── BRIEF.md                    # Your idea — skill workflow state
├── STATE.md                    # Playbook step — skill workflow state
├── MANIFEST.md                 # written by /everglades-export — copy-paste map
└── runs/
    ├── verify_<ts>.json
    ├── shortcut_<ts>.json
    └── preview_<ts>.json
```

**Forward tasks** swap `oracle/setup.py` for a `simulation/` directory of model-visible input files.

## File → RLS field mapping (on `/everglades-export`)

| Canonical file | RLS form field | Type |
|---|---|---|
| `problem.md` | **User Prompt** | text — paste |
| `oracle/setup.py` | **Oracle File** | file upload |
| `solution/main.py` | **Verification Code** | file upload |
| `golden/expected.json` → `answer` | **Golden Response** | text |
| `golden/expected.json` → `tolerance` | **Tolerance** | numeric |
| `grader/grading_guide.md` | **Grading Guidance** | text |
| `reasoning_trap.md` | **Reasoning Trap** | text |
| `requirements.txt` | **Required Packages** | text |
| `config.yaml` → `domain` / `sub_domain` / `direction` / `simulator` | **Domain** / **Subdomain** / **Directionality** / **Required Tool** | dropdown + text |
| _(write fresh in RLS UI)_ | **Explanation/Context** | text |

**AI Use Policy:** The skill helps scaffold `oracle/setup.py`, `solution/main.py`, and `solution/shortcut.py`. The skill does NOT write `problem.md`, `reasoning_trap.md`, `grader/grading_guide.md`, or your explanation. **You own the science.**

## Preview eval — how it works

The `/everglades-preview` command launches N parallel Anthropic API calls (default: Opus 4.7 × 8 attempts), each with tool-use access to:

- `query_oracle(mode, parameters)` — routes to your local `oracle/setup.py`
- `submit_answer(value)` — compares to `golden/expected.json` within tolerance

Pass rate interpretation (validated against Taiga ground truth, 2026-05-28):

| Pass rate | Verdict | Action |
|---|---|---|
| 0/8 | CHECK MAIN OR ORACLE | Likely main.py or oracle.py is broken |
| 1–2/8 | IN RANGE | `/everglades-export` and paste to RLS |
| 3/8 | BORDERLINE | Harden once, re-preview, OR `--force` if confident |
| 4+/8 | TOO EASY | Skill suggests which Strategy (1–5) to apply |

**~90 seconds wall-clock** with `--attempts 8`, vs ~40 minutes per real Taiga 16-model run.

## Example walkthrough

See [`examples/example-walkthrough.md`](examples/example-walkthrough.md) for a real anonymized walkthrough.

## Status

**v0.3 — local-only.** The skill makes zero RLS or Taiga API calls. Calibration happens locally; RLS submission is manual copy-paste from the MANIFEST.

## License

Internal use only. Not for redistribution outside Mercor.
