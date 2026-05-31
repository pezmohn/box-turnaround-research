"""Summary tables and diagnostic analysis for box-turnaround research."""

from __future__ import annotations

import pandas as pd


def streak_survival_table(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize continuation/opposite probabilities by streak length."""
    raise NotImplementedError


def session_heatmaps(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return tables suitable for heatmap plotting by session bucket."""
    raise NotImplementedError
