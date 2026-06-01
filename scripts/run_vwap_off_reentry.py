#!/usr/bin/env python3
"""Test VWAP_OFF reversal boxes as main-trend re-entry context."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_vwap_filter_ab import _build_events, _load_config, _markdown_table, _symbols
from src.analysis import add_analysis_flags, add_validation_split


METRICS = [
    "p_extension_hit",
    "p_continuation",
    "p_opposite_box_within_3",
    "p_opposite_box_within_6",
    "mean_forward_return_3_boxes",
    "mean_forward_return_6_boxes",
    "mean_mfe_6_boxes",
    "mean_mae_6_boxes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", help="Comma-separated symbols. Defaults to config data.default_symbols.")
    parser.add_argument("--data-dir", default="/home/backtest/stockdata/stock_data_1min")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--output-dir", default="outputs/vwap_off_reentry")
    parser.add_argument("--research-fraction", type=float, default=0.70)
    parser.add_argument("--start", help="Optional inclusive timestamp filter.")
    parser.add_argument("--end", help="Optional exclusive timestamp filter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = _load_config(Path(args.config))
    config.setdefault("indicator", {})["use_vwap_filter"] = False
    symbols = _symbols(args.symbols, config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = _build_events(
        symbols=symbols,
        data_dir=Path(args.data_dir),
        config=config,
        start=args.start,
        end=args.end,
    )
    events.to_parquet(output_dir / "vwap_off_box_events_all.parquet", index=False)
    events.to_csv(output_dir / "vwap_off_box_events_all.csv", index=False)

    tagged = add_reentry_flags(events)
    tagged.to_parquet(output_dir / "vwap_off_reentry_events.parquet", index=False)
    tagged.to_csv(output_dir / "vwap_off_reentry_events.csv", index=False)

    summary = build_reentry_summary(tagged, research_fraction=args.research_fraction)
    summary.to_csv(output_dir / "vwap_off_reentry_summary.csv", index=False)
    _write_report(
        output_dir / "vwap_off_reentry_report.md",
        summary=summary,
        symbols=symbols,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
    )
    print(f"Wrote {output_dir / 'vwap_off_reentry_report.md'}")
    return 0


def add_reentry_flags(events: pd.DataFrame) -> pd.DataFrame:
    """Mark first reversal boxes that resume a prior same-direction structure."""

    if events.empty:
        return events.copy()

    out = add_analysis_flags(events).sort_values(["symbol", "timestamp_close"]).copy()
    out["is_first_reversal_box"] = out["streak_length"] == 1
    out["countertrend_len"] = out["prior_streak_length"].fillna(0).astype(int)
    out["pre_countertrend_len"] = 0
    out["pre_countertrend_direction"] = 0
    out["countertrend_extension_failure_3"] = False
    out["countertrend_extension_failure_6"] = False
    out["countertrend_had_extension"] = False
    out["reentry_vwap_side"] = (out["direction"].eq(1) & out["close_above_vwap"]) | (
        out["direction"].eq(-1) & ~out["close_above_vwap"]
    )

    for _, idxs in out.groupby("symbol", sort=False).groups.items():
        idx_list = list(idxs)
        run_starts = [idx for idx in idx_list if bool(out.at[idx, "is_first_reversal_box"])]
        for pos, run_start in enumerate(run_starts):
            if pos < 2:
                continue
            previous_run_start = run_starts[pos - 1]
            pre_previous_run_start = run_starts[pos - 2]
            previous_run_members = [
                idx for idx in idx_list if previous_run_start <= idx < run_start
            ]
            if not previous_run_members:
                continue
            previous_terminal = previous_run_members[-1]
            out.at[run_start, "pre_countertrend_direction"] = int(out.at[pre_previous_run_start, "direction"])
            out.at[run_start, "pre_countertrend_len"] = int(out.at[previous_run_start, "prior_streak_length"])
            out.at[run_start, "countertrend_extension_failure_3"] = bool(
                out.at[previous_terminal, "extension_failure_3"]
            )
            out.at[run_start, "countertrend_extension_failure_6"] = bool(
                out.at[previous_terminal, "extension_failure_6"]
            )
            out.at[run_start, "countertrend_had_extension"] = bool(out.at[previous_terminal, "extension_hit"])

    out["main_structure_reentry_3"] = (
        out["is_first_reversal_box"]
        & (out["direction"] == out["pre_countertrend_direction"])
        & (out["pre_countertrend_len"] >= 3)
        & (out["countertrend_len"] >= 2)
        & out["countertrend_extension_failure_3"]
    )
    out["main_structure_reentry_5"] = (
        out["is_first_reversal_box"]
        & (out["direction"] == out["pre_countertrend_direction"])
        & (out["pre_countertrend_len"] >= 5)
        & (out["countertrend_len"] >= 2)
        & out["countertrend_extension_failure_3"]
    )
    out["main_structure_reentry_3_vwap_side"] = out["main_structure_reentry_3"] & out["reentry_vwap_side"]
    out["standalone_failed_countertrend_reversal"] = (
        out["is_first_reversal_box"]
        & (out["countertrend_len"] >= 2)
        & out["countertrend_extension_failure_3"]
    )
    return out


def build_reentry_summary(events: pd.DataFrame, research_fraction: float = 0.70) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    prepared = add_validation_split(events, research_fraction=research_fraction)
    scopes = {
        "all_vwap_off_boxes": prepared,
        "first_reversal_box": prepared[prepared["is_first_reversal_box"]],
        "standalone_failed_countertrend_reversal": prepared[
            prepared["standalone_failed_countertrend_reversal"]
        ],
        "main_structure_reentry_3": prepared[prepared["main_structure_reentry_3"]],
        "main_structure_reentry_5": prepared[prepared["main_structure_reentry_5"]],
        "main_structure_reentry_3_vwap_side": prepared[
            prepared["main_structure_reentry_3_vwap_side"]
        ],
    }
    rows: list[dict[str, object]] = []
    for split_name, _ in [("all", prepared), *prepared.groupby("split", sort=True)]:
        for scope, scope_df in scopes.items():
            if split_name != "all":
                scope_df = scope_df[scope_df["split"] == split_name]
            rows.append(_rate_row(str(split_name), scope, scope_df))
    return pd.DataFrame(rows)


def _rate_row(split: str, scope: str, events: pd.DataFrame) -> dict[str, object]:
    row: dict[str, object] = {
        "split": split,
        "scope": scope,
        "n": len(events),
    }
    row["p_extension_hit"] = _mean_bool(events, "extension_hit")
    row["p_continuation"] = _mean_bool(events, "continuation")
    row["p_opposite_box_within_3"] = _mean_bool(events, "opposite_box_within_3")
    row["p_opposite_box_within_6"] = _mean_bool(events, "opposite_box_within_6")
    for col in ["forward_return_3_boxes", "forward_return_6_boxes", "mfe_6_boxes", "mae_6_boxes"]:
        row[f"mean_{col}"] = _mean_float(events, col)
    return row


def _mean_bool(events: pd.DataFrame, column: str) -> float:
    if events.empty or column not in events.columns:
        return float("nan")
    return float(events[column].fillna(False).astype(bool).mean())


def _mean_float(events: pd.DataFrame, column: str) -> float:
    if events.empty or column not in events.columns:
        return float("nan")
    return float(pd.to_numeric(events[column], errors="coerce").mean())


def _write_report(
    path: Path,
    summary: pd.DataFrame,
    symbols: list[str],
    data_dir: str,
    start: str | None,
    end: str | None,
) -> None:
    headline_cols = ["split", "scope", "n", *METRICS]
    headline = summary[(summary["split"] == "validation")][headline_cols]
    lines = [
        "# VWAP_OFF Reversal Box Re-Entry Report",
        "",
        "## Scope",
        "",
        "- Purpose: test `VWAP_OFF reversal box as trend-continuation re-entry`, not as a standalone extension signal.",
        "- Entry proxy: first opposite/reversal box after a failed countertrend box streak.",
        "- Main-trend proxy: the box run before that countertrend streak was in the same direction as the re-entry box.",
        "- This is context research only: no entries, exits, sizing, PnL, scanner, paper, or live changes.",
        f"- Symbols: {', '.join(symbols)}",
        f"- Data dir: `{data_dir}`",
        f"- Start: `{start or 'full history'}`",
        f"- End: `{end or 'full history'}`",
        "",
        "## Validation Split",
        "",
        _markdown_table(headline),
        "",
        "## Decision Rules",
        "",
        "- Prefer re-entry only if `main_structure_reentry_*` improves continuation/extension and forward returns versus `standalone_failed_countertrend_reversal`.",
        "- Reject as trade trigger if lift is small, sample is thin, or opposite-box failure remains high.",
        "- Do not treat `opposite_box_within_*` as success here; for the re-entry event it means the re-entry failed.",
        "",
        "## Full Summary",
        "",
        _markdown_table(summary[headline_cols]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
