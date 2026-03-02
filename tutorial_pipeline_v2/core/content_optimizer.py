"""Data-driven content optimization and suggestions."""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Dict, List

from core.trend_analyzer import get_trends_cached
from utils.historial import cargar_datos


def _safe_score(item: Dict[str, Any]) -> float:
    return float(item.get("performance_score") or 0.0)


def calculate_optimal_length(performance_data: List[Dict[str, Any]]) -> int:
    """Calculate median word count from historical winners."""
    lengths = [int(item.get("length", 0) or 0) for item in performance_data if int(item.get("length", 0) or 0) > 0]
    if not lengths:
        return 1200
    return int(median(lengths))


def find_most_effective_tags(performance_data: List[Dict[str, Any]], top_k: int = 15) -> List[str]:
    """Find tags correlated with high performance."""
    weights: Dict[str, float] = defaultdict(float)
    for item in performance_data:
        score = float(item.get("score") or 0)
        for tag in item.get("tags", []):
            weights[str(tag).lower()] += score
    ranked = sorted(weights.items(), key=lambda item: item[1], reverse=True)
    return [tag for tag, _ in ranked[:top_k]]


def analyze_platform_performance(performance_data: List[Dict[str, Any]]) -> List[str]:
    """Rank platforms by average score."""
    buckets: Dict[str, List[float]] = defaultdict(list)
    for item in performance_data:
        score = float(item.get("score") or 0)
        for platform in item.get("platforms", []):
            buckets[str(platform).lower()].append(score)

    platform_avg = []
    for platform, scores in buckets.items():
        if not scores:
            continue
        platform_avg.append((platform, sum(scores) / len(scores)))

    platform_avg.sort(key=lambda it: it[1], reverse=True)
    return [platform for platform, _ in platform_avg]


def analyze_historical_performance() -> Dict[str, Any]:
    """Inspect tutorial history and extract optimization insights."""
    history = cargar_datos()
    performance_data: List[Dict[str, Any]] = []

    for item in history:
        score = item.get("performance_score")
        if score is None:
            continue
        performance_data.append(
            {
                "id": item.get("id"),
                "topic": item.get("topic", ""),
                "score": float(score or 0),
                "length": int(item.get("word_count", 0) or 0),
                "tags": item.get("tags", []),
                "platforms": item.get("platforms_published", []),
            }
        )

    if not performance_data:
        return {
            "best_topics": [],
            "optimal_length": 1200,
            "recommended_tags": [],
            "best_platforms": ["devto", "hashnode", "telegram", "blogger"],
        }

    best_topics = sorted(performance_data, key=lambda row: row["score"], reverse=True)[:10]
    optimal_length = calculate_optimal_length(performance_data)
    best_tags = find_most_effective_tags(performance_data)

    return {
        "best_topics": best_topics,
        "optimal_length": optimal_length,
        "recommended_tags": best_tags,
        "best_platforms": analyze_platform_performance(performance_data) or ["devto", "hashnode"],
    }


def suggest_improvements(tutorial_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate optimization tips from historical behavior."""
    suggestions: List[Dict[str, str]] = []

    historical = analyze_historical_performance()
    word_count = int(tutorial_data.get("word_count", 0) or 0)

    optimal = int(historical["optimal_length"])
    if abs(word_count - optimal) > 200:
        suggestions.append(
            {
                "type": "length",
                "message": f"Longitud optima: ~{optimal} palabras (actual: {word_count})",
                "priority": "medium",
            }
        )

    current_tags = {str(tag).lower() for tag in tutorial_data.get("tags", [])}
    recommended_tags = {str(tag).lower() for tag in historical.get("recommended_tags", [])[:5]}
    missing = sorted(recommended_tags - current_tags)
    if missing:
        suggestions.append(
            {
                "type": "tags",
                "message": f"Considera agregar tags: {', '.join(missing)}",
                "priority": "low",
            }
        )

    best_platforms = historical.get("best_platforms", [])
    current_platforms = {str(platform).lower() for platform in tutorial_data.get("platforms", [])}
    if best_platforms:
        winner = str(best_platforms[0]).lower()
        if winner and winner not in current_platforms:
            suggestions.append(
                {
                    "type": "platform",
                    "message": f"{winner.capitalize()} muestra mejor rendimiento para contenido similar.",
                    "priority": "high",
                }
            )

    return suggestions


def categorize_topic(topic: str) -> str:
    """Guess category from topic text."""
    low = str(topic).lower()
    mapping = {
        "python": ["python", "pandas", "fastapi", "django"],
        "javascript": ["javascript", "node", "react", "next"],
        "devops": ["docker", "kubernetes", "terraform", "ci/cd", "git"],
        "ai": ["llm", "ai", "machine learning", "prompt"],
    }
    for category, keywords in mapping.items():
        if any(keyword in low for keyword in keywords):
            return category
    return "general"


def estimate_difficulty(topic: str) -> str:
    """Estimate topic difficulty from keyword signals."""
    low = str(topic).lower()
    advanced_signals = ["architecture", "performance", "distributed", "kubernetes", "compiler"]
    basic_signals = ["intro", "basics", "primer", "quickstart", "getting started"]

    if any(signal in low for signal in advanced_signals):
        return "advanced"
    if any(signal in low for signal in basic_signals):
        return "beginner"
    return "intermediate"


def generate_content_suggestions(limit: int = 15) -> List[Dict[str, Any]]:
    """Build idea backlog combining trends and uncovered topics."""
    trends = get_trends_cached("programming")
    history = cargar_datos()
    covered_topics = {str(item.get("topic", "")).strip().lower() for item in history}

    suggestions: List[Dict[str, Any]] = []
    for topic, score in trends:
        clean_topic = str(topic).strip()
        if not clean_topic or clean_topic.lower() in covered_topics:
            continue
        suggestions.append(
            {
                "id": abs(hash(clean_topic)) % (10**10),
                "title": f"Tutorial: {clean_topic}",
                "topic": clean_topic,
                "category": categorize_topic(clean_topic),
                "difficulty": estimate_difficulty(clean_topic),
                "trend_score": int(score),
                "reason": "Trending y no cubierto aun",
            }
        )

    suggestions.sort(key=lambda item: item["trend_score"], reverse=True)
    return suggestions[:limit]


def find_related_topics(topic: str) -> List[str]:
    """Generate adjacent topic ideas for series continuation."""
    low = str(topic).lower()
    relations = {
        "python": ["python virtual environments", "python typing", "python testing with pytest"],
        "react": ["react server components", "react performance tuning", "react state management"],
        "git": ["git hooks", "git rebase workflows", "git bisect guide"],
        "docker": ["docker networking", "docker compose patterns", "docker security basics"],
    }
    for key, values in relations.items():
        if key in low:
            return values
    return [f"advanced {topic}", f"best practices for {topic}"]


def detect_content_opportunities(limit: int = 20) -> List[Dict[str, Any]]:
    """Find high-value opportunities from trends + best performers."""
    opportunities: List[Dict[str, Any]] = []

    trends = get_trends_cached("programming")
    history = cargar_datos()
    covered = {str(item.get("topic", "")).strip().lower() for item in history}

    for topic, score in trends:
        if topic.lower() not in covered and int(score) > 75:
            opportunities.append(
                {
                    "type": "trending_gap",
                    "topic": topic,
                    "score": int(score),
                    "reason": "Trending y no cubierto",
                }
            )

    top_posts = sorted(history, key=_safe_score, reverse=True)[:5]
    for post in top_posts:
        related_topics = find_related_topics(str(post.get("topic", "")))
        for related in related_topics:
            if related.lower() in covered:
                continue
            opportunities.append(
                {
                    "type": "series_continuation",
                    "topic": related,
                    "score": int(float(post.get("performance_score") or 0) * 0.8),
                    "reason": f"Relacionado a tu exito: {post.get('title', 'tutorial')}",
                }
            )

    opportunities.sort(key=lambda item: item["score"], reverse=True)
    return opportunities[:limit]
