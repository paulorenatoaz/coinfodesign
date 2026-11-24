# Attribution and data provenance

CoInfoDesign is new code (GPL-3.0-or-later, see [LICENSE](LICENSE)) that computes and
displays generating-function reliability polynomials over sensor-availability states.
It does not import, fork, or run any upstream simulator code.

## Source of the experimental input

The two loss tables consumed by `coinfodesign build` are **not vendored** in this
repository. They are fetched at build time, byte-for-byte, from an immutable commit of
the upstream [CoInfoSim](https://github.com/paulorenatoaz/coinfosim) repository
(by Paulo Renato Azevedo, GPL-3.0-or-later, see its `CITATION.cff`):

```
https://raw.githubusercontent.com/paulorenatoaz/coinfosim/4d294c93075be06ee856549fb001efda4883398a/reports/simulations/000018_air_quality_real_data_full-scale/full_loss_table_real_to_real.csv
https://raw.githubusercontent.com/paulorenatoaz/coinfosim/4d294c93075be06ee856549fb001efda4883398a/reports/simulations/000018_air_quality_real_data_full-scale/subset_metadata_table.csv
```

Every build verifies both files against fixed SHA-256 hashes before use:

| File | SHA-256 |
|---|---|
| `full_loss_table_real_to_real.csv` | `32c3cf4e64db2971c091308b0e216e9a28f9c6809ff164c0c1dc70ec061b75cd` |
| `subset_metadata_table.csv` | `5dc595a5995227c8512a15b292b532eb0b952f6c78972c410d90d799ae36289e` |

This corresponds to CoInfoSim simulation run **000018** (scenario 6, "Air Quality",
real-to-real arm, linear SVM classifier), recovered from the pinned public gh-pages
commit `c8f210458109a54a5268f1998683ff57802d2c09` (see the upstream repository's
`docs/provenance/gh_pages_recovery_manifest.json`).

The underlying raw measurements originate from the **UCI Air Quality** dataset,
credit Saverio Vito (2008), UCI Machine Learning Repository,
[DOI 10.24432/C59K5F](https://doi.org/10.24432/C59K5F) (CC BY 4.0, research-only use
note in the dataset description). CoInfoDesign never redistributes raw measurements;
it only consumes CoInfoSim's already-computed, persisted mean test losses.

## Test fixture

`tests/fixtures/air_quality_40_cases_reference.{csv,json}` is a small, focused golden
fixture (the 40 `(n, tau)` case summaries only — no raw losses, no measurements)
derived from the same CoInfoSim run above, included here under GPL-3.0-or-later for
regression testing. It is not used by the production build or site.

## What CoInfoDesign adds

CoInfoDesign is an independent reliability-design layer: given CoInfoSim's persisted
empirical losses, it computes the canonical availability-success generating function
and a division-free reliability formula, and renders both an experimental panorama and
an interactive laboratory. It performs no training, resampling, or Monte Carlo
simulation of its own.
