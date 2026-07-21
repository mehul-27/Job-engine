"""Public job listing discovery for V1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from .domain import RoleTarget


@dataclass(frozen=True)
class DiscoveredOpportunity:
    source: str
    title: str
    company: str
    url: str
    location: str | None
    description: str


def discover_role(role: RoleTarget, *, timeout: int = 15) -> list[DiscoveredOpportunity]:
    request = Request(role.source_url, headers={"User-Agent": "CareerOS/0.4"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    jobs = payload.get("jobs", payload) if isinstance(payload, dict) else payload
    if not isinstance(jobs, list):
        return []
    return [job for item in jobs if (job := normalize_job(item, role)) is not None]


def normalize_job(item: Any, role: RoleTarget) -> DiscoveredOpportunity | None:
    if not isinstance(item, dict):
        return None
    title = first_text(item, "position", "title", "role")
    company = first_text(item, "company", "company_name", "organization") or "Unknown company"
    url = first_text(item, "url", "apply_url", "job_url", "link")
    description = first_text(item, "description", "tags", "summary") or ""
    location = first_text(item, "location", "region")
    if not title or not url:
        return None
    haystack = " ".join([title, company, location or "", description]).lower()
    keywords = [part.strip().lower() for part in role.keywords.replace(";", ",").split(",") if part.strip()]
    if keywords and not any(keyword in haystack for keyword in keywords):
        return None
    if role.remote_preference == "remote" and "remote" not in haystack:
        return None
    return DiscoveredOpportunity(
        source=role.source_url,
        title=title,
        company=company,
        url=url,
        location=location,
        description=description,
    )


def first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, list):
            value = ", ".join(str(part) for part in value)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None
