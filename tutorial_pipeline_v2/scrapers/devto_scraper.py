"""Dev.to trend scraping using official API."""

from __future__ import annotations

from typing import Dict

import requests

from config import settings
from scrapers.keyword_analyzer import analyze_publish_dates, extract_keywords
from utils.logger import get_logger

logger = get_logger(__name__)

TIMEFRAME_TO_DAYS = {
    "day": 1,
    "week": 7,
    "month": 30,
}


def analyze_devto_trends(tag: str = "python", timeframe: str = "week", limit: int = 50) -> Dict[str, object]:
    """Analyze top Dev.to articles by tag and timeframe."""
    days = TIMEFRAME_TO_DAYS.get(str(timeframe).lower(), 7)
    url = "https://dev.to/api/articles"
    params = {
        "tag": tag,
        "top": days,
        "per_page": min(limit, 100),
    }

    try:
        response = requests.get(url, params=params, timeout=settings.REQUEST_TIMEOUT_S)
        response.raise_for_status()
        articles = response.json()
        if not isinstance(articles, list):
            articles = []
    except requests.RequestException as exc:
        logger.warning("Dev.to trends request failed for tag=%s: %s", tag, exc)
        articles = []

    titles = [str(article.get("title", "")) for article in articles]
    reactions = [int(article.get("positive_reactions_count", 0) or 0) for article in articles]
    avg_reactions = round(sum(reactions) / len(reactions), 2) if reactions else 0.0

    return {
        "hot_topics": extract_keywords(titles),
        "avg_reactions": avg_reactions,
        "best_posting_times": analyze_publish_dates(articles),
        "raw_articles": articles,
        "source": "devto",
    }
