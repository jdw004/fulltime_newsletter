"""Discord webhook digest for fresh jobs."""

from __future__ import annotations

import logging
import re

import requests

from ..models import Job

log = logging.getLogger(__name__)

DISCORD_CONTENT_LIMIT = 2000


def _job_sort_key(job: Job) -> tuple[str, str, str]:
    return (job.company.lower(), job.title.lower(), job.url)


def _wrap_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    return f"<{url}>"


def _compact_location(job: Job) -> str:
    loc = re.sub(r"\s+", " ", (job.location_str or "").strip())
    return loc or "Remote/US"


def _job_line(job: Job) -> str:
    return f"• {job.title} — {job.company} [{_compact_location(job)}] {_wrap_url(job.url)}"


def build_body(jobs: list[Job], max_jobs: int = 15, max_chars: int = DISCORD_CONTENT_LIMIT) -> str:
    jobs_sorted = sorted(jobs, key=_job_sort_key)
    if max_jobs and max_jobs > 0:
        jobs_sorted = jobs_sorted[:max_jobs]

    total = len(jobs)
    lines = [f"{total} new full-time job(s)"]

    if not jobs_sorted:
        return lines[0]

    shown = 0
    for job in jobs_sorted:
        candidate = lines + [_job_line(job)]
        if len("\n".join(candidate)) > max_chars:
            break
        lines.append(_job_line(job))
        shown += 1

    remaining = total - shown
    if remaining > 0:
        summary = f"... and {remaining} more"
        if len("\n".join(lines + [summary])) <= max_chars:
            lines.append(summary)
        else:
            # Keep the message valid even if the footer does not fit.
            while lines and len("\n".join(lines + [summary])) > max_chars:
                if len(lines) == 1:
                    break
                lines.pop()
            if len("\n".join(lines + [summary])) <= max_chars:
                lines.append(summary)

    return "\n".join(lines)[:max_chars]


def send_discord(jobs: list[Job], secrets: dict[str, str], discord_cfg: dict) -> bool:
    webhook_url = secrets.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log.warning("discord skipped: DISCORD_WEBHOOK_URL not set")
        return False

    body = build_body(jobs, int(discord_cfg.get("max_jobs", 15)), DISCORD_CONTENT_LIMIT)
    payload = {
        "content": body,
        "allowed_mentions": {"parse": []},
    }
    username = discord_cfg.get("username")
    if username:
        payload["username"] = username

    timeout = int(discord_cfg.get("timeout_seconds", 10))
    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
        if resp.status_code not in {200, 204}:
            log.error("discord send failed: HTTP %s %s", resp.status_code, resp.text[:200])
            return False
        log.info("discord sent to webhook (%d jobs)", len(jobs))
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("discord send failed: %s", exc)
        return False
