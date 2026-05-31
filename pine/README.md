# Pine Sources

`confirmed_box_logic.pine` is a compact reference for confirmed historical box events. It intentionally excludes:

- realtime Ghost Box preview
- stoploss table
- visual-only management code
- discretionary tape-reading interpretation

For research, this compact file should be used to reproduce confirmed box events. If the full TradingView indicator changes, update the compact reference or add the full source here and document the difference in `docs/assumptions.md`.

`box_context_overlay.pine` is a TradingView review overlay for Phase 1-3 findings. It marks 5m confirmed box streak context, live-visible extension-failure states, midpoint watchlist context, VWAP confirmation context, and combined midpoint+VWAP context. It is not an entry/exit strategy and does not calculate PnL.
