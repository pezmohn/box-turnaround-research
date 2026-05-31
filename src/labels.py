"""Context labels for continuation, opposite boxes, and turnaround candidates."""

from __future__ import annotations

import pandas as pd


def add_context_labels(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Create research labels, not trade labels."""

    if events.empty:
        return events.copy()
    out = events.copy()
    min_streak = min(config.get("research", {}).get("min_streak_values", [2]))
    out["opposite_box"] = out["bars_until_opposite_box"] == 1
    out["continuation"] = out["extension_hit"] & ~out["opposite_box_within_3"]
    out["exhaustion"] = (
        (out["adx_drop_from_streak_max"] > 0)
        | out["failed_new_extreme_within_3"]
        | out.groupby(["symbol", "direction"])["box_range"].diff().lt(0).fillna(False)
    )
    out["turnaround_candidate"] = (
        (out["streak_length"] >= min_streak)
        & out["opposite_box_within_3"]
        & (out["vwap_reclaim_within_3"] | out["prior_box_mid_break_within_3"])
        & out["failed_new_extreme_within_3"]
    )
    out["failed_turnaround"] = (
        out["opposite_box_within_3"]
        & out["extension_hit"]
        & (out["bars_until_extension_hit"] <= 6)
    )
    out["reversal_followthrough"] = (
        out["opposite_box_within_3"]
        & out["failed_new_extreme_within_6"]
        & ~out["continuation"]
    )
    out["vwap_hold_after_reclaim"] = (
        out["vwap_reclaim_within_3"]
        & out["opposite_box_within_6"]
        & ~out["continuation"]
    )
    out["midpoint_hold"] = (
        out["prior_box_mid_break_within_3"]
        & out["opposite_box_within_6"]
        & ~out["continuation"]
    )
    return out