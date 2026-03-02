"""Path helpers and directory bootstrap for Tutorial Pipeline v2."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]


def p(*parts: str) -> str:
    """Return absolute path from project root."""
    return str(BASE_DIR.joinpath(*parts))


DIR_TUTORIALS = p("tutorials_generated")
DIR_CACHE = p("cache")
DIR_ANALYTICS = p("analytics")
DIR_TEMPLATES = p("templates")
DIR_HISTORY = p("history")
DIR_LOGS = p("logs")
DIR_DATA = p("data")

DATA_HISTORY_FILE = p("data", "history.json")
DATA_ANALYTICS_FILE = p("data", "analytics.json")
DATA_TRENDS_CACHE_FILE = p("data", "trends_cache.json")
DATA_PERFORMANCE_FILE = p("data", "performance.json")
DATA_QUEUE_FILE = p("data", "publication_queue.json")
DATA_SPONSOR_LEADS_FILE = p("data", "sponsor_leads.csv")
DATA_SPONSOR_OUTREACH_HISTORY_FILE = p("data", "sponsor_outreach_history.json")


def _ensure_json_file(path: str, default_payload: object) -> None:
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(default_payload, handle, ensure_ascii=False, indent=2)


def ensure_dirs(extra_dirs: Iterable[str] | None = None) -> None:
    """Create core directories and seed data files."""
    core_dirs = [
        DIR_TUTORIALS,
        DIR_CACHE,
        DIR_ANALYTICS,
        DIR_TEMPLATES,
        DIR_HISTORY,
        DIR_LOGS,
        DIR_DATA,
    ]
    if extra_dirs:
        core_dirs.extend(extra_dirs)

    for directory in core_dirs:
        os.makedirs(directory, exist_ok=True)

    _ensure_json_file(DATA_HISTORY_FILE, [])
    _ensure_json_file(DATA_ANALYTICS_FILE, {})
    _ensure_json_file(DATA_TRENDS_CACHE_FILE, {})
    _ensure_json_file(DATA_PERFORMANCE_FILE, {})
    _ensure_json_file(DATA_QUEUE_FILE, [])
    _ensure_json_file(DATA_SPONSOR_OUTREACH_HISTORY_FILE, [])
