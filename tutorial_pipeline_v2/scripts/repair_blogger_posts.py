"""Repair existing Blogger posts by converting stored markdown to HTML and updating posts in place."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

# Allow running this script directly from project root.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from publishers.blogger_publisher import BloggerPublisher
from utils.historial import cargar_datos
from utils.logger import get_logger

logger = get_logger(__name__)


def _select_candidates(history: List[Dict[str, Any]], tutorial_id: str | None, repair_all: bool) -> List[Dict[str, Any]]:
    with_blogger = [
        item
        for item in history
        if isinstance(item.get("urls"), dict) and item.get("urls", {}).get("blogger")
    ]
    if tutorial_id:
        return [item for item in with_blogger if str(item.get("id")) == tutorial_id]
    if repair_all:
        return with_blogger
    return with_blogger[-1:] if with_blogger else []


def repair_blogger_posts(tutorial_id: str | None = None, repair_all: bool = False) -> Dict[str, Any]:
    history = cargar_datos()
    candidates = _select_candidates(history, tutorial_id=tutorial_id, repair_all=repair_all)
    if not candidates:
        return {"success": False, "error": "No Blogger posts found in history for requested scope."}

    publisher = BloggerPublisher()
    results: List[Dict[str, Any]] = []

    for item in candidates:
        post_url = str(item.get("urls", {}).get("blogger", "")).strip()
        post_id = publisher.resolve_post_id_from_url(post_url)
        if not post_id:
            results.append(
                {
                    "tutorial_id": item.get("id"),
                    "success": False,
                    "error": f"Could not resolve Blogger post id from URL: {post_url}",
                }
            )
            continue

        update_result = publisher.update_post(post_id=post_id, tutorial_data=item)
        results.append(
            {
                "tutorial_id": item.get("id"),
                "post_id": post_id,
                "url": post_url,
                **update_result,
            }
        )

    success_count = sum(1 for row in results if row.get("success"))
    return {
        "success": success_count > 0,
        "attempted": len(results),
        "updated": success_count,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair Blogger post formatting for historical tutorials.")
    parser.add_argument("--tutorial-id", dest="tutorial_id", default=None, help="Repair only one tutorial id.")
    parser.add_argument("--all", dest="repair_all", action="store_true", help="Repair all Blogger posts in history.")
    args = parser.parse_args()

    summary = repair_blogger_posts(tutorial_id=args.tutorial_id, repair_all=args.repair_all)
    logger.info("Blogger repair summary: %s", summary)
    print(summary)
    return 0 if summary.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
