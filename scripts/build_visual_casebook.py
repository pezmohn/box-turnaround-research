#!/usr/bin/env python3
"""Build a visual casebook of confirmed-box context events.

The output is a research artifact: SVG chart snippets plus a manifest and
Markdown index. It does not define entries, exits, stops, targets, or PnL.
"""

from __future__ import annotations

import argparse
import html
import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PATTERN_ORDER = [
    "broad_midpoint_watchlist",
    "hard_vwap_confirmation",
    "highest_conviction_vwap_midpoint",
    "power_hour_broad_reclaim",
    "ignore_long_streak_only",
]

PATTERN_LABELS = {
    "broad_midpoint_watchlist": "5+ streak + extension failure + midpoint break",
    "hard_vwap_confirmation": "5+ streak + extension failure + VWAP reclaim",
    "highest_conviction_vwap_midpoint": "5+ streak + extension failure + VWAP + midpoint",
    "power_hour_broad_reclaim": "5+ streak + extension failure + VWAP/midpoint in power hour",
    "ignore_long_streak_only": "5+ streak without failure/reclaim",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-file", default="data/processed/box_events_all.parquet")
    parser.add_argument("--data-dir", default="/home/backtest/stockdata/stock_data_1min")
    parser.add_argument("--output-dir", default="outputs/casebook")
    parser.add_argument("--samples-per-pattern", type=int, default=24)
    parser.add_argument("--lookback-minutes", type=int, default=90)
    parser.add_argument("--lookahead-minutes", type=int, default=90)
    parser.add_argument("--split", choices=["all", "research", "validation"], default="validation")
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    events = read_events(Path(args.events_file))
    if events.empty:
        raise ValueError("events file contains no rows")
    events = add_casebook_flags(events)
    if args.split != "all":
        events = events[events["casebook_split"] == args.split].copy()
    out_dir = Path(args.output_dir)
    chart_dir = out_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    raw_cache: dict[str, pd.DataFrame] = {}
    manifest_rows: list[dict[str, object]] = []

    for pattern_name in PATTERN_ORDER:
        candidates = events[events[pattern_name]].copy()
        if candidates.empty:
            continue
        sample_n = min(args.samples_per_pattern, len(candidates))
        sample = candidates.sample(sample_n, random_state=args.seed).sort_values(["symbol", "timestamp_close"])
        pattern_dir = chart_dir / pattern_name
        pattern_dir.mkdir(parents=True, exist_ok=True)
        for _, event in sample.iterrows():
            symbol = str(event["symbol"]).upper()
            raw = raw_cache.get(symbol)
            if raw is None:
                raw = read_symbol_data(Path(args.data_dir) / f"{symbol}.parquet")
                raw_cache[symbol] = raw
            chart_bars = window_bars(
                raw,
                pd.Timestamp(event["timestamp_close"]),
                args.lookback_minutes,
                args.lookahead_minutes,
            )
            classification = classify_event(event)
            filename = safe_filename(f"{event['event_id']}_{classification}.svg")
            chart_path = pattern_dir / filename
            chart_path.write_text(render_svg(chart_bars, event, pattern_name, classification), encoding="utf-8")
            manifest_rows.append(
                {
                    "pattern": pattern_name,
                    "pattern_label": PATTERN_LABELS[pattern_name],
                    "classification": classification,
                    "chart_path": str(chart_path.relative_to(out_dir)),
                    "event_id": event["event_id"],
                    "symbol": symbol,
                    "timestamp_close": event["timestamp_close"],
                    "direction": "green" if int(event["direction"]) == 1 else "red",
                    "streak_length": int(event["streak_length"]),
                    "session_bucket": event["session_bucket"],
                    "in_play": bool(event["in_play"]),
                    "extension_failure_3": bool(event["extension_failure_3"]),
                    "vwap_reclaim_3": bool(event["vwap_reclaim_3"]),
                    "midpoint_break_3": bool(event["midpoint_break_3"]),
                    "opposite_box_within_3": bool(event["opposite_box_within_3"]),
                    "reversal_followthrough": bool(event["reversal_followthrough"]),
                    "continuation": bool(event["continuation"]),
                    "extension_hit": bool(event["extension_hit"]),
                }
            )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = out_dir / "casebook_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    write_report(out_dir / "casebook_report.md", manifest, args)
    print(f"Wrote {len(manifest):,} casebook examples to {out_dir}")
    return 0


def read_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing events file: {path}")
    if path.suffix == ".csv":
        events = pd.read_csv(path, parse_dates=["timestamp_open", "timestamp_close"])
    else:
        events = pd.read_parquet(path)
    events["timestamp_close"] = pd.to_datetime(events["timestamp_close"])
    return events


def read_symbol_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing symbol data: {path}")
    data = pd.read_parquet(path).copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    return data.sort_values("timestamp").reset_index(drop=True)


def add_casebook_flags(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    out["casebook_split"] = chronological_split(out)
    out["extension_failure_3"] = out["failed_new_extreme_within_3"].fillna(False).astype(bool)
    out["vwap_reclaim_3"] = out["vwap_reclaim_within_3"].fillna(False).astype(bool)
    out["midpoint_break_3"] = out["prior_box_mid_break_within_3"].fillna(False).astype(bool)
    for col in ["reversal_followthrough", "continuation", "extension_hit", "in_play"]:
        out[col] = out[col].fillna(False).astype(bool)

    streak5 = out["streak_length"] >= 5
    ext_fail = out["extension_failure_3"]
    vwap = out["vwap_reclaim_3"]
    midpoint = out["midpoint_break_3"]
    out["broad_midpoint_watchlist"] = streak5 & ext_fail & midpoint
    out["hard_vwap_confirmation"] = streak5 & ext_fail & vwap
    out["highest_conviction_vwap_midpoint"] = streak5 & ext_fail & vwap & midpoint
    out["power_hour_broad_reclaim"] = streak5 & ext_fail & (vwap | midpoint) & (out["session_bucket"] == "power_hour")
    out["ignore_long_streak_only"] = streak5 & ~ext_fail & ~vwap & ~midpoint
    return out


def chronological_split(events: pd.DataFrame, research_fraction: float = 0.70) -> pd.Series:
    ordered_timestamps = events["timestamp_close"].dropna().sort_values().unique()
    if len(ordered_timestamps) == 0:
        return pd.Series("research", index=events.index)
    split_idx = max(1, min(len(ordered_timestamps) - 1, int(len(ordered_timestamps) * research_fraction)))
    cutoff = ordered_timestamps[split_idx]
    return pd.Series(
        ["research" if ts < cutoff else "validation" for ts in events["timestamp_close"]],
        index=events.index,
    )


def classify_event(event: pd.Series) -> str:
    if bool(event["vwap_reclaim_3"]) and bool(event["midpoint_break_3"]) and bool(event["reversal_followthrough"]):
        return "clean_transition"
    if bool(event["vwap_reclaim_3"]) and bool(event["reversal_followthrough"]):
        return "hard_confirmation"
    if bool(event["midpoint_break_3"]) and bool(event["reversal_followthrough"]):
        return "watchlist_followthrough"
    if bool(event["continuation"]):
        return "noisy_continuation"
    if bool(event["extension_failure_3"]):
        return "warning_only"
    return "ignore_state"


def window_bars(raw: pd.DataFrame, event_time: pd.Timestamp, lookback: int, lookahead: int) -> pd.DataFrame:
    start = event_time - pd.Timedelta(minutes=lookback)
    end = event_time + pd.Timedelta(minutes=lookahead)
    return raw[(raw["timestamp"] >= start) & (raw["timestamp"] <= end)].copy()


def render_svg(bars: pd.DataFrame, event: pd.Series, pattern_name: str, classification: str) -> str:
    width = 1120
    height = 660
    left = 70
    right = 30
    top = 82
    bottom = 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    title = (
        f"{event['symbol']} {event['timestamp_close']} | {PATTERN_LABELS[pattern_name]} | "
        f"{classification}"
    )
    if bars.empty:
        return svg_empty(width, height, title, "No raw bars available for this event window.")

    price_values = list(bars["high"]) + list(bars["low"])
    for col in ["box_top", "box_bottom", "box_mid", "vwap"]:
        val = event.get(col)
        if pd.notna(val):
            price_values.append(float(val))
    min_price = min(price_values)
    max_price = max(price_values)
    pad = max((max_price - min_price) * 0.08, max_price * 0.001)
    min_price -= pad
    max_price += pad

    def x_at(i: int) -> float:
        if len(bars) == 1:
            return left + plot_w / 2
        return left + (i / (len(bars) - 1)) * plot_w

    def y_at(price: float) -> float:
        return top + (max_price - price) / (max_price - min_price) * plot_h

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="{left}" y="32" font-family="Arial" font-size="18" font-weight="700" fill="#0f172a">{esc(title)}</text>',
        f'<text x="{left}" y="56" font-family="Arial" font-size="13" fill="#475569">{esc(metric_line(event))}</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#ffffff" stroke="#cbd5e1"/>',
    ]
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = top + frac * plot_h
        price = max_price - frac * (max_price - min_price)
        elements.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e2e8f0"/>')
        elements.append(f'<text x="8" y="{y + 4:.1f}" font-family="Arial" font-size="11" fill="#64748b">{price:.2f}</text>')

    candle_w = max(2.0, min(8.0, plot_w / max(len(bars), 1) * 0.58))
    for i, (_, bar) in enumerate(bars.iterrows()):
        x = x_at(i)
        open_y = y_at(float(bar["open"]))
        close_y = y_at(float(bar["close"]))
        high_y = y_at(float(bar["high"]))
        low_y = y_at(float(bar["low"]))
        up = float(bar["close"]) >= float(bar["open"])
        color = "#16a34a" if up else "#dc2626"
        body_y = min(open_y, close_y)
        body_h = max(abs(close_y - open_y), 1.0)
        elements.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{high_y:.1f}" y2="{low_y:.1f}" stroke="{color}" stroke-width="1"/>')
        elements.append(
            f'<rect x="{x - candle_w / 2:.1f}" y="{body_y:.1f}" width="{candle_w:.1f}" height="{body_h:.1f}" fill="{color}" opacity="0.85"/>'
        )

    if "vwap" in bars.columns and bars["vwap"].notna().any():
        points = []
        for i, (_, bar) in enumerate(bars.iterrows()):
            if pd.notna(bar.get("vwap")):
                points.append(f"{x_at(i):.1f},{y_at(float(bar['vwap'])):.1f}")
        if len(points) >= 2:
            elements.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="#2563eb" stroke-width="1.5" opacity="0.85"/>')

    for label, col, color in [
        ("box_top", "box_top", "#0f766e"),
        ("box_mid", "box_mid", "#f59e0b"),
        ("box_bottom", "box_bottom", "#0f766e"),
        ("event_vwap", "vwap", "#2563eb"),
    ]:
        val = event.get(col)
        if pd.notna(val):
            y = y_at(float(val))
            elements.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1" stroke-dasharray="5 4"/>')
            elements.append(f'<text x="{left + plot_w - 120}" y="{y - 4:.1f}" font-family="Arial" font-size="11" fill="{color}">{label}</text>')

    event_time = pd.Timestamp(event["timestamp_close"])
    event_idx = int((bars["timestamp"] - event_time).abs().reset_index(drop=True).idxmin())
    event_x = x_at(event_idx)
    elements.append(f'<line x1="{event_x:.1f}" x2="{event_x:.1f}" y1="{top}" y2="{top + plot_h}" stroke="#111827" stroke-width="2"/>')
    elements.append(f'<text x="{event_x + 5:.1f}" y="{top + 16}" font-family="Arial" font-size="11" fill="#111827">event close</text>')

    first_ts = bars["timestamp"].iloc[0]
    last_ts = bars["timestamp"].iloc[-1]
    elements.append(f'<text x="{left}" y="{height - 24}" font-family="Arial" font-size="12" fill="#475569">{esc(str(first_ts))}</text>')
    elements.append(f'<text x="{left + plot_w - 145}" y="{height - 24}" font-family="Arial" font-size="12" fill="#475569">{esc(str(last_ts))}</text>')
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def metric_line(event: pd.Series) -> str:
    direction = "green" if int(event["direction"]) == 1 else "red"
    return (
        f"direction={direction} | streak={int(event['streak_length'])} | "
        f"session={event['session_bucket']} | in_play={bool(event['in_play'])} | "
        f"opp3={bool(event['opposite_box_within_3'])} | followthrough={bool(event['reversal_followthrough'])} | "
        f"continuation={bool(event['continuation'])}"
    )


def svg_empty(width: int, height: int, title: str, message: str) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
            '<rect width="100%" height="100%" fill="#f8fafc"/>',
            f'<text x="40" y="40" font-family="Arial" font-size="18" font-weight="700">{esc(title)}</text>',
            f'<text x="40" y="80" font-family="Arial" font-size="14">{esc(message)}</text>',
            "</svg>",
        ]
    )


def write_report(path: Path, manifest: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Visual Casebook",
        "",
        "This is a visual audit artifact for confirmed-box context states. It is not a trading strategy.",
        "",
        f"- Split sampled: `{args.split}`",
        f"- Samples per pattern: `{args.samples_per_pattern}`",
        f"- Window: `{args.lookback_minutes}` minutes before to `{args.lookahead_minutes}` minutes after event close",
        "",
    ]
    if manifest.empty:
        lines.append("_No examples generated._")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    summary = (
        manifest.groupby(["pattern", "classification"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values(["pattern", "classification"])
    )
    lines.extend(["## Classification Summary", "", markdown_table(summary), ""])
    for pattern in PATTERN_ORDER:
        rows = manifest[manifest["pattern"] == pattern]
        if rows.empty:
            continue
        lines.extend([f"## {PATTERN_LABELS[pattern]}", ""])
        for _, row in rows.head(12).iterrows():
            lines.append(
                f"- [{row['symbol']} {row['timestamp_close']} {row['classification']}]({row['chart_path']})"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    rows = [list(df.columns)]
    rows.extend(df.astype(object).where(pd.notna(df), "").values.tolist())
    rows = [[str(cell) for cell in row] for row in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join([header, sep, *body])


def safe_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    return safe[:180]


def esc(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
