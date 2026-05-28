# Forward Task Guide (skill-internal reference)

Forward tasks don't have an oracle. The model gets simulation inputs directly and runs the domain tool.

## When to choose forward over inverse

Choose forward when:
- The task naturally requires *running* a specific simulation (mesh, solver, convergence) and difficulty is in those choices
- Hiding parameters would feel artificial
- A single well-defined numeric answer comes out

Otherwise default to inverse — cleaner reasoning signal.

## The hard part of a forward task

NOT the simulation itself — models can drive any supported tool. The hard part is the non-obvious method-selection decision that quietly determines correctness:

- Mesh / discretization (default mesh → unconverged)
- Solver choice (SIMPLE vs PIMPLE, direct vs iterative)
- Convergence criteria (when to stop; residuals can lie)
- Boundary conditions (Dirichlet vs Neumann, outlet pressure vs velocity)
- Validation (mass balance, energy conservation)

## Skill differences from inverse

- No `oracle.py`. Replace with `simulation/` directory containing tool input files.
- `shortcut.py` implements the default-mesh / default-solver path that silently fails.
- Preview eval: same Anthropic tool-use pattern, but Claude calls a `run_simulation` tool that subprocesses the tool against the local `simulation/` directory.

## Scaffolding heuristic

Pick the closest anchor example. For OpenFOAM tasks → cylinder drag at Re=100 pattern (steady-state silently wrong, need transient + time-average + mesh-refinement). For FEM → Timoshenko-vs-Euler-Bernoulli pattern.

## Forward task pre-submission checklist

In addition to the standard checklist:

- [ ] Default simulation parameters intentionally cause naive approach to fail
- [ ] Answer verified against literature or independent setup
- [ ] 16-model eval ≤ 4/16 (forward tasks tend to be EASIER; may need extra hardening)
- [ ] No "this requires transient/refined mesh" hint in prompt
