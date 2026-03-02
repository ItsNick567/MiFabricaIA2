"""Global settings for Tutorial Pipeline v2."""

from __future__ import annotations

import os
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


PROJECT_NAME = "Tutorial Pipeline v2"
PROJECT_VERSION = "2.0.0"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_list(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


# LLMs
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:14b")
LOCAL_LLM_STRICT = _as_bool(os.getenv("LOCAL_LLM_STRICT", "0"), default=False)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

LLM_ENGINE_PRIMARY = os.getenv("LLM_ENGINE_PRIMARY", "Groq")
LLM_ENGINE_SECONDARY = os.getenv("LLM_ENGINE_SECONDARY", "Local (Ollama)")
LLM_ENGINE_FALLBACK = os.getenv("LLM_ENGINE_FALLBACK", "Gemini (GRATIS)")

# Publishing platforms
DEVTO_API_KEY = os.getenv("DEVTO_API_KEY", "")
HASHNODE_API_KEY = os.getenv("HASHNODE_API_KEY", "")
HASHNODE_PUBLICATION_ID = os.getenv("HASHNODE_PUBLICATION_ID", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

BLOGGER_ACCESS_TOKEN = os.getenv("BLOGGER_ACCESS_TOKEN", "")
BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "")
BLOGGER_CLIENT_ID = os.getenv("BLOGGER_CLIENT_ID", "")
BLOGGER_CLIENT_SECRET = os.getenv("BLOGGER_CLIENT_SECRET", "")
BLOGGER_REFRESH_TOKEN = os.getenv("BLOGGER_REFRESH_TOKEN", "")

# Content and automation
AUTO_GENERATE_ENABLED = _as_bool(os.getenv("AUTO_GENERATE_ENABLED", "false"), default=False)
AUTO_GENERATE_PER_DAY = _as_int(os.getenv("AUTO_GENERATE_PER_DAY", "3"), default=3)
AUTO_GENERATE_PER_WEEK = AUTO_GENERATE_PER_DAY  # Backward compatibility for existing UI.
DEFAULT_LENGTH = os.getenv("DEFAULT_LENGTH", "medium")
PRIORITY_CATEGORIES = _as_list(
    os.getenv("PRIORITY_CATEGORIES", "python,javascript,react,git,docker"),
    ["python", "javascript", "react", "git", "docker"],
)
FORCE_ENGLISH = _as_bool(os.getenv("FORCE_ENGLISH", "true"), default=True)
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
TRENDS_UPDATE_HOUR = _as_int(os.getenv("TRENDS_UPDATE_HOUR", "2"), default=2)
AUTO_PUBLISH_TIMES = _as_list(os.getenv("AUTO_PUBLISH_TIMES", "09:00,14:00,20:00"), ["09:00", "14:00", "20:00"])
PIPELINE_TIMEZONE = os.getenv("PIPELINE_TIMEZONE", "America/Santiago").strip()
CRON_WINDOW_MINUTES = _as_int(os.getenv("CRON_WINDOW_MINUTES", "15"), default=15)

# Growth and monetization funnel
SPONSOR_CTA_ENABLED = _as_bool(os.getenv("SPONSOR_CTA_ENABLED", "true"), default=True)
BUSINESS_CONTACT_EMAIL = os.getenv("BUSINESS_CONTACT_EMAIL", "").strip()
SPONSORSHIP_PAGE_URL = os.getenv("SPONSORSHIP_PAGE_URL", "").strip()
NEWSLETTER_URL = os.getenv("NEWSLETTER_URL", "").strip()
COMMUNITY_URL = os.getenv("COMMUNITY_URL", "").strip()
SPONSOR_CTA_TEXT = os.getenv(
    "SPONSOR_CTA_TEXT",
    "Want weekly practical tutorials and collaboration opportunities?",
).strip()

# Sponsor discovery and outreach bot
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
SPONSOR_SEARCH_KEYWORDS = _as_list(
    os.getenv("SPONSOR_SEARCH_KEYWORDS", "ai,automation,developer tools,devops,testing,api,saas"),
    ["ai", "automation", "developer tools", "devops", "testing", "api", "saas"],
)
SPONSOR_HUNTER_MAX_LEADS = _as_int(os.getenv("SPONSOR_HUNTER_MAX_LEADS", "30"), default=30)
SPONSOR_MIN_SCORE = _as_int(os.getenv("SPONSOR_MIN_SCORE", "35"), default=35)

OUTREACH_SEND_ENABLED = _as_bool(os.getenv("OUTREACH_SEND_ENABLED", "false"), default=False)
OUTREACH_MAX_EMAILS_PER_RUN = _as_int(os.getenv("OUTREACH_MAX_EMAILS_PER_RUN", "10"), default=10)
OUTREACH_SENDER_NAME = os.getenv("OUTREACH_SENDER_NAME", "").strip()
OUTREACH_FROM_EMAIL = os.getenv("OUTREACH_FROM_EMAIL", "").strip()
OUTREACH_REPLY_TO = os.getenv("OUTREACH_REPLY_TO", "").strip()
OUTREACH_SITE_OR_PROFILE = os.getenv("OUTREACH_SITE_OR_PROFILE", "").strip()

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _as_int(os.getenv("SMTP_PORT", "587"), default=587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_USE_TLS = _as_bool(os.getenv("SMTP_USE_TLS", "true"), default=True)
SMTP_USE_SSL = _as_bool(os.getenv("SMTP_USE_SSL", "false"), default=False)

# Trends and cache
TRENDS_CACHE_DURATION_HOURS = _as_int(os.getenv("TRENDS_CACHE_DURATION", "6"), default=6)
TREND_SOURCES = _as_list(
    os.getenv("TREND_SOURCES", "devto,hashnode,github,reddit"),
    ["devto", "hashnode", "github", "reddit"],
)

ENABLE_CONTENT_CACHE = _as_bool(os.getenv("ENABLE_CONTENT_CACHE", "true"), default=True)
CACHE_DURATION_HOURS = _as_int(os.getenv("CACHE_DURATION", "24"), default=24)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Runtime behavior
REQUEST_TIMEOUT_S = _as_float(os.getenv("REQUEST_TIMEOUT_S", "30"), default=30.0)
MAX_RETRIES = _as_int(os.getenv("MAX_RETRIES", "3"), default=3)


def get_llm_priority() -> List[str]:
    """Return configured LLM fallback order."""
    return [LLM_ENGINE_PRIMARY, LLM_ENGINE_SECONDARY, LLM_ENGINE_FALLBACK]


def to_dict() -> Dict[str, object]:
    """Expose selected settings for diagnostics."""
    return {
        "project": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "llm_priority": get_llm_priority(),
        "default_length": DEFAULT_LENGTH,
        "default_language": DEFAULT_LANGUAGE,
        "force_english": FORCE_ENGLISH,
        "priority_categories": PRIORITY_CATEGORIES,
        "trends_cache_hours": TRENDS_CACHE_DURATION_HOURS,
        "enable_content_cache": ENABLE_CONTENT_CACHE,
        "cache_hours": CACHE_DURATION_HOURS,
        "log_level": LOG_LEVEL,
    }
