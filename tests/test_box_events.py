from __future__ import annotations

import pandas as pd

from src.box_events import REQUIRED_COLUMNS, build_box_events


def _config() -> dict:
    return {
        "indicator": {
            "consecutive_confirms": 1,
            "use_close_breakout": True,
            "use_alternating_filter": False,
            "use_adx_filter": False,
            "use_session_filter": True,
            "trade_session": "09:30-16:00",
            "use_vwap_filter": False,
            "use_volume_filter": False,
            "use_range_filter": False,
            "extension_target": 1.618,
        },
        "research": {
            "session_buckets": {
                "open_impulse": ["09:30", "10:00"],
                "morning_trend": ["10:00", "11:30"],
                "midday": ["11:30", "13:30"],
                "afternoon": ["13:30", "15:00"],
                "power_hour": ["15:00", "16:00"],
            },
            "in_play": {
                "premarket_window": ["04:00", "09:30"],
                "gap_threshold_pct": 3.0,
                "premarket_volume_relative_threshold": 2.0,
                "premarket_dollar_volume_min": 5_000_000,
            },
        },
    }


def _minute_data_from_5m(rows: list[tuple[str, float, float, float, float, float]]) -> pd.DataFrame:
    minutes = []
    for ts, open_, high, low, close, volume in rows:
        start = pd.Timestamp(ts)
        for minute in range(5):
            frac = minute / 4
            price = open_ + (close - open_) * frac
            minutes.append(
                {
                    "timestamp": start + pd.Timedelta(minutes=minute),
                    "open": price,
                    "high": max(price, high if minute == 2 else price),
                    "low": min(price, low if minute == 2 else price),
                    "close": price,
                    "volume": volume / 5,
                }
            )
    return pd.DataFrame(minutes)


def test_confirmed_close_breakout_uses_closed_5m_bar() -> None:
    data = _minute_data_from_5m(
        [
            ("2026-01-02 09:30", 100, 101, 99, 100, 1000),
            ("2026-01-02 09:35", 100, 101, 99, 100, 1000),
            ("2026-01-02 09:40", 100, 103, 100, 102, 1000),
        ]
    )

    events = build_box_events(data, _config(), symbol="TEST")

    assert len(events) == 1
    assert events.iloc[0]["direction"] == 1
    assert events.iloc[0]["timestamp_open"] == pd.Timestamp("2026-01-02 09:40")
    assert events.iloc[0]["timestamp_close"] == pd.Timestamp("2026-01-02 09:45")
    assert events.iloc[0]["box_top"] == 103
    assert events.iloc[0]["box_bottom"] == 99


def test_no_event_without_completed_breakout_bar() -> None:
    data = _minute_data_from_5m(
        [
            ("2026-01-02 09:30", 100, 101, 99, 100, 1000),
            ("2026-01-02 09:35", 100, 101, 99, 100, 1000),
        ]
    )

    events = build_box_events(data, _config(), symbol="TEST")

    assert events.empty


def test_event_schema_columns_are_present() -> None:
    data = _minute_data_from_5m(
        [
            ("2026-01-02 09:30", 100, 101, 99, 100, 1000),
            ("2026-01-02 09:35", 100, 101, 99, 100, 1000),
            ("2026-01-02 09:40", 100, 103, 100, 102, 1000),
        ]
    )

    events = build_box_events(data, _config(), symbol="TEST")

    assert list(events.columns) == list(REQUIRED_COLUMNS)
    assert {"in_play", "gap_pct", "premarket_volume", "premarket_volume_relative"}.issubset(events.columns)
