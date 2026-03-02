"""Blogger publisher implementation using Blogger API v3."""

from __future__ import annotations

import html
import re
from typing import Any, Dict

import requests

from config import settings
from config.platforms import BloggerConfig
from publishers.base_publisher import BasePublisher
from utils.logger import get_logger

logger = get_logger(__name__)


class BloggerPublisher(BasePublisher):
    """Publisher for Google Blogger API."""

    platform_name = "blogger"

    def __init__(
        self,
        access_token: str | None = None,
        blog_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        cfg = BloggerConfig()
        self.access_token = access_token if access_token is not None else cfg.access_token
        self.blog_id = blog_id if blog_id is not None else cfg.blog_id
        self.client_id = client_id if client_id is not None else cfg.client_id
        self.client_secret = client_secret if client_secret is not None else cfg.client_secret
        self.refresh_token = refresh_token if refresh_token is not None else cfg.refresh_token

    def _can_refresh(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _refresh_access_token(self) -> bool:
        """Refresh Blogger OAuth access token using refresh token."""
        if not self._can_refresh():
            return False

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data=payload,
                timeout=settings.REQUEST_TIMEOUT_S,
            )
            if response.status_code != 200:
                logger.warning("Blogger token refresh failed status=%s", response.status_code)
                return False

            data = response.json() if response.text else {}
            token = str(data.get("access_token", "")).strip()
            if not token:
                logger.warning("Blogger token refresh returned empty access_token")
                return False

            self.access_token = token
            return True
        except requests.RequestException as exc:
            logger.warning("Blogger token refresh request failed: %s", exc)
            return False

    def _request_with_refresh(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=settings.REQUEST_TIMEOUT_S,
            **kwargs,
        )
        if response.status_code == 401 and self._refresh_access_token():
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=settings.REQUEST_TIMEOUT_S,
                **kwargs,
            )
        return response

    def _inline_markdown_to_html(self, text: str) -> str:
        escaped = html.escape(text or "", quote=False)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
        return escaped

    def _extract_labels(self, tutorial_data: Dict[str, Any], limit: int = 8) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()

        raw_tags = tutorial_data.get("tags", [])
        tags = raw_tags if isinstance(raw_tags, list) else []
        for tag in tags:
            cleaned = re.sub(r"[^a-zA-Z0-9+\-# ]+", "", str(tag)).strip().lower()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            labels.append(cleaned[:30])
            if len(labels) >= limit:
                return labels

        title = str(tutorial_data.get("title") or tutorial_data.get("topic") or "")
        for token in re.findall(r"[a-zA-Z0-9+#-]{4,}", title.lower()):
            if token in seen:
                continue
            seen.add(token)
            labels.append(token[:30])
            if len(labels) >= limit:
                break
        return labels

    def _markdown_to_html(self, markdown_text: str) -> str:
        normalized = (markdown_text or "").replace("\r\n", "\n")
        code_blocks: Dict[str, str] = {}

        def _store_code_block(match: re.Match[str]) -> str:
            token = f"@@CODEBLOCK_{len(code_blocks)}@@"
            code_text = html.escape(match.group(1).strip("\n"), quote=False)
            code_blocks[token] = f"<pre><code>{code_text}</code></pre>"
            return token

        normalized = re.sub(r"```[a-zA-Z0-9_+\-]*\n(.*?)```", _store_code_block, normalized, flags=re.S)
        lines = normalized.split("\n")

        html_lines: list[str] = []
        in_ul = False
        in_ol = False

        def _close_lists() -> None:
            nonlocal in_ul, in_ol
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                _close_lists()
                continue

            if stripped in code_blocks:
                _close_lists()
                html_lines.append(stripped)
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading_match:
                _close_lists()
                level = len(heading_match.group(1))
                title = self._inline_markdown_to_html(heading_match.group(2).strip())
                html_lines.append(f"<h{level}>{title}</h{level}>")
                continue

            ul_match = re.match(r"^[-*]\s+(.*)$", stripped)
            if ul_match:
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False
                if not in_ul:
                    html_lines.append("<ul>")
                    in_ul = True
                html_lines.append(f"<li>{self._inline_markdown_to_html(ul_match.group(1).strip())}</li>")
                continue

            ol_match = re.match(r"^\d+\.\s+(.*)$", stripped)
            if ol_match:
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                if not in_ol:
                    html_lines.append("<ol>")
                    in_ol = True
                html_lines.append(f"<li>{self._inline_markdown_to_html(ol_match.group(1).strip())}</li>")
                continue

            _close_lists()
            html_lines.append(f"<p>{self._inline_markdown_to_html(stripped)}</p>")

        _close_lists()
        output = "\n".join(html_lines)
        for token, code_html in code_blocks.items():
            output = output.replace(token, code_html)
        return output

    def format_tutorial_for_blogger(self, tutorial_data: Dict[str, Any]) -> str:
        """Convert markdown tutorial payload to Blogger-compatible HTML."""
        markdown_text = self._compose_markdown(tutorial_data)
        return self._markdown_to_html(markdown_text)

    def resolve_post_id_from_url(self, post_url: str) -> str | None:
        """Resolve Blogger post ID from a full post URL path."""
        if not self.blog_id or not post_url:
            return None
        if not self.access_token and not self._refresh_access_token():
            return None

        path_match = re.match(r"^https?://[^/]+(/.*)$", post_url.strip())
        if not path_match:
            return None
        path = path_match.group(1)
        if not path.startswith("/"):
            path = "/" + path

        endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts/bypath"
        try:
            response = self._request_with_refresh("GET", endpoint, params={"path": path})
            if response.status_code != 200:
                logger.warning("Could not resolve Blogger post id from url=%s status=%s", post_url, response.status_code)
                return None
            payload = response.json() if response.text else {}
            post_id = payload.get("id")
            return str(post_id) if post_id else None
        except requests.RequestException as exc:
            logger.warning("Failed to resolve Blogger post id url=%s error=%s", post_url, exc)
            return None

    def update_post(self, post_id: str, tutorial_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing Blogger post with reformatted HTML content."""
        if not self.blog_id:
            return {"success": False, "platform": self.platform_name, "error": "Missing BLOGGER_BLOG_ID"}
        if not post_id:
            return {"success": False, "platform": self.platform_name, "error": "Missing post_id"}
        if not self.access_token and not self._refresh_access_token():
            return {
                "success": False,
                "platform": self.platform_name,
                "error": "Missing BLOGGER_ACCESS_TOKEN and could not refresh token",
            }

        payload = {
            "kind": "blogger#post",
            "id": str(post_id),
            "title": tutorial_data.get("title") or tutorial_data.get("topic") or "Tutorial",
            "content": self.format_tutorial_for_blogger(tutorial_data),
            "labels": self._extract_labels(tutorial_data),
        }
        endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts/{post_id}"
        try:
            response = self._request_with_refresh(
                "PUT",
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code != 200:
                return {
                    "success": False,
                    "platform": self.platform_name,
                    "error": f"Blogger update error: {response.status_code} {response.text[:200]}",
                }

            data = response.json() if response.text else {}
            return {
                "success": True,
                "platform": self.platform_name,
                "url": data.get("url"),
                "post_id": data.get("id"),
            }
        except requests.RequestException as exc:
            return {"success": False, "platform": self.platform_name, "error": str(exc)}

    def publish(self, tutorial_data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Publish tutorial post to Blogger."""
        if not self.blog_id:
            return {
                "success": False,
                "platform": self.platform_name,
                "error": "Missing BLOGGER_BLOG_ID",
            }

        if not self.access_token and not self._refresh_access_token():
            return {
                "success": False,
                "platform": self.platform_name,
                "error": "Missing BLOGGER_ACCESS_TOKEN and could not refresh token",
            }

        payload = {
            "kind": "blogger#post",
            "title": tutorial_data.get("title") or tutorial_data.get("topic") or "Tutorial",
            "content": self.format_tutorial_for_blogger(tutorial_data),
            "labels": self._extract_labels(tutorial_data),
        }
        params = {
            "isDraft": str(kwargs.get("is_draft", False)).lower(),
        }

        def _do_publish_request() -> requests.Response:
            return self._request_with_refresh(
                "POST",
                f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts/",
                params=params,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        try:
            response = _do_publish_request()
            if response.status_code not in (200, 201):
                return {
                    "success": False,
                    "platform": self.platform_name,
                    "error": f"Blogger API error: {response.status_code} {response.text[:200]}",
                }

            data = response.json() if response.text else {}
            result = {
                "success": True,
                "platform": self.platform_name,
                "url": data.get("url"),
                "post_id": data.get("id"),
                "estimated_reads": 0,
                "estimated_revenue": 0.0,
            }
            self.track_publication(tutorial_data, result)
            return result
        except requests.RequestException as exc:
            logger.error("Blogger publish failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "platform": self.platform_name,
                "error": str(exc),
            }

    def get_performance_metrics(self, post_id: str) -> Dict[str, Any]:
        """Return placeholder metrics for Blogger."""
        return {
            "estimated_reads": 0,
            "estimated_revenue": 0.0,
            "platform": self.platform_name,
            "note": "Blogger metrics depend on linked Analytics/AdSense.",
        }
