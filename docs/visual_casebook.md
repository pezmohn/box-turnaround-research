# Visual Casebook

The visual casebook turns validated context states into chart snippets for manual review.
It is still a research artifact: no entries, stops, targets, sizing, or PnL.

## Purpose

The Phase 1-3 tables show that long confirmed-box streaks become interesting only after extension failure plus a structural reclaim or break.
The casebook checks whether those states look usable on actual charts.

Review each sampled example as one of:

- `clean_transition`: failure and reclaim/break are visible without immediate continuation.
- `hard_confirmation`: VWAP reclaim/loss confirms the transition, but may be late.
- `watchlist_followthrough`: midpoint break gives a broader warning state.
- `noisy_continuation`: the context fires but the original streak keeps control.
- `warning_only`: extension failure appears without strong structural confirmation.
- `ignore_state`: long streak state without failure/reclaim evidence.

## Generate

On Backtesta:

```bash
python scripts/build_visual_casebook.py \
  --events-file data/processed/box_events_all.parquet \
  --data-dir /home/backtest/stockdata/stock_data_1min \
  --samples-per-pattern 24 \
  --split validation
```

Outputs:

- `outputs/casebook/casebook_report.md`
- `outputs/casebook/casebook_manifest.csv`
- `outputs/casebook/charts/**/*.svg`

These outputs are gitignored. Commit the generator and docs, not the chart artifacts.

## Review Rules

- Check the chart first, then the manifest row.
- Separate "context shifted" from "tradable entry existed".
- Treat VWAP reclaim/loss as confirmation, not prediction.
- Keep late-but-correct examples separate from clean early transitions.
- Do not promote to TradingView overlay until noisy/late/untradable examples have been reviewed.
