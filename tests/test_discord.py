"""Discord webhook digest behaviour."""

from __future__ import annotations

from src.models import Job
from src.notify import discord as D


def _job(company, title, url, location=None):
    return Job(company=company, title=title, url=url, locations=[location] if location else [])


def test_digest_includes_job_company_location():
    body = D.build_body([_job("Acme", "Software Engineer", "https://example.com/job", "New York, NY")])
    assert "Software Engineer" in body
    assert "Acme" in body
    assert "New York, NY" in body


def test_urls_are_wrapped_in_angle_brackets():
    body = D.build_body([_job("Acme", "Software Engineer", "https://example.com/job")])
    assert "<https://example.com/job>" in body


def test_max_jobs_truncates_output():
    jobs = [_job(f"Co{i}", f"Role{i}", f"https://example.com/{i}") for i in range(6)]
    body = D.build_body(jobs, max_jobs=3)
    assert body.count("• ") == 3
    assert "... and 3 more" in body


def test_message_stays_under_discord_limit():
    jobs = [
        _job(
            "Acme",
            "Very Long Role Title That Keeps Going",
            f"https://example.com/{i}",
            "New York, NY",
        )
        for i in range(200)
    ]
    body = D.build_body(jobs, max_jobs=200)
    assert len(body) <= D.DISCORD_CONTENT_LIMIT


def test_missing_webhook_skips_cleanly(monkeypatch):
    called = {}

    def fake_post(*args, **kwargs):
        called["called"] = True
        raise AssertionError("should not post without webhook")

    monkeypatch.setattr(D.requests, "post", fake_post)
    assert not D.send_discord([_job("Acme", "Software Engineer", "https://example.com/job")], {}, {})
    assert "called" not in called
