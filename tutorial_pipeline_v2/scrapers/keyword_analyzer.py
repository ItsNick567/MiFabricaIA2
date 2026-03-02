"""Keyword extraction and publication-time analysis helpers."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Iterable, List

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "for",
    "with",
    "from",
    "into",
    "your",
    "you",
    "this",
    "that",
    "how",
    "what",
    "when",
    "why",
    "guide",
    "tutorial",
    "using",
    "build",
    "learn",
    "best",
    "tips",
    "de",
    "la",
    "el",
    "los",
    "las",
    "y",
    "o",
    "para",
    "como",
    "que",
    "con",
    "por",
    "una",
    "un",
}


def _tokenize(text: str) -> List[str]:
    return [
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9+#.-]+", text or "")
        if len(token) >= 3 and token.lower() not in STOPWORDS
    ]


def extract_keywords(texts: Iterable[str], top_k: int = 20) -> List[str]:
    """Extract ranked keywords from title/topic lists."""
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(_tokenize(text))
    return [word for word, _ in counter.most_common(top_k)]


def analyze_publish_dates(items: Iterable[dict]) -> List[str]:
    """Return most frequent publication windows from API payloads."""
    hour_counter: Counter[int] = Counter()
    for item in items:
        date_value = item.get("published_at") or item.get("created_at")
        if not date_value:
            continue
        try:
            hour = datetime.fromisoformat(str(date_value).replace("Z", "+00:00")).hour
        except ValueError:
            continue
        hour_counter[hour] += 1

    top_hours = [hour for hour, _ in hour_counter.most_common(3)]
    return [f"{hour:02d}:00" for hour in sorted(top_hours)]


def estimate_optimal_length(texts: Iterable[str], default_value: int = 1200) -> int:
    """Estimate target word count from a set of documents."""
    lengths = [len((text or "").split()) for text in texts if text]
    if not lengths:
        return default_value
    lengths.sort()
    return lengths[len(lengths) // 2]
