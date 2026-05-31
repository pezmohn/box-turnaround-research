from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.serve_casebook_reviewer import load_items, upsert_review


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "event_id",
                "chart_path",
                "symbol",
                "timestamp_close",
                "pattern",
                "pattern_label",
                "classification",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "event_id": "A",
                "chart_path": "charts/a.svg",
                "symbol": "SPY",
                "timestamp_close": "2026-01-02 10:00:00",
                "pattern": "hard_vwap_confirmation",
                "pattern_label": "5+ streak + extension failure + VWAP reclaim",
                "classification": "clean_transition",
            }
        )


def test_upsert_review_creates_and_updates_manual_review(tmp_path: Path) -> None:
    review_path = tmp_path / "manual_review.csv"

    saved = upsert_review(
        review_path,
        {"event_id": "A", "chart_path": "charts/a.svg", "manual_label": "clean", "notes": "clear"},
    )
    assert saved["manual_label"] == "clean"

    saved = upsert_review(
        review_path,
        {"event_id": "A", "chart_path": "charts/a.svg", "manual_label": "late", "notes": "too late"},
    )
    rows = list(csv.DictReader(review_path.open(encoding="utf-8")))

    assert saved["manual_label"] == "late"
    assert len(rows) == 1
    assert rows[0]["notes"] == "too late"


def test_upsert_review_rejects_unknown_label(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        upsert_review(
            tmp_path / "manual_review.csv",
            {"event_id": "A", "chart_path": "charts/a.svg", "manual_label": "maybe"},
        )


def test_load_items_merges_existing_reviews(tmp_path: Path) -> None:
    casebook_dir = tmp_path / "casebook"
    _write_manifest(casebook_dir / "casebook_manifest.csv")
    upsert_review(
        casebook_dir / "manual_review.csv",
        {"event_id": "A", "chart_path": "charts/a.svg", "manual_label": "noisy", "notes": "chop"},
    )

    items = load_items(casebook_dir)

    assert len(items) == 1
    assert items[0]["manual_label"] == "noisy"
    assert items[0]["notes"] == "chop"
