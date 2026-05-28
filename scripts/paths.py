"""Canonical paths inside an Everglades draft folder.

Matches the master Everglades CLI structure:
  problem.md, config.yaml, requirements.txt          (root)
  oracle/setup.py        (inverse only — HIDDEN)
  simulation/            (forward only — visible to model)
  solution/main.py
  solution/shortcut.py   (skill-local, not uploaded to RLS)
  grader/grading_guide.md
  golden/expected.json
  reasoning_trap.md      (skill addition; maps to RLS Reasoning Trap field)
  BRIEF.md, STATE.md     (skill workflow state, not part of canonical spec)
"""
from __future__ import annotations
from pathlib import Path


def problem_md(draft: Path) -> Path: return draft / "problem.md"
def config_yaml(draft: Path) -> Path: return draft / "config.yaml"
def requirements_txt(draft: Path) -> Path: return draft / "requirements.txt"
def reasoning_trap(draft: Path) -> Path: return draft / "reasoning_trap.md"
def state_md(draft: Path) -> Path: return draft / "STATE.md"
def brief_md(draft: Path) -> Path: return draft / "BRIEF.md"

# Canonical nested locations
def oracle_setup(draft: Path) -> Path: return draft / "oracle" / "setup.py"
def simulation_dir(draft: Path) -> Path: return draft / "simulation"
def main_py(draft: Path) -> Path: return draft / "solution" / "main.py"
def shortcut_py(draft: Path) -> Path: return draft / "solution" / "shortcut.py"
def grading_guide(draft: Path) -> Path: return draft / "grader" / "grading_guide.md"
def expected_json(draft: Path) -> Path: return draft / "golden" / "expected.json"

# Output dir for skill-local run logs
def runs_dir(draft: Path) -> Path: return draft / "runs"


def detect_direction(draft: Path) -> str:
    """Determine whether a draft is inverse or forward.

    Heuristic:
      - oracle/setup.py exists  -> inverse
      - simulation/ exists      -> forward
      - else read direction from config.yaml
    """
    if oracle_setup(draft).exists():
        return "inverse"
    if simulation_dir(draft).exists() and any(simulation_dir(draft).iterdir()):
        return "forward"
    cfg = config_yaml(draft)
    if cfg.exists():
        for line in cfg.read_text().splitlines():
            line = line.strip()
            if line.startswith("direction:"):
                return line.split(":", 1)[1].strip()
    return "unknown"
