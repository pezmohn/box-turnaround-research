"""Summary tables and diagnostic analysis for box-turnaround research."""

from __future__ import annotations

import pandas as pd


def streak_survival_table(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize continuation/opposite probabilities by streak length."""

    if events.empty:
        return pd.DataFrame()
    out = events.copy()
    out["streak_bucket"] = out["streak_length"].clip(upper=5).astype(int).astype(str)
    out.loc[out["streak_length"] >= 5, "streak_bucket"] = "5+"
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
    out = events.copy()
    out["streak_bucket"] = out["streak_length"].clip(upper=5).astype(int).astype(str)
    out.loc[out["streak_length"] >= 5, "streak_bucket"] = "5+"
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
