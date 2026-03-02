"""Legacy aggregator wrappers for trend sources."""

from __future__ import annotations

from typing import List, Tuple

from core.trend_analyzer import aggregate_trending_topics


def get_trending_topics_aggregated(category: str = "programming") -> List[Tuple[str, int]]:
    """Return top ranked topics as (topic, score) tuples."""
    topics = aggregate_trending_topics(category=category, limit=20)
    return [(str(item.get("title", "")), int(item.get("score", 0))) for item in topics if item.get("title")]
