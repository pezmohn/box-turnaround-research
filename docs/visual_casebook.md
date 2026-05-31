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

## HTML Reviewer

Use the local reviewer instead of editing CSVs by hand:

```bash
python scripts/serve_casebook_reviewer.py \
  --casebook-dir outputs/casebook \
  --host 127.0.0.1 \
  --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

The reviewer shows the SVG chart, pattern metadata, current auto-classification,
manual label buttons, notes, filtering, and progress counts. It writes manual
reviews to:

```text
outputs/casebook/manual_review.csv
```

Keyboard shortcuts:

- `1` clean
- `2` late
- `3` noisy
- `4` untradable
- `5` ignore
- `n` next
- `p` previous

## Offline Export

When the Lenovo local server is not reachable, export one portable HTML file:

```bash
python scripts/export_casebook_offline.py \
  --casebook-dir outputs/casebook \
  --output-html outputs/casebook/offline_reviewer.html \
  --zip outputs/casebook/offline_reviewer.zip
```

The offline reviewer embeds all sampled SVG charts. It stores labels in the
browser's local storage and provides a `Download CSV` button for the manual
review results.
