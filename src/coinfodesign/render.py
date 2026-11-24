"""HTML rendering of structured and expanded generating functions.

Plain HTML (<sub>/<sup>), no JS math renderer, no network dependency —
accessible to screen readers and keyboard navigation by construction.
"""
from __future__ import annotations

from decimal import Decimal

from .polynomial import Add, AltProd, Const, FreeProd, Mono, Mul, Node, Var, UNIVERSE, Subset


def label_for(group: Subset, universe: Subset = UNIVERSE) -> str:
    if frozenset(group) == frozenset(universe):
        return "x"
    if len(group) == 1:
        (i,) = group
        return f"x<sub>{i}</sub>"
    digits = "".join(str(i) for i in sorted(group))
    return f"x<sub>{digits}</sub>"


def identity_labels(universe: Subset = UNIVERSE) -> dict[int, str]:
    return {i: f"x<sub>{i}</sub>" for i in universe}


def labels_from_groups(groups: list[Subset]) -> dict[int, str]:
    labels: dict[int, str] = {}
    for group in groups:
        lbl = label_for(group)
        for i in group:
            labels[i] = lbl
    return labels


def _tally(indices: Subset, label_of: dict[int, str]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    order: list[str] = []
    for i in sorted(indices):
        lbl = label_of[i]
        if lbl not in counts:
            counts[lbl] = 0
            order.append(lbl)
        counts[lbl] += 1
    return [(lbl, counts[lbl]) for lbl in order]


def _mono_str(indices: Subset, label_of: dict[int, str]) -> str:
    if not indices:
        return "1"
    return "".join(
        lbl if c == 1 else f"{lbl}<sup>{c}</sup>" for lbl, c in _tally(indices, label_of)
    )


def _freeprod_str(indices: Subset, label_of: dict[int, str]) -> str:
    if not indices:
        return "1"
    return "".join(
        f"(1+{lbl})" if c == 1 else f"(1+{lbl})<sup>{c}</sup>"
        for lbl, c in _tally(indices, label_of)
    )


def render_structured(node: Node, label_of: dict[int, str]) -> tuple[str, bool]:
    """Returns (html, is_sum) where is_sum flags whether the text is a
    top-level '+' expression (so a caller multiplying by it must parenthesize)."""
    if isinstance(node, Const):
        return (str(node.value), False)
    if isinstance(node, Var):
        return (label_of[node.i], False)
    if isinstance(node, Mono):
        return (_mono_str(node.indices, label_of), False)
    if isinstance(node, FreeProd):
        return (_freeprod_str(node.indices, label_of), False)
    if isinstance(node, AltProd):
        inner = _freeprod_str(node.indices, label_of)
        return (f"[{inner}&minus;1]", False)
    if isinstance(node, Add):
        parts = []
        for term in node.terms:
            text, is_sum = render_structured(term, label_of)
            parts.append(f"({text})" if is_sum else text)
        return (" + ".join(parts), True)
    if isinstance(node, Mul):
        parts = []
        for factor in node.factors:
            text, is_sum = render_structured(factor, label_of)
            parts.append(f"({text})" if is_sum else text)
        return ("".join(parts), False)
    raise TypeError(f"unknown node type: {node!r}")


def render_structured_html(node: Node, label_of: dict[int, str]) -> str:
    text, _ = render_structured(node, label_of)
    return text


def render_expanded_html(canonical: dict[Subset, int], label_of: dict[int, str]) -> str:
    """Sum of monomials, each with coefficient 1 (canonical is square-free)."""
    if not canonical:
        return "0"
    ordered = sorted(canonical.items(), key=lambda kv: (len(kv[0]), sorted(kv[0])))
    terms = []
    for subset, coeff in ordered:
        mono = _mono_str(subset, label_of)
        terms.append(mono if coeff == 1 else f"{coeff}{mono}")
    return " + ".join(terms)


def render_grouped_expanded_html(grouped: dict[tuple, int], groups: list[Subset]) -> str:
    labels = [label_for(g) for g in groups]
    if not grouped:
        return "0"
    ordered = sorted(grouped.items(), key=lambda kv: (sum(kv[0]), kv[0]))
    terms = []
    for exponents, coeff in ordered:
        factors = []
        for lbl, e in zip(labels, exponents):
            if e == 0:
                continue
            factors.append(lbl if e == 1 else f"{lbl}<sup>{e}</sup>")
        mono = "".join(factors) if factors else "1"
        terms.append(mono if coeff == 1 else f"{coeff}{mono}")
    return " + ".join(terms)


_SUPERSCRIPT = {0: "", 1: ""}


def render_univariate_html(counts: list[int]) -> str:
    terms = []
    for k, c in enumerate(counts):
        if c == 0:
            continue
        if k == 0:
            terms.append(str(c))
            continue
        x_part = "x" if k == 1 else f"x<sup>{k}</sup>"
        terms.append(x_part if c == 1 else f"{c}{x_part}")
    return " + ".join(terms) if terms else "0"


def identity_labels_text(universe: Subset = UNIVERSE) -> dict[int, str]:
    return {i: f"x{i}" for i in universe}


def _tally_text(indices: Subset, label_of: dict[int, str]) -> list[tuple[str, int]]:
    return _tally(indices, label_of)


def _mono_str_text(indices: Subset, label_of: dict[int, str]) -> str:
    if not indices:
        return "1"
    return "".join(
        lbl if c == 1 else f"{lbl}^{c}" for lbl, c in _tally_text(indices, label_of)
    )


def _freeprod_str_text(indices: Subset, label_of: dict[int, str]) -> str:
    if not indices:
        return "1"
    return "".join(
        f"(1+{lbl})" if c == 1 else f"(1+{lbl})^{c}"
        for lbl, c in _tally_text(indices, label_of)
    )


def render_structured_text(node: Node, label_of: dict[int, str]) -> str:
    if isinstance(node, Const):
        return str(node.value)
    if isinstance(node, Var):
        return label_of[node.i]
    if isinstance(node, Mono):
        return _mono_str_text(node.indices, label_of)
    if isinstance(node, FreeProd):
        return _freeprod_str_text(node.indices, label_of)
    if isinstance(node, AltProd):
        return f"[{_freeprod_str_text(node.indices, label_of)}-1]"
    if isinstance(node, Add):
        parts = []
        for term in node.terms:
            text = render_structured_text(term, label_of)
            parts.append(f"({text})" if isinstance(term, Add) else text)
        return " + ".join(parts)
    if isinstance(node, Mul):
        parts = []
        for factor in node.factors:
            text = render_structured_text(factor, label_of)
            parts.append(f"({text})" if isinstance(factor, Add) else text)
        return "".join(parts)
    raise TypeError(f"unknown node type: {node!r}")


def render_expanded_text(canonical: dict[Subset, int], label_of: dict[int, str]) -> str:
    if not canonical:
        return "0"
    ordered = sorted(canonical.items(), key=lambda kv: (len(kv[0]), sorted(kv[0])))
    terms = []
    for subset, coeff in ordered:
        mono = _mono_str_text(subset, label_of)
        terms.append(mono if coeff == 1 else f"{coeff}{mono}")
    return " + ".join(terms)


def render_univariate_text(counts: list[int]) -> str:
    terms = []
    for k, c in enumerate(counts):
        if c == 0:
            continue
        if k == 0:
            terms.append(str(c))
            continue
        x_part = "x" if k == 1 else f"x^{k}"
        terms.append(x_part if c == 1 else f"{c}{x_part}")
    return " + ".join(terms) if terms else "0"


def format_percent_br(value: Decimal, places: int = 3) -> str:
    """Brazilian decimal-comma percent formatting, fixed to `places` decimals,
    e.g. Decimal('0.98991') -> '98,991%'. The fractional part is dropped only
    when it rounds to all zero (e.g. '100%', '0%'), never trimmed digit by digit
    (so '0.8991' -> '89,910%', matching ACCEPTANCE.md)."""
    pct = value * 100
    quant = Decimal(1).scaleb(-places)
    pct = pct.quantize(quant)
    text = f"{pct:f}"
    if "." in text:
        integer, frac = text.split(".")
        text = integer if frac.strip("0") == "" else f"{integer},{frac}"
    return f"{text}%"
