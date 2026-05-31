"""Feature engineering for box-streak and turnaround context research."""

from __future__ import annotations

import pandas as pd


def add_streak_features(events: pd.DataFrame) -> pd.DataFrame:
    """Add same-direction streak length and prior-streak context."""
    raise NotImplementedError


def add_exhaustion_features(events: pd.DataFrame) -> pd.DataFrame:
    """Add ADX fade, extension failure, VWAP distance, and range-compression features."""
    raise NotImplementedError
