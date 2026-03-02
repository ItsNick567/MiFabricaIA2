"""Analytics storage and metrics calculations."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any, Dict, List

from utils.historial import cargar_datos
from utils.paths import DATA_ANALYTICS_FILE, ensure_dirs

DEFAULT_ANALYTICS_SCHEMA: Dict[str, Any] = {
    "global": {
        "total_generated": 0,
        "total_published": 0,
        "total_publication_attempts": 0,
        "total_estimated_revenue": 0.0,
        "avg_generation_time": 0.0,
        "success_rate": 0.0,
    },
    "by_platform": {
        "devto": {
            "published": 0,
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "avg_claps": 0,
            "visits": 0,
            "subscribers": 0,
        },
        "hashnode": {
            "published": 0,
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "avg_claps": 0,
            "visits": 0,
            "subscribers": 0,
        },
        "telegram": {
            "published": 0,
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "avg_claps": 0,
            "visits": 0,
            "subscribers": 0,
        },
        "blogger": {
            "published": 0,
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "avg_claps": 0,
            "visits": 0,
            "subscribers": 0,
        },
    },
    "by_topic_category": {},
    "by_llm_engine": {
        "groq": {"uses": 0, "avg_time": 0.0, "success_rate": 0.0, "successes": 0, "attempts": 0},
        "ollama": {"uses": 0, "avg_time": 0.0, "success_rate": 0.0, "successes": 0, "attempts": 0},
        "gemini": {"uses": 0, "avg_time": 0.0, "success_rate": 0.0, "successes": 0, "attempts": 0},
        "unknown": {"uses": 0, "avg_time": 0.0, "success_rate": 0.0, "successes": 0, "attempts": 0},
    },
    "timeline": [],
}


def _deep_merge(default: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(default)
    for key, value in current.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_analytics() -> Dict[str, Any]:
    """Load analytics file and apply schema defaults."""
    ensure_dirs()
    try:
        with open(DATA_ANALYTICS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict):
                data = {}
    except Exception:
        data = {}
    return _deep_merge(DEFAULT_ANALYTICS_SCHEMA, data)


def save_analytics(analytics: Dict[str, Any]) -> None:
    """Persist analytics payload."""
    ensure_dirs()
    with open(DATA_ANALYTICS_FILE, "w", encoding="utf-8") as handle:
        json.dump(analytics, handle, ensure_ascii=False, indent=2)


def _update_timeline(analytics: Dict[str, Any], published_count: int, revenue_delta: float) -> None:
    today = datetime.now().date().isoformat()
    timeline = analytics.setdefault("timeline", [])
    entry = next((item for item in timeline if item.get("date") == today), None)
    if entry is None:
        entry = {"date": today, "generated": 0, "published": 0, "revenue_estimate": 0.0}
        timeline.append(entry)

    entry["generated"] = int(entry.get("generated", 0)) + 1
    entry["published"] = int(entry.get("published", 0)) + int(published_count)
    entry["revenue_estimate"] = round(float(entry.get("revenue_estimate", 0.0)) + float(revenue_delta), 2)


def _update_topic_category(analytics: Dict[str, Any], tutorial_item: Dict[str, Any]) -> None:
    category = "general"
    topic = str(tutorial_item.get("topic", "")).lower()
    for label in ("python", "javascript", "react", "git", "docker", "ai", "data"):
        if label in topic:
            category = label
            break

    by_category = analytics.setdefault("by_topic_category", {})
    record = by_category.setdefault(category, {"count": 0, "avg_performance": 0.0, "best_performing": []})
    record["count"] += 1

    score = float(tutorial_item.get("performance_score") or 0)
    count = float(record["count"])
    previous_avg = float(record.get("avg_performance", 0.0))
    record["avg_performance"] = round(((previous_avg * (count - 1)) + score) / count, 2)

    best = record.setdefault("best_performing", [])
    best.append(
        {
            "id": tutorial_item.get("id"),
            "title": tutorial_item.get("title"),
            "score": score,
        }
    )
    best.sort(key=lambda item: item.get("score", 0), reverse=True)
    del best[5:]


def _update_llm_stats(analytics: Dict[str, Any], tutorial_item: Dict[str, Any]) -> None:
    engine = str(tutorial_item.get("llm_used", "unknown") or "unknown").lower()
    if engine not in analytics["by_llm_engine"]:
        analytics["by_llm_engine"][engine] = {
            "uses": 0,
            "avg_time": 0.0,
            "success_rate": 0.0,
            "successes": 0,
            "attempts": 0,
        }

    item = analytics["by_llm_engine"][engine]
    item["uses"] += 1
    item["attempts"] += 1
    item["successes"] += 1

    generation_time = float(tutorial_item.get("generation_time") or 0.0)
    uses = float(item["uses"])
    current_avg = float(item.get("avg_time", 0.0))
    item["avg_time"] = round(((current_avg * (uses - 1)) + generation_time) / uses, 2)
    item["success_rate"] = round((item["successes"] / max(1, item["attempts"])) * 100, 2)


def update_analytics(tutorial_item: Dict[str, Any], publish_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Update analytics after generation and publication events."""
    analytics = load_analytics()

    global_stats = analytics["global"]
    global_stats["total_generated"] += 1

    generation_time = float(tutorial_item.get("generation_time") or 0.0)
    total_generated = float(global_stats["total_generated"])
    current_avg_time = float(global_stats.get("avg_generation_time", 0.0))
    global_stats["avg_generation_time"] = round(
        ((current_avg_time * (total_generated - 1)) + generation_time) / max(total_generated, 1),
        2,
    )

    success_count = 0
    revenue_delta = 0.0

    for platform, result in (publish_results or {}).items():
        global_stats["total_publication_attempts"] += 1
        platform_entry = analytics["by_platform"].setdefault(
            platform,
            {
                "published": 0,
                "estimated_reads": 0,
                "estimated_revenue": 0.0,
                "avg_claps": 0,
                "visits": 0,
                "subscribers": 0,
            },
        )

        if result.get("success"):
            success_count += 1
            global_stats["total_published"] += 1
            platform_entry["published"] += 1

        platform_entry["estimated_reads"] += int(result.get("estimated_reads", 0) or 0)
        if "visits" in result:
            platform_entry["visits"] += int(result.get("visits", 0) or 0)
        if "subscribers" in result:
            platform_entry["subscribers"] += int(result.get("subscribers", 0) or 0)

        revenue_part = float(result.get("estimated_revenue", 0.0) or 0.0)
        current_revenue = float(platform_entry.get("estimated_revenue", 0.0))
        platform_entry["estimated_revenue"] = round(current_revenue + revenue_part, 2)
        revenue_delta += revenue_part

    total_attempts = max(1, global_stats["total_publication_attempts"])
    global_stats["success_rate"] = round((global_stats["total_published"] / total_attempts) * 100, 2)

    _update_topic_category(analytics, tutorial_item)
    _update_llm_stats(analytics, tutorial_item)
    _update_timeline(analytics, success_count, revenue_delta)

    analytics["global"]["total_estimated_revenue"] = calculate_revenue_estimate(analytics)
    save_analytics(analytics)
    return analytics


def update_analytics_for_platform(
    platform: str,
    tutorial_id: str,
    url: str | None = None,
    estimated_reads: int = 0,
    estimated_revenue: float = 0.0,
) -> Dict[str, Any]:
    """Update only platform counters after publication."""
    analytics = load_analytics()
    platform_entry = analytics["by_platform"].setdefault(
        platform,
        {
            "published": 0,
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "avg_claps": 0,
            "visits": 0,
            "subscribers": 0,
        },
    )

    platform_entry["published"] += 1
    platform_entry["estimated_reads"] += int(estimated_reads)
    current_revenue = float(platform_entry.get("estimated_revenue", 0.0))
    platform_entry["estimated_revenue"] = round(current_revenue + float(estimated_revenue), 2)

    analytics["global"]["total_published"] += 1
    analytics["global"]["total_publication_attempts"] += 1
    analytics["global"]["success_rate"] = round(
        (analytics["global"]["total_published"] / max(1, analytics["global"]["total_publication_attempts"])) * 100,
        2,
    )
    analytics["global"]["total_estimated_revenue"] = calculate_revenue_estimate(analytics)

    save_analytics(analytics)
    return analytics


def calculate_revenue_estimate(analytics_data: Dict[str, Any]) -> float:
    """Estimate revenue from cross-platform proxy metrics."""
    by_platform = analytics_data.get("by_platform", {})

    devto_reads = float(by_platform.get("devto", {}).get("estimated_reads", 0) or 0)
    hashnode_reads = float(by_platform.get("hashnode", {}).get("estimated_reads", 0) or 0)
    blogger_visits = float(by_platform.get("blogger", {}).get("visits", 0) or 0)
    telegram_subscribers = float(by_platform.get("telegram", {}).get("subscribers", 0) or 0)

    tracked_platform_revenue = sum(
        float((platform_metrics or {}).get("estimated_revenue", 0.0) or 0.0)
        for platform_metrics in by_platform.values()
        if isinstance(platform_metrics, dict)
    )

    proxy_revenue = 0.0
    proxy_revenue += devto_reads * 0.02
    proxy_revenue += hashnode_reads * 0.015
    proxy_revenue += blogger_visits * 0.03
    proxy_revenue += telegram_subscribers * 0.02

    return round(max(tracked_platform_revenue, proxy_revenue), 2)


def get_top_performing_tutorials(limit: int = 5) -> List[Dict[str, Any]]:
    """Return top tutorials based on history performance score."""
    history = cargar_datos()
    ranked = sorted(history, key=lambda item: float(item.get("performance_score") or 0), reverse=True)
    return ranked[:limit]
