"""Canonical availability-success generating function and reliability.

Implements the deterministic structured recursion from SPECIFICATION.md
("Generating function and reliability") plus a brute-force canonical
builder used as an independent cross-check, the division-free reliability
evaluator R, and grouped-symbol specialization for display.

The five physical sensors are indexed 1..5 throughout and always remain
independent; grouping/specialization only changes how a result is *shown*,
never the canonical polynomial or the R value computed from it.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

UNIVERSE = frozenset(range(1, 6))
Subset = frozenset  # frozenset[int]
Canonical = dict  # dict[frozenset[int], int]


# ---------------------------------------------------------------- minsets --

def minimal_sets(passing: set[Subset]) -> frozenset[Subset]:
    """Inclusion-minimal members of `passing` (an antichain)."""
    passing = set(passing)
    return frozenset(s for s in passing if not any(t < s for t in passing))


def success_states(minimal: frozenset[Subset], universe: Subset = UNIVERSE) -> frozenset[Subset]:
    """All subsets of `universe` containing some member of `minimal`."""
    states = []
    for size in range(len(universe) + 1):
        for combo in itertools.combinations(sorted(universe), size):
            a = frozenset(combo)
            if any(m <= a for m in minimal):
                states.append(a)
    return frozenset(states)


def degree_counts(canonical: Canonical, universe: Subset = UNIVERSE) -> list[int]:
    counts = [0] * (len(universe) + 1)
    for subset, coeff in canonical.items():
        counts[len(subset)] += coeff
    return counts


def canonical_from_minimal(minimal: frozenset[Subset], universe: Subset = UNIVERSE) -> Canonical:
    """Brute-force canonical H: coefficient 1 on x_A for every success state A.

    Independent of the structured recursion below; used as ground truth.
    """
    states = success_states(minimal, universe)
    return {a: 1 for a in states}


# --------------------------------------------------------- structured tree --

class Node:
    __slots__ = ()


@dataclass(frozen=True)
class Const(Node):
    value: int


@dataclass(frozen=True)
class Var(Node):
    i: int


@dataclass(frozen=True)
class Mono(Node):
    """Product of distinct raw variables: prod x_i for i in indices."""
    indices: Subset


@dataclass(frozen=True)
class FreeProd(Node):
    """prod_{i in indices} (1 + x_i)."""
    indices: Subset


@dataclass(frozen=True)
class AltProd(Node):
    """prod_{i in indices} (1 + x_i) - 1."""
    indices: Subset


@dataclass(frozen=True)
class Add(Node):
    terms: tuple


@dataclass(frozen=True)
class Mul(Node):
    factors: tuple


def _minimize(family: frozenset[Subset]) -> frozenset[Subset]:
    family = frozenset(frozenset(m) for m in family)
    return frozenset(m for m in family if not any(other < m for other in family if other != m))


def build_structured(variables: Subset, requirements: frozenset[Subset]) -> Node:
    """Deterministic recursion: SPECIFICATION.md steps 1-4."""
    requirements = _minimize(requirements)

    # Step 1: empty family / empty requirement.
    if not requirements:
        return Const(0)
    if requirements == frozenset({frozenset()}):
        return FreeProd(variables)

    # Step 2: all requirements are singletons.
    if all(len(m) == 1 for m in requirements):
        alts = frozenset(next(iter(m)) for m in requirements)
        remaining = variables - alts
        if not remaining:
            return AltProd(alts)
        return Mul((AltProd(alts), FreeProd(remaining)))

    # Step 3: a singleton present among mixed requirements -> split on it (lowest index).
    singleton_indices = sorted(next(iter(m)) for m in requirements if len(m) == 1)
    if singleton_indices:
        return _split(variables, requirements, singleton_indices[0])

    # Step 3 (otherwise): extract common required indices.
    common = frozenset.intersection(*(frozenset(m) for m in requirements))
    if common:
        remainder = frozenset(frozenset(m - common) for m in requirements)
        rest = build_structured(variables - common, remainder)
        return Mul((Mono(common), rest))

    # Step 3 (remaining mixed case): split on the lowest index appearing in M.
    lowest = min(min(m) for m in requirements)
    return _split(variables, requirements, lowest)


def _split(variables: Subset, requirements: frozenset[Subset], i: int) -> Node:
    m0 = frozenset(m for m in requirements if i not in m)
    m1 = frozenset(frozenset(m - {i}) for m in requirements)
    remaining = variables - {i}
    h0 = build_structured(remaining, m0)
    h1 = build_structured(remaining, m1)
    return Add((Mul((Var(i), h1)), h0))


def _mul_poly(a: Canonical, b: Canonical) -> Canonical:
    result: Canonical = {}
    for ka, va in a.items():
        for kb, vb in b.items():
            if ka & kb:
                raise AssertionError(f"overlapping variables in product: {ka} & {kb}")
            k = ka | kb
            result[k] = result.get(k, 0) + va * vb
    return {k: v for k, v in result.items() if v != 0}


def expand(node: Node) -> Canonical:
    """Expand a structured-tree node into its coefficient map."""
    if isinstance(node, Const):
        return {frozenset(): node.value} if node.value else {}
    if isinstance(node, Var):
        return {frozenset({node.i}): 1}
    if isinstance(node, Mono):
        return {frozenset(node.indices): 1} if node.indices else {frozenset(): 1}
    if isinstance(node, FreeProd):
        poly: Canonical = {frozenset(): 1}
        for i in sorted(node.indices):
            poly = _mul_poly(poly, {frozenset(): 1, frozenset({i}): 1})
        return poly
    if isinstance(node, AltProd):
        poly = dict(expand(FreeProd(node.indices)))
        poly[frozenset()] = poly.get(frozenset(), 0) - 1
        if poly[frozenset()] == 0:
            del poly[frozenset()]
        return poly
    if isinstance(node, Add):
        result: Canonical = {}
        for term in node.terms:
            for k, v in expand(term).items():
                result[k] = result.get(k, 0) + v
        return {k: v for k, v in result.items() if v != 0}
    if isinstance(node, Mul):
        poly = {frozenset(): 1}
        for factor in node.factors:
            poly = _mul_poly(poly, expand(factor))
        return poly
    raise TypeError(f"unknown node type: {node!r}")


# --------------------------------------------------------------- reliability --

def reliability(canonical: Canonical, p: Mapping[int, Decimal], universe: Subset = UNIVERSE) -> Decimal:
    """Division-free R(p) = sum over success states A of prod p_i * prod (1-p_i).

    Defined and exact at every p_i in [0,1], including 0 and 1.
    """
    total = Decimal(0)
    for subset, coeff in canonical.items():
        term = Decimal(coeff)
        for i in universe:
            term *= p[i] if i in subset else (Decimal(1) - p[i])
        total += term
    return total


def _dpow(base: Decimal, exponent: int) -> Decimal:
    """base**exponent, with the x**0 = 1 convention even when base is 0
    (Decimal's 0**0 raises InvalidOperation, which is wrong for polynomials)."""
    if exponent == 0:
        return Decimal(1)
    return base ** exponent


def univariate_value(counts: list[int], x: Decimal) -> Decimal:
    return sum(Decimal(c) * _dpow(x, k) for k, c in enumerate(counts))


def equal_p_reliability(counts: list[int], p: Decimal) -> Decimal:
    """R at p1=...=p5=p: sum a_k p^k (1-p)^(5-k)."""
    n = len(counts) - 1
    q = 1 - p
    return sum(Decimal(c) * _dpow(p, k) * _dpow(q, n - k) for k, c in enumerate(counts))


# ------------------------------------------------------------- grouping ----

def group_signature(subset: Subset, groups: list[Subset]) -> tuple:
    return tuple(len(subset & g) for g in groups)


def grouped_canonical(canonical: Canonical, groups: list[Subset]) -> dict[tuple, int]:
    result: dict[tuple, int] = {}
    for subset, coeff in canonical.items():
        key = group_signature(subset, groups)
        result[key] = result.get(key, 0) + coeff
    return result


def to_jsonable(node: Node) -> dict:
    if isinstance(node, Const):
        return {"type": "const", "value": node.value}
    if isinstance(node, Var):
        return {"type": "var", "i": node.i}
    if isinstance(node, Mono):
        return {"type": "mono", "indices": sorted(node.indices)}
    if isinstance(node, FreeProd):
        return {"type": "freeprod", "indices": sorted(node.indices)}
    if isinstance(node, AltProd):
        return {"type": "altprod", "indices": sorted(node.indices)}
    if isinstance(node, Add):
        return {"type": "add", "terms": [to_jsonable(t) for t in node.terms]}
    if isinstance(node, Mul):
        return {"type": "mul", "factors": [to_jsonable(f) for f in node.factors]}
    raise TypeError(f"unknown node type: {node!r}")


def groups_from_equal_values(values: Mapping[int, Decimal]) -> list[Subset]:
    """Partition sensors 1..5 into groups of equal probability, ordered by
    the first (lowest-index) sensor in each group."""
    by_value: dict[Decimal, list[int]] = {}
    for i in sorted(values):
        by_value.setdefault(values[i], []).append(i)
    groups = [frozenset(members) for members in by_value.values()]
    groups.sort(key=lambda g: min(g))
    return groups
