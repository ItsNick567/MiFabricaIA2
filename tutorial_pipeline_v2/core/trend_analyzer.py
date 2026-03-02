"""Daily trend aggregation with multi-source scraping and caching."""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup

from config import settings
from utils.cache_manager import CacheManager
from utils.logger import get_logger
from utils.paths import DATA_TRENDS_CACHE_FILE, p

logger = get_logger(__name__)

CACHE_DURATION = settings.TRENDS_CACHE_DURATION_HOURS * 3600
REDDIT_USER_AGENT = "TutorialPipelineBot/2.0 (+https://github.com/tutorial-pipeline)"

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
}


def _cache_file_for_category(category: str) -> str:
    return p("data", f"trends_cache_{category.lower().strip() or 'general'}.json")


def _read_file_cache(file_path: str) -> list | dict | None:
    if not os.path.exists(file_path):
        return None
    age = time.time() - os.path.getmtime(file_path)
    if age > CACHE_DURATION:
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not read trends cache file=%s: %s", file_path, exc)
        return None


def _write_file_cache(file_path: str, payload: object) -> None:
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _normalize_text(text: str) -> str:
    tokens = re.findall(r"[a-zA-Z0-9+#.-]{3,}", text.lower())
    filtered = [token for token in tokens if token not in STOPWORDS]
    return " ".join(filtered[:7]) if filtered else text.strip().lower()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_compact_number(raw_value: str) -> int:
    clean = raw_value.strip().upper().replace(",", "")
    if not clean:
        return 0
    multiplier = 1
    if clean.endswith("K"):
        multiplier = 1000
        clean = clean[:-1]
    elif clean.endswith("M"):
        multiplier = 1000000
        clean = clean[:-1]
    try:
        return int(float(clean) * multiplier)
    except ValueError:
        return 0


def _score_from_card_text(card_text: str) -> int:
    values: List[int] = []
    for token in re.findall(r"\b\d+(?:\.\d+)?[KM]?\b", card_text.upper()):
        parsed = _parse_compact_number(token)
        if parsed > 0:
            values.append(parsed)
    if not values:
        return 0
    return max(values)


def get_devto_trending(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch top Dev.to posts from the last 7 days."""
    url = "https://dev.to/api/articles"
    params = {"top": "7", "per_page": min(max(limit, 1), 100)}

    try:
        response = requests.get(url, params=params, timeout=settings.REQUEST_TIMEOUT_S)
        response.raise_for_status()
        articles = response.json()
    except requests.RequestException as exc:
        logger.warning("Dev.to trends fetch failed: %s", exc)
        return []

    topics: List[Dict[str, Any]] = []
    for article in articles if isinstance(articles, list) else []:
        title = str(article.get("title", "")).strip()
        if not title:
            continue
        reactions = _safe_int(article.get("positive_reactions_count"))
        comments = _safe_int(article.get("comments_count"))
        score = reactions + (comments * 2)
        tags = article.get("tag_list", [])
        tag_list = [str(tag).lower() for tag in tags] if isinstance(tags, list) else []

        topics.append(
            {
                "title": title,
                "score": max(score, 1),
                "tags": tag_list,
                "source": "devto",
                "url": article.get("url"),
            }
        )

    topics.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
    return topics[:limit]


def get_hashnode_trending(limit: int = 30) -> List[Dict[str, Any]]:
    """Scrape Hashnode trending page and score visible popularity signals."""
    url = "https://hashnode.com/trending"
    headers = {"User-Agent": REDDIT_USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT_S)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Hashnode trending scrape failed: %s", exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    candidates = soup.select("article") or soup.select("a[href*='/p/']")

    topics: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()

    for rank, card in enumerate(candidates, start=1):
        title_node = card.select_one("h1, h2, h3")
        if title_node is None:
            title_node = card.select_one("a[href*='/p/']")
        title = title_node.get_text(" ", strip=True) if title_node else ""
        if not title or len(title) < 8:
            continue

        key = title.lower().strip()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        card_text = card.get_text(" ", strip=True)
        score = _score_from_card_text(card_text)
        if score == 0:
            score = max(1, (limit + 1) - rank)

        link_node = card.select_one("a[href*='/p/']")
        href = link_node.get("href") if link_node else ""
        if href and href.startswith("/"):
            href = f"https://hashnode.com{href}"

        tags = re.findall(r"#[a-zA-Z0-9_-]+", card_text)
        topics.append(
            {
                "title": title,
                "score": int(score),
                "tags": [tag.lstrip("#").lower() for tag in tags[:6]],
                "source": "hashnode",
                "url": href,
            }
        )

        if len(topics) >= limit:
            break

    topics.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
    return topics


def get_github_trending(limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch rising GitHub repos and convert them into tutorial topic ideas."""
    since = (datetime.now(timezone.utc) - timedelta(days=120)).date().isoformat()
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"created:>{since}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(max(limit, 1), 100),
    }
    headers = {"Accept": "application/vnd.github+json"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=settings.REQUEST_TIMEOUT_S)
        response.raise_for_status()
        payload = response.json() if response.text else {}
    except requests.RequestException as exc:
        logger.warning("GitHub trending fetch failed: %s", exc)
        return []

    topics: List[Dict[str, Any]] = []
    for repo in payload.get("items", []) if isinstance(payload, dict) else []:
        name = str(repo.get("name", "")).strip()
        if not name:
            continue

        stars = _safe_int(repo.get("stargazers_count"))
        forks = _safe_int(repo.get("forks_count"))
        watchers = _safe_int(repo.get("watchers_count"))
        score = stars + forks + watchers
        tags = repo.get("topics", [])
        tag_list = [str(tag).lower() for tag in tags] if isinstance(tags, list) else []

        topics.append(
            {
                "title": f"Getting Started with {name}",
                "score": max(score, 1),
                "tags": tag_list,
                "source": "github",
                "url": repo.get("html_url"),
            }
        )

    topics.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
    return topics[:limit]


def get_reddit_programming(limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch hot posts from r/programming JSON feed."""
    url = "https://www.reddit.com/r/programming/hot.json"
    params = {"limit": min(max(limit, 1), 100)}
    headers = {"User-Agent": REDDIT_USER_AGENT}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=settings.REQUEST_TIMEOUT_S)
        response.raise_for_status()
        payload = response.json() if response.text else {}
    except requests.RequestException as exc:
        logger.warning("Reddit programming fetch failed: %s", exc)
        return []

    topics: List[Dict[str, Any]] = []
    children = payload.get("data", {}).get("children", []) if isinstance(payload, dict) else []
    for child in children:
        data = child.get("data", {}) if isinstance(child, dict) else {}
        title = str(data.get("title", "")).strip()
        if not title:
            continue

        ups = _safe_int(data.get("ups"))
        comments = _safe_int(data.get("num_comments"))
        score = ups + (comments * 2)

        topics.append(
            {
                "title": title,
                "score": max(score, 1),
                "tags": [],
                "source": "reddit",
                "url": f"https://reddit.com{data.get('permalink', '')}",
            }
        )

    topics.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
    return topics[:limit]


def _merge_topics(all_topics: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for topic in all_topics:
        title = str(topic.get("title", "")).strip()
        if not title:
            continue

        key = _normalize_text(title)
        score = int(topic.get("score", 0) or 0)
        tags = topic.get("tags", [])
        source = str(topic.get("source", "unknown"))

        if key not in merged:
            merged[key] = {
                "title": title,
                "score": max(score, 0),
                "tags": list(tags) if isinstance(tags, list) else [],
                "source": source,
                "sources": [source],
                "evidence_count": 1,
            }
            continue

        bucket = merged[key]
        bucket["score"] += max(score, 0)
        bucket["evidence_count"] += 1

        existing_tags = {str(tag).lower() for tag in bucket.get("tags", [])}
        for tag in tags if isinstance(tags, list) else []:
            low = str(tag).lower()
            if low and low not in existing_tags:
                bucket["tags"].append(low)
                existing_tags.add(low)

        if source not in bucket["sources"]:
            bucket["sources"].append(source)

    merged_topics = list(merged.values())
    merged_topics.sort(
        key=lambda item: (int(item.get("score", 0)), int(item.get("evidence_count", 0))),
        reverse=True,
    )
    return merged_topics


def aggregate_trending_topics(category: str = "programming", limit: int = 20) -> List[Dict[str, Any]]:
    """Combine all trend sources and return ranked topics."""
    source_fetchers = {
        "devto": get_devto_trending,
        "hashnode": get_hashnode_trending,
        "github": get_github_trending,
        "reddit": get_reddit_programming,
    }

    selected_sources = [src.lower() for src in settings.TREND_SOURCES]
    all_topics: List[Dict[str, Any]] = []

    for source in selected_sources:
        fetcher = source_fetchers.get(source)
        if not fetcher:
            continue
        try:
            all_topics.extend(fetcher())
        except Exception as exc:  # pragma: no cover
            logger.warning("Trend source failed source=%s error=%s", source, exc)

    if not all_topics:
        logger.warning("No trends collected for category=%s", category)
        return []

    merged = _merge_topics(all_topics)
    return merged[:limit]


def get_trending_topics_aggregated(category: str = "programming") -> List[Tuple[str, int]]:
    """Compatibility wrapper used by UI/content optimizer."""
    topics = aggregate_trending_topics(category=category, limit=20)
    return [(str(item.get("title", "")), int(item.get("score", 0))) for item in topics if item.get("title")]


def save_trends_cache(topics: List[Dict[str, Any]], category: str = "programming") -> None:
    """Persist trends for autonomous execution and dashboard usage."""
    cache = CacheManager(ttl_hours=settings.TRENDS_CACHE_DURATION_HOURS)
    cache_key = f"trends_{category.lower()}_detailed"
    cache.set(cache_key, topics)

    category_file = _cache_file_for_category(category)
    _write_file_cache(category_file, topics)

    consolidated = _read_file_cache(DATA_TRENDS_CACHE_FILE) or {}
    if not isinstance(consolidated, dict):
        consolidated = {}
    consolidated[category] = topics
    _write_file_cache(DATA_TRENDS_CACHE_FILE, consolidated)


def load_trends_cache(category: str = "programming") -> List[Dict[str, Any]]:
    """Load cached detailed trend items, refreshing if stale."""
    cache = CacheManager(ttl_hours=settings.TRENDS_CACHE_DURATION_HOURS)
    cache_key = f"trends_{category.lower()}_detailed"
    cached = cache.get(cache_key, max_age_seconds=CACHE_DURATION)
    if isinstance(cached, list) and cached:
        return [item for item in cached if isinstance(item, dict)]

    category_file = _cache_file_for_category(category)
    file_cached = _read_file_cache(category_file)
    if isinstance(file_cached, list) and file_cached:
        return [item for item in file_cached if isinstance(item, dict)]

    fresh = aggregate_trending_topics(category=category, limit=20)
    save_trends_cache(fresh, category=category)
    return fresh


def get_trends_cached(category: str = "programming") -> List[Tuple[str, int]]:
    """Return cached tuple format for the Streamlit trends UI."""
    detailed = load_trends_cache(category=category)
    return [(str(item.get("title", "")), int(item.get("score", 0))) for item in detailed if item.get("title")]
