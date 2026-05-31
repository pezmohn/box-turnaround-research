# Box Event Schema

Each confirmed 5-minute box should become one event row.

## Required Columns

```text
event_id
symbol
timeframe
timestamp_open
timestamp_close
session_date
session_bucket

direction                  # 1 long/green, -1 short/red
streak_direction           # current streak direction
streak_length              # same-color confirmed boxes in a row
prior_streak_direction
prior_streak_length

box_top
box_bottom
box_range
box_mid
box_fib_236
box_extension_target
box_range_atr_ratio

close
high
low
volume
volume_sma
volume_relative
atr
adx
adx_change_1
adx_change_3
adx_streak_max
adx_drop_from_streak_max
vwap
vwap_distance
vwap_distance_atr
close_above_vwap

extension_hit
bars_until_extension_hit
bars_until_opposite_box
opposite_box_within_3
opposite_box_within_6
opposite_box_within_12

vwap_reclaim_within_3
vwap_reclaim_within_6
prior_box_mid_break_within_3
prior_box_mid_break_within_6
failed_new_extreme_within_3
failed_new_extreme_within_6

forward_return_1_box
forward_return_3_boxes
forward_return_6_boxes
forward_return_12_boxes
mfe_3_boxes
mae_3_boxes
mfe_6_boxes
mae_6_boxes
mfe_12_boxes
mae_12_boxes
```

## Session Buckets

Default buckets should be configurable, but start with:

```text
09:30-10:00 open_impulse
10:00-11:30 morning_trend
11:30-13:30 midday
13:30-15:00 afternoon
15:00-16:00 power_hour
```

Use exchange time.

## Directional Interpretation

For a red streak, a potential bullish transition may involve:

- first opposite green box
- reclaim of VWAP
- break above midpoint of the last red trend box
- failure to make a fresh downside extension

For a green streak, invert the logic.

## Notes

- `mfe` and `mae` are context excursions, not trade PnL unless a later strategy layer defines entry/exit.
- Keep raw price movements and normalized ATR/R values where possible.
- Every conditional summary should include sample size.
