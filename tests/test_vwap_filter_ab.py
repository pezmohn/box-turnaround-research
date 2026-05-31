from __future__ import annotations

import pandas as pd

from scripts.run_vwap_filter_ab import build_summary


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "A",
                "symbol": "NVDA",
                "timestamp_close": pd.Timestamp("2026-01-02 10:00"),
                "streak_length": 5,
                "adx_drop_from_streak_max": 1.0,
                "failed_new_extreme_within_3": True,
                "failed_new_extreme_within_6": True,
                "vwap_reclaim_within_3": True,
                "prior_box_mid_break_within_3": True,
                "box_range": 1.0,
                "opposite_box_within_3": True,
                "opposite_box_within_6": True,
                "turnaround_candidate": True,
                "continuation": False,
                "extension_hit": False,
                "reversal_followthrough": True,
                "vwap_hold_after_reclaim": True,
                "midpoint_hold": True,
            },
            {
                "event_id": "B",
                "symbol": "SPY",
                "timestamp_close": pd.Timestamp("2026-01-03 10:00"),
                "streak_length": 5,
                "adx_drop_from_streak_max": 0.0,
                "failed_new_extreme_within_3": False,
                "failed_new_extreme_within_6": False,
                "vwap_reclaim_within_3": False,
                "prior_box_mid_break_within_3": False,
                "box_range": 1.2,
                "opposite_box_within_3": False,
                "opposite_box_within_6": False,
                "turnaround_candidate": False,
                "continuation": True,
                "extension_hit": True,
                "reversal_followthrough": False,
                "vwap_hold_after_reclaim": False,
                "midpoint_hold": False,
            },
        ]
    )


def test_build_summary_includes_on_off_context_scopes() -> None:
    summary = build_summary({"vwap_on": _events(), "vwap_off": _events()}, research_fraction=0.5)

    assert set(summary["variant"]) == {"vwap_on", "vwap_off"}
    assert "streak5_extfail_vwap_or_midpoint" in set(summary["scope"])
    row = summary[
        (summary["variant"] == "vwap_on")
        & (summary["split"] == "all")
        & (summary["scope"] == "streak5_extfail_vwap_and_midpoint")
    ].iloc[0]
    assert row["n"] == 1
    assert row["p_reversal_followthrough"] == 1.0
