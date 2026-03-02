"""Send one SMTP test email using configured outreach credentials."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow running this script directly from project root.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.sponsor_hunter import _send_email  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one SMTP test email.")
    parser.add_argument("--to", required=True, help="Recipient email")
    args = parser.parse_args()

    load_dotenv(dotenv_path=ROOT_DIR / ".env")
    ok, detail = _send_email(
        to_email=args.to,
        subject="Test outreach email - Autonomous World Dev",
        body=(
            "Hi,\n\n"
            "This is a test email from Tutorial Pipeline sponsor hunter.\n\n"
            "Best,\n"
            "Nico"
        ),
    )
    print({"success": ok, "detail": detail, "to": args.to})
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
