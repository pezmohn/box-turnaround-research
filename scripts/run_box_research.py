#!/usr/bin/env python3
"""Run confirmed-box research for one or more symbols."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import session_heatmaps, streak_survival_table
from src.box_events import build_box_events
from src.labels import add_context_labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", help="Comma-separated symbols. Defaults to config data.default_symbols.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data/processed")
    parser.add_argument("--tables-dir", default="outputs/tables")
    parser.add_argument("--reports-dir", default="outputs/reports")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--start", help="Optional inclusive timestamp filter.")
    parser.add_argument("--end", help="Optional exclusive timestamp filter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with open(args.config, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    symbols = (
        [s.strip().upper().lstrip("$") for s in args.symbols.split(",") if s.strip()]
        if args.symbols
        else config["data"]["default_symbols"]
    )
    output_dir = Path(args.output_dir)
    tables_dir = Path(args.tables_dir)
    reports_dir = Path(args.reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    all_events = []
    for symbol in symbols:
        path = Path(args.data_dir) / f"{symbol}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Missing data for {symbol}: {path}")
        ohlcv = pd.read_parquet(path)
        if args.start or args.end:
            ts = pd.to_datetime(ohlcv["timestamp"] if "timestamp" in ohlcv.columns else ohlcv.index)
            mask = pd.Series(True, index=ohlcv.index)
            if args.start:
                mask &= ts >= pd.Timestamp(args.start)
            if args.end:
                mask &= ts < pd.Timestamp(args.end)
            ohlcv = ohlcv.loc[mask]
        events = build_box_events(ohlcv, config, symbol=symbol)
        events = add_context_labels(events, config)
        events.to_parquet(output_dir / f"box_events_{symbol}.parquet", index=False)
        events.to_csv(output_dir / f"box_events_{symbol}.csv", index=False)
        all_events.append(events)
        print(f"{symbol}: {len(events):,} events")

    combined = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    if not combined.empty:
        combined.to_parquet(output_dir / "box_events_all.parquet", index=False)
        streak_table = streak_survival_table(combined)
        streak_table.to_csv(tables_dir / "streak_survival.csv", index=False)
        heatmaps = session_heatmaps(combined)
        for name, table in heatmaps.items():
            table.to_csv(tables_dir / f"{name}.csv")
        _write_report(combined, streak_table, heatmaps, reports_dir / "baseline_context_report.md", symbols)
    return 0


def _write_report(
    events: pd.DataFrame,
    streak_table: pd.DataFrame,
    heatmaps: dict[str, pd.DataFrame],
    path: Path,
    symbols: list[str],
) -> None:
    symbol_counts = events.groupby("symbol").size().sort_index()
    in_play_counts = events.groupby(["symbol", "in_play"]).size().unstack(fill_value=0)
    session_counts = events["session_bucket"].value_counts()
    lines = [
        "# Baseline Box Context Report",
        "",
        "## Scope",
        "",
        "- Research layer only: confirmed 5-minute box events, context labels, and forward outcomes.",
        "- No entries, exits, position sizing, PnL optimization, or trading recommendation.",
        f"- Symbols: {', '.join(symbols)}",
        f"- Events: {len(events):,}",
        "",
        "## Event Counts By Symbol",
        "",
        _markdown_table(symbol_counts.reset_index(name="events")),
        "",
        "## In-Play Split",
        "",
        _markdown_table(in_play_counts.reset_index()),
        "",
        "## Session Bucket Counts",
        "",
        _markdown_table(session_counts.reset_index()),
        "",
        "## Streak Survival",
        "",
        _markdown_table(streak_table),
        "",
        "## Heatmap Tables",
        "",
    ]
    for name, table in heatmaps.items():
        lines.extend([f"### {name}", "", _markdown_table(table.reset_index()), ""])
    lines.extend(
        [
            "## Caveats",
            "",
            "- Confirmed boxes are evaluated only after the 5-minute candle is closed.",
            "- Forward columns are outcome labels for research and must not be used as same-bar input features.",
            "- In-play classification is a simple day-level subgroup label based on premarket context: gap, premarket relative volume, and premarket dollar volume.",
            "- Premarket relative volume uses available lookback history in the input data; early history can be sparse.",
            "- Raw market data and generated event datasets are local artifacts and should not be committed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cleaned = df.copy()
    cleaned.columns = [str(col) for col in cleaned.columns]
    rows = [list(cleaned.columns)]
    rows.extend(cleaned.astype(object).where(pd.notna(cleaned), "").values.tolist())
    rows = [[_format_cell(cell) for cell in row] for row in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join([header, sep, *body])


def _format_cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
