"""Sponsor discovery and outreach automation."""

from __future__ import annotations

import csv
import json
import math
import re
import smtplib
from dataclasses import dataclass, asdict
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import settings
from utils.logger import get_logger
from utils.paths import DATA_SPONSOR_LEADS_FILE, DATA_SPONSOR_OUTREACH_HISTORY_FILE, ensure_dirs

logger = get_logger(__name__)

GITHUB_SEARCH_ENDPOINT = "https://api.github.com/search/repositories"
GITHUB_USER_ENDPOINT = "https://api.github.com/users/{login}"
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
CONTACT_HINTS = ("contact", "about", "team", "company", "sponsor", "partnership")
DEFAULT_HEADERS = {
    "User-Agent": "TutorialPipelineSponsorHunter/1.0 (+https://autonomousworld.hashnode.dev)",
    "Accept": "application/json",
}
OWNER_PROFILE_CACHE: Dict[str, Dict[str, str]] = {}


@dataclass
class SponsorLead:
    company: str
    contact_name: str
    email: str
    website: str
    domain: str
    contact_url: str
    source: str
    source_id: str
    stars: int
    description: str
    keywords: str
    score: int
    reason: str
    created_at: str


def _github_headers() -> Dict[str, str]:
    headers = dict(DEFAULT_HEADERS)
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_url(url: str) -> str:
    value = _safe_text(url)
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value}"


def _extract_domain(url: str) -> str:
    parsed = urlparse(_normalize_url(url))
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def _extract_emails(text: str) -> List[str]:
    matches = {item.lower() for item in EMAIL_REGEX.findall(text or "")}
    filtered = [item for item in matches if _is_usable_email(item)]
    return sorted(filtered)


def _is_usable_email(email: str) -> bool:
    value = _safe_text(email).lower()
    if not value or "@" not in value:
        return False
    local, domain = value.split("@", 1)
    if not local or not domain:
        return False

    blocked_prefixes = ("noreply", "no-reply", "donotreply", "do-not-reply")
    blocked_locals = ("security", "abuse", "privacy", "legal", "mailer-daemon")
    blocked_domains = ("sentry.io", "example.com", "localhost")

    if local.startswith(blocked_prefixes) or local in blocked_locals:
        return False
    if any(blocked in domain for blocked in blocked_domains):
        return False
    if re.search(r"[0-9a-f]{20,}", local):
        return False
    return True


def _request_text(url: str) -> str:
    try:
        response = requests.get(
            _normalize_url(url),
            headers={"User-Agent": DEFAULT_HEADERS["User-Agent"]},
            timeout=settings.REQUEST_TIMEOUT_S,
        )
        if response.status_code != 200:
            return ""
        return response.text or ""
    except requests.RequestException:
        return ""


def _discover_contact_urls(base_url: str, html: str, limit: int = 3) -> List[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    urls: List[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = _safe_text(anchor.get("href"))
        text = _safe_text(anchor.get_text(" ", strip=True)).lower()
        candidate = href.lower()
        if not any(token in candidate or token in text for token in CONTACT_HINTS):
            continue
        resolved = urljoin(_normalize_url(base_url), href)
        if resolved in seen:
            continue
        seen.add(resolved)
        urls.append(resolved)
        if len(urls) >= limit:
            break
    return urls


def _decode_cf_email(encoded: str) -> str:
    raw = _safe_text(encoded)
    if len(raw) < 4 or len(raw) % 2 != 0:
        return ""
    try:
        key = int(raw[:2], 16)
        decoded_chars = []
        for idx in range(2, len(raw), 2):
            decoded_chars.append(chr(int(raw[idx:idx + 2], 16) ^ key))
        return "".join(decoded_chars)
    except ValueError:
        return ""


def _extract_emails_from_html(html: str) -> List[str]:
    emails = set(_extract_emails(html))
    if not html:
        return sorted(emails)

    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.select("a[href]"):
        href = _safe_text(anchor.get("href"))
        if href.lower().startswith("mailto:"):
            mail = href.split(":", 1)[1].split("?", 1)[0]
            if _is_usable_email(mail):
                emails.add(mail.lower())

    for node in soup.select("[data-cfemail]"):
        encoded = _safe_text(node.get("data-cfemail"))
        decoded = _decode_cf_email(encoded)
        if _is_usable_email(decoded):
            emails.add(decoded.lower())

    return sorted(emails)


def _pick_best_email(candidates: Iterable[str], domain: str) -> str:
    emails = [item for item in candidates if item]
    if not emails:
        return ""
    if domain:
        domain_match = [item for item in emails if item.endswith("@" + domain)]
        if domain_match:
            return sorted(domain_match)[0]
        return ""
    priority_order = ("partnership", "sponsor", "marketing", "hello", "team", "info", "contact")
    for token in priority_order:
        for email in emails:
            if token in email:
                return email
    return sorted(emails)[0]


def discover_contact_points(website: str) -> Tuple[str, str]:
    """Return best email and best contact page URL for a website."""
    normalized = _normalize_url(website)
    if not normalized:
        return "", ""

    home_html = _request_text(normalized)
    emails: List[str] = _extract_emails_from_html(home_html)
    candidate_urls = _discover_contact_urls(normalized, home_html)

    best_contact_url = candidate_urls[0] if candidate_urls else ""
    for url in candidate_urls:
        content = _request_text(url)
        emails.extend(_extract_emails_from_html(content))

    domain = _extract_domain(normalized)
    chosen_email = _pick_best_email(set(emails), domain)
    return chosen_email, best_contact_url


def _keyword_hits(text: str, keywords: List[str]) -> int:
    value = _safe_text(text).lower()
    if not value:
        return 0
    hits = 0
    for keyword in keywords:
        token = keyword.strip().lower()
        if token and token in value:
            hits += 1
    return hits


def _score_candidate(
    stars: int,
    description: str,
    topics: List[str],
    has_email: bool,
    has_contact_url: bool,
    has_homepage: bool,
    is_org: bool,
    keywords: List[str],
) -> Tuple[int, str]:
    star_score = min(35, int(math.log10(max(stars, 1)) * 12))
    text_blob = f"{description} {' '.join(topics)}"
    keyword_hits = _keyword_hits(text_blob, keywords)
    keyword_score = min(30, keyword_hits * 7)
    contact_score = 25 if has_email else (10 if has_contact_url else 0)
    base_score = 5 if has_homepage else 0
    org_bonus = 5 if is_org else 0
    total = min(100, star_score + keyword_score + contact_score + base_score + org_bonus)
    reason = (
        f"stars={stars}, keyword_hits={keyword_hits}, "
        f"email={'yes' if has_email else 'no'}, contact_url={'yes' if has_contact_url else 'no'}"
    )
    return total, reason


def _fetch_owner_profile(login: str) -> Dict[str, str]:
    key = _safe_text(login).strip().lower()
    if not key:
        return {}
    if key in OWNER_PROFILE_CACHE:
        return OWNER_PROFILE_CACHE[key]

    try:
        response = requests.get(
            GITHUB_USER_ENDPOINT.format(login=key),
            headers=_github_headers(),
            timeout=settings.REQUEST_TIMEOUT_S,
        )
        if response.status_code != 200:
            OWNER_PROFILE_CACHE[key] = {}
            return {}
        payload = response.json() if response.text else {}
        result = {
            "email": _safe_text(payload.get("email")),
            "blog": _safe_text(payload.get("blog")),
            "name": _safe_text(payload.get("name")),
        }
        OWNER_PROFILE_CACHE[key] = result
        return result
    except requests.RequestException:
        OWNER_PROFILE_CACHE[key] = {}
        return {}


def _repo_to_lead(repo: Dict[str, Any], keywords: List[str]) -> SponsorLead:
    owner = repo.get("owner", {}) if isinstance(repo.get("owner"), dict) else {}
    owner_login = _safe_text(owner.get("login"))
    owner_profile = _fetch_owner_profile(owner_login)

    company = owner_login or _safe_text(repo.get("name")) or "Unknown"
    source_id = _safe_text(repo.get("full_name")) or _safe_text(repo.get("html_url"))
    description = _safe_text(repo.get("description"))
    stars = int(repo.get("stargazers_count") or 0)
    topics_raw = repo.get("topics", [])
    topics = [str(item).strip().lower() for item in topics_raw if str(item).strip()]
    homepage = _normalize_url(_safe_text(repo.get("homepage")))
    if not homepage:
        homepage = _normalize_url(_safe_text(owner_profile.get("blog")))
    website = homepage or _safe_text(repo.get("html_url"))
    domain = _extract_domain(website)

    email, contact_url = discover_contact_points(website)
    owner_email = _safe_text(owner_profile.get("email")).lower()
    if not email and _is_usable_email(owner_email):
        email = owner_email

    contact_name = _safe_text(owner_profile.get("name")) or company
    score, reason = _score_candidate(
        stars=stars,
        description=description,
        topics=topics,
        has_email=bool(email),
        has_contact_url=bool(contact_url),
        has_homepage=bool(homepage),
        is_org=_safe_text(owner.get("type")).lower() == "organization",
        keywords=keywords,
    )

    return SponsorLead(
        company=company,
        contact_name=contact_name,
        email=email,
        website=website,
        domain=domain,
        contact_url=contact_url,
        source="github",
        source_id=source_id,
        stars=stars,
        description=description,
        keywords=",".join(topics),
        score=score,
        reason=reason,
        created_at=datetime.utcnow().isoformat(),
    )


def _github_search_for_keyword(keyword: str, per_keyword: int = 20, min_stars: int = 100) -> List[Dict[str, Any]]:
    query = f"{keyword} in:name,description stars:>{min_stars}"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_keyword,
    }
    try:
        response = requests.get(
            GITHUB_SEARCH_ENDPOINT,
            params=params,
            headers=_github_headers(),
            timeout=settings.REQUEST_TIMEOUT_S,
        )
        if response.status_code != 200:
            logger.warning("GitHub search failed keyword=%s status=%s", keyword, response.status_code)
            return []
        payload = response.json() if response.text else {}
        items = payload.get("items", [])
        return items if isinstance(items, list) else []
    except requests.RequestException as exc:
        logger.warning("GitHub search request failed keyword=%s error=%s", keyword, exc)
        return []


def discover_sponsor_leads(
    keywords: List[str] | None = None,
    max_leads: int | None = None,
    min_score: int | None = None,
) -> List[SponsorLead]:
    ensure_dirs()
    selected_keywords = keywords or settings.SPONSOR_SEARCH_KEYWORDS
    max_items = max_leads if max_leads is not None else settings.SPONSOR_HUNTER_MAX_LEADS
    threshold = min_score if min_score is not None else settings.SPONSOR_MIN_SCORE

    seen: set[str] = set()
    leads: List[SponsorLead] = []
    per_keyword = min(20, max(5, max_items // max(1, len(selected_keywords)) + 3))

    for keyword in selected_keywords:
        repos = _github_search_for_keyword(keyword=keyword, per_keyword=per_keyword)
        for repo in repos:
            unique_key = _safe_text(repo.get("full_name")).lower()
            if not unique_key or unique_key in seen:
                continue
            seen.add(unique_key)

            lead = _repo_to_lead(repo, selected_keywords)
            if lead.score < threshold:
                continue
            leads.append(lead)

    leads.sort(key=lambda item: item.score, reverse=True)
    return leads[:max_items]


def save_leads_csv(leads: List[SponsorLead], filepath: str = DATA_SPONSOR_LEADS_FILE) -> str:
    ensure_dirs()
    fieldnames = [
        "company",
        "contact_name",
        "email",
        "website",
        "domain",
        "contact_url",
        "source",
        "source_id",
        "stars",
        "description",
        "keywords",
        "score",
        "reason",
        "created_at",
    ]
    with open(filepath, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            writer.writerow(asdict(lead))
    return filepath


def _load_outreach_history() -> List[Dict[str, Any]]:
    ensure_dirs()
    try:
        with open(DATA_SPONSOR_OUTREACH_HISTORY_FILE, "r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
            return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _save_outreach_history(history: List[Dict[str, Any]]) -> None:
    with open(DATA_SPONSOR_OUTREACH_HISTORY_FILE, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)


def _history_key(lead: SponsorLead) -> str:
    return f"{lead.domain}:{lead.email}".lower().strip(":")


def _already_contacted(history: List[Dict[str, Any]], lead: SponsorLead) -> bool:
    key = _history_key(lead)
    for item in history:
        if _safe_text(item.get("key")).lower() == key:
            return True
    return False


def _render_template(raw_text: str, lead: SponsorLead) -> str:
    replacements = {
        "{{name}}": lead.contact_name or lead.company or "team",
        "{{company}}": lead.company,
        "{{domain}}": lead.domain,
        "{{website}}": lead.website,
        "{{your_name}}": settings.OUTREACH_SENDER_NAME or "Nico",
        "{{business_email}}": settings.OUTREACH_FROM_EMAIL or settings.BUSINESS_CONTACT_EMAIL,
        "{{site_or_profile}}": settings.OUTREACH_SITE_OR_PROFILE or settings.SPONSORSHIP_PAGE_URL,
    }
    content = raw_text
    for token, value in replacements.items():
        content = content.replace(token, _safe_text(value))
    return content


def _split_subject_body(template_text: str) -> Tuple[str, str]:
    lines = template_text.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
        return subject, body
    return "Sponsorship Opportunity", template_text.strip()


def _smtp_config_ok() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_PORT and settings.OUTREACH_FROM_EMAIL)


def _send_email(to_email: str, subject: str, body: str) -> Tuple[bool, str]:
    if not _smtp_config_ok():
        return False, "SMTP config incomplete"

    msg = EmailMessage()
    sender_name = settings.OUTREACH_SENDER_NAME or "Tutorial Pipeline"
    from_email = settings.OUTREACH_FROM_EMAIL
    msg["From"] = f"{sender_name} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    if settings.OUTREACH_REPLY_TO:
        msg["Reply-To"] = settings.OUTREACH_REPLY_TO
    msg.set_content(body)

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
        return True, "sent"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def run_outreach_for_leads(
    leads: List[SponsorLead],
    template_path: str,
    send_enabled: bool,
    max_emails: int | None = None,
    min_score: int | None = None,
) -> Dict[str, Any]:
    ensure_dirs()
    limit = max_emails if max_emails is not None else settings.OUTREACH_MAX_EMAILS_PER_RUN
    threshold = min_score if min_score is not None else settings.SPONSOR_MIN_SCORE
    history = _load_outreach_history()

    with open(template_path, "r", encoding="utf-8") as handle:
        raw_template = handle.read()
    subject_template, body_template = _split_subject_body(raw_template)

    prepared = 0
    sent = 0
    skipped = 0
    failed = 0
    updates: List[Dict[str, Any]] = []

    for lead in leads:
        if prepared >= limit:
            break
        if not lead.email:
            skipped += 1
            continue
        if lead.score < threshold:
            skipped += 1
            continue
        if _already_contacted(history, lead):
            skipped += 1
            continue

        subject = _render_template(subject_template, lead)
        body = _render_template(body_template, lead)
        prepared += 1

        if send_enabled:
            ok, detail = _send_email(to_email=lead.email, subject=subject, body=body)
            if ok:
                sent += 1
            else:
                failed += 1
        else:
            ok, detail = True, "prepared_only"

        entry = {
            "key": _history_key(lead),
            "company": lead.company,
            "email": lead.email,
            "domain": lead.domain,
            "subject": subject,
            "status": detail,
            "send_enabled": send_enabled,
            "timestamp": datetime.utcnow().isoformat(),
        }
        history.append(entry)
        updates.append(entry)

    _save_outreach_history(history)
    return {
        "prepared": prepared,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "send_enabled": send_enabled,
        "history_file": DATA_SPONSOR_OUTREACH_HISTORY_FILE,
        "updates": updates,
    }
