"""Context labels for continuation, opposite boxes, and turnaround candidates."""

from __future__ import annotations

import pandas as pd


def add_context_labels(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Create research labels, not trade labels.

    Baseline labels should include continuation, opposite_box,
    turnaround_candidate, failed_turnaround, and exhaustion.
    """
    raise NotImplementedError
