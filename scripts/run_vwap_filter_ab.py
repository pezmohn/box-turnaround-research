#!/usr/bin/env python3
"""Compare confirmed-box research with VWAP box filter on vs off."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import add_analysis_flags, add_validation_split
from src.box_events import build_box_events
from src.labels import add_context_labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", help="Comma-separated symbols. Defaults to config data.default_symbols.")
    parser.add_argument("--data-dir", default="/home/backtest/stockdata/stock_data_1min")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--output-dir", default="outputs/vwap_filter_ab")
    parser.add_argument("--research-fraction", type=float, default=0.70)
    parser.add_argument("--start", help="Optional inclusive timestamp filter.")
    parser.add_argument("--end", help="Optional exclusive timestamp filter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_config = _load_config(Path(args.config))
    symbols = _symbols(args.symbols, base_config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("vwap_on", True),
        ("vwap_off", False),
    ]
    event_sets: dict[str, pd.DataFrame] = {}
    for name, use_vwap_filter in variants:
        config = copy.deepcopy(base_config)
        config.setdefault("indicator", {})["use_vwap_filter"] = use_vwap_filter
        events = _build_events(
            symbols=symbols,
            data_dir=Path(args.data_dir),
            config=config,
            start=args.start,
            end=args.end,
        )
        variant_dir = output_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        events.to_parquet(variant_dir / "box_events_all.parquet", index=False)
        events.to_csv(variant_dir / "box_events_all.csv", index=False)
        event_sets[name] = events

    summary = build_summary(event_sets, research_fraction=args.research_fraction)
    summary.to_csv(output_dir / "vwap_filter_ab_summary.csv", index=False)
    _write_report(
        output_dir / "vwap_filter_ab_report.md",
        summary=summary,
        symbols=symbols,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
    )
    print(f"Wrote {output_dir / 'vwap_filter_ab_report.md'}")
    return 0


def build_summary(event_sets: dict[str, pd.DataFrame], research_fraction: float = 0.70) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for variant, events in event_sets.items():
        rows.extend(_summary_rows(variant, events, research_fraction=research_fraction))
    return pd.DataFrame(rows)


def _summary_rows(variant: str, events: pd.DataFrame, research_fraction: float) -> list[dict[str, object]]:
    if events.empty:
        return [
            {
                "variant": variant,
                "split": "all",
                "scope": "all_events",
                "n": 0,
            }
        ]
    prepared = add_validation_split(add_analysis_flags(events), research_fraction=research_fraction)
    scopes = {
        "all_events": prepared,
        "streak5": prepared[prepared["streak_length"] >= 5],
        "streak5_extfail": prepared[
            (prepared["streak_length"] >= 5) & prepared["extension_failure_3"]
        ],
        "streak5_extfail_vwap": prepared[
            (prepared["streak_length"] >= 5)
            & prepared["extension_failure_3"]
            & prepared["vwap_reclaim_3"]
        ],
        "streak5_extfail_midpoint": prepared[
            (prepared["streak_length"] >= 5)
            & prepared["extension_failure_3"]
            & prepared["midpoint_break_3"]
        ],
        "streak5_extfail_vwap_or_midpoint": prepared[
            (prepared["streak_length"] >= 5)
            & prepared["extension_failure_3"]
            & (prepared["vwap_reclaim_3"] | prepared["midpoint_break_3"])
        ],
        "streak5_extfail_vwap_and_midpoint": prepared[
            (prepared["streak_length"] >= 5)
            & prepared["extension_failure_3"]
            & prepared["vwap_reclaim_3"]
            & prepared["midpoint_break_3"]
        ],
    }
    rows: list[dict[str, object]] = []
    for split_name, split_df in [("all", prepared), *prepared.groupby("split", sort=True)]:
        for scope_name in scopes:
            scope_df = scopes[scope_name]
            if split_name != "all":
                scope_df = scope_df[scope_df["split"] == split_name]
            rows.append(_rate_row(variant, str(split_name), scope_name, scope_df))
    return rows


def _rate_row(variant: str, split: str, scope: str, events: pd.DataFrame) -> dict[str, object]:
    row: dict[str, object] = {
        "variant": variant,
        "split": split,
        "scope": scope,
        "n": len(events),
    }
    for metric in [
        "opposite_box_within_3",
        "opposite_box_within_6",
        "turnaround_candidate",
        "continuation",
        "extension_hit",
        "reversal_followthrough",
        "vwap_hold_after_reclaim",
        "midpoint_hold",
    ]:
        row[f"p_{metric}"] = _mean_bool(events, metric)
    return row


def _mean_bool(events: pd.DataFrame, column: str) -> float:
    if events.empty or column not in events.columns:
        return float("nan")
    return float(events[column].fillna(False).astype(bool).mean())


def _build_events(
    symbols: list[str],
    data_dir: Path,
    config: dict,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    all_events = []
    for symbol in symbols:
        path = data_dir / f"{symbol}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Missing data for {symbol}: {path}")
        ohlcv = pd.read_parquet(path)
        ohlcv = _filter_time_range(ohlcv, start=start, end=end)
        events = build_box_events(ohlcv, config, symbol=symbol)
        events = add_context_labels(events, config)
        all_events.append(events)
        print(f"{symbol}: {len(events):,} events ({'VWAP ON' if config['indicator']['use_vwap_filter'] else 'VWAP OFF'})")
    if not all_events:
        return pd.DataFrame()
    return pd.concat(all_events, ignore_index=True)


def _filter_time_range(ohlcv: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if not start and not end:
        return ohlcv
    ts = pd.to_datetime(ohlcv["timestamp"] if "timestamp" in ohlcv.columns else ohlcv.index)
    mask = pd.Series(True, index=ohlcv.index)
    if start:
        mask &= ts >= pd.Timestamp(start)
    if end:
        mask &= ts < pd.Timestamp(end)
    return ohlcv.loc[mask]


def _load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _symbols(symbols_arg: str | None, config: dict) -> list[str]:
    if symbols_arg:
        return [s.strip().upper().lstrip("$") for s in symbols_arg.split(",") if s.strip()]
    return list(config["data"]["default_symbols"])


def _write_report(
    path: Path,
    summary: pd.DataFrame,
    symbols: list[str],
    data_dir: str,
    start: str | None,
    end: str | None,
) -> None:
    headline = _headline_table(summary)
    validation = summary[(summary["split"] == "validation") & summary["scope"].str.startswith("streak5")]
    lines = [
        "# VWAP Box-Formation Filter A/B Report",
        "",
        "## Scope",
        "",
        "- Purpose: sensitivity-check the box-turnaround research with VWAP box formation ON vs OFF.",
        "- This is still research context only: no entries, exits, sizing, PnL, or scanner promotion.",
        f"- Symbols: {', '.join(symbols)}",
        f"- Data dir: `{data_dir}`",
        f"- Start: `{start or 'full history'}`",
        f"- End: `{end or 'full history'}`",
        "",
        "## Headline",
        "",
        _markdown_table(headline),
        "",
        "## Validation Split: 5+ Context Scopes",
        "",
        _markdown_table(validation),
        "",
        "## Interpretation Checklist",
        "",
        "- If VWAP OFF adds many events but lowers validation followthrough/continuation quality, keep VWAP ON as research default.",
        "- If VWAP OFF adds meaningful 5+ extension-failure contexts without degrading validation metrics, review those charts before changing Pine defaults.",
        "- Do not optimize thresholds from this run alone; use it to decide whether VWAP OFF deserves visual casebook review.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _headline_table(summary: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "variant",
        "split",
        "scope",
        "n",
        "p_opposite_box_within_3",
        "p_turnaround_candidate",
        "p_reversal_followthrough",
        "p_continuation",
    ]
    scopes = [
        "all_events",
        "streak5",
        "streak5_extfail_vwap_or_midpoint",
        "streak5_extfail_vwap_and_midpoint",
    ]
    return summary[(summary["split"] == "all") & summary["scope"].isin(scopes)][cols]


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    table = df.copy()
    rows = [list(table.columns), *table.astype(object).where(pd.notna(table), "").values.tolist()]
    formatted = [[_format_cell(cell) for cell in row] for row in rows]
    header = "| " + " | ".join(formatted[0]) + " |"
    sep = "| " + " | ".join(["---"] * len(formatted[0])) + " |"
    body = ["| " + " | ".join(row) + " |" for row in formatted[1:]]
    return "\n".join([header, sep, *body])


def _format_cell(value: object) -> str:
    if isinstance(value, float):
        return "" if pd.isna(value) else f"{value:.4f}"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())