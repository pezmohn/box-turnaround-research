# Box Turnaround Research

Research workspace for quantifying a TradingView 5-minute breakout box indicator as a market-context and tape-reading tool.

This is not yet a trading strategy. The first objective is to build an event dataset of confirmed 5-minute box events and analyze streaks, session behavior, exhaustion, extension failure, ADX fade, VWAP reclaim, and turnaround probability.

## Current Goal

Treat the indicator as a market-state classifier:

- identify confirmed green/red 5m breakout boxes
- measure how long same-color box streaks persist
- study how continuation and reversal probabilities change by streak length and session window
- find which contextual features make a turnaround more likely
- avoid PnL optimization until context labels show stable predictive value

## Current Research Read

The current Phase 1-3 result is summarized in `docs/context_playbook.md`.
Short version: long box streaks do not reverse by themselves. The useful
context appears when a 5+ streak also shows extension failure plus structural
reclaim or break, especially VWAP reclaim/loss and prior box midpoint break.

## Suggested Workflow

1. Reproduce the confirmed-box logic from the Pine script in `pine/mtf_breakout_box.pine`.
2. Build a box-event dataset as specified in `docs/event_schema.md`.
3. Generate baseline streak/session summaries.
4. Define and validate context labels in `docs/research_questions.md`.
5. Only then test whether context states are tradeable.

## Research Runner

The runner builds confirmed-box event datasets and summary tables. It does not
run entries, exits, position sizing, or PnL optimization.

Baseline universe:

```bash
python scripts/run_box_research.py \
  --data-dir /home/backtest/stockdata/stock_data_1min
```

Ad-hoc ticker check:

```bash
python scripts/run_box_research.py \
  --symbols NOW \
  --data-dir /home/backtest/stockdata/stock_data_1min
```

Multiple ad-hoc tickers:

```bash
python scripts/run_box_research.py \
  --symbols NOW,CRM,SNOW \
  --data-dir /home/backtest/stockdata/stock_data_1min
```

Ticker fit check against the validated box-research profile:

```bash
python scripts/analyze_ticker_fit.py NOW \
  --data-dir /home/backtest/stockdata/stock_data_1min \
  --baseline-events data/processed/box_events_all.parquet
```

This writes `outputs/ticker_fit/NOW_fit_report.md`. The verdict is a fit/context
classification, not a directional trade call.

VWAP_OFF re-entry sensitivity:

```bash
python scripts/run_vwap_off_reentry.py \
  --data-dir /home/backtest/stockdata/stock_data_1min
```

Generated event datasets are written under `data/processed/`. Tables and the
Markdown report are written under `outputs/`. These are local artifacts and are
gitignored by design.

## Visual Casebook

After Phase 3 validation, use the visual casebook to audit real chart examples
for the strongest context states. See `docs/visual_casebook.md`.

```bash
python scripts/build_visual_casebook.py \
  --events-file data/processed/box_events_all.parquet \
  --data-dir /home/backtest/stockdata/stock_data_1min \
  --samples-per-pattern 24 \
  --split validation
```

Manual review app:

```bash
python scripts/serve_casebook_reviewer.py \
  --casebook-dir outputs/casebook \
  --host 127.0.0.1 \
  --port 8765
```

Portable offline export:

```bash
python scripts/export_casebook_offline.py \
  --casebook-dir outputs/casebook \
  --output-html outputs/casebook/offline_reviewer.html \
  --zip outputs/casebook/offline_reviewer.zip
```

## Repository Layout

```text
pine/                 TradingView source logic
docs/                 research brief, assumptions, event schema, questions
configs/              default research parameters
src/                  Python modules for event extraction and analysis
scripts/              repeatable research runners
tests/                synthetic timing/schema checks
notebooks/            exploratory notebooks
data/                 local data location, raw data is gitignored
outputs/              local reports/figures, gitignored
```

## Important Caveat

The Ghost Box is a realtime preview feature. It should not be used for historical labels unless lower-timeframe intrabar data is available and the exact realtime visibility can be reconstructed.
