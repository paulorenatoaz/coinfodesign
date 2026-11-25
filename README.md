# CoInfoDesign

Reliability design over previously evaluated predictor subsets, via generating
functions — ICP747, PPGI/UFRJ.

Given CoInfoSim's already-persisted empirical test losses for every nonempty
subset of five air-quality sensors, CoInfoDesign computes, for a training
sample size `n` and loss tolerance `τ`, the canonical availability-success
generating function `H_{n,τ}` and a division-free reliability formula `R`,
then renders a single reactive report: one shared set of controls (`n`, `τ`,
and five independent sensor-availability probabilities) drives an overview
chart, a scenario analysis panel, and the full 40-case table together.

**Live site:** https://paulorenatoaz.github.io/coinfodesign/

## What this does and does not do

- Reads CoInfoSim's persisted mean test losses (never trains, resamples, or
  runs Monte Carlo of its own). See [ATTRIBUTION.md](ATTRIBUTION.md).
- Computes the canonical generating function via a deterministic structured
  recursion ([`polynomial.py`](src/coinfodesign/polynomial.py)), cross-checked
  against a brute-force enumeration in tests.
- The general (ungrouped) generating function is a pure function of `(n, τ)`
  and never changes when probabilities change; only its display
  specialization (grouping sensors with equal probability) and the numeric
  reliability value respond to the probability controls.
- All 40 `(n, τ)` cases (`n ∈ {2,4,...,1024}`, `τ ∈ {0.02,0.05,0.10,0.20}`)
  are computed fresh on every build from the original loss tables — never
  from precomputed/golden results. The only golden fixture used is a small,
  explicitly-labeled reference for regression testing (see
  [tests/fixtures](tests/fixtures)).

## Build

Requires Python 3.11+, standard library only (no runtime dependencies).

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m coinfodesign build --out _site
```

This fetches the two pinned upstream CSVs (verifying their SHA-256 against
[ATTRIBUTION.md](ATTRIBUTION.md) on every run), computes all 40 cases, and
writes a deterministic static site to `_site/` plus `cases.csv`/`cases.json`
under `_site/data/`. Pass `--source <dir>` to build from a local copy of the
two CSVs instead of fetching (same hash verification either way). Serve it
with any static file server, e.g. `python -m http.server --directory _site`.

## Test

```bash
.venv/bin/python -m pytest
```

The suite covers: the data loader (hash/shape validation, synthetic
boundary losses at and immediately above τ), the polynomial engine (all 52
set partitions of the five sensors, structured/expanded equality, all 32
probability-hypercube endpoints, the zero generating function, an
independent from-scratch oracle cross-check), the 40-case study against the
golden fixture and the published landmark values, and the generated site's
structure.

## License and attribution

New code is licensed [GPL-3.0-or-later](LICENSE). See
[ATTRIBUTION.md](ATTRIBUTION.md) for the upstream CoInfoSim run this project
reads from and the underlying UCI Air Quality dataset, and
[CITATION.cff](CITATION.cff) to cite this work.
