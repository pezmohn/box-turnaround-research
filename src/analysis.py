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


def _rate_table(events: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
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
            ]
        )
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
        )
        .reset_index()
        .sort_values(group_cols)
    )


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
