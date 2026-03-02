"""Telegram channel publisher implementation."""

from __future__ import annotations

import re
from typing import Any, Dict

import requests

from config import settings
from config.platforms import TelegramConfig
from publishers.base_publisher import BasePublisher
from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramPublisher(BasePublisher):
    """Publisher for Telegram channel posts."""

    platform_name = "telegram"

    def __init__(self, bot_token: str | None = None, channel_id: str | None = None) -> None:
        cfg = TelegramConfig()
        self.bot_token = bot_token if bot_token is not None else cfg.bot_token
        self.channel_id = channel_id if channel_id is not None else cfg.channel_id

    def _short_summary(self, content: str, max_len: int = 260) -> str:
        no_code = re.sub(r"```.*?```", " ", content or "", flags=re.S)
        no_headings = re.sub(r"^#{1,6}\s*", "", no_code, flags=re.M)
        compact = " ".join(no_headings.split())
        if not compact:
            return "New hands-on developer tutorial is live."
        if len(compact) <= max_len:
            return compact
        return compact[: max_len - 3].rstrip() + "..."

    def _build_links_block(self, tutorial_data: Dict[str, Any]) -> str:
        urls = tutorial_data.get("urls", {})
        if not isinstance(urls, dict):
            return ""

        preferred = [("devto", "Dev.to"), ("hashnode", "Hashnode"), ("blogger", "Blogger")]
        lines = []
        for key, label in preferred:
            value = urls.get(key)
            if value:
                lines.append(f"- {label}: {value}")

        if not lines:
            return ""
        return "\n".join(lines)

    def _format_message(self, tutorial_data: Dict[str, Any]) -> str:
        title = str(tutorial_data.get("title") or tutorial_data.get("topic") or "Tutorial")
        summary = self._short_summary(str(tutorial_data.get("content", "")))
        links_block = self._build_links_block(tutorial_data)

        lines = [
            f"{title}",
            "",
            summary,
            "",
            "Read the full tutorial:",
        ]
        if links_block:
            lines.append(links_block)
        else:
            lines.append("- Full article link will be added after publication.")
        lines.extend(
            [
                "",
                self._sponsor_line(),
                "Subscribe for daily practical dev tutorials.",
                "#tutorial #dev #automation",
            ]
        )
        return "\n".join(lines)

    def _sponsor_line(self) -> str:
        if settings.SPONSORSHIP_PAGE_URL:
            return f"Sponsor/Partner: {settings.SPONSORSHIP_PAGE_URL}"
        if settings.BUSINESS_CONTACT_EMAIL:
            return f"Sponsor/Partner: {settings.BUSINESS_CONTACT_EMAIL}"
        return "Sponsor/Partner inquiries: DM this channel."

    def publish(self, tutorial_data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Publish markdown message to Telegram channel."""
        if not self.bot_token or not self.channel_id:
            return {
                "success": False,
                "platform": self.platform_name,
                "error": "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID",
            }

        payload = {
            "chat_id": self.channel_id,
            "text": self._format_message(tutorial_data),
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json=payload,
                timeout=settings.REQUEST_TIMEOUT_S,
            )
            if response.status_code != 200:
                return {
                    "success": False,
                    "platform": self.platform_name,
                    "error": f"Telegram API error: {response.status_code} {response.text[:200]}",
                }

            data = response.json().get("result", {})
            result = {
                "success": True,
                "platform": self.platform_name,
                "url": None,
                "post_id": data.get("message_id"),
                "estimated_reads": 10,
                "estimated_revenue": 0.2,
            }
            self.track_publication(tutorial_data, result)
            return result
        except requests.RequestException as exc:
            logger.error("Telegram publish failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "platform": self.platform_name,
                "error": str(exc),
            }

    def get_performance_metrics(self, post_id: str) -> Dict[str, Any]:
        """Return conservative Telegram estimate metrics."""
        estimated_reads = 50
        return {
            "estimated_reads": estimated_reads,
            "estimated_revenue": round(estimated_reads * 0.02, 2),
            "platform": self.platform_name,
        }
