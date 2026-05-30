# tests/

Unit tests for the `everglades-multitask` skill. Lightweight pytest suite —
no Anthropic API calls (mocked or skipped), no RLS/Taiga network access.

## Run

```bash
cd ~/.claude/skills/everglades-multitask
pip install pytest
pytest tests/ -v
```

## Coverage

| Module under test | Test file | What it locks |
|---|---|---|
| `scripts/grading.py` | `test_grading.py` | Scalar, string, sequence (Strategy-5 tuple regression), structural, tolerance edge cases |
| `scripts/yaml_io.py` | `test_yaml_io.py` | Inline-comment stripping (the v0.2 bug), missing/empty files, quoted values, nesting, dump roundtrip |
| `scripts/paths.py` | `test_paths.py` | Canonical CLI layout positions, direction detection from oracle/simulation/config.yaml |
| `scripts/lint.py` | `test_lint.py` | Strategy-1 method-name leaks, Strategy-2 canonical targets, missing submit_answer, oracle-as-grader, missing budget/help |

## What's NOT tested

- The Anthropic preview eval (would require an API key + cost). Skill-level
  smoke test exists at `examples/example-walkthrough.md`; the empirical
  threshold validation lives in `SKILL.md` under "Threshold design".
- The export.py MANIFEST writer (no logic worth testing — it's just template
  interpolation).
