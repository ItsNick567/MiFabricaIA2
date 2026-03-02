"""Run sponsor discovery and outreach flow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

# Allow running this script directly from project root.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings  # noqa: E402
from core.sponsor_hunter import discover_sponsor_leads, run_outreach_for_leads, save_leads_csv  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.paths import DATA_SPONSOR_LEADS_FILE, p  # noqa: E402

logger = get_logger(__name__)


def _parse_keywords(raw: str) -> List[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or settings.SPONSOR_SEARCH_KEYWORDS


def main() -> int:
    parser = argparse.ArgumentParser(description="Sponsor hunter: discover leads, score, and send outreach emails.")
    parser.add_argument(
        "--keywords",
        default=",".join(settings.SPONSOR_SEARCH_KEYWORDS),
        help="Comma-separated keywords for GitHub sponsor discovery.",
    )
    parser.add_argument("--max-leads", type=int, default=settings.SPONSOR_HUNTER_MAX_LEADS)
    parser.add_argument("--min-score", type=int, default=settings.SPONSOR_MIN_SCORE)
    parser.add_argument("--max-emails", type=int, default=settings.OUTREACH_MAX_EMAILS_PER_RUN)
    parser.add_argument(
        "--template",
        default=p("templates", "sponsor_outreach_email.txt"),
        help="Path to outreach template text file.",
    )
    parser.add_argument(
        "--csv",
        default=DATA_SPONSOR_LEADS_FILE,
        help="Output CSV path for discovered leads.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send emails via SMTP. Without this flag, only prepares outreach history.",
    )
    args = parser.parse_args()

    keywords = _parse_keywords(args.keywords)
    leads = discover_sponsor_leads(keywords=keywords, max_leads=args.max_leads, min_score=args.min_score)
    csv_path = save_leads_csv(leads, filepath=args.csv)
    logger.info("Sponsor leads saved count=%s path=%s", len(leads), csv_path)

    outreach = run_outreach_for_leads(
        leads=leads,
        template_path=args.template,
        send_enabled=bool(args.send or settings.OUTREACH_SEND_ENABLED),
        max_emails=args.max_emails,
        min_score=args.min_score,
    )

    summary = {
        "keywords": keywords,
        "leads_found": len(leads),
        "csv_path": csv_path,
        "outreach": outreach,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
