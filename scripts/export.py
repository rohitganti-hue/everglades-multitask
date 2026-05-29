"""Export a draft to a copy-paste-ready bundle for the RLS web UI.

Writes a MANIFEST.md to the draft directory listing exactly which local file
goes to which RLS form field. The expert opens https://studio.mercor.com/,
creates a new task in their domain world, and copy-pastes from each file.

No RLS API calls. The skill is local-only.

CLI:
  python3 export.py <draft_dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import paths as paths_mod


MANIFEST_TEMPLATE = """# {name} — RLS submission manifest

Local draft is calibrated. Copy each file's contents into the matching field
in the RLS task form at https://studio.mercor.com/.

## File → RLS field

| Local file | RLS form field | Type |
|---|---|---|
| `problem.md` | **User Prompt** | text — paste contents |
| `oracle/setup.py` | **Oracle File** | file upload — drag-drop the file |
| `solution/main.py` | **Verification Code** | file upload — drag-drop the file |
| `golden/expected.json` → `answer` | **Golden Response** | text — paste the `answer` value only |
| `golden/expected.json` → `tolerance` | **Tolerance** | numeric — paste the `tolerance` value |
| `grader/grading_guide.md` | **Grading Guidance** | text — paste contents |
| `reasoning_trap.md` | **Reasoning Trap** | text — paste contents |
| `requirements.txt` | **Required Packages** | text — paste contents |
| `config.yaml` → `domain` | **Domain** (dropdown) | select the matching value |
| `config.yaml` → `sub_domain` | **Subdomain** | text |
| `config.yaml` → `direction` | **Directionality** (dropdown) | Forward or Inverse |
| `config.yaml` → `simulator` | **Required Tool** | text — primary tool |
| (write fresh in the RLS UI) | **Explanation/Context** | text — your reasoning the reviewer reads |

## After pasting

1. Click the magic-star icon at the top of the RLS task → **Run AutoQC**. Address any failures.
2. Click magic-star → **STEM Software Runner** to dispatch the real Taiga 16-model eval.
3. Wait ~30–50 minutes. If ≤ 4/16 pass, click **Submit for Review**. If 5+/16, harden and re-export.

## Calibration snapshot

{calibration}

## Draft files (raw paths)

{file_listing}
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("draft")
    args = p.parse_args()
    draft = Path(args.draft).expanduser().resolve()
    if not draft.is_dir():
        print(f"No such draft: {draft}", file=sys.stderr)
        sys.exit(2)

    # Gather calibration snapshot
    parts = []
    expected = paths_mod.expected_json(draft)
    if expected.exists():
        try:
            data = json.loads(expected.read_text())
            parts.append(f"- **Golden answer:** `{data.get('answer')}`")
            parts.append(f"- **Tolerance:** `{data.get('tolerance')}` ({data.get('unit', '')})".rstrip(' ()'))
        except Exception:
            pass

    runs = paths_mod.runs_dir(draft)
    if runs.exists():
        verify = sorted(runs.glob("verify_*.json"))
        shortcut = sorted(runs.glob("shortcut_*.json"))
        preview = sorted(runs.glob("preview_*.json"))
        if verify:
            v = json.loads(verify[-1].read_text())
            parts.append(f"- **Local verify:** main.py returned `{v.get('submitted')}` (passed: {v.get('passed')})")
        if shortcut:
            s = json.loads(shortcut[-1].read_text())
            parts.append(f"- **Local shortcut:** naive solver returned `{s.get('submitted')}` (must fail: {not s.get('passed')})")
        if preview:
            pv = json.loads(preview[-1].read_text())
            parts.append(f"- **Proxy eval:** {pv.get('passes')}/{pv.get('attempts')} attempts passed ({pv.get('model')})")
    calibration = "\n".join(parts) if parts else "_(no run logs yet — run /everglades-verify and /everglades-preview before exporting)_"

    # File listing
    files = []
    for relpath in [
        "problem.md",
        "oracle/setup.py",
        "solution/main.py",
        "solution/shortcut.py",
        "golden/expected.json",
        "grader/grading_guide.md",
        "reasoning_trap.md",
        "config.yaml",
        "requirements.txt",
    ]:
        f = draft / relpath
        marker = "✓" if f.exists() else "✗"
        files.append(f"- {marker} `{relpath}`")
    file_listing = "\n".join(files)

    manifest = MANIFEST_TEMPLATE.format(
        name=draft.name,
        calibration=calibration,
        file_listing=file_listing,
    )
    (draft / "MANIFEST.md").write_text(manifest)

    # Update STATE.md
    state_path = paths_mod.state_md(draft)
    if state_path.exists():
        text = state_path.read_text()
        if "state: " in text:
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("state:"):
                    lines[i] = "state: EXPORTED"
                    break
            state_path.write_text("\n".join(lines))

    print(f"\n✓ Wrote {draft / 'MANIFEST.md'}")
    print(f"\nNext: open https://studio.mercor.com/, create a new task in your domain")
    print(f"world, and copy-paste each file per the MANIFEST mapping. Then click")
    print(f"magic-star → STEM Software Runner to launch the Taiga 16-model eval.\n")


if __name__ == "__main__":
    main()
