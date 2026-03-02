"""Publisher registry and helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from publishers.blogger_publisher import BloggerPublisher
from publishers.devto_publisher import DevToPublisher
from publishers.hashnode_publisher import HashnodePublisher
from publishers.telegram_publisher import TelegramPublisher
from utils.logger import get_logger

logger = get_logger(__name__)


def create_publisher_registry() -> Dict[str, Any]:
    """Instantiate all available publishers."""
    return {
        "devto": DevToPublisher(),
        "hashnode": HashnodePublisher(),
        "telegram": TelegramPublisher(),
        "blogger": BloggerPublisher(),
    }


def publish_to_platforms(tutorial_data: Dict[str, Any], platforms: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Publish tutorial to selected platforms."""
    registry = create_publisher_registry()
    results: Dict[str, Dict[str, Any]] = {}

    for platform in platforms:
        key = str(platform).lower().strip()
        publisher = registry.get(key)
        if not publisher:
            results[key] = {
                "success": False,
                "platform": key,
                "error": "Platform not supported",
            }
            continue
        result = publisher.publish_with_retry(tutorial_data=tutorial_data)
        results[key] = result
        if result.get("success"):
            logger.info("Publish success platform=%s url=%s", key, result.get("url"))
        else:
            logger.warning("Publish failed platform=%s error=%s", key, result.get("error"))

    return results


def publish_to_devto(tutorial_data: Dict[str, Any]) -> Dict[str, Any]:
    return DevToPublisher().publish_with_retry(tutorial_data=tutorial_data)


def publish_to_hashnode(tutorial_data: Dict[str, Any]) -> Dict[str, Any]:
    return HashnodePublisher().publish_with_retry(tutorial_data=tutorial_data)


def publish_to_telegram(tutorial_data: Dict[str, Any]) -> Dict[str, Any]:
    return TelegramPublisher().publish_with_retry(tutorial_data=tutorial_data)


def publish_to_blogger(tutorial_data: Dict[str, Any]) -> Dict[str, Any]:
    return BloggerPublisher().publish_with_retry(tutorial_data=tutorial_data)
