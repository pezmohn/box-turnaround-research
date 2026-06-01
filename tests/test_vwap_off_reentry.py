from __future__ import annotations

import pandas as pd

from scripts.run_vwap_off_reentry import add_reentry_flags, build_reentry_summary


def _events() -> pd.DataFrame:
    base = {
        "timeframe": "5m",
        "session_date": "2026-01-01",
        "session_bucket": "morning_trend",
        "in_play": False,
        "gap_pct": 0.0,
        "premarket_volume": 0.0,
        "premarket_volume_relative": 0.0,
        "premarket_dollar_volume": 0.0,
        "box_top": 10.0,
        "box_bottom": 9.0,
        "box_range": 1.0,
        "box_mid": 9.5,
        "box_fib_236": 9.236,
        "box_extension_target": 11.0,
        "box_range_atr_ratio": 1.0,
        "high": 10.0,
        "low": 9.0,
        "volume": 100.0,
        "volume_sma": 100.0,
        "volume_relative": 1.0,
        "atr": 1.0,
        "adx": 25.0,
        "adx_change_1": 0.0,
        "adx_change_3": 0.0,
        "adx_streak_max": 25.0,
        "adx_drop_from_streak_max": 0.0,
        "vwap": 10.0,
        "vwap_distance": 0.5,
        "vwap_distance_atr": 0.5,
        "close_above_vwap": True,
        "bars_until_extension_hit": pd.NA,
        "bars_until_opposite_box": pd.NA,
        "opposite_box_within_3": False,
        "opposite_box_within_6": False,
        "opposite_box_within_12": False,
        "vwap_reclaim_within_3": False,
        "vwap_reclaim_within_6": False,
        "prior_box_mid_break_within_3": False,
        "prior_box_mid_break_within_6": False,
        "forward_return_1_box": 0.0,
        "forward_return_3_boxes": 0.0,
        "forward_return_6_boxes": 0.0,
        "forward_return_12_boxes": 0.0,
        "mfe_3_boxes": 0.0,
        "mae_3_boxes": 0.0,
        "mfe_6_boxes": 0.0,
        "mae_6_boxes": 0.0,
        "mfe_12_boxes": 0.0,
        "mae_12_boxes": 0.0,
        "turnaround_candidate": False,
        "continuation": False,
        "reversal_followthrough": False,
        "vwap_hold_after_reclaim": False,
        "midpoint_hold": False,
    }
    rows = []
    directions = [1, 1, 1, -1, -1, 1]
    streak_lengths = [1, 2, 3, 1, 2, 1]
    prior_lengths = [0, 0, 0, 3, 3, 2]
    for i, (direction, streak_len, prior_len) in enumerate(zip(directions, streak_lengths, prior_lengths)):
        row = dict(base)
        row.update(
            {
                "event_id": f"EV{i}",
                "symbol": "TEST",
                "timestamp_open": pd.Timestamp("2026-01-01 10:00") + pd.Timedelta(minutes=i * 5),
                "timestamp_close": pd.Timestamp("2026-01-01 10:05") + pd.Timedelta(minutes=i * 5),
                "direction": direction,
                "streak_direction": direction,
                "streak_length": streak_len,
                "prior_streak_direction": -direction if prior_len else 0,
                "prior_streak_length": prior_len,
                "close": 10.5 if direction == 1 else 9.5,
                "close_above_vwap": direction == 1,
                "extension_hit": i == 5,
                "failed_new_extreme_within_3": i == 4,
                "failed_new_extreme_within_6": i == 4,
                "forward_return_3_boxes": 0.01 if i == 5 else 0.0,
                "forward_return_6_boxes": 0.02 if i == 5 else 0.0,
                "mfe_6_boxes": 0.03 if i == 5 else 0.0,
                "mae_6_boxes": -0.004 if i == 5 else 0.0,
                "continuation": i == 5,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def test_add_reentry_flags_identifies_failed_countertrend_reentry() -> None:
    tagged = add_reentry_flags(_events())
    reentry = tagged[tagged["event_id"] == "EV5"].iloc[0]

    assert bool(reentry["main_structure_reentry_3"])
    assert not bool(reentry["main_structure_reentry_5"])
    assert bool(reentry["main_structure_reentry_3_vwap_side"])
    assert reentry["pre_countertrend_len"] == 3
    assert bool(reentry["countertrend_extension_failure_3"])


def test_build_reentry_summary_reports_validation_scope() -> None:
    tagged = add_reentry_flags(_events())
    summary = build_reentry_summary(tagged, research_fraction=0.5)

    row = summary[(summary["split"] == "all") & (summary["scope"] == "main_structure_reentry_3")].iloc[0]
    assert row["n"] == 1
    assert row["p_extension_hit"] == 1.0
    assert row["mean_forward_return_6_boxes"] == 0.02
