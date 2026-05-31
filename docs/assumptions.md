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
- Baseline research uses the full regular trading hours session, 09:30-16:00 exchange time.
- The Pine reference default of 09:30-11:30 is not used as the baseline research universe because it would exclude midday, afternoon, and power-hour streak behavior. Morning-only analysis may be added later as a subgroup, not as the event-dataset filter.
- The baseline report starts with a liquid default universe, but the workflow must support ad-hoc symbol analysis for any ticker with available 1-minute data, for example `NOW`.
- In-play/out-of-play classification is a day-level research feature, not a trade signal. The first version classifies a symbol-day as in-play using premarket context available before the RTH open: gap percentage, premarket relative volume, and premarket dollar volume.
- The initial in-play thresholds are deliberately simple and documented in config. They should be treated as subgroup labels for research, not optimized parameters.

## Indicator Reproduction

- Reproduce the confirmed Pine logic as closely as possible.
- Start with default Pine parameters unless a config explicitly overrides them.
- If TradingView built-ins such as ADX, VWAP, or ATR differ from Python calculations, document the library and formula used.
- The Python baseline calculates ATR/ADX with Wilder-style RMA and VWAP as cumulative daily typical-price dollar volume divided by cumulative volume. Treat small TradingView differences as an implementation audit item before making final claims.

## Labels

- Labels are context outcomes, not trades.
- A turnaround label should not imply a specific entry or stop.
- `turnaround_candidate` is provisional and should be used to sort research cases, not to claim a trading edge.
- PnL backtesting should happen only after context labels show stable predictive value.

## Validation

- Split research and validation periods chronologically.
- Report trade/event count for every subgroup.
- Avoid optimizing on the same sample used for final claims.
