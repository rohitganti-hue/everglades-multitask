"""Single source of truth for the draft state machine.

Previously the state list lived in two places — status.py (which introduced a
JOBS state) and SKILL.md (which had no JOBS but added BORDERLINE). The two
could drift independently. This module is now the canonical definition; both
status.py and the SKILL.md state table are derived from it.

When the skill state machine changes:
  1. Edit STATES below.
  2. Run `python3 scripts/state_machine.py --render-markdown` to regenerate
     the state-table snippet for SKILL.md.
  3. Update SKILL.md's state table from the rendered output.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    name: str
    marker: str           # what file/condition proves we're in this state
    next_cmd: str         # the next /everglades-* command to suggest
    description: str      # one-line human-readable description


STATES: tuple[State, ...] = (
    State(
        name="BRIEFED",
        marker="BRIEF.md exists",
        next_cmd="/everglades-lock",
        description="Idea captured. Need to lock the answer.",
    ),
    State(
        name="LOCKED",
        marker="golden/expected.json populated + STATE.md.why",
        next_cmd="/everglades-jobs",
        description="Answer + tolerance locked. Need candidate-jobs table.",
    ),
    State(
        name="JOBS",
        marker="grader/grading_guide.md near-miss table populated",
        next_cmd="/everglades-scaffold",
        description="Near-misses catalogued. Scaffold oracle + main.py.",
    ),
    State(
        name="SCAFFOLDED",
        marker="oracle/setup.py + solution/main.py + solution/shortcut.py exist",
        next_cmd="/everglades-verify",
        description="Code scaffolded. Run local verify.",
    ),
    State(
        name="CALIBRATED",
        marker="verify PASSES + shortcut FAILS",
        next_cmd="/everglades-preview",
        description="Local verify clean. Run proxy preview.",
    ),
    State(
        name="BORDERLINE",
        marker="preview 3/8 pass (proxy not conclusive)",
        next_cmd="harden + re-preview, OR /everglades-export --force",
        description="Proxy on the fence. Harden or override.",
    ),
    State(
        name="READY",
        marker="preview ≤ 2/8 pass + lint clean",
        next_cmd="/everglades-export",
        description="Calibrated. Export the MANIFEST.",
    ),
    State(
        name="EXPORTED",
        marker="MANIFEST.md written",
        next_cmd="open RLS UI, paste per MANIFEST, click magic-star",
        description="Local work done. Hand off to RLS UI.",
    ),
)

# Fast lookup
BY_NAME: dict[str, State] = {s.name: s for s in STATES}


def next_action(state_name: str) -> str:
    s = BY_NAME.get(state_name)
    return s.next_cmd if s else "/everglades-status"


def render_markdown_table() -> str:
    rows = ["| State | Marker | Next action |", "|---|---|---|"]
    for s in STATES:
        rows.append(f"| `{s.name}` | {s.marker} | {s.next_cmd} |")
    return "\n".join(rows)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--render-markdown", action="store_true")
    args = p.parse_args()
    if args.render_markdown:
        print(render_markdown_table())
    else:
        for s in STATES:
            print(f"{s.name:14s} → {s.next_cmd}")
            print(f"               {s.description}")
