"""The 40 (n_per_class, tau) cases of the air-quality availability study."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from decimal import Decimal

from . import polynomial as poly
from .data import N_VALUES, SourceDataset

TAUS = (Decimal(".02"), Decimal(".05"), Decimal(".10"), Decimal(".20"))
NONEMPTY_SUBSETS = tuple(
    frozenset(c) for size in range(1, 6) for c in itertools.combinations(sorted(poly.UNIVERSE), size)
)


@dataclass(frozen=True)
class Case:
    n_per_class: int
    tau: Decimal
    minimal_sets: tuple
    tree: poly.Node
    canonical: dict
    counts: list
    states: int
    r_at_90: Decimal
    r_at_50: Decimal

    @property
    def case_key(self) -> str:
        return f"n{self.n_per_class}-tau{self.tau:.2f}"


def compute_case(dataset: SourceDataset, n_per_class: int, tau: Decimal) -> Case:
    passing = {
        s for s in NONEMPTY_SUBSETS
        if dataset.losses[(n_per_class, s)].mean_loss <= tau
    }
    minimal = poly.minimal_sets(passing)
    tree = poly.build_structured(poly.UNIVERSE, minimal)
    canonical = poly.expand(tree)
    brute = poly.canonical_from_minimal(minimal)
    if canonical != brute:
        raise AssertionError(
            f"structured/expanded mismatch for n={n_per_class}, tau={tau}: "
            f"structured gave {len(canonical)} monomials, brute gave {len(brute)}"
        )
    counts = poly.degree_counts(canonical)
    r90 = poly.equal_p_reliability(counts, Decimal(".9"))
    r50 = poly.equal_p_reliability(counts, Decimal(".5"))
    return Case(
        n_per_class=n_per_class,
        tau=tau,
        minimal_sets=tuple(sorted(tuple(sorted(m)) for m in minimal)),
        tree=tree,
        canonical=canonical,
        counts=counts,
        states=sum(counts),
        r_at_90=r90,
        r_at_50=r50,
    )


def compute_all_cases(dataset: SourceDataset) -> list[Case]:
    return [compute_case(dataset, n, tau) for n in N_VALUES for tau in TAUS]


def plateau_starts(cases: list[Case]) -> dict[Decimal, int]:
    """Earliest n per tau after which the success-state signature is
    identical for every later sampled n (exact equality on this finite grid)."""
    by_tau: dict[Decimal, dict[int, frozenset]] = {}
    for case in cases:
        states = frozenset(
            a for a in [frozenset(c) for size in range(6)
                        for c in itertools.combinations(sorted(poly.UNIVERSE), size)]
            if case.canonical.get(a) == 1
        )
        by_tau.setdefault(case.tau, {})[case.n_per_class] = states
    result = {}
    for tau, by_n in by_tau.items():
        ordered_n = sorted(by_n)
        plateau = ordered_n[-1]
        for n in ordered_n:
            if all(by_n[m] == by_n[n] for m in ordered_n if m >= n):
                plateau = n
                break
        result[tau] = plateau
    return result
