"""Confirmed 5-minute box event extraction.

The extractor reproduces the confirmed historical Pine logic from
``pine/confirmed_box_logic.pine``. Realtime Ghost Boxes are intentionally
excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Iterable

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
    "event_id",
    "symbol",
    "timeframe",
    "timestamp_open",
    "timestamp_close",
    "session_date",
    "session_bucket",
    "in_play",
    "gap_pct",
    "premarket_volume",
    "premarket_volume_relative",
    "premarket_dollar_volume",
    "direction",
    "streak_direction",
    "streak_length",
    "prior_streak_direction",
    "prior_streak_length",
    "box_top",
    "box_bottom",
    "box_range",
    "box_mid",
    "box_fib_236",
    "box_extension_target",
    "box_range_atr_ratio",
    "close",
    "high",
    "low",
    "volume",
    "volume_sma",
    "volume_relative",
    "atr",
    "adx",
    "adx_change_1",
    "adx_change_3",
    "adx_streak_max",
    "adx_drop_from_streak_max",
    "vwap",
    "vwap_distance",
    "vwap_distance_atr",
    "close_above_vwap",
    "extension_hit",
    "bars_until_extension_hit",
    "bars_until_opposite_box",
    "opposite_box_within_3",
    "opposite_box_within_6",
    "opposite_box_within_12",
    "vwap_reclaim_within_3",
    "vwap_reclaim_within_6",
    "prior_box_mid_break_within_3",
    "prior_box_mid_break_within_6",
    "failed_new_extreme_within_3",
    "failed_new_extreme_within_6",
    "forward_return_1_box",
    "forward_return_3_boxes",
    "forward_return_6_boxes",
    "forward_return_12_boxes",
    "mfe_3_boxes",
    "mae_3_boxes",
    "mfe_6_boxes",
    "mae_6_boxes",
    "mfe_12_boxes",
    "mae_12_boxes",
)


@dataclass(frozen=True)
class SessionWindow:
    start: time
    end: time

    def contains_open_left(self, value: time) -> bool:
        return self.start <= value < self.end


def build_box_events(
    ohlcv: pd.DataFrame,
    config: dict,
    symbol: str | None = None,
) -> pd.DataFrame:
    """Build one event row per confirmed 5-minute box.

    Features use data available at the event bar close. Columns that explicitly
    look forward are outcome labels for research and must not be used as input
    features in later strategy work.
    """

    bars_1m = _normalize_ohlcv(ohlcv)
    bars_5m = _resample_5m(bars_1m)
    bars_5m = _add_indicators(bars_5m)
    bars_5m = _add_session_fields(bars_5m, config)

    day_context = _build_day_context(bars_1m, config)
    rows: list[dict] = []
    indicator_cfg = config.get("indicator", {})

    last_signal = 0
    current_streak_direction = 0
    current_streak_length = 0
    prior_streak_direction = 0
    prior_streak_length = 0

    for i in range(2, len(bars_5m)):
        row = bars_5m.iloc[i]
        prev = bars_5m.iloc[i - 1]
        prev2 = bars_5m.iloc[i - 2]

        direction = _confirmed_direction(row, prev, prev2, indicator_cfg, last_signal)
        if direction == 0:
            continue

        if direction == current_streak_direction:
            current_streak_length += 1
        else:
            if current_streak_direction != 0:
                prior_streak_direction = current_streak_direction
                prior_streak_length = current_streak_length
            current_streak_direction = direction
            current_streak_length = 1

        last_signal = direction
        box_top = max(float(row.high), float(prev.high))
        box_bottom = min(float(row.low), float(prev.low))
        box_range = box_top - box_bottom
        box_mid = (box_top + box_bottom) / 2.0
        extension_value = float(indicator_cfg.get("extension_target", 1.618))
        extension = (
            box_bottom + box_range * extension_value
            if direction == 1
            else box_top - box_range * extension_value
        )
        fib_236 = (
            box_bottom + box_range * 0.236
            if direction == 1
            else box_top - box_range * 0.236
        )

        day = day_context.get(row.session_date, {})
        rows.append(
            {
                "event_id": "",
                "symbol": symbol or _infer_symbol(ohlcv),
                "timeframe": "5m",
                "bar_index": i,
                "timestamp_open": row.timestamp_open,
                "timestamp_close": row.timestamp_close,
                "session_date": row.session_date,
                "session_bucket": row.session_bucket,
                "in_play": bool(day.get("in_play", False)),
                "gap_pct": day.get("gap_pct", np.nan),
                "premarket_volume": day.get("premarket_volume", np.nan),
                "premarket_volume_relative": day.get("premarket_volume_relative", np.nan),
                "premarket_dollar_volume": day.get("premarket_dollar_volume", np.nan),
                "direction": direction,
                "streak_direction": current_streak_direction,
                "streak_length": current_streak_length,
                "prior_streak_direction": prior_streak_direction,
                "prior_streak_length": prior_streak_length,
                "box_top": box_top,
                "box_bottom": box_bottom,
                "box_range": box_range,
                "box_mid": box_mid,
                "box_fib_236": fib_236,
                "box_extension_target": extension,
                "box_range_atr_ratio": _safe_div(box_range, row.atr),
                "close": float(row.close),
                "high": float(row.high),
                "low": float(row.low),
                "volume": float(row.volume),
                "volume_sma": float(row.volume_sma) if pd.notna(row.volume_sma) else np.nan,
                "volume_relative": _safe_div(row.volume, row.volume_sma),
                "atr": float(row.atr) if pd.notna(row.atr) else np.nan,
                "adx": float(row.adx) if pd.notna(row.adx) else np.nan,
                "adx_change_1": float(row.adx_change_1) if pd.notna(row.adx_change_1) else np.nan,
                "adx_change_3": float(row.adx_change_3) if pd.notna(row.adx_change_3) else np.nan,
                "adx_streak_max": np.nan,
                "adx_drop_from_streak_max": np.nan,
                "vwap": float(row.vwap) if pd.notna(row.vwap) else np.nan,
                "vwap_distance": float(row.close - row.vwap) if pd.notna(row.vwap) else np.nan,
                "vwap_distance_atr": _safe_div(row.close - row.vwap, row.atr),
                "close_above_vwap": bool(row.close > row.vwap) if pd.notna(row.vwap) else False,
                "extension_hit": False,
                "bars_until_extension_hit": np.nan,
                "bars_until_opposite_box": np.nan,
                "opposite_box_within_3": False,
                "opposite_box_within_6": False,
                "opposite_box_within_12": False,
                "vwap_reclaim_within_3": False,
                "vwap_reclaim_within_6": False,
                "prior_box_mid_break_within_3": False,
                "prior_box_mid_break_within_6": False,
                "failed_new_extreme_within_3": False,
                "failed_new_extreme_within_6": False,
                "forward_return_1_box": np.nan,
                "forward_return_3_boxes": np.nan,
                "forward_return_6_boxes": np.nan,
                "forward_return_12_boxes": np.nan,
                "mfe_3_boxes": np.nan,
                "mae_3_boxes": np.nan,
                "mfe_6_boxes": np.nan,
                "mae_6_boxes": np.nan,
                "mfe_12_boxes": np.nan,
                "mae_12_boxes": np.nan,
            }
        )

    events = pd.DataFrame(rows)
    if events.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    events = _add_streak_adx(events)
    events = _add_forward_outcomes(events, bars_5m)
    sym = events["symbol"].astype(str).str.upper()
    events["symbol"] = sym
    events["event_id"] = (
        sym
        + "_"
        + events["timestamp_close"].dt.strftime("%Y%m%d%H%M")
        + "_"
        + events["direction"].map({1: "G", -1: "R"})
    )
    return events.loc[:, list(REQUIRED_COLUMNS)]


def _normalize_ohlcv(ohlcv: pd.DataFrame) -> pd.DataFrame:
    df = ohlcv.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
    elif not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("OHLCV data needs a DatetimeIndex or a timestamp column")

    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    df = df.sort_index()
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV data missing columns: {sorted(missing)}")
    return df[list(required)].astype(float)


def _resample_5m(bars_1m: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    bars = bars_1m.resample("5min", label="left", closed="left").agg(agg).dropna()
    bars["timestamp_open"] = bars.index
    bars["timestamp_close"] = bars.index + pd.Timedelta(minutes=5)
    return bars.reset_index(drop=True)


def _add_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    out = bars.copy()
    out["volume_sma"] = out["volume"].rolling(20, min_periods=1).mean()

    prev_close = out["close"].shift(1)
    tr = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = _rma(tr, 14)

    up_move = out["high"].diff()
    down_move = -out["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0))
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0))
    plus_di = 100 * _safe_series_div(_rma(plus_dm, 14), out["atr"])
    minus_di = 100 * _safe_series_div(_rma(minus_dm, 14), out["atr"])
    dx = 100 * _safe_series_div((plus_di - minus_di).abs(), plus_di + minus_di)
    out["adx"] = _rma(dx, 14)
    out["adx_change_1"] = out["adx"].diff(1)
    out["adx_change_3"] = out["adx"].diff(3)

    session_date = out["timestamp_close"].dt.date
    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    pv = typical * out["volume"]
    out["vwap"] = pv.groupby(session_date).cumsum() / out["volume"].groupby(session_date).cumsum()
    return out


def _add_session_fields(bars: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = bars.copy()
    out["session_date"] = out["timestamp_close"].dt.date
    buckets = [
        (name, SessionWindow(_parse_time(start), _parse_time(end)))
        for name, (start, end) in config.get("research", {}).get("session_buckets", {}).items()
    ]
    out["session_bucket"] = [
        _bucket_for_time(ts.time(), buckets) for ts in out["timestamp_open"]
    ]
    session = _parse_window(config.get("indicator", {}).get("trade_session", "09:30-16:00"))
    out["session_pass"] = [session.contains_open_left(ts.time()) for ts in out["timestamp_open"]]
    return out


def _confirmed_direction(
    row: pd.Series,
    prev: pd.Series,
    prev2: pd.Series,
    indicator_cfg: dict,
    last_signal: int,
) -> int:
    use_close = bool(indicator_cfg.get("use_close_breakout", True))
    consecutive = int(indicator_cfg.get("consecutive_confirms", 1))
    break_high_1 = row.close > prev.high if use_close else row.high > prev.high
    break_low_1 = row.close < prev.low if use_close else row.low < prev.low
    break_high_2 = prev.close > prev2.high if use_close else prev.high > prev2.high
    break_low_2 = prev.close < prev2.low if use_close else prev.low < prev2.low

    signal_long = break_high_1 if consecutive == 1 else break_high_1 and break_high_2
    signal_short = break_low_1 if consecutive == 1 else break_low_1 and break_low_2

    if bool(indicator_cfg.get("use_alternating_filter", False)):
        signal_long = signal_long and last_signal != 1
        signal_short = signal_short and last_signal != -1
    if bool(indicator_cfg.get("use_adx_filter", True)):
        signal_long = signal_long and row.adx > float(indicator_cfg.get("adx_threshold", 20))
        signal_short = signal_short and row.adx > float(indicator_cfg.get("adx_threshold", 20))
    if bool(indicator_cfg.get("use_session_filter", True)):
        signal_long = signal_long and bool(row.session_pass)
        signal_short = signal_short and bool(row.session_pass)
    if bool(indicator_cfg.get("use_vwap_filter", True)):
        signal_long = signal_long and row.close > row.vwap
        signal_short = signal_short and row.close < row.vwap
    if bool(indicator_cfg.get("use_volume_filter", False)):
        mult = float(indicator_cfg.get("volume_multiplier", 1.2))
        signal_long = signal_long and row.volume > row.volume_sma * mult
        signal_short = signal_short and row.volume > row.volume_sma * mult
    if bool(indicator_cfg.get("use_range_filter", False)):
        box_range = max(float(row.high), float(prev.high)) - min(float(row.low), float(prev.low))
        min_mult = float(indicator_cfg.get("min_box_atr_mult", 0.35))
        signal_long = signal_long and box_range > row.atr * min_mult
        signal_short = signal_short and box_range > row.atr * min_mult

    if signal_long and not signal_short:
        return 1
    if signal_short and not signal_long:
        return -1
    return 0


def _build_day_context(bars_1m: pd.DataFrame, config: dict) -> dict:
    in_play_cfg = config.get("research", {}).get("in_play", {})
    premarket = _parse_window_from_list(in_play_cfg.get("premarket_window", ["04:00", "09:30"]))
    gap_threshold = float(in_play_cfg.get("gap_threshold_pct", 3.0))
    rel_threshold = float(in_play_cfg.get("premarket_volume_relative_threshold", 2.0))
    dollar_min = float(in_play_cfg.get("premarket_dollar_volume_min", 5_000_000))

    df = bars_1m.copy()
    df["session_date"] = df.index.date
    df["tod"] = [ts.time() for ts in df.index]
    daily = {}
    dates = sorted(df["session_date"].unique())
    premarket_volumes = []

    for idx, date in enumerate(dates):
        day = df[df["session_date"] == date]
        pre = day[[premarket.contains_open_left(t) for t in day["tod"]]]
        rth = day[[(time(9, 30) <= t < time(16, 0)) for t in day["tod"]]]
        prior_close = np.nan
        if idx > 0:
            prior_day = df[df["session_date"] == dates[idx - 1]]
            prior_rth = prior_day[[(time(9, 30) <= t < time(16, 0)) for t in prior_day["tod"]]]
            if not prior_rth.empty:
                prior_close = float(prior_rth["close"].iloc[-1])
        rth_open = float(rth["open"].iloc[0]) if not rth.empty else np.nan
        gap_pct = ((rth_open - prior_close) / prior_close * 100.0) if prior_close and pd.notna(prior_close) else np.nan
        pre_vol = float(pre["volume"].sum()) if not pre.empty else 0.0
        pre_dollar = float((pre["close"] * pre["volume"]).sum()) if not pre.empty else 0.0
        lookback = premarket_volumes[-20:]
        pre_rel = pre_vol / np.mean(lookback) if lookback and np.mean(lookback) > 0 else np.nan
        in_play = (
            pd.notna(gap_pct)
            and abs(gap_pct) >= gap_threshold
            and pd.notna(pre_rel)
            and pre_rel >= rel_threshold
            and pre_dollar >= dollar_min
        )
        daily[date] = {
            "gap_pct": gap_pct,
            "premarket_volume": pre_vol,
            "premarket_volume_relative": pre_rel,
            "premarket_dollar_volume": pre_dollar,
            "in_play": in_play,
        }
        premarket_volumes.append(pre_vol)
    return daily


def _add_streak_adx(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    streak_group = (out["direction"] != out["direction"].shift()).cumsum()
    out["adx_streak_max"] = out.groupby(streak_group)["adx"].cummax()
    out["adx_drop_from_streak_max"] = out["adx_streak_max"] - out["adx"]
    return out


def _add_forward_outcomes(events: pd.DataFrame, bars_5m: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    for idx, event in out.iterrows():
        future_events = out.iloc[idx + 1 :]
        opposite_positions = np.flatnonzero(future_events["direction"].to_numpy() == -event.direction)
        if len(opposite_positions):
            bars_until_opp = int(opposite_positions[0] + 1)
            out.at[idx, "bars_until_opposite_box"] = bars_until_opp
            for window in (3, 6, 12):
                out.at[idx, f"opposite_box_within_{window}"] = bars_until_opp <= window

        bar_index = int(event.bar_index)
        ext_bar = _first_extension_bar(bars_5m, bar_index, int(event.direction), float(event.box_extension_target))
        if ext_bar is not None:
            out.at[idx, "extension_hit"] = True
            out.at[idx, "bars_until_extension_hit"] = ext_bar - bar_index

        for n in (1, 3, 6, 12):
            if idx + n < len(out):
                future_close = float(out.iloc[idx + n]["close"])
                out.at[idx, f"forward_return_{n}_box" if n == 1 else f"forward_return_{n}_boxes"] = (
                    (future_close - float(event.close)) / float(event.close) * int(event.direction)
                )
        for n in (3, 6, 12):
            future_bars = bars_5m.iloc[bar_index + 1 : bar_index + n + 1]
            if not future_bars.empty:
                if int(event.direction) == 1:
                    out.at[idx, f"mfe_{n}_boxes"] = (future_bars["high"].max() - event.close) / event.close
                    out.at[idx, f"mae_{n}_boxes"] = (future_bars["low"].min() - event.close) / event.close
                else:
                    out.at[idx, f"mfe_{n}_boxes"] = (event.close - future_bars["low"].min()) / event.close
                    out.at[idx, f"mae_{n}_boxes"] = (event.close - future_bars["high"].max()) / event.close

            out.at[idx, f"failed_new_extreme_within_{n}"] = not bool(
                out.at[idx, "extension_hit"]
            ) or (
                pd.notna(out.at[idx, "bars_until_extension_hit"])
                and float(out.at[idx, "bars_until_extension_hit"]) > n
            )

        for n in (3, 6):
            future_bars = bars_5m.iloc[bar_index + 1 : bar_index + n + 1]
            if future_bars.empty:
                continue
            if int(event.direction) == -1:
                out.at[idx, f"vwap_reclaim_within_{n}"] = bool((future_bars["close"] > future_bars["vwap"]).any())
                out.at[idx, f"prior_box_mid_break_within_{n}"] = bool((future_bars["high"] > event.box_mid).any())
            else:
                out.at[idx, f"vwap_reclaim_within_{n}"] = bool((future_bars["close"] < future_bars["vwap"]).any())
                out.at[idx, f"prior_box_mid_break_within_{n}"] = bool((future_bars["low"] < event.box_mid).any())

    return out.drop(columns=["bar_index"])


def _first_extension_bar(
    bars_5m: pd.DataFrame,
    bar_index: int,
    direction: int,
    target: float,
    max_bars: int = 12,
) -> int | None:
    future = bars_5m.iloc[bar_index + 1 : bar_index + max_bars + 1]
    if direction == 1:
        hits = future.index[future["high"] >= target]
    else:
        hits = future.index[future["low"] <= target]
    return int(hits[0]) if len(hits) else None


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _parse_window(value: str) -> SessionWindow:
    start, end = value.split("-")
    return SessionWindow(_parse_time(start), _parse_time(end))


def _parse_window_from_list(value: Iterable[str]) -> SessionWindow:
    start, end = list(value)
    return SessionWindow(_parse_time(start), _parse_time(end))


def _bucket_for_time(value: time, buckets: list[tuple[str, SessionWindow]]) -> str:
    for name, window in buckets:
        if window.contains_open_left(value):
            return name
    return "outside_rth"


def _rma(series: pd.Series, period: int) -> pd.Series:
    return series.astype(float).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return np.nan
    return float(numerator) / float(denominator)


def _safe_series_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def _infer_symbol(ohlcv: pd.DataFrame) -> str:
    if "symbol" in ohlcv.columns and not ohlcv["symbol"].empty:
        return str(ohlcv["symbol"].iloc[0]).upper()
    return "UNKNOWN"
