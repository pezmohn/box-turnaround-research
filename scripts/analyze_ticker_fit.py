#!/usr/bin/env python3
"""Score one ticker against the validated box-context research profile."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import add_analysis_flags
from src.box_events import build_box_events
from src.labels import add_context_labels


DEFAULT_BASELINE_EVENTS = Path("data/processed/box_events_all.parquet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", help="Ticker to score, e.g. NOW or $NOW.")
    parser.add_argument("--data-dir", default="/home/backtest/stockdata/stock_data_1min")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--baseline-events", help="Optional existing baseline events parquet/csv.")
    parser.add_argument("--output-dir", default="outputs/ticker_fit")
    parser.add_argument("--start", help="Optional inclusive timestamp filter.")
    parser.add_argument("--end", help="Optional exclusive timestamp filter.")
    parser.add_argument("--min-events", type=int, default=500)
    parser.add_argument("--exit-prep-streak", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbol = normalize_symbol(args.symbol)
    config = load_config(Path(args.config))
    target_events, baseline_events, baseline_source = load_ticker_and_baseline_events(
        symbol=symbol,
        config=config,
        data_dir=Path(args.data_dir),
        baseline_events_path=Path(args.baseline_events) if args.baseline_events else None,
        start=args.start,
        end=args.end,
    )
    if target_events.empty:
        raise ValueError(f"No box events found for {symbol}")
    if baseline_events.empty:
        raise ValueError("No baseline events available for comparison")

    result = analyze_fit(
        symbol,
        target_events,
        baseline_events,
        min_events=args.min_events,
        exit_prep_streak=args.exit_prep_streak,
    )
    result["baseline_source"] = baseline_source
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{symbol}_fit_report.md"
    summary_path = output_dir / f"{symbol}_fit_summary.csv"
    write_report(result, report_path)
    pd.DataFrame([result["ticker_metrics"]]).to_csv(summary_path, index=False)
    print(f"{symbol}: {result['fit_rating']} | {result['current_context']['state']}")
    print(f"Report: {report_path}")
    return 0


def normalize_symbol(value: str) -> str:
    return value.strip().upper().lstrip("$")


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_ticker_and_baseline_events(
    symbol: str,
    config: dict,
    data_dir: Path,
    baseline_events_path: Path | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    baseline_path = baseline_events_path or DEFAULT_BASELINE_EVENTS
    if baseline_path.exists():
        all_events = _filter_events(_read_events_file(baseline_path), start=start, end=end)
        all_events = add_context_labels(all_events, config)
        all_events["symbol"] = all_events["symbol"].astype(str).str.upper()
        target = all_events[all_events["symbol"] == symbol].copy()
        if target.empty:
            target = build_symbol_events(symbol, data_dir, config, start=start, end=end)
        baseline = all_events[all_events["symbol"] != symbol].copy()
        return target, baseline, str(baseline_path)

    target = build_symbol_events(symbol, data_dir, config, start=start, end=end)
    baseline_symbols = [normalize_symbol(s) for s in config["data"]["default_symbols"] if normalize_symbol(s) != symbol]
    baseline_parts = [
        build_symbol_events(candidate, data_dir, config, start=start, end=end)
        for candidate in baseline_symbols
        if (data_dir / f"{candidate}.parquet").exists()
    ]
    baseline = pd.concat(baseline_parts, ignore_index=True) if baseline_parts else pd.DataFrame()
    return target, baseline, f"{data_dir} default_symbols"


def build_symbol_events(
    symbol: str,
    data_dir: Path,
    config: dict,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    path = data_dir / f"{symbol}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing 1m data for {symbol}: {path}")
    ohlcv = pd.read_parquet(path)
    if start or end:
        ts = pd.to_datetime(ohlcv["timestamp"] if "timestamp" in ohlcv.columns else ohlcv.index)
        mask = pd.Series(True, index=ohlcv.index)
        if start:
            mask &= ts >= pd.Timestamp(start)
        if end:
            mask &= ts < pd.Timestamp(end)
        ohlcv = ohlcv.loc[mask]
    return add_context_labels(build_box_events(ohlcv, config, symbol=symbol), config)


def analyze_fit(
    symbol: str,
    ticker_events: pd.DataFrame,
    baseline_events: pd.DataFrame,
    min_events: int = 500,
    exit_prep_streak: int = 4,
) -> dict:
    ticker_prepared = prepare_fit_events(ticker_events)
    baseline_prepared = prepare_fit_events(baseline_events)
    ticker_metrics = profile_metrics(ticker_prepared)
    baseline_metrics = profile_metrics(baseline_prepared)
    fit_rating, score, reasons = score_fit(ticker_metrics, baseline_metrics, min_events=min_events)
    current_context = classify_current_context(ticker_prepared, exit_prep_streak=exit_prep_streak)
    decision = decision_output(fit_rating, current_context["state"])
    return {
        "symbol": symbol,
        "fit_rating": fit_rating,
        "score": score,
        "reasons": reasons,
        "ticker_metrics": ticker_metrics,
        "baseline_metrics": baseline_metrics,
        "current_context": current_context,
        "decision": decision,
    }


def prepare_fit_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    out = add_analysis_flags(events)
    for col in [
        "opposite_box",
        "opposite_box_within_3",
        "continuation",
        "extension_failure_3",
        "vwap_reclaim_3",
        "midpoint_break_3",
        "reversal_followthrough",
    ]:
        if col not in out.columns:
            out[col] = False
        out[col] = out[col].fillna(False).astype(bool)
    out["is_first_box"] = out["streak_length"] == 1
    out["is_4th_box"] = out["streak_length"] == 4
    out["is_5plus"] = out["streak_length"] >= 5
    out["streak5_extfail_vwap_or_midpoint"] = (
        out["is_5plus"] & out["extension_failure_3"] & (out["vwap_reclaim_3"] | out["midpoint_break_3"])
    )
    out["streak5_extfail_vwap_and_midpoint"] = (
        out["is_5plus"] & out["extension_failure_3"] & out["vwap_reclaim_3"] & out["midpoint_break_3"]
    )
    return out


def profile_metrics(events: pd.DataFrame) -> dict[str, float | int]:
    if events.empty:
        return _empty_metrics()
    days = _session_days(events)
    symbol_days = _symbol_session_days(events)
    streak5 = events[events["is_5plus"]]
    return {
        "n_events": int(len(events)),
        "n_days": int(days),
        "n_symbol_days": int(symbol_days),
        "events_per_symbol_day": _safe_div(len(events), symbol_days),
        "rate_first_box": _mean(events["is_first_box"]),
        "rate_4th_box": _mean(events["is_4th_box"]),
        "rate_5plus": _mean(events["is_5plus"]),
        "rate_5plus_extension_failure_3": _conditional_mean(streak5, "extension_failure_3"),
        "rate_5plus_vwap_reclaim_3": _conditional_mean(streak5, "vwap_reclaim_3"),
        "rate_5plus_midpoint_break_3": _conditional_mean(streak5, "midpoint_break_3"),
        "rate_5plus_transition_pattern": _conditional_mean(streak5, "streak5_extfail_vwap_or_midpoint"),
        "rate_5plus_hard_transition_pattern": _conditional_mean(streak5, "streak5_extfail_vwap_and_midpoint"),
        "p_5plus_opposite_within_3": _conditional_mean(streak5, "opposite_box_within_3"),
        "p_5plus_continuation": _conditional_mean(streak5, "continuation"),
        "p_5plus_reversal_followthrough": _conditional_mean(streak5, "reversal_followthrough"),
    }


def score_fit(
    ticker: dict[str, float | int],
    baseline: dict[str, float | int],
    min_events: int,
) -> tuple[str, int, list[str]]:
    reasons: list[str] = []
    if int(ticker["n_events"]) < min_events:
        return "bad fit", 0, [f"sample too small: {ticker['n_events']} events < {min_events}"]

    score = 0
    score += _score_ratio(
        "event density",
        ticker["events_per_symbol_day"],
        baseline["events_per_symbol_day"],
        0.35,
        2.75,
        reasons,
    )
    score += _score_ratio("5+ streak frequency", ticker["rate_5plus"], baseline["rate_5plus"], 0.50, 1.80, reasons)
    score += _score_ratio("4th-box frequency", ticker["rate_4th_box"], baseline["rate_4th_box"], 0.50, 2.00, reasons)

    first_box_limit = float(baseline["rate_first_box"]) * 1.35 + 0.05
    if float(ticker["rate_first_box"]) <= first_box_limit:
        score += 1
    else:
        reasons.append("too choppy: first-box alternation rate is high versus baseline")

    transition_floor = float(baseline["rate_5plus_transition_pattern"]) * 0.50
    if float(ticker["rate_5plus_transition_pattern"]) >= transition_floor:
        score += 1
    else:
        reasons.append("weak match to validated 5+ extension-failure transition pattern")

    if score >= 4:
        return "fits model", score, reasons or ["profile is close to the baseline box-research universe"]
    if score >= 2:
        return "partial fit", score, reasons
    return "bad fit", score, reasons


def classify_current_context(events: pd.DataFrame, exit_prep_streak: int = 4) -> dict:
    if events.empty:
        return {"state": "no context", "reason": "no confirmed boxes"}
    latest = events.sort_values("timestamp_close").iloc[-1]
    streak = int(latest["streak_length"])
    direction = "green" if int(latest["direction"]) == 1 else "red"
    prior_len = int(latest.get("prior_streak_length", 0) or 0)
    if streak == 1 and prior_len >= exit_prep_streak:
        state = "transition confirmed"
        reason = f"fresh opposite {direction} box after prior {prior_len}-box streak"
    elif streak == exit_prep_streak:
        state = "exit-prep only"
        reason = f"{exit_prep_streak}th same-color box is visible; manage risk, not a reversal claim"
    elif streak > exit_prep_streak:
        state = "mature streak watch"
        reason = "mature streak; wait for extension failure plus VWAP/midpoint confirmation"
    elif streak >= 2:
        state = "trend continuation building"
        reason = "same-color streak is building, but not mature yet"
    else:
        state = "neutral"
        reason = "single confirmed box without mature prior streak context"
    return {
        "state": state,
        "reason": reason,
        "timestamp_close": str(latest["timestamp_close"]),
        "direction": direction,
        "streak_length": streak,
        "prior_streak_length": prior_len,
        "session_bucket": str(latest.get("session_bucket", "")),
        "close_above_vwap": bool(latest.get("close_above_vwap", False)),
        "vwap_distance_atr": _round_or_none(latest.get("vwap_distance_atr")),
    }


def decision_output(fit_rating: str, state: str) -> str:
    if fit_rating == "bad fit":
        return "ignore, too noisy or off-profile"
    if state == "transition confirmed":
        return "transition watch"
    if state == "exit-prep only":
        return "exit-prep only"
    if state == "mature streak watch":
        return "mature streak watch"
    if state == "trend continuation building":
        return "trend continuation still in control"
    return "neutral / insufficient context"


def write_report(result: dict, path: Path) -> None:
    ticker = result["ticker_metrics"]
    baseline = result["baseline_metrics"]
    context = result["current_context"]
    lines = [
        f"# {result['symbol']} Box-Research Fit Check",
        "",
        "## Verdict",
        "",
        f"- Fit: `{result['fit_rating']}`",
        f"- Score: `{result['score']}/5`",
        f"- Current state: `{context['state']}`",
        f"- Decision output: `{result['decision']}`",
        f"- Baseline source: `{result.get('baseline_source', 'unknown')}`",
        "",
        "## Why",
        "",
        *[f"- {reason}" for reason in result["reasons"]],
        "",
        "## Structural Fit",
        "",
        _metric_table(ticker, baseline),
        "",
        "## Current Context",
        "",
        _dict_table(context),
        "",
        "## Caveats",
        "",
        "- This is a ticker fit check against the box-research profile, not a buy/sell signal.",
        "- Structural rates use historical forward outcomes; current context only uses confirmed-box state available at the latest box close.",
        "- A 4th-box warning means exit preparation, not a reversal prediction.",
        "- Raw event datasets and generated reports are local artifacts.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metric_table(ticker: dict, baseline: dict) -> str:
    rows = [
        ("events", ticker["n_events"], baseline["n_events"]),
        ("days", ticker["n_days"], baseline["n_days"]),
        ("symbol_days", ticker["n_symbol_days"], baseline["n_symbol_days"]),
        ("events_per_symbol_day", ticker["events_per_symbol_day"], baseline["events_per_symbol_day"]),
        ("rate_first_box", ticker["rate_first_box"], baseline["rate_first_box"]),
        ("rate_4th_box", ticker["rate_4th_box"], baseline["rate_4th_box"]),
        ("rate_5plus", ticker["rate_5plus"], baseline["rate_5plus"]),
        ("rate_5plus_transition_pattern", ticker["rate_5plus_transition_pattern"], baseline["rate_5plus_transition_pattern"]),
        ("p_5plus_opposite_within_3", ticker["p_5plus_opposite_within_3"], baseline["p_5plus_opposite_within_3"]),
        ("p_5plus_continuation", ticker["p_5plus_continuation"], baseline["p_5plus_continuation"]),
    ]
    lines = ["| metric | ticker | baseline |", "| --- | --- | --- |"]
    lines.extend(f"| {name} | {_format(value)} | {_format(base)} |" for name, value, base in rows)
    return "\n".join(lines)


def _dict_table(values: dict) -> str:
    lines = ["| field | value |", "| --- | --- |"]
    lines.extend(f"| {key} | {_format(value)} |" for key, value in values.items())
    return "\n".join(lines)


def _read_events_file(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path, parse_dates=["timestamp_open", "timestamp_close"])
    return pd.read_parquet(path)


def _filter_events(events: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if events.empty or (not start and not end):
        return events
    out = events.copy()
    ts = pd.to_datetime(out["timestamp_close"])
    if start:
        out = out[ts >= pd.Timestamp(start)]
        ts = pd.to_datetime(out["timestamp_close"])
    if end:
        out = out[ts < pd.Timestamp(end)]
    return out


def _session_days(events: pd.DataFrame) -> int:
    if "session_date" in events.columns:
        return max(1, int(events["session_date"].nunique()))
    return max(1, int(pd.to_datetime(events["timestamp_close"]).dt.date.nunique()))


def _symbol_session_days(events: pd.DataFrame) -> int:
    if events.empty:
        return 0
    out = events.copy()
    if "session_date" not in out.columns:
        out["session_date"] = pd.to_datetime(out["timestamp_close"]).dt.date
    return max(1, int(out[["symbol", "session_date"]].drop_duplicates().shape[0]))


def _score_ratio(
    label: str,
    value: float | int,
    baseline: float | int,
    low: float,
    high: float,
    reasons: list[str],
) -> int:
    ratio = _safe_div(float(value), float(baseline))
    if low <= ratio <= high:
        return 1
    reasons.append(f"{label} off baseline: ratio {ratio:.2f} outside {low:.2f}-{high:.2f}")
    return 0


def _conditional_mean(events: pd.DataFrame, col: str) -> float:
    if events.empty or col not in events.columns:
        return 0.0
    return _mean(events[col])


def _mean(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.fillna(False).astype(float).mean())


def _safe_div(numerator: float | int, denominator: float | int) -> float:
    if denominator == 0 or pd.isna(denominator):
        return 0.0
    return float(numerator) / float(denominator)


def _round_or_none(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def _empty_metrics() -> dict[str, float | int]:
    return {
        "n_events": 0,
        "n_days": 0,
        "n_symbol_days": 0,
        "events_per_symbol_day": 0.0,
        "rate_first_box": 0.0,
        "rate_4th_box": 0.0,
        "rate_5plus": 0.0,
        "rate_5plus_extension_failure_3": 0.0,
        "rate_5plus_vwap_reclaim_3": 0.0,
        "rate_5plus_midpoint_break_3": 0.0,
        "rate_5plus_transition_pattern": 0.0,
        "rate_5plus_hard_transition_pattern": 0.0,
        "p_5plus_opposite_within_3": 0.0,
        "p_5plus_continuation": 0.0,
        "p_5plus_reversal_followthrough": 0.0,
    }


def _format(value: object) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.4f}"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
