"""Conflict Collection public API.

High-level exports:

- Conflict type collector: :func:`collect_conflict_types`
- Societal signals collector: :func:`collect_societal_signals`
- Anchored similarity metric: :func:`anchored_ratio`
- Data models: conflict case dataclasses & pydantic schemas
"""

from .collectors.conflict_type.collector import collect as collect_conflict_types
from .collectors.societal.collector import collect as collect_societal_signals
from .metrics.anchored_ratio.anchored_ratio import anchored_ratio

__all__ = [
    "collect_conflict_types",
    "collect_societal_signals",
    "anchored_ratio",
]
