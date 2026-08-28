"""Discord webhook digest for fresh jobs."""

from __future__ import annotations

import logging
import re
import requests

from ..filters import match_priority
from ..models import Job

log = logging.getLogger(__name__)

DISCORD_CONTENT_LIMIT = 2000
DISCORD_SUPPRESS_EMBEDS = 4


def _job_sort_key(job: Job) -> tuple[str, str, str]:
    return (job.company.lower(), job.title.lower(), job.url)


def _ranked_jobs(jobs: list[Job]) -> list[Job]:
    """Put explicit new-grad postings first, preserving readable sort order."""
    return sorted(jobs, key=lambda job: (-match_priority(job), *_job_sort_key(job)))


def _compact_location(job: Job) -> str:
    loc = re.sub(r"\s+", " ", (job.location_str or "").strip())
    return loc or "Remote/US"


def _job_line(job: Job) -> str:
    parts = [f"• {job.company} - {job.title} [{_compact_location(job)}]"]
    url = (job.url or "").strip()
    if url:
        parts.append(f"[Link]({url})")
    return " ".join(parts)


def _render_body_unbounded(jobs: list[Job], heading: str | None = None) -> str:
    jobs_sorted = sorted(jobs, key=_job_sort_key)
    lines = []
    if heading:
        lines.append(heading)
    lines.append(f"{len(jobs)} new full-time job(s)")
    lines.extend(_job_line(job) for job in jobs_sorted)
    return "\n".join(lines)


def _render_body(
    jobs: list[Job], max_chars: int = DISCORD_CONTENT_LIMIT, heading: str | None = None
) -> str:
    """Render one Discord message body from a chunk of jobs."""
    jobs_sorted = sorted(jobs, key=_job_sort_key)
    total = len(jobs)
    lines = [heading] if heading else []
    lines.append(f"{total} new full-time job(s)")

    if not jobs_sorted:
        return lines[0]

    for job in jobs_sorted:
        candidate = lines + [_job_line(job)]
        if len("\n".join(candidate)) > max_chars:
            if len(lines) == (2 if heading else 1):
                line = _job_line(job)
                room = max_chars - len("\n".join(lines)) - 1
                if room > 0:
                    if len(line) > room:
                        line = line[: max(0, room - 3)].rstrip() + ("..." if room >= 3 else "")
                    lines.append(line)
            break
        lines.append(_job_line(job))

    return "\n".join(lines)[:max_chars]


def build_bodies(jobs: list[Job], max_jobs: int = 15, max_chars: int = DISCORD_CONTENT_LIMIT) -> list[str]:
    jobs_sorted = _ranked_jobs(jobs)
    if not jobs_sorted:
        return ["0 new full-time job(s)"]

    bodies: list[str] = []

    top_matches = [job for job in jobs_sorted if match_priority(job)]
    other_matches = [job for job in jobs_sorted if not match_priority(job)]
    sections = [("Top Matches", top_matches), ("Other Matches", other_matches)]

    for heading, section_jobs in sections:
        if not section_jobs:
            continue
        current: list[Job] = []
        for job in section_jobs:
            candidate = current + [job]
            over_job_cap = max_jobs > 0 and len(candidate) > max_jobs
            over_char_cap = len(_render_body_unbounded(candidate, heading)) > max_chars
            if current and (over_job_cap or over_char_cap):
                bodies.append(_render_body(current, max_chars, heading))
                current = [job]
            else:
                current = candidate
        if current:
            bodies.append(_render_body(current, max_chars, heading))

    return bodies


def build_body(jobs: list[Job], max_jobs: int = 15, max_chars: int = DISCORD_CONTENT_LIMIT) -> str:
    bodies = build_bodies(jobs, max_jobs, max_chars)
    return bodies[0] if bodies else ""


def send_discord(jobs: list[Job], secrets: dict[str, str], discord_cfg: dict) -> bool:
    webhook_url = secrets.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log.warning("discord skipped: DISCORD_WEBHOOK_URL not set")
        return False

    timeout = int(discord_cfg.get("timeout_seconds", 10))
    bodies = build_bodies(jobs, int(discord_cfg.get("max_jobs", 15)), DISCORD_CONTENT_LIMIT)
    username = discord_cfg.get("username")
    try:
        for body in bodies:
            payload = {
                "content": body,
                "allowed_mentions": {"parse": []},
                "flags": DISCORD_SUPPRESS_EMBEDS,
            }
            if username:
                payload["username"] = username
            resp = requests.post(webhook_url, json=payload, timeout=timeout)
            if resp.status_code not in {200, 204}:
                log.error("discord send failed: HTTP %s %s", resp.status_code, resp.text[:200])
                return False
        log.info("discord sent %d message(s) to webhook (%d jobs)", len(bodies), len(jobs))
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("discord send failed: %s", exc)
        return False
