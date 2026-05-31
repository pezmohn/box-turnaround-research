"""Feature engineering for box-streak and turnaround context research."""

from __future__ import annotations

import pandas as pd


def add_streak_features(events: pd.DataFrame) -> pd.DataFrame:
    """Add same-direction streak length and prior-streak context.

    ``build_box_events`` already emits these columns; this function recomputes
    them for imported or externally edited event datasets.
    """

    if events.empty:
        return events.copy()
    out = events.sort_values(["symbol", "timestamp_close"]).copy()
    for symbol, idxs in out.groupby("symbol").groups.items():
        current_dir = 0
        current_len = 0
        prior_dir = 0
        prior_len = 0
        for idx in idxs:
            direction = int(out.at[idx, "direction"])
            if direction == current_dir:
                current_len += 1
            else:
                if current_dir != 0:
                    prior_dir = current_dir
                    prior_len = current_len
                current_dir = direction
                current_len = 1
            out.at[idx, "streak_direction"] = current_dir
            out.at[idx, "streak_length"] = current_len
            out.at[idx, "prior_streak_direction"] = prior_dir
            out.at[idx, "prior_streak_length"] = prior_len
    return out


def add_exhaustion_features(events: pd.DataFrame) -> pd.DataFrame:
    """Add simple exhaustion feature flags from existing event columns."""

    out = events.copy()
    out["adx_fade"] = out["adx_drop_from_streak_max"] > 0
    out["range_shrinking"] = out.groupby(["symbol", "direction"])["box_range"].diff() < 0
    out["extension_failure_3"] = out["failed_new_extreme_within_3"]
    out["extension_failure_6"] = out["failed_new_extreme_within_6"]
    return out
