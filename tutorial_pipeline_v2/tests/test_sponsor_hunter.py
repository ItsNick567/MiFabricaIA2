"""Tests for sponsor hunter utilities."""

from core.sponsor_hunter import (
    SponsorLead,
    _extract_emails,
    _extract_emails_from_html,
    _render_template,
    _score_candidate,
    _split_subject_body,
)


def _sample_lead() -> SponsorLead:
    return SponsorLead(
        company="Acme DevTools",
        contact_name="Acme Team",
        email="hello@acme.dev",
        website="https://acme.dev",
        domain="acme.dev",
        contact_url="https://acme.dev/contact",
        source="github",
        source_id="acme/devtools",
        stars=1234,
        description="Developer productivity and AI tooling",
        keywords="developer,ai,tooling",
        score=75,
        reason="sample",
        created_at="2026-03-02T00:00:00",
    )


def test_extract_emails_filters_no_reply() -> None:
    content = "Contact us at hello@acme.dev or noreply@acme.dev"
    emails = _extract_emails(content)
    assert "hello@acme.dev" in emails
    assert "noreply@acme.dev" not in emails


def test_extract_emails_from_html_mailto() -> None:
    html = '<a href="mailto:partnerships@acme.dev">Contact</a>'
    emails = _extract_emails_from_html(html)
    assert "partnerships@acme.dev" in emails


def test_render_template_replaces_tokens() -> None:
    template = "Hi {{name}},\nCompany: {{company}}\nSite: {{website}}"
    rendered = _render_template(template, _sample_lead())
    assert "Acme Team" in rendered
    assert "Acme DevTools" in rendered
    assert "https://acme.dev" in rendered


def test_split_subject_body() -> None:
    subject, body = _split_subject_body("Subject: Hello\n\nBody line")
    assert subject == "Hello"
    assert "Body line" in body


def test_score_candidate_prioritizes_contact_and_keywords() -> None:
    high_score, _ = _score_candidate(
        stars=5000,
        description="AI devtools for automation",
        topics=["ai", "developer-tools"],
        has_email=True,
        has_contact_url=True,
        has_homepage=True,
        is_org=True,
        keywords=["ai", "automation", "developer"],
    )
    low_score, _ = _score_candidate(
        stars=50,
        description="Random repo",
        topics=["misc"],
        has_email=False,
        has_contact_url=False,
        has_homepage=False,
        is_org=False,
        keywords=["ai", "automation", "developer"],
    )
    assert high_score > low_score
