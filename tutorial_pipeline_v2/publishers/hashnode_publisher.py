"""Hashnode publisher implementation via GraphQL API."""

from __future__ import annotations

from typing import Any, Dict, List

import requests

from config import settings
from config.platforms import HashnodeConfig
from publishers.base_publisher import BasePublisher
from utils.logger import get_logger

logger = get_logger(__name__)

HASHNODE_ENDPOINT = "https://gql.hashnode.com"


class HashnodePublisher(BasePublisher):
    """Publisher for Hashnode GraphQL API."""

    platform_name = "hashnode"

    def __init__(self, api_key: str | None = None, publication_id: str | None = None) -> None:
        cfg = HashnodeConfig()
        self.api_key = api_key if api_key is not None else cfg.api_key
        self.publication_id = publication_id if publication_id is not None else cfg.publication_id

    def _format_tags(self, tutorial_data: Dict[str, Any]) -> List[Dict[str, str]]:
        tags = tutorial_data.get("tags", [])
        formatted: List[Dict[str, str]] = []

        for raw_tag in tags[:5] if isinstance(tags, list) else []:
            tag = str(raw_tag).strip().lower().replace(" ", "-")
            if not tag:
                continue
            formatted.append({"name": tag.replace("-", " "), "slug": tag})

        return formatted

    def publish(self, tutorial_data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Publish tutorial to Hashnode using `publishPost` mutation."""
        if not self.api_key or not self.publication_id:
            return {
                "success": False,
                "platform": self.platform_name,
                "error": "Missing HASHNODE_API_KEY or HASHNODE_PUBLICATION_ID",
            }

        mutation = """
        mutation PublishPost($input: PublishPostInput!) {
          publishPost(input: $input) {
            post {
              id
              slug
              url
            }
          }
        }
        """

        input_payload = {
            "title": tutorial_data.get("title") or tutorial_data.get("topic") or "Tutorial",
            "contentMarkdown": self._compose_markdown(tutorial_data),
            "publicationId": self.publication_id,
            "tags": self._format_tags(tutorial_data),
        }

        payload = {
            "query": mutation,
            "variables": {"input": input_payload},
        }
        auth_value = self.api_key.strip()
        if auth_value and not auth_value.lower().startswith("bearer "):
            auth_value = f"Bearer {auth_value}"
        headers = {
            "Authorization": auth_value,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                HASHNODE_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=settings.REQUEST_TIMEOUT_S,
            )
            if response.status_code != 200:
                return {
                    "success": False,
                    "platform": self.platform_name,
                    "error": f"Hashnode API error: {response.status_code} {response.text[:200]}",
                }

            data = response.json() if response.text else {}
            if data.get("errors"):
                return {
                    "success": False,
                    "platform": self.platform_name,
                    "error": f"Hashnode GraphQL error: {data['errors'][0].get('message', 'unknown error')}",
                }

            post = data.get("data", {}).get("publishPost", {}).get("post", {})
            result = {
                "success": True,
                "platform": self.platform_name,
                "url": post.get("url"),
                "post_id": post.get("id") or post.get("slug"),
                "estimated_reads": 0,
                "estimated_revenue": 0.0,
            }
            self.track_publication(tutorial_data, result)
            return result
        except requests.RequestException as exc:
            logger.error("Hashnode publish failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "platform": self.platform_name,
                "error": str(exc),
            }

    def get_performance_metrics(self, post_id: str) -> Dict[str, Any]:
        """Return placeholder metrics for Hashnode."""
        return {
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "platform": self.platform_name,
            "note": "Hashnode metrics require a separate analytics strategy.",
        }
