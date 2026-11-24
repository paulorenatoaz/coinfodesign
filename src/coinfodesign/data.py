"""Loader for the CoInfoSim run 000018 loss tables.

Fetches (or reads locally) the two pinned upstream CSVs, verifies their
SHA-256 against the fixed hashes recorded in ATTRIBUTION.md, parses the
mean test loss as Decimal, and selects the 310 (n_per_class, subset)
real_to_real / linear_svm cells used by the study.

Never trains, resamples, or fabricates a loss. A malformed, missing, or
hash-mismatched input fails loudly with the offending file and key.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Mapping

PINNED_COMMIT = "4d294c93075be06ee856549fb001efda4883398a"
PINNED_URL_PREFIX = (
    "https://raw.githubusercontent.com/paulorenatoaz/coinfosim/"
    f"{PINNED_COMMIT}/reports/simulations/"
    "000018_air_quality_real_data_full-scale/"
)

LOSS_FILENAME = "full_loss_table_real_to_real.csv"
METADATA_FILENAME = "subset_metadata_table.csv"

EXPECTED_SHA256 = {
    LOSS_FILENAME: "32c3cf4e64db2971c091308b0e216e9a28f9c6809ff164c0c1dc70ec061b75cd",
    METADATA_FILENAME: "5dc595a5995227c8512a15b292b532eb0b952f6c78972c410d90d799ae36289e",
}

ARM = "real_to_real"
CLASSIFIER = "linear_svm"
SENSOR_NAMES = (
    "PT08.S1(CO)",
    "PT08.S2(NMHC)",
    "PT08.S3(NOx)",
    "PT08.S4(NO2)",
    "PT08.S5(O3)",
)
N_VALUES = tuple(2 ** k for k in range(1, 11))  # 2,4,...,1024
SOURCE_RUN_ID = "000018"


class EvidenceError(RuntimeError):
    """Raised when an input file is missing, malformed, or hash-mismatched."""


@dataclass(frozen=True)
class LossRecord:
    n_per_class: int
    subset: frozenset
    mean_loss: Decimal
    replications: int


@dataclass(frozen=True)
class SourceDataset:
    losses: Mapping[tuple, LossRecord]  # key: (n_per_class, subset frozenset)
    subset_by_id: Mapping[int, frozenset]
    source_commit: str = PINNED_COMMIT
    source_run: str = SOURCE_RUN_ID


def _verify_hash(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise EvidenceError(
            f"hash mismatch for {path.name}: expected {expected}, observed {digest}"
        )


def _fetch(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url) as response:  # noqa: S310 - pinned https URL
        dest.write_bytes(response.read())


def _resolve_source_file(source: Path | None, cache_dir: Path, filename: str) -> Path:
    if source is not None:
        candidate = source / filename
        if not candidate.is_file():
            raise EvidenceError(f"missing required source file: {candidate}")
        return candidate
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / filename
    if not cached.is_file():
        _fetch(PINNED_URL_PREFIX + filename, cached)
    return cached


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _parse_subset(label: str) -> frozenset:
    inner = label.strip()[1:-1]
    return frozenset(int(token.strip()[1:]) for token in inner.split(","))


def load_subset_metadata(path: Path) -> dict[int, frozenset]:
    mapping: dict[int, frozenset] = {}
    for row in _rows(path):
        try:
            key = int(row["subset_id"])
            subset = _parse_subset(row["x_label"])
            size = int(row["subset_size"])
            label_names = [n.strip() for n in row["subset_label"].strip()[1:-1].split(",")]
        except (KeyError, ValueError) as exc:
            raise EvidenceError(f"malformed row in {path.name}: {row!r} ({exc})") from exc
        if key in mapping:
            raise EvidenceError(f"duplicate subset_id {key} in {path.name}")
        if len(subset) != size:
            raise EvidenceError(f"subset_size mismatch for subset_id {key} in {path.name}")
        expected_names = [SENSOR_NAMES[i - 1] for i in sorted(subset)]
        if label_names != expected_names:
            raise EvidenceError(
                f"subset_label mismatch for subset_id {key}: {label_names} != {expected_names}"
            )
        mapping[key] = subset
    if len(mapping) != 31:
        raise EvidenceError(f"{path.name}: expected 31 nonempty subsets, found {len(mapping)}")
    universe = frozenset(range(1, 6))
    all_nonempty = {
        frozenset(c)
        for size in range(1, 6)
        for c in itertools.combinations(sorted(universe), size)
    }
    if set(mapping.values()) != all_nonempty:
        raise EvidenceError(f"{path.name}: subset coverage incomplete")
    return mapping


def load_losses(path: Path, subset_by_id: dict[int, frozenset]) -> dict[tuple, LossRecord]:
    result: dict[tuple, LossRecord] = {}
    seen_keys: set[tuple] = set()
    for row in _rows(path):
        if row.get("arm") != ARM or row.get("classifier") != CLASSIFIER:
            continue
        try:
            subset_id = int(row["subset_id"])
            subset = subset_by_id[subset_id]
            n_per_class = int(row["n_per_class"])
            mean_loss = Decimal(row["mean_loss"])
            replications = int(row["replications"])
        except (KeyError, ValueError) as exc:
            raise EvidenceError(f"malformed row in {path.name}: {row!r} ({exc})") from exc
        label_subset = _parse_subset(row["x_label"])
        if label_subset != subset:
            raise EvidenceError(
                f"x_label/subset_id mismatch for subset_id {subset_id} in {path.name}"
            )
        if not mean_loss.is_finite() or mean_loss < 0 or mean_loss > 1:
            raise EvidenceError(f"mean_loss out of [0,1] for key ({n_per_class}, {subset})")
        if replications <= 0:
            raise EvidenceError(f"non-positive replications for key ({n_per_class}, {subset})")
        key = (n_per_class, subset)
        if key in seen_keys:
            raise EvidenceError(f"duplicate loss record for key {key} in {path.name}")
        seen_keys.add(key)
        result[key] = LossRecord(
            n_per_class=n_per_class,
            subset=subset,
            mean_loss=mean_loss,
            replications=replications,
        )
    expected_keys = set(itertools.product(N_VALUES, subset_by_id.values()))
    if set(result.keys()) != expected_keys:
        missing = expected_keys - set(result.keys())
        extra = set(result.keys()) - expected_keys
        raise EvidenceError(
            f"{path.name}: selected {ARM}/{CLASSIFIER} rows do not match the expected "
            f"310 cells (10 n x 31 subsets); missing={len(missing)} extra={len(extra)}"
        )
    return result


def load_source(source: Path | None = None, cache_dir: Path | None = None) -> SourceDataset:
    """Load, hash-verify, and select the 310 real_to_real/linear_svm loss cells.

    `source`, if given, is a local directory containing the two pinned CSVs.
    Otherwise they are fetched from the immutable pinned URL and cached under
    `cache_dir` (default: `.cache/coinfosim-000018` under the current directory).
    """
    cache_dir = cache_dir or Path(".cache/coinfosim-000018")
    metadata_path = _resolve_source_file(source, cache_dir, METADATA_FILENAME)
    loss_path = _resolve_source_file(source, cache_dir, LOSS_FILENAME)
    _verify_hash(metadata_path, EXPECTED_SHA256[METADATA_FILENAME])
    _verify_hash(loss_path, EXPECTED_SHA256[LOSS_FILENAME])
    subset_by_id = load_subset_metadata(metadata_path)
    losses = load_losses(loss_path, subset_by_id)
    return SourceDataset(losses=losses, subset_by_id=subset_by_id)
