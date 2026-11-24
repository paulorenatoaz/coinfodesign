import itertools
from decimal import Decimal

import pytest

from coinfodesign import polynomial as poly

UNIVERSE = poly.UNIVERSE


def all_set_partitions(items):
    """All set partitions of `items` (Bell number B5 = 52 for 5 items)."""
    items = list(items)
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for smaller in all_set_partitions(rest):
        for i in range(len(smaller)):
            yield smaller[:i] + [[first] + smaller[i]] + smaller[i + 1:]
        yield [[first]] + smaller


# Representative minimal-set families covering every recursion branch:
# all-zero, a lone singleton, all-singletons, common-index extraction,
# no-common mixed, and the full classroom example.
FAMILIES = {
    "zero": frozenset(),
    "single_singleton": frozenset({frozenset({3})}),
    "all_singletons": frozenset({frozenset({1}), frozenset({2}), frozenset({4})}),
    "common_index": frozenset({frozenset({1, 4}), frozenset({3, 4}), frozenset({4, 5})}),
    "no_common_mixed": frozenset({frozenset({1, 2}), frozenset({2, 3}), frozenset({3, 1})}),
    "classroom": frozenset(
        {frozenset({2}), frozenset({1, 4}), frozenset({3, 4}), frozenset({4, 5})}
    ),
    "all_active_required": frozenset({frozenset({1, 2, 3, 4, 5})}),
}


@pytest.mark.parametrize("name", FAMILIES)
def test_structured_matches_brute_force(name):
    minimal = FAMILIES[name]
    tree = poly.build_structured(UNIVERSE, minimal)
    expanded = poly.expand(tree)
    brute = poly.canonical_from_minimal(minimal)
    assert expanded == brute


def test_zero_generating_function():
    tree = poly.build_structured(UNIVERSE, frozenset())
    assert poly.expand(tree) == {}
    assert poly.degree_counts({}) == [0, 0, 0, 0, 0, 0]
    p = {i: Decimal("0.5") for i in range(1, 6)}
    assert poly.reliability({}, p) == 0


@pytest.mark.parametrize("name", FAMILIES)
def test_52_equality_partitions(name):
    """For every set partition of {1..5}, the grouped canonical's total
    coefficient mass must equal the ungrouped canonical's (grouping only
    relabels/aggregates monomials, it never changes what succeeds)."""
    minimal = FAMILIES[name]
    canonical = poly.canonical_from_minimal(minimal)
    partitions = list(all_set_partitions(sorted(UNIVERSE)))
    assert len(partitions) == 52
    for partition in partitions:
        groups = [frozenset(g) for g in partition]
        grouped = poly.grouped_canonical(canonical, groups)
        assert sum(grouped.values()) == sum(canonical.values())
        # Expanded-term multiplicity: every ungrouped monomial maps to exactly
        # one grouped exponent tuple, and grouped coefficients tally that count.
        recount = {}
        for subset, coeff in canonical.items():
            key = poly.group_signature(subset, groups)
            recount[key] = recount.get(key, 0) + coeff
        assert recount == grouped


@pytest.mark.parametrize("name", FAMILIES)
def test_identity_specialization_is_a_no_op(name):
    minimal = FAMILIES[name]
    canonical = poly.canonical_from_minimal(minimal)
    identity_groups = [frozenset({i}) for i in sorted(UNIVERSE)]
    grouped = poly.grouped_canonical(canonical, identity_groups)
    # Identity grouping: each grouped key is just the sorted membership vector,
    # recoverable 1:1 from each original subset.
    for subset, coeff in canonical.items():
        key = tuple(1 if i in subset else 0 for i in sorted(UNIVERSE))
        assert grouped[key] == sum(
            c for s, c in canonical.items()
            if tuple(1 if i in s else 0 for i in sorted(UNIVERSE)) == key
        )
        assert coeff <= grouped[key]


@pytest.mark.parametrize("name", FAMILIES)
def test_all_equal_specialization_matches_univariate(name):
    minimal = FAMILIES[name]
    canonical = poly.canonical_from_minimal(minimal)
    counts = poly.degree_counts(canonical)
    all_equal_group = [UNIVERSE]
    grouped = poly.grouped_canonical(canonical, all_equal_group)
    for k, c in enumerate(counts):
        assert grouped.get((k,), 0) == c


@pytest.mark.parametrize("name", FAMILIES)
@pytest.mark.parametrize("p_value", [Decimal("0"), Decimal("0.3"), Decimal("0.5"), Decimal("0.9"), Decimal("1")])
def test_equal_grouped_unreduced_r_agreement(name, p_value):
    """R computed three ways must agree exactly: the equal-p univariate shortcut,
    the generic multivariate reliability() with all p_i equal, and reliability()
    evaluated through the all-in-one-group specialization."""
    minimal = FAMILIES[name]
    canonical = poly.canonical_from_minimal(minimal)
    counts = poly.degree_counts(canonical)

    r_univariate = poly.equal_p_reliability(counts, p_value)
    r_multivariate = poly.reliability(canonical, {i: p_value for i in UNIVERSE})
    assert r_univariate == r_multivariate

    grouped = poly.grouped_canonical(canonical, [UNIVERSE])
    r_grouped = sum(
        Decimal(c) * poly._dpow(p_value, exponents[0]) * poly._dpow(1 - p_value, 5 - exponents[0])
        for exponents, c in grouped.items()
    )
    assert r_grouped == r_univariate


@pytest.mark.parametrize("name", FAMILIES)
def test_all_32_endpoint_vectors(name):
    """At every corner of the probability hypercube, R must equal the
    independent 0/1 success indicator for that exact availability state."""
    minimal = FAMILIES[name]
    canonical = poly.canonical_from_minimal(minimal)
    for size in range(6):
        for combo in itertools.combinations(sorted(UNIVERSE), size):
            available = frozenset(combo)
            p = {i: (Decimal(1) if i in available else Decimal(0)) for i in UNIVERSE}
            r = poly.reliability(canonical, p)
            expected = Decimal(1) if any(m <= available for m in minimal) else Decimal(0)
            assert r == expected, (name, available)


@pytest.mark.parametrize("name", FAMILIES)
def test_mixed_boundary_and_interior_probabilities(name):
    minimal = FAMILIES[name]
    canonical = poly.canonical_from_minimal(minimal)
    mixed_vectors = [
        {1: Decimal("0"), 2: Decimal("1"), 3: Decimal("0.5"), 4: Decimal("1"), 5: Decimal("0")},
        {1: Decimal("0.9"), 2: Decimal("0.7"), 3: Decimal("0.9"), 4: Decimal("0.4"), 5: Decimal("0.9")},
        {1: Decimal("1"), 2: Decimal("1"), 3: Decimal("1"), 4: Decimal("1"), 5: Decimal("1")},
        {1: Decimal("0"), 2: Decimal("0"), 3: Decimal("0"), 4: Decimal("0"), 5: Decimal("0")},
    ]
    for p in mixed_vectors:
        r = poly.reliability(canonical, p)
        assert Decimal(0) <= r <= Decimal(1)
        # Cross-check against a direct (independent-style) brute sum.
        expected = Decimal(0)
        for size in range(6):
            for combo in itertools.combinations(sorted(UNIVERSE), size):
                a = frozenset(combo)
                if any(m <= a for m in minimal):
                    term = Decimal(1)
                    for i in UNIVERSE:
                        term *= p[i] if i in a else (1 - p[i])
                    expected += term
        assert r == expected


def test_classroom_structured_rendering_matches_specification():
    from coinfodesign import render

    minimal = FAMILIES["classroom"]
    tree = poly.build_structured(UNIVERSE, minimal)
    labels = render.identity_labels()
    text = render.render_structured_html(tree, labels)
    assert text == (
        "x<sub>2</sub>(1+x<sub>1</sub>)(1+x<sub>3</sub>)(1+x<sub>4</sub>)(1+x<sub>5</sub>) + "
        "x<sub>4</sub>[(1+x<sub>1</sub>)(1+x<sub>3</sub>)(1+x<sub>5</sub>)&minus;1]"
    )
    counts = poly.degree_counts(poly.expand(tree))
    assert counts == [0, 1, 7, 9, 5, 1]
    assert render.render_univariate_html(counts) == "x + 7x<sup>2</sup> + 9x<sup>3</sup> + 5x<sup>4</sup> + x<sup>5</sup>"
    assert poly.equal_p_reliability(counts, Decimal(".5")) == Decimal(".71875")
    r90 = poly.equal_p_reliability(counts, Decimal(".9"))
    assert r90 == Decimal(".98991")
    assert render.format_percent_br(r90) == "98,991%"
