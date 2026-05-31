"""Confirmed 5-minute box event extraction scaffold.

Implement this module by reproducing the confirmed Pine logic documented in
`docs/indicator_logic.md` and `pine/confirmed_box_logic.pine`.
"""

from __future__ import annotations

import pandas as pd


def build_box_events(ohlcv: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Build one event row per confirmed 5-minute box.

    Parameters
    ----------
    ohlcv:
        Time-indexed OHLCV data. Prefer 1-minute data resampled into 5-minute
        bars before signal evaluation.
    config:
        Parsed research config.

    Returns
    -------
    pd.DataFrame
        Event dataset matching `docs/event_schema.md`.
    """
    raise NotImplementedError("Reproduce confirmed Pine box logic here.")
