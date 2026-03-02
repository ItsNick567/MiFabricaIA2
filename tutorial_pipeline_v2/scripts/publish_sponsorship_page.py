"""Publish a sponsorship page to selected platforms."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

# Allow running this script directly from project root.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings  # noqa: E402
from publishers import publish_to_blogger, publish_to_devto, publish_to_hashnode  # noqa: E402


PublisherFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def _build_page_content() -> str:
    email = settings.BUSINESS_CONTACT_EMAIL
    sponsorship_url = settings.SPONSORSHIP_PAGE_URL
    newsletter_url = settings.NEWSLETTER_URL
    community_url = settings.COMMUNITY_URL

    contact_lines = []
    if sponsorship_url:
        contact_lines.append(f"- Sponsorship page: {sponsorship_url}")
    if email:
        contact_lines.append(f"- Email: {email}")
    if newsletter_url:
        contact_lines.append(f"- Newsletter: {newsletter_url}")
    if community_url:
        contact_lines.append(f"- Community: {community_url}")
    if not contact_lines:
        contact_lines.append("- Email: Configure BUSINESS_CONTACT_EMAIL in .env")

    return f"""
I publish practical developer tutorials focused on tools, automation, and AI workflows.

## Who this is for

- Dev tools and SaaS companies
- AI/automation products
- Technical education brands

## Collaboration options

1. Sponsored tutorial
2. Product integration walkthrough
3. Newsletter mention
4. Community mention

## Audience fit

- Developers and builders (beginner to intermediate)
- Readers interested in automation, AI, and practical implementation

## Contact

{chr(10).join(contact_lines)}

## Notes

- I only accept partnerships that are relevant for my developer audience.
- Transparency first: sponsored content is clearly disclosed.
""".strip()


def _build_tutorial_payload() -> Dict[str, Any]:
    return {
        "title": "Work with Me - Sponsorships and Partnerships",
        "content": _build_page_content(),
        "tags": ["sponsorship", "developer", "ai", "automation"],
        "topic": "Sponsorships and Partnerships",
        "skip_growth_footer": True,
    }


def _parse_platforms(raw: str) -> List[str]:
    selected = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not selected:
        return ["hashnode", "devto", "blogger"]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish sponsorship page to configured platforms.")
    parser.add_argument(
        "--platforms",
        default="hashnode,devto,blogger",
        help="Comma separated list: hashnode,devto,blogger",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payload without publishing")
    args = parser.parse_args()

    tutorial_data = _build_tutorial_payload()
    if args.dry_run:
        print(json.dumps(tutorial_data, indent=2))
        return 0

    registry: Dict[str, PublisherFn] = {
        "hashnode": publish_to_hashnode,
        "devto": publish_to_devto,
        "blogger": publish_to_blogger,
    }

    results: Dict[str, Dict[str, Any]] = {}
    for platform in _parse_platforms(args.platforms):
        publisher = registry.get(platform)
        if publisher is None:
            results[platform] = {
                "success": False,
                "platform": platform,
                "error": "Unsupported platform",
            }
            continue
        results[platform] = publisher(tutorial_data)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
