import itertools
from decimal import Decimal
from pathlib import Path

import pytest

from coinfodesign.data import load_source

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def dataset():
    """Pinned-fetch (hash-verified) source dataset, cached under .cache/ for reruns."""
    return load_source(cache_dir=Path(".cache/coinfosim-000018"))


def oracle_passing(losses, n, tau):
    """Independent test oracle: which nonempty subsets pass tau, straight from losses."""
    universe = range(1, 6)
    return {
        frozenset(c)
        for size in range(1, 6)
        for c in itertools.combinations(universe, size)
        if losses[(n, frozenset(c))].mean_loss <= tau
    }


def oracle_success(subset_a, passing):
    """A state succeeds iff it contains some passing subset (direct enumeration)."""
    return any(s <= subset_a for s in passing)


def oracle_reliability(passing, p: dict):
    """Sum of disjoint-state probabilities, enumerated independently of polynomial.py."""
    universe = range(1, 6)
    total = Decimal(0)
    for size in range(6):
        for combo in itertools.combinations(universe, size):
            a = frozenset(combo)
            if oracle_success(a, passing):
                term = Decimal(1)
                for i in universe:
                    term *= p[i] if i in a else (1 - p[i])
                total += term
    return total
