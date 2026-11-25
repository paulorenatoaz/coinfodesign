"""Deterministic build: source losses -> CSV/JSON + static PT-BR site."""
from __future__ import annotations

import csv
import json
import os
import shutil
from decimal import Decimal
from pathlib import Path

from . import polynomial as poly
from . import render
from .cases import Case, TAUS, compute_all_cases, plateau_starts
from .data import PINNED_COMMIT, SOURCE_RUN_ID, load_source
from . import sitegen


def _case_to_jsonable(case: Case) -> dict:
    labels = render.identity_labels()
    labels_text = render.identity_labels_text()
    canonical_pairs = [
        [sorted(subset), coeff] for subset, coeff in sorted(
            case.canonical.items(), key=lambda kv: (len(kv[0]), sorted(kv[0]))
        )
    ]
    return {
        "n_per_class": case.n_per_class,
        "tau": f"{case.tau:.2f}",
        "case_key": case.case_key,
        "minimal_sets": [list(m) for m in case.minimal_sets],
        "tree": poly.to_jsonable(case.tree),
        "canonical": canonical_pairs,
        "counts": case.counts,
        "states": case.states,
        "r_at_90": str(case.r_at_90),
        "r_at_50": str(case.r_at_50),
        "r_at_90_br": render.format_percent_br(case.r_at_90),
        "h_structured_html": render.render_structured_html(case.tree, labels),
        "h_expanded_html": render.render_expanded_html(case.canonical, labels),
        "h_univariate_html": render.render_univariate_html(case.counts),
        "h_structured_text": render.render_structured_text(case.tree, labels_text),
        "h_expanded_text": render.render_expanded_text(case.canonical, labels_text),
        "h_univariate_text": render.render_univariate_text(case.counts),
    }


def write_data(cases: list[Case], out_dir: Path, build_commit: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    plateau = plateau_starts(cases)

    jsonable_cases = [_case_to_jsonable(c) for c in cases]
    payload = {
        "source": {"repo": "paulorenatoaz/coinfosim", "commit": PINNED_COMMIT, "run": SOURCE_RUN_ID},
        "build_commit": build_commit,
        "case_count": len(cases),
        "plateau_start_n": {f"{tau:.2f}": n for tau, n in plateau.items()},
        "cases": jsonable_cases,
    }
    (out_dir / "cases.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8"
    )

    with (out_dir / "cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["n_per_class", "tau", "minimal_sets", "a0", "a1", "a2", "a3", "a4", "a5",
             "states", "H_univariate", "R_at_p_0.90", "R_at_p_0.50"]
        )
        for case in cases:
            writer.writerow(
                [
                    case.n_per_class,
                    f"{case.tau:.2f}",
                    json.dumps([list(m) for m in case.minimal_sets]),
                    *case.counts,
                    case.states,
                    render.render_univariate_text(case.counts),
                    case.r_at_90,
                    case.r_at_50,
                ]
            )
    return payload


def build(source: Path | None, out: Path, commit: str) -> dict:
    dataset = load_source(source=source)
    cases = compute_all_cases(dataset)
    if len(cases) != 40:
        raise AssertionError(f"expected 40 cases, computed {len(cases)}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    payload = write_data(cases, out / "data", commit)
    sitegen.generate(out, payload, commit, cases)
    repo_root = Path(__file__).resolve().parents[2]
    for name in ("LICENSE", "ATTRIBUTION.md", "CITATION.cff"):
        src_file = repo_root / name
        if src_file.is_file():
            shutil.copy2(src_file, out / name)
    return payload


def resolve_commit(explicit: str | None) -> str:
    if explicit:
        return explicit
    env_sha = os.environ.get("GITHUB_SHA")
    if env_sha:
        return env_sha[:12]
    return "local-dev"
