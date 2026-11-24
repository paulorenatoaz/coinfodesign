import csv
from decimal import Decimal
from pathlib import Path

import pytest

from coinfodesign.data import EvidenceError, load_losses, load_source, load_subset_metadata


def test_load_source_selects_exactly_310_cells(dataset):
    assert len(dataset.losses) == 310
    assert len(dataset.subset_by_id) == 31


def test_hash_mismatch_is_rejected(tmp_path):
    (tmp_path / "subset_metadata_table.csv").write_text(
        "subset_id,x_label,subset_label,subset_size\n0,{X1},{A},1\n"
    )
    (tmp_path / "full_loss_table_real_to_real.csv").write_text(
        "arm,n_per_class,classifier,subset_id,x_label,mean_loss,replications\n"
    )
    with pytest.raises(EvidenceError, match="hash mismatch"):
        load_source(source=tmp_path)


def test_malformed_metadata_row_fails_clearly(tmp_path):
    path = tmp_path / "subset_metadata_table.csv"
    path.write_text(
        "subset_id,x_label,subset_label,subset_size\n"
        "0,{X1},{PT08.S1(CO)},1\n"
        "0,{X2},{PT08.S2(NMHC)},1\n"  # duplicate subset_id
    )
    with pytest.raises(EvidenceError, match="duplicate subset_id"):
        load_subset_metadata(path)


def test_synthetic_boundary_loss_at_and_above_tau(dataset, tmp_path):
    """A loss exactly at tau must pass; immediately above tau must fail."""
    metadata_path = tmp_path / "subset_metadata_table.csv"
    rows = []
    for sid, subset in dataset.subset_by_id.items():
        rows.append(subset)
    # Reuse the real metadata file content by re-deriving labels from the dataset.
    from coinfodesign.data import SENSOR_NAMES

    with metadata_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["subset_id", "x_label", "subset_label", "subset_size"])
        for sid, subset in dataset.subset_by_id.items():
            x_label = "{" + ",".join(f"X{i}" for i in sorted(subset)) + "}"
            label = "{" + ",".join(SENSOR_NAMES[i - 1] for i in sorted(subset)) + "}"
            writer.writerow([sid, x_label, label, len(subset)])

    tau = Decimal("0.10")
    at_tau_subset_id = next(iter(dataset.subset_by_id))
    above_tau_subset_id = next(i for i in dataset.subset_by_id if i != at_tau_subset_id)

    loss_path = tmp_path / "full_loss_table_real_to_real.csv"
    with loss_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["arm", "n_per_class", "classifier", "subset_id", "x_label", "mean_loss", "replications"])
        for n in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024):
            for sid, subset in dataset.subset_by_id.items():
                x_label = "{" + ",".join(f"X{i}" for i in sorted(subset)) + "}"
                if sid == at_tau_subset_id:
                    loss = tau
                elif sid == above_tau_subset_id:
                    loss = tau + Decimal("0.0000000001")
                else:
                    loss = Decimal("0.5")
                writer.writerow(["real_to_real", n, "linear_svm", sid, x_label, str(loss), 2000])

    subset_by_id = load_subset_metadata(metadata_path)
    losses = load_losses(loss_path, subset_by_id)
    at_subset = subset_by_id[at_tau_subset_id]
    above_subset = subset_by_id[above_tau_subset_id]
    assert losses[(512, at_subset)].mean_loss <= tau
    assert losses[(512, above_subset)].mean_loss > tau
