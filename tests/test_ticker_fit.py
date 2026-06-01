from __future__ import annotations

import pandas as pd

from scripts.analyze_ticker_fit import (
    _cache_is_usable,
    _cache_path,
    analyze_fit,
    classify_current_context,
    prepare_fit_events,
)


def _row(
    idx: int,
    symbol: str,
    streak_length: int,
    direction: int = 1,
    prior_streak_length: int = 0,
    transition: bool = False,
    first_box: bool = False,
) -> dict:
    return {
        "event_id": f"{symbol}_{idx}",
        "symbol": symbol,
        "timestamp_close": pd.Timestamp("2026-01-02 09:30") + pd.Timedelta(minutes=idx * 5),
        "session_date": pd.Timestamp("2026-01-02").date(),
        "direction": direction,
        "streak_length": 1 if first_box else streak_length,
        "prior_streak_length": prior_streak_length,
        "session_bucket": "morning_trend",
        "in_play": False,
        "adx_drop_from_streak_max": 2.0,
        "failed_new_extreme_within_3": transition,
        "failed_new_extreme_within_6": transition,
        "vwap_reclaim_within_3": transition,
        "prior_box_mid_break_within_3": transition,
        "box_range": 1.0,
        "opposite_box": transition,
        "opposite_box_within_3": transition,
        "opposite_box_within_6": transition,
        "opposite_box_within_12": transition,
        "turnaround_candidate": transition,
        "continuation": not transition,
        "extension_hit": not transition,
        "reversal_followthrough": transition,
        "vwap_hold_after_reclaim": transition,
        "midpoint_hold": transition,
        "close_above_vwap": direction == 1,
        "vwap_distance_atr": 0.5 if direction == 1 else -0.5,
    }


def _profile_like_events(symbol: str, n: int = 120) -> pd.DataFrame:
    rows = []
    for idx in range(n):
        mod = idx % 10
        if mod == 0:
            rows.append(_row(idx, symbol, 1, first_box=True))
        elif mod in {1, 2}:
            rows.append(_row(idx, symbol, 4))
        elif mod in {3, 4, 5}:
            rows.append(_row(idx, symbol, 5, transition=mod == 3))
        else:
            rows.append(_row(idx, symbol, 2))
    return pd.DataFrame(rows)


def test_analyze_fit_rates_profile_like_ticker_as_fit() -> None:
    baseline = _profile_like_events("SPY", n=160)
    ticker = _profile_like_events("NOW", n=120)

    result = analyze_fit("NOW", ticker, baseline, min_events=50, exit_prep_streak=4)

    assert result["fit_rating"] == "fits model"
    assert result["score"] >= 4


def test_analyze_fit_rejects_too_small_sample() -> None:
    baseline = _profile_like_events("SPY", n=160)
    ticker = _profile_like_events("NOW", n=20)

    result = analyze_fit("NOW", ticker, baseline, min_events=50, exit_prep_streak=4)

    assert result["fit_rating"] == "bad fit"
    assert "sample too small" in result["reasons"][0]


def test_current_context_marks_fourth_box_as_exit_prep() -> None:
    events = prepare_fit_events(pd.DataFrame([_row(1, "NOW", 4)]))

    context = classify_current_context(events, exit_prep_streak=4)

    assert context["state"] == "exit-prep only"
    assert context["streak_length"] == 4


def test_current_context_marks_fresh_opposite_after_mature_streak() -> None:
    events = prepare_fit_events(pd.DataFrame([_row(1, "NOW", 1, direction=-1, prior_streak_length=5)]))

    context = classify_current_context(events, exit_prep_streak=4)

    assert context["state"] == "transition confirmed"
    assert context["prior_streak_length"] == 5


def test_cache_path_uses_plain_symbol_without_date_filter(tmp_path) -> None:
    assert _cache_path("DELL", tmp_path, start=None, end=None) == tmp_path / "DELL_box_events.parquet"


def test_cache_path_is_date_filter_specific(tmp_path) -> None:
    assert _cache_path("DELL", tmp_path, start="2025-01-01", end="2026-01-01") == (
        tmp_path / "DELL_2025-01-01_2026-01-01_box_events.parquet"
    )


def test_cache_is_not_used_when_source_is_newer(tmp_path) -> None:
    source = tmp_path / "DELL.parquet"
    cache = tmp_path / "DELL_box_events.parquet"
    source.write_text("source", encoding="utf-8")
    cache.write_text("cache", encoding="utf-8")
    old_cache_time = source.stat().st_mtime - 10
    cache.touch()
    import os

    os.utime(cache, (old_cache_time, old_cache_time))

    assert not _cache_is_usable(cache, source)
