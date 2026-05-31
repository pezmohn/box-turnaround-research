# Assumptions

These assumptions are part of the research contract. If implementation requires a different assumption, document it before running analysis.

## Signal Timing

- Confirmed boxes are evaluated only after a 5-minute candle is closed.
- A confirmed box may only use data available at that 5-minute close.
- Realtime Ghost Boxes are excluded from baseline historical labels.
- Ghost Box research is a separate task and requires lower-timeframe data to reconstruct intrabar visibility.

## Data

- Prefer 1-minute data resampled into 5-minute bars.
- If only 5-minute OHLCV is available, do not infer intrabar ordering when multiple levels are touched inside the same candle.
- Timestamps should be normalized to exchange time before session bucketing.
- Raw market data should not be committed to the repo.

## Indicator Reproduction

- Reproduce the confirmed Pine logic as closely as possible.
- Start with default Pine parameters unless a config explicitly overrides them.
- If TradingView built-ins such as ADX, VWAP, or ATR differ from Python calculations, document the library and formula used.

## Labels

- Labels are context outcomes, not trades.
- A turnaround label should not imply a specific entry or stop.
- PnL backtesting should happen only after context labels show stable predictive value.

## Validation

- Split research and validation periods chronologically.
- Report trade/event count for every subgroup.
- Avoid optimizing on the same sample used for final claims.
