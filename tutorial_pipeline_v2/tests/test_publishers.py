"""Tests for publisher formatting and config validation."""

from publishers.blogger_publisher import BloggerPublisher
from publishers.hashnode_publisher import HashnodePublisher


def test_hashnode_requires_credentials() -> None:
    """Hashnode publisher should fail clearly when credentials are missing."""
    publisher = HashnodePublisher(api_key="", publication_id="")
    result = publisher.publish({"title": "Test", "content": "Hello"})

    assert result["success"] is False
    assert "HASHNODE" in result["error"]


def test_blogger_requires_credentials() -> None:
    """Blogger publisher should fail clearly when credentials are missing."""
    publisher = BloggerPublisher(access_token="", blog_id="")
    result = publisher.publish({"title": "Test", "content": "Hello"})

    assert result["success"] is False
    assert "BLOGGER" in result["error"]


def test_blogger_formats_markdown_to_html() -> None:
    """Blogger formatter should transform markdown into HTML tags."""
    publisher = BloggerPublisher(access_token="token", blog_id="blog-id")
    tutorial = {
        "title": "Markdown Test",
        "content": "## Intro\n\n- item one\n- item two\n\n```python\nprint('hi')\n```",
    }

    html_content = publisher.format_tutorial_for_blogger(tutorial)

    assert "<h2>Intro</h2>" in html_content
    assert "<ul>" in html_content
    assert "<li>item one</li>" in html_content
    assert "<pre><code>" in html_content
