"""Template storage for reusable tutorial structures."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from utils.paths import DIR_TEMPLATES, ensure_dirs, p

TEMPLATES_FILE = p("templates", "templates.json")


def _load_file() -> List[Dict[str, Any]]:
    ensure_dirs([DIR_TEMPLATES])
    if not os.path.exists(TEMPLATES_FILE):
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as handle:
            json.dump([], handle, ensure_ascii=False, indent=2)
        return []
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def _save_file(templates: List[Dict[str, Any]]) -> None:
    ensure_dirs([DIR_TEMPLATES])
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as handle:
        json.dump(templates, handle, ensure_ascii=False, indent=2)


def list_templates() -> List[Dict[str, Any]]:
    """Return all saved templates."""
    return _load_file()


def save_template(template: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a template by name."""
    templates = _load_file()
    name = str(template.get("name", "")).strip()
    if not name:
        raise ValueError("Template name no puede estar vacio")

    payload = {
        "name": name,
        "structure": template.get("structure", []),
        "tone": template.get("tone", "educational"),
        "includes_code": bool(template.get("includes_code", True)),
        "avg_performance": float(template.get("avg_performance", 0) or 0),
        "tutorial_type": template.get("tutorial_type", "technical"),
        "length": template.get("length", "medium"),
        "tags": template.get("tags", []),
        "updated_at": datetime.now().isoformat(),
    }

    replaced = False
    for idx, item in enumerate(templates):
        if str(item.get("name", "")).strip().lower() == name.lower():
            templates[idx] = payload
            replaced = True
            break
    if not replaced:
        templates.append(payload)

    _save_file(templates)
    return payload


def get_template_by_name(name: str) -> Dict[str, Any] | None:
    """Return a template by name."""
    for item in _load_file():
        if str(item.get("name", "")).strip().lower() == str(name).strip().lower():
            return item
    return None
