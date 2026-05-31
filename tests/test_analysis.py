from __future__ import annotations

import pandas as pd

from src.analysis import add_analysis_flags, context_interaction_tables


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "A",
                "symbol": "NVDA",
                "timestamp_close": pd.Timestamp("2026-01-02 10:00"),
                "direction": 1,
                "streak_length": 5,
                "session_bucket": "morning_trend",
                "in_play": True,
                "adx_drop_from_streak_max": 4.0,
                "failed_new_extreme_within_3": True,
                "failed_new_extreme_within_6": True,
                "vwap_reclaim_within_3": True,
                "prior_box_mid_break_within_3": False,
                "box_range": 2.0,
                "opposite_box": True,
                "opposite_box_within_3": True,
                "opposite_box_within_6": True,
                "opposite_box_within_12": True,
                "turnaround_candidate": True,
                "continuation": False,
                "extension_hit": False,
            },
            {
                "event_id": "B",
                "symbol": "SPY",
                "timestamp_close": pd.Timestamp("2026-01-02 10:05"),
                "direction": 1,
                "streak_length": 2,
                "session_bucket": "morning_trend",
                "in_play": False,
                "adx_drop_from_streak_max": 0.0,
                "failed_new_extreme_within_3": False,
                "failed_new_extreme_within_6": False,
                "vwap_reclaim_within_3": False,
                "prior_box_mid_break_within_3": False,
                "box_range": 1.0,
                "opposite_box": False,
                "opposite_box_within_3": False,
                "opposite_box_within_6": True,
                "opposite_box_within_12": True,
                "turnaround_candidate": False,
                "continuation": True,
                "extension_hit": True,
            },
        ]
    )


def test_analysis_flags_bucket_and_symbol_group() -> None:
    events = add_analysis_flags(_events())

    assert events.loc[0, "streak_bucket"] == "5+"
    assert events.loc[0, "symbol_group"] == "high_beta"
    assert events.loc[1, "symbol_group"] == "index_etf"


def test_context_interaction_tables_include_top_candidates() -> None:
    tables = context_interaction_tables(_events())

    assert "streak_x_adx_fade" in tables
    assert "top_context_candidates" in tables
    assert tables["top_context_candidates"].iloc[0]["n"] == 1
    assert tables["top_context_candidates"].iloc[0]["p_turnaround_candidate"] == 1.0
