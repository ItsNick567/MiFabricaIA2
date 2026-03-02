"""Platform-specific configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import settings


@dataclass(slots=True)
class DevToConfig:
    api_key: str = settings.DEVTO_API_KEY


@dataclass(slots=True)
class HashnodeConfig:
    api_key: str = settings.HASHNODE_API_KEY
    publication_id: str = settings.HASHNODE_PUBLICATION_ID


@dataclass(slots=True)
class TelegramConfig:
    bot_token: str = settings.TELEGRAM_BOT_TOKEN
    channel_id: str = settings.TELEGRAM_CHANNEL_ID


@dataclass(slots=True)
class BloggerConfig:
    access_token: str = settings.BLOGGER_ACCESS_TOKEN
    blog_id: str = settings.BLOGGER_BLOG_ID
    client_id: str = settings.BLOGGER_CLIENT_ID
    client_secret: str = settings.BLOGGER_CLIENT_SECRET
    refresh_token: str = settings.BLOGGER_REFRESH_TOKEN


@dataclass(slots=True)
class PlatformConfig:
    devto: DevToConfig = field(default_factory=DevToConfig)
    hashnode: HashnodeConfig = field(default_factory=HashnodeConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    blogger: BloggerConfig = field(default_factory=BloggerConfig)


def get_platform_config() -> PlatformConfig:
    """Return all platform settings in one object."""
    return PlatformConfig()
