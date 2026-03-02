"""Dev.to publisher implementation."""

from __future__ import annotations

from typing import Any, Dict

import requests

from config import settings
from config.platforms import DevToConfig
from publishers.base_publisher import BasePublisher
from utils.logger import get_logger

logger = get_logger(__name__)


class DevToPublisher(BasePublisher):
    """Publisher for Dev.to API."""

    platform_name = "devto"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else DevToConfig().api_key

    def format_tutorial_for_devto(self, tutorial_data: Dict[str, Any]) -> str:
        """Convert tutorial payload to Dev.to markdown body."""
        return self._compose_markdown(tutorial_data)

    def publish(self, tutorial_data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Publish tutorial to Dev.to."""
        if not self.api_key:
            return {
                "success": False,
                "platform": self.platform_name,
                "error": "Missing DEVTO_API_KEY",
            }

        payload = {
            "article": {
                "title": tutorial_data.get("title") or tutorial_data.get("topic") or "Tutorial",
                "body_markdown": self.format_tutorial_for_devto(tutorial_data),
                "published": kwargs.get("published", True),
                "tags": [str(tag)[:20] for tag in tutorial_data.get("tags", [])[:4]],
            }
        }
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://dev.to/api/articles",
                json=payload,
                headers=headers,
                timeout=settings.REQUEST_TIMEOUT_S,
            )
            if response.status_code not in (200, 201):
                return {
                    "success": False,
                    "platform": self.platform_name,
                    "error": f"Dev.to API error: {response.status_code} {response.text[:200]}",
                }

            data = response.json() if response.text else {}
            result = {
                "success": True,
                "platform": self.platform_name,
                "url": data.get("url") or data.get("canonical_url"),
                "post_id": data.get("id"),
                "estimated_reads": int(data.get("page_views_count", 0) or 0),
                "estimated_revenue": 0.0,
            }
            self.track_publication(tutorial_data, result)
            return result
        except requests.RequestException as exc:
            logger.error("Dev.to publish failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "platform": self.platform_name,
                "error": str(exc),
            }

    def get_performance_metrics(self, post_id: str) -> Dict[str, Any]:
        """Return placeholder metrics for Dev.to."""
        return {
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "platform": self.platform_name,
            "note": "Dev.to metrics endpoint requires per-user strategy.",
        }
