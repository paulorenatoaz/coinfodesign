import json
from decimal import Decimal

import pytest

from coinfodesign.cases import TAUS, compute_all_cases, compute_case, plateau_starts
from coinfodesign.data import N_VALUES

from conftest import FIXTURES, oracle_passing, oracle_reliability, oracle_success


@pytest.fixture(scope="module")
def all_cases(dataset):
    return compute_all_cases(dataset)


@pytest.fixture(scope="module")
def golden():
    data = json.loads((FIXTURES / "air_quality_40_cases_reference.json").read_text(), parse_float=Decimal)
    return {(r["n_per_class"], r["tau"]): r for r in data["cases"]}


def test_exactly_40_unique_case_keys(all_cases):
    assert len(all_cases) == 40
    assert len({c.case_key for c in all_cases}) == 40


def test_against_golden_fixture(all_cases, golden):
    for case in all_cases:
        fixture = golden[(case.n_per_class, case.tau)]
        fixture_minsets = {
            frozenset(int(x[1:]) if isinstance(x, str) else int(x) for x in s)
            for s in fixture["minimal_success_sets"]
        }
        assert {frozenset(m) for m in case.minimal_sets} == fixture_minsets
        assert case.counts == fixture["a_k"]
        assert case.states == fixture["successful_availability_states"]
        assert abs(case.r_at_90 - fixture["R_at_equal_p_0_9"]) < Decimal("1e-12")


def test_golden_landmarks_from_acceptance(all_cases):
    by_key = {(c.n_per_class, c.tau): c for c in all_cases}

    for n in (2, 4, 8, 16, 32):
        c = by_key[(n, Decimal(".02"))]
        assert c.states == 0 and c.r_at_90 == 0

    c64 = by_key[(64, Decimal(".02"))]
    assert {frozenset(m) for m in c64.minimal_sets} == {frozenset({2, 4})}
    assert c64.r_at_90 == Decimal(".81")

    c128 = by_key[(128, Decimal(".02"))]
    assert {frozenset(m) for m in c128.minimal_sets} == {frozenset({2})}
    assert c128.r_at_90 == Decimal(".90")

    for n in (2, 4):
        c = by_key[(n, Decimal(".05"))]
        assert c.states == 0 and c.r_at_90 == 0
    c8 = by_key[(8, Decimal(".05"))]
    assert {frozenset(m) for m in c8.minimal_sets} == {frozenset({2})}
    assert c8.r_at_90 == Decimal(".90")

    expected_counts_by_n = {2: [0, 1, 4, 6, 4, 1], 4: [0, 1, 5, 8, 5, 1], 8: [0, 1, 6, 9, 5, 1]}
    for n, expected in expected_counts_by_n.items():
        assert by_key[(n, Decimal(".10"))].counts == expected
    for n in (16, 32, 64, 128, 256, 512, 1024):
        assert by_key[(n, Decimal(".10"))].counts == [0, 1, 7, 9, 5, 1]

    c2_20 = by_key[(2, Decimal(".20"))]
    assert {frozenset(m) for m in c2_20.minimal_sets} == {frozenset({1}), frozenset({2}), frozenset({4})}
    assert c2_20.r_at_90 == Decimal(".999")
    c4_20 = by_key[(4, Decimal(".20"))]
    assert c4_20.counts == [0, 4, 10, 10, 5, 1]
    assert c4_20.r_at_90 == Decimal(".9999")

    classroom = by_key[(512, Decimal(".10"))]
    assert {frozenset(m) for m in classroom.minimal_sets} == {
        frozenset({2}), frozenset({1, 4}), frozenset({3, 4}), frozenset({4, 5})
    }
    assert classroom.states == 23
    assert classroom.r_at_90 == Decimal(".98991")
    assert classroom.r_at_50 == Decimal(".71875")


def test_plateau_starts_match_acceptance(all_cases):
    plateau = plateau_starts(all_cases)
    assert plateau[Decimal(".02")] == 128
    assert plateau[Decimal(".05")] == 8
    assert plateau[Decimal(".10")] == 16
    assert plateau[Decimal(".20")] == 4


def test_tau_nesting_never_asserts_n_monotonicity(all_cases):
    """Raising tau at fixed n can only add success states (nesting holds);
    n itself has no monotonicity guarantee (not asserted here)."""
    by_n = {}
    for case in all_cases:
        by_n.setdefault(case.n_per_class, {})[case.tau] = set(
            s for s, c in case.canonical.items() if c
        )
    ordered_taus = sorted(TAUS)
    for n, by_tau in by_n.items():
        for a, b in zip(ordered_taus, ordered_taus[1:]):
            assert by_tau[a] <= by_tau[b]


@pytest.mark.parametrize("n", N_VALUES)
@pytest.mark.parametrize("tau_str", [".02", ".05", ".10", ".20"])
def test_independent_oracle_cross_check(dataset, n, tau_str):
    """Cross-check production cases against a from-scratch, test-only oracle
    that never calls polynomial.minimal_sets / canonical_from_minimal."""
    tau = Decimal(tau_str)
    case = compute_case(dataset, n, tau)
    passing = oracle_passing(dataset.losses, n, tau)

    for degree in range(6):
        pass  # state enumeration happens inside oracle_reliability/oracle_success

    p = {i: Decimal(".9") for i in range(1, 6)}
    oracle_r = oracle_reliability(passing, p)
    assert abs(oracle_r - case.r_at_90) < Decimal("1e-12")

    # Minimal sets independently re-derived (antichain of `passing`).
    oracle_minimal = {s for s in passing if not any(t < s for t in passing)}
    assert {frozenset(m) for m in case.minimal_sets} == oracle_minimal
