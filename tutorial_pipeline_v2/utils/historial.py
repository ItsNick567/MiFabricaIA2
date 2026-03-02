"""History management for generated and published tutorials."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from utils.logger import get_logger
from utils.paths import DATA_HISTORY_FILE, ensure_dirs

logger = get_logger(__name__)

HISTORIAL_PATH = DATA_HISTORY_FILE
MAX_AGE_EMPTY_DAYS = 30
GRACE_SECONDS = 10 * 60


def ensure_item_id(item: Dict[str, Any]) -> str:
    """Ensure an item has a stable id."""
    if item.get("id"):
        return str(item["id"])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_id = f"{ts}_{uuid.uuid4().hex[:6]}"
    item["id"] = new_id
    return new_id


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Apply default fields for v2 history schema."""
    ensure_item_id(item)
    item.setdefault("timestamp", datetime.now().isoformat())
    item.setdefault("topic", "")
    item.setdefault("title", "")
    item.setdefault("platforms_published", [])
    item.setdefault("urls", {})
    item.setdefault("llm_used", "unknown")
    item.setdefault("generation_time", 0.0)
    item.setdefault("word_count", 0)
    item.setdefault("estimated_reads", 0)
    item.setdefault("estimated_revenue", 0.0)
    item.setdefault("performance_score", None)
    item.setdefault("tags", [])
    return item


def _flatten_if_legacy(data: Any) -> List[Dict[str, Any]]:
    """Convert old dict-based history format to list."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items: List[Dict[str, Any]] = []
        for values in data.values():
            if isinstance(values, list):
                items.extend(item for item in values if isinstance(item, dict))
        return items
    return []


def limpiar_historial(datos: Any) -> List[Dict[str, Any]]:
    """Remove stale/empty records while preserving meaningful content."""
    items = _flatten_if_legacy(datos)
    now = time.time()
    cleaned: List[Dict[str, Any]] = []

    for raw_item in items:
        item = _normalize_item(dict(raw_item))
        has_content = any(
            bool(str(item.get(field, "")).strip())
            for field in ("topic", "title", "content", "summary")
        )
        has_urls = bool(item.get("urls"))

        ts_text = str(item.get("timestamp", "")).strip()
        age_seconds = None
        if ts_text:
            try:
                age_seconds = now - datetime.fromisoformat(ts_text).timestamp()
            except ValueError:
                age_seconds = None

        if has_content or has_urls:
            cleaned.append(item)
            continue
        if age_seconds is None or age_seconds <= GRACE_SECONDS:
            cleaned.append(item)
            continue
        if age_seconds > MAX_AGE_EMPTY_DAYS * 86400:
            continue
        cleaned.append(item)

    return cleaned


def cargar_datos() -> List[Dict[str, Any]]:
    """Load history items."""
    ensure_dirs()
    if not os.path.exists(HISTORIAL_PATH):
        return []
    try:
        # utf-8-sig handles files saved with UTF-8 BOM from external editors.
        with open(HISTORIAL_PATH, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception as exc:
        logger.warning("Failed to load history: %s", exc)
        return []
    return limpiar_historial(data)


def guardar_datos(datos: Any) -> None:
    """Save normalized and cleaned history items."""
    ensure_dirs()
    cleaned = limpiar_historial(datos)
    with open(HISTORIAL_PATH, "w", encoding="utf-8") as handle:
        json.dump(cleaned, handle, ensure_ascii=False, indent=2)


def normalizar_historial_ids(historial: Any) -> bool:
    """Ensure each item has an id, returns True if modified."""
    items = _flatten_if_legacy(historial)
    changed = False
    for item in items:
        if not item.get("id"):
            ensure_item_id(item)
            changed = True
    return changed


def append_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Append one history record and return stored item."""
    items = cargar_datos()
    stored = _normalize_item(dict(item))
    items.append(stored)
    guardar_datos(items)
    return stored


def update_item(item_id: str, updates: Dict[str, Any]) -> Dict[str, Any] | None:
    """Update a history item by id."""
    items = cargar_datos()
    for idx, item in enumerate(items):
        if str(item.get("id")) == str(item_id):
            merged = {**item, **updates}
            items[idx] = _normalize_item(merged)
            guardar_datos(items)
            return items[idx]
    return None
