# Indicator Logic Summary

This document summarizes the confirmed-box logic that should be reproduced from the Pine script.

## Inputs To Preserve Initially

- `consecutive_confirms`: 1 or 2
- `use_close_breakout`
- `use_alternating_filter`
- ADX filter and threshold
- session filter
- VWAP filter
- volume filter
- minimum box range filter
- extension target

## 5-Minute Data

The Pine script requests 5-minute series and uses prior confirmed 5-minute bars for confirmed signals.

Core derived values:

```text
box_top = max(high_5m[1], high_5m[2])
box_bottom = min(low_5m[1], low_5m[2])
box_range = box_top - box_bottom
```

## Breakout Conditions

Long breakout:

```text
if use_close_breakout:
    close_5m[1] > high_5m[2]
else:
    high_5m[1] > high_5m[2]
```

Short breakout:

```text
if use_close_breakout:
    close_5m[1] < low_5m[2]
else:
    low_5m[1] < low_5m[2]
```

If `consecutive_confirms == 2`, the prior 5-minute bar must also have broken the bar before it in the same direction.

## Filters

Confirmed boxes may require:

- ADX above threshold
- active session
- close above VWAP for long / below VWAP for short
- volume greater than volume SMA times multiplier
- box range greater than ATR times multiplier
- alternating long/short behavior if enabled

## Levels

For long boxes:

```text
entry_236 = box_bottom + box_range * 0.236
extension = box_bottom + box_range * extension_value
stop_reference = box_bottom
```

For short boxes:

```text
entry_236 = box_top - box_range * 0.236
extension = box_top - box_range * extension_value
stop_reference = box_top
```

## Realtime Ghost Box

Ghost Box is a realtime preview based on the currently forming bar. It is useful visually, but is excluded from baseline historical event labels.

## Existing Turnaround Hooks

The Pine script already emits simple first-opposite-box alerts:

```text
first_green_after_red
first_red_after_green
```

These are too coarse for research. The research layer should add streak length, exhaustion, extension failure, ADX fade, VWAP reclaim/loss, and prior-box midpoint break.
