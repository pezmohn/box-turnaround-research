"""Summary tables and diagnostic analysis for box-turnaround research."""

from __future__ import annotations

import pandas as pd


def add_analysis_flags(events: pd.DataFrame) -> pd.DataFrame:
    """Add boolean buckets used for context interaction tables."""

    if events.empty:
        return events.copy()
    out = events.copy()
    out["streak_bucket"] = _streak_bucket(out)
    out["symbol_group"] = out["symbol"].map(_symbol_group)
    out["adx_fade"] = out["adx_drop_from_streak_max"] > 0
    out["adx_fade_3"] = out["adx_drop_from_streak_max"] >= 3.0
    out["extension_failure_3"] = out["failed_new_extreme_within_3"].fillna(False).astype(bool)
    out["extension_failure_6"] = out["failed_new_extreme_within_6"].fillna(False).astype(bool)
    out["vwap_reclaim_3"] = out["vwap_reclaim_within_3"].fillna(False).astype(bool)
    out["midpoint_break_3"] = out["prior_box_mid_break_within_3"].fillna(False).astype(bool)
    for col in ["reversal_followthrough", "vwap_hold_after_reclaim", "midpoint_hold"]:
        if col not in out.columns:
            out[col] = False
        out[col] = out[col].fillna(False).astype(bool)
    out["range_shrinking"] = (
        out.sort_values(["symbol", "timestamp_close"])
        .groupby(["symbol", "direction"])["box_range"]
        .diff()
        .lt(0)
        .reindex(out.index)
        .fillna(False)
    )
    return out


def streak_survival_table(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize continuation/opposite probabilities by streak length."""

    if events.empty:
        return pd.DataFrame()
    out = add_analysis_flags(events)
    grouped = out.groupby(["direction", "streak_bucket"], dropna=False)
    return grouped.agg(
        n=("event_id", "count"),
        p_opposite_next=("opposite_box", "mean"),
        p_opposite_within_3=("opposite_box_within_3", "mean"),
        p_turnaround_candidate=("turnaround_candidate", "mean"),
        p_extension_hit=("extension_hit", "mean"),
    ).reset_index()


def session_heatmaps(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return tables suitable for heatmap plotting by session bucket."""

    if events.empty:
        return {}
    out = add_analysis_flags(events)
    return {
        "p_opposite_next_by_streak_session": out.pivot_table(
            index="streak_bucket",
            columns="session_bucket",
            values="opposite_box",
            aggfunc="mean",
        ),
        "n_by_streak_session": out.pivot_table(
            index="streak_bucket",
            columns="session_bucket",
            values="event_id",
            aggfunc="count",
        ),
        "p_turnaround_by_streak_in_play": out.pivot_table(
            index="streak_bucket",
            columns="in_play",
            values="turnaround_candidate",
            aggfunc="mean",
        ),
    }


def context_interaction_tables(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build Phase 2 context tables for feature interactions."""

    if events.empty:
        return {}
    out = add_analysis_flags(events)
    tables = {
        "streak_x_adx_fade": _rate_table(out, ["streak_bucket", "adx_fade"]),
        "streak_x_adx_fade_3": _rate_table(out, ["streak_bucket", "adx_fade_3"]),
        "streak_x_extension_failure_3": _rate_table(out, ["streak_bucket", "extension_failure_3"]),
        "streak_x_vwap_reclaim_3": _rate_table(out, ["streak_bucket", "vwap_reclaim_3"]),
        "streak_x_midpoint_break_3": _rate_table(out, ["streak_bucket", "midpoint_break_3"]),
        "streak_x_range_shrinking": _rate_table(out, ["streak_bucket", "range_shrinking"]),
        "streak_x_in_play": _rate_table(out, ["streak_bucket", "in_play"]),
        "streak_x_session": _rate_table(out, ["streak_bucket", "session_bucket"]),
        "streak_x_symbol_group": _rate_table(out, ["streak_bucket", "symbol_group"]),
        "symbol_summary": _rate_table(out, ["symbol"]),
    }
    combos = out[
        (out["streak_length"] >= 2)
        & out["adx_fade"]
        & out["extension_failure_3"]
        & (out["vwap_reclaim_3"] | out["midpoint_break_3"])
    ].copy()
    tables["top_context_candidates"] = _rate_table(
        combos,
        ["direction", "streak_bucket", "session_bucket", "in_play"],
    ).sort_values(["p_turnaround_candidate", "n"], ascending=[False, False])
    return tables


def robustness_validation_tables(events: pd.DataFrame, research_fraction: float = 0.70) -> dict[str, pd.DataFrame]:
    """Build Phase 3 train/validation diagnostics for top context patterns."""

    if events.empty:
        return {}
    out = add_validation_split(add_analysis_flags(events), research_fraction=research_fraction)
    out = _add_phase3_patterns(out)
    pattern_names = [col for col in out.columns if col.startswith("pattern_")]
    base = out[out["streak_length"] >= 5].copy()
    tables = {
        "phase3_base_rates_by_split": _rate_table(base, ["split"]),
        "phase3_base_rates_by_split_symbol_group": _rate_table(base, ["split", "symbol_group"]),
        "phase3_pattern_split_summary": _pattern_rate_table(out, pattern_names, ["split"], base, ["split"]),
        "phase3_pattern_symbol_group_summary": _pattern_rate_table(
            out,
            pattern_names,
            ["split", "symbol_group"],
            base,
            ["split", "symbol_group"],
        ),
        "phase3_pattern_symbol_summary": _pattern_rate_table(
            out,
            pattern_names,
            ["split", "symbol"],
            base,
            ["split", "symbol"],
        ),
    }
    return tables


def add_validation_split(events: pd.DataFrame, research_fraction: float = 0.70) -> pd.DataFrame:
    """Assign a chronological research/validation split without shuffling."""

    if events.empty:
        return events.copy()
    if not 0 < research_fraction < 1:
        raise ValueError("research_fraction must be between 0 and 1")
    out = events.copy()
    ordered_timestamps = out["timestamp_close"].dropna().sort_values().unique()
    if len(ordered_timestamps) == 0:
        out["split"] = "research"
        return out
    split_idx = max(1, min(len(ordered_timestamps) - 1, int(len(ordered_timestamps) * research_fraction)))
    cutoff = ordered_timestamps[split_idx]
    out["split"] = "validation"
    out.loc[out["timestamp_close"] < cutoff, "split"] = "research"
    return out


def _rate_table(events: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    metric_cols = [
        "opposite_box",
        "opposite_box_within_3",
        "opposite_box_within_6",
        "opposite_box_within_12",
        "turnaround_candidate",
        "continuation",
        "extension_hit",
        "reversal_followthrough",
        "vwap_hold_after_reclaim",
        "midpoint_hold",
    ]
    if events.empty:
        return pd.DataFrame(
            columns=[
                *group_cols,
                "n",
                "p_opposite_next",
                "p_opposite_within_3",
                "p_opposite_within_6",
                "p_opposite_within_12",
                "p_turnaround_candidate",
                "p_continuation",
                "p_extension_hit",
                "p_reversal_followthrough",
                "p_vwap_hold_after_reclaim",
                "p_midpoint_hold",
            ]
        )
    events = events.copy()
    for col in metric_cols:
        if col not in events.columns:
            events[col] = False
    grouped = events.groupby(group_cols, dropna=False)
    return (
        grouped.agg(
            n=("event_id", "count"),
            p_opposite_next=("opposite_box", "mean"),
            p_opposite_within_3=("opposite_box_within_3", "mean"),
            p_opposite_within_6=("opposite_box_within_6", "mean"),
            p_opposite_within_12=("opposite_box_within_12", "mean"),
            p_turnaround_candidate=("turnaround_candidate", "mean"),
            p_continuation=("continuation", "mean"),
            p_extension_hit=("extension_hit", "mean"),
            p_reversal_followthrough=("reversal_followthrough", "mean"),
            p_vwap_hold_after_reclaim=("vwap_hold_after_reclaim", "mean"),
            p_midpoint_hold=("midpoint_hold", "mean"),
        )
        .reset_index()
        .sort_values(group_cols)
    )


def _add_phase3_patterns(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    streak5 = out["streak_length"] >= 5
    ext_fail = out["extension_failure_3"]
    vwap = out["vwap_reclaim_3"]
    midpoint = out["midpoint_break_3"]
    out["pattern_streak5_extfail_vwap"] = streak5 & ext_fail & vwap
    out["pattern_streak5_extfail_midpoint"] = streak5 & ext_fail & midpoint
    out["pattern_streak5_extfail_vwap_or_midpoint"] = streak5 & ext_fail & (vwap | midpoint)
    out["pattern_streak5_extfail_vwap_and_midpoint"] = streak5 & ext_fail & vwap & midpoint
    out["pattern_streak5_extfail_vwap_or_midpoint_power_hour"] = (
        out["pattern_streak5_extfail_vwap_or_midpoint"] & (out["session_bucket"] == "power_hour")
    )
    out["pattern_streak5_extfail_vwap_or_midpoint_morning_trend"] = (
        out["pattern_streak5_extfail_vwap_or_midpoint"] & (out["session_bucket"] == "morning_trend")
    )
    return out


def _pattern_rate_table(
    events: pd.DataFrame,
    pattern_names: list[str],
    group_cols: list[str],
    base_events: pd.DataFrame,
    base_group_cols: list[str],
) -> pd.DataFrame:
    rows = []
    for pattern_name in pattern_names:
        pattern_events = events[events[pattern_name]].copy()
        if pattern_events.empty:
            continue
        table = _rate_table(pattern_events, group_cols)
        table.insert(0, "pattern", pattern_name.removeprefix("pattern_"))
        rows.append(table)
    if not rows:
        return pd.DataFrame()
    pattern_table = pd.concat(rows, ignore_index=True)
    base_table = _rate_table(base_events, base_group_cols)
    if base_table.empty:
        return pattern_table
    base_cols = [
        *base_group_cols,
        "n",
        "p_opposite_within_3",
        "p_turnaround_candidate",
        "p_reversal_followthrough",
        "p_vwap_hold_after_reclaim",
        "p_midpoint_hold",
        "p_continuation",
    ]
    base_table = base_table[base_cols].rename(
        columns={
            "n": "base_n",
            "p_opposite_within_3": "base_p_opposite_within_3",
            "p_turnaround_candidate": "base_p_turnaround_candidate",
            "p_reversal_followthrough": "base_p_reversal_followthrough",
            "p_vwap_hold_after_reclaim": "base_p_vwap_hold_after_reclaim",
            "p_midpoint_hold": "base_p_midpoint_hold",
            "p_continuation": "base_p_continuation",
        }
    )
    merged = pattern_table.merge(base_table, left_on=base_group_cols, right_on=base_group_cols, how="left")
    for metric in [
        "p_opposite_within_3",
        "p_turnaround_candidate",
        "p_reversal_followthrough",
        "p_vwap_hold_after_reclaim",
        "p_midpoint_hold",
    ]:
        merged[f"lift_{metric.removeprefix('p_')}"] = merged[metric] - merged[f"base_{metric}"]
    return merged.sort_values(["pattern", *group_cols]).reset_index(drop=True)


def _streak_bucket(events: pd.DataFrame) -> pd.Series:
    bucket = events["streak_length"].clip(upper=5).astype(int).astype(str)
    bucket = bucket.where(events["streak_length"] < 5, "5+")
    return bucket


def _symbol_group(symbol: str) -> str:
    symbol = str(symbol).upper()
    if symbol in {"SPY", "QQQ"}:
        return "index_etf"
    if symbol in {"NVDA", "TSLA", "AMD"}:
        return "high_beta"
    return "single_stock"
