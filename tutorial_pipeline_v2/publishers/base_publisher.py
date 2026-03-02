"""Base publisher abstractions and retry behavior."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def retry_on_failure(max_retries: int = settings.MAX_RETRIES, delay_seconds: int = 2) -> Callable:
    """Decorator to retry publisher operations."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            last_result: Dict[str, Any] = {"success": False, "error": "unknown"}
            for attempt in range(1, max_retries + 1):
                result = func(*args, **kwargs)
                if result.get("success"):
                    return result
                last_result = result
                logger.warning("Publish attempt %s/%s failed: %s", attempt, max_retries, result.get("error"))
                if attempt < max_retries:
                    time.sleep(delay_seconds)
            return last_result

        return wrapper

    return decorator


class BasePublisher(ABC):
    """Base class for all content publishers."""

    platform_name = "unknown"

    @abstractmethod
    def publish(self, tutorial_data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Publish tutorial and return structured result."""

    @retry_on_failure(max_retries=settings.MAX_RETRIES)
    def publish_with_retry(self, tutorial_data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Retry wrapper around publish."""
        return self.publish(tutorial_data=tutorial_data, **kwargs)

    def track_publication(self, tutorial_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Track successful publication event in analytics."""
        if not result.get("success"):
            return
        from core.analytics_engine import update_analytics_for_platform

        update_analytics_for_platform(
            platform=self.platform_name,
            tutorial_id=str(tutorial_data.get("id", "")),
            url=result.get("url"),
            estimated_reads=int(result.get("estimated_reads", 0) or 0),
            estimated_revenue=float(result.get("estimated_revenue", 0.0) or 0.0),
        )

    @abstractmethod
    def get_performance_metrics(self, post_id: str) -> Dict[str, Any]:
        """Return platform-specific performance metrics."""

    def _compose_markdown(self, tutorial_data: Dict[str, Any]) -> str:
        title = str(tutorial_data.get("title", "Tutorial"))
        content = str(tutorial_data.get("content", ""))
        markdown = ""
        skip_footer = bool(tutorial_data.get("skip_growth_footer", False))

        if content:
            markdown = f"# {title}\n\n{content}" if not content.strip().startswith("#") else content
            return markdown.strip() if skip_footer else self._append_growth_footer(markdown)

        sections = tutorial_data.get("sections", [])
        lines = [f"# {title}", ""]
        intro = str(tutorial_data.get("intro", "")).strip()
        if intro:
            lines.append(intro)
            lines.append("")

        for section in sections:
            lines.append(f"## {section.get('title', 'Section')}")
            lines.append(str(section.get("content", "")))
            lines.append("")

        conclusion = str(tutorial_data.get("conclusion", "")).strip()
        if conclusion:
            lines.append("## Conclusion")
            lines.append(conclusion)

        markdown = "\n".join(lines).strip()
        return markdown.strip() if skip_footer else self._append_growth_footer(markdown)

    def _append_growth_footer(self, markdown: str) -> str:
        if not settings.SPONSOR_CTA_ENABLED:
            return markdown.strip()
        if "## Sponsor & Subscribe" in markdown:
            return markdown.strip()

        items: list[str] = []
        if settings.NEWSLETTER_URL:
            items.append(f"- Newsletter: {settings.NEWSLETTER_URL}")
        if settings.COMMUNITY_URL:
            items.append(f"- Community: {settings.COMMUNITY_URL}")
        if settings.SPONSORSHIP_PAGE_URL:
            items.append(f"- Sponsorship details: {settings.SPONSORSHIP_PAGE_URL}")
        if settings.BUSINESS_CONTACT_EMAIL:
            items.append(f"- Contact: {settings.BUSINESS_CONTACT_EMAIL}")

        if not items:
            return markdown.strip()

        footer_lines = [
            "",
            "---",
            "",
            "## Sponsor & Subscribe",
            settings.SPONSOR_CTA_TEXT or "Want weekly practical tutorials and collaboration opportunities?",
            "",
            *items,
        ]
        return (markdown.rstrip() + "\n" + "\n".join(footer_lines)).strip()
