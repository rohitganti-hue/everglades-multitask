# Anchor Examples Summary

When scaffolding code, pick the closest example and adapt to the expert's specifics.
Full walkthroughs in the Everglades Hub Anchor Example Library.

| # | Domain | Title | Shape |
|---|---|---|---|
| 1 | EG-1 Bioinformatics & Systems Biology | BAM file with systematically wrong variant calls | candidate-set classification |
| 2 | EG-2 Computational Chemistry | Unknown molecule from IR spectrum (candidate set) | candidate-set + multi-mode |
| 3 | EG-3 Physics | Lattice QCD hadron-mass ratios → bare quark mass | continuous-parameter regression |
| 4 | EG-4 Electrical Engineering | AAH metamaterial chain | multi-parameter + common-mode systematic |
| 5 | EG-4 Electrical Engineering | Hidden RF filter topology from S-parameters | topology-id + values |
| 6 | EG-3 Physics | Orbit determination from sparse observations (astrophysics) | 6-param continuous regression |
| 7 | EG-3 Physics | Earthquake hypocenter from synthetic seismograms (geophysics) | localization |
| 8 | EG-1 Bioinformatics & Systems Biology | Two-compartment PK from sparse concentrations | complementary-mode (plasma + urine) |
| 9 | EG-5 Mechanical & Structural Engineering | Applied force on plate from strain gauges | sparse-sensor inversion + non-canonical assumption |

## Selecting an analog

**Within-domain first.** When scaffolding, pick an anchor from the expert's configured domain whenever possible — same tool family, same oracle patterns, same review conventions. Cross-domain anchors are a last-resort analogy.

| Domain | Primary anchor(s) | Tool family |
|---|---|---|
| EG-1 Bioinformatics & Systems Biology | #1 BAM variant calls, #8 PK 2-compartment | BioPython, PySAM, scanpy, anndata, scipy.integrate, PyMC |
| EG-2 Computational Chemistry | #2 IR spectrum | PySCF, ORCA, RDKit |
| EG-3 Physics | #3 Lattice QCD, #6 Orbit determination, #7 Earthquake hypocenter | scikit-hep, astropy, Poliastro, ObsPy, SpecFEM3D |
| EG-4 Electrical Engineering | #4 AAH metamaterial, #5 RF filter | ngspice, scikit-rf, openEMS |
| EG-5 Mechanical & Structural Engineering | #9 Plate strain gauges | scikit-fem, OpenFOAM |
| EG-6 Applied Statistics & Mathematics | analog to #8 / #9 (parameter inference) | PyMC, JAGS, statsmodels |

If the expert's domain doesn't have a direct anchor or their task shape doesn't match the domain's primary anchor, **then** consider these cross-domain shape-matches as a secondary fallback:

| If the task shape is... | Cross-domain analog |
|---|---|
| Candidate set, model picks one | #1 (variant calls) or #2 (IR spectrum) |
| Continuous parameters | #3, #4, #6 |
| Topology / discrete structure | #5 |
| Localization (lat/lon, hypocenter, force position) | #7, #9 |
| Multi-parameter with complementary modes | #4 (4 modes), #8 (plasma+urine) |
| Sparse data + dense parameters | #6 (sparse obs, 6 elements) |

## Bioinformatics scaffolding hints (most-common Everglades domain)

EG-1 makes up 57% of approved tasks. Common patterns:

1. **AnnData + scanpy** — load synthetic single-cell data; query modes return
   expression panels or summary statistics
2. **Multi-omics integration trap** — observed pattern: rank by a "permissive
   integrated score" → wrong; require row-level decomposition → right
3. **PBMC perturbation candidate set** — 6 candidates, oracle returns
   single-cell summaries per candidate; trap = whole-PBMC summary
4. **Cancer genomics VAF distribution** — PySAM/BAM file, model reads VCF;
   trap = take max VAF cluster

## EG-1 approved-task case examples

The skill's scaffolding draws from these real approved tasks as concrete patterns to adapt:

- `Task xm0vffa1` / `w49sa943` — SingleCell, "permissive integrated score" trap.
  ⚠ These two are near-duplicates — `/everglades-degeneracy-check` would have
  flagged them at scaffold time.
- `Task u9541c9e` — ATAC-seq, ALS subtype-specific signal. Tool: PySAM.
- `Task 47zn5f8f` — Single-cell AD biomarker, PANEL_B vs PANEL_A trap. Tool: ScanPy.
- `Task l4qs273b` — RNA velocity reversion candidate (colorectal cancer GSE125970).
  Tool: scanpy + scVelo.
- `Task tals96f0` — Single-cell multiomics QTL, PP-H4 ranking inversion.
  Tool: Scanpy.
