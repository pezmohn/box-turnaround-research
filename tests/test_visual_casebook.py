from __future__ import annotations

import pandas as pd

from scripts.build_visual_casebook import add_casebook_flags, classify_event, chronological_split


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "A",
                "timestamp_close": pd.Timestamp("2026-01-02 10:00"),
                "streak_length": 5,
                "session_bucket": "power_hour",
                "failed_new_extreme_within_3": True,
                "vwap_reclaim_within_3": True,
                "prior_box_mid_break_within_3": True,
                "reversal_followthrough": True,
                "continuation": False,
                "extension_hit": False,
                "in_play": False,
            },
            {
                "event_id": "B",
                "timestamp_close": pd.Timestamp("2026-01-02 10:05"),
                "streak_length": 5,
                "session_bucket": "midday",
                "failed_new_extreme_within_3": False,
                "vwap_reclaim_within_3": False,
                "prior_box_mid_break_within_3": False,
                "reversal_followthrough": False,
                "continuation": True,
                "extension_hit": True,
                "in_play": False,
            },
            {
                "event_id": "C",
                "timestamp_close": pd.Timestamp("2026-01-02 10:10"),
                "streak_length": 4,
                "session_bucket": "power_hour",
                "failed_new_extreme_within_3": True,
                "vwap_reclaim_within_3": False,
                "prior_box_mid_break_within_3": True,
                "reversal_followthrough": True,
                "continuation": False,
                "extension_hit": False,
                "in_play": True,
            },
        ]
    )


def test_casebook_flags_identify_watchlist_and_ignore_states() -> None:
    flagged = add_casebook_flags(_events())

    assert bool(flagged.loc[0, "highest_conviction_vwap_midpoint"])
    assert bool(flagged.loc[0, "power_hour_broad_reclaim"])
    assert bool(flagged.loc[1, "ignore_long_streak_only"])
    assert not bool(flagged.loc[2, "broad_midpoint_watchlist"])


def test_casebook_classification_prefers_clean_transition() -> None:
    event = add_casebook_flags(_events()).iloc[0]

    assert classify_event(event) == "clean_transition"


def test_casebook_chronological_split_has_validation_tail() -> None:
    split = chronological_split(_events(), research_fraction=0.67)

    assert split.iloc[0] == "research"
    assert split.iloc[-1] == "validation"
