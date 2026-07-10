"""Discord webhook digest behaviour."""

from __future__ import annotations

from src.models import Job
from src.notify import discord as D


def _job(company, title, url, location=None):
    return Job(company=company, title=title, url=url, locations=[location] if location else [])


def test_digest_includes_job_company_title():
    body = D.build_body([_job("Acme", "Software Engineer", "https://example.com/job", "New York, NY")])
    assert "Acme - Software Engineer" in body
    assert "Software Engineer" in body
    assert "New York, NY" not in body


def test_urls_are_rendered_as_markdown_link():
    body = D.build_body([_job("Acme", "Software Engineer", "https://example.com/job")])
    assert "[Link](https://example.com/job)" in body


def test_max_jobs_truncates_output():
    jobs = [_job(f"Co{i}", f"Role{i}", f"https://example.com/{i}") for i in range(6)]
    body = D.build_body(jobs, max_jobs=3)
    assert body.count("• ") == 3


def test_digest_splits_into_multiple_messages():
    jobs = [
        _job(
            "Acme",
            "Very Long Role Title That Keeps Going " * 3,
            f"https://example.com/{i}",
            "New York, NY",
        )
        for i in range(12)
    ]
    bodies = D.build_bodies(jobs, max_jobs=200, max_chars=250)
    assert len(bodies) > 1
    assert all(len(body) <= 250 for body in bodies)
    assert sum(body.count("• ") for body in bodies) == len(jobs)


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
    bodies = D.build_bodies(jobs, max_jobs=200)
    assert all(len(body) <= D.DISCORD_CONTENT_LIMIT for body in bodies)


def test_send_discord_posts_multiple_messages(monkeypatch):
    jobs = [
        _job(
            "Acme",
            "Very Long Role Title That Keeps Going " * 3,
            f"https://example.com/{i}",
            "New York, NY",
        )
        for i in range(12)
    ]
    calls = []

    class Resp:
        status_code = 204
        text = ""

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return Resp()

    monkeypatch.setattr(D.requests, "post", fake_post)
    monkeypatch.setattr(D, "DISCORD_CONTENT_LIMIT", 250)

    assert D.send_discord(jobs, {"DISCORD_WEBHOOK_URL": "https://discord.example/webhook"}, {})
    assert len(calls) > 1
    assert all(len(call["json"]["content"]) <= 250 for call in calls)
    assert all(call["json"]["allowed_mentions"] == {"parse": []} for call in calls)
    assert sum(call["json"]["content"].count("• ") for call in calls) == len(jobs)


def test_missing_webhook_skips_cleanly(monkeypatch):
    called = {}

    def fake_post(*args, **kwargs):
        called["called"] = True
        raise AssertionError("should not post without webhook")

    monkeypatch.setattr(D.requests, "post", fake_post)
    assert not D.send_discord([_job("Acme", "Software Engineer", "https://example.com/job")], {}, {})
    assert "called" not in called
