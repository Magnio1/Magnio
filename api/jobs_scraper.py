"""
JobRadar scraper.

Sources
-------
- YC startup jobs pages — public HTML on ycombinator.com/jobs and job detail pages.
- Greenhouse public job-board API — no auth required.

Output
------
Normalized job documents written to Firestore collection ``jobs_raw``.
Each document: {id, title, company, url, source, location, remote, salary,
                jd_full, scraped_at, status: "pending"}

Configuration
-------------
JOBRADAR_YC_PUBLIC_URL          — default: https://www.ycombinator.com/jobs
JOBRADAR_YC_LIMIT               — max YC jobs per run (default: 40)
JOBRADAR_GREENHOUSE_COMPANIES   — comma-separated Greenhouse watchlist slugs
JOBRADAR_GREENHOUSE_DISCOVERY_COMPANIES
                                — broader startup discovery slugs for
                                  smaller / less-famous companies
JOBRADAR_LEVER_COMPANIES        — comma-separated Lever watchlist slugs
JOBRADAR_LEVER_DISCOVERY_COMPANIES
                                — broader startup discovery slugs for
                                  Lever boards
JOBRADAR_LEVER_MAX_PER_COMPANY  — cap Lever jobs per company (default: 25)
JOBRADAR_ASHBY_COMPANIES        — comma-separated Ashby watchlist slugs
JOBRADAR_ASHBY_DISCOVERY_COMPANIES
                                — broader startup discovery slugs for
                                  Ashby boards
"""
from __future__ import annotations

import datetime
import html
import json
import logging
import os
import re
import uuid
from collections import defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from api.firebase_client import get_firestore_client

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YC startup jobs — public pages
# ---------------------------------------------------------------------------
YC_PUBLIC_JOBS_URL = os.environ.get("JOBRADAR_YC_PUBLIC_URL", "https://www.ycombinator.com/jobs").strip()
YC_SITE_BASE_URL = "https://www.ycombinator.com"

# ---------------------------------------------------------------------------
# Greenhouse — public boards API
# ---------------------------------------------------------------------------
GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"

DEFAULT_GREENHOUSE_DISCOVERY_COMPANIES = [
    "warp", "merge", "modal", "mercor", "clay", "pylon",
]


def _parse_company_list(raw: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in raw.split(","):
        slug = item.strip().lower()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        values.append(slug)
    return values


def _normalize_job_text(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    return normalized


def _normalize_job_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value.strip())
    path = re.sub(r"/+", "/", parsed.path or "").rstrip("/")
    host = (parsed.netloc or "").lower()
    return f"{host}{path}".strip()


def build_job_dedupe_keys(job: dict[str, Any]) -> tuple[str, str]:
    company = _normalize_job_text(str(job.get("company") or ""))
    title = _normalize_job_text(str(job.get("title") or ""))
    normalized_url = _normalize_job_url(str(job.get("url") or ""))
    location = _normalize_job_text(str(job.get("location") or ""))
    dedupe_key = "|".join(part for part in [company, title, normalized_url] if part)
    role_key = "|".join(part for part in [company, title, location] if part)
    return dedupe_key, role_key


def _job_quality_score(job: dict[str, Any]) -> tuple[int, int, int, int]:
    source_rank = {
        "ashby": 4,
        "greenhouse": 3,
        "lever": 2,
        "yc": 1,
    }.get(str(job.get("source") or "").lower(), 0)
    lane_rank = 1 if job.get("collection_lane") == "watchlist" else 0
    salary_rank = 1 if str(job.get("salary") or "").strip() else 0
    jd_len = len(str(job.get("jd_full") or ""))
    return (source_rank, lane_rank, salary_rank, jd_len)


def dedupe_jobs(jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        dedupe_key, role_key = build_job_dedupe_keys(job)
        enriched_job = {
            **job,
            "dedupe_key": dedupe_key,
            "role_key": role_key,
        }
        group_key = dedupe_key or role_key or str(job.get("id") or uuid.uuid4().hex)
        groups[group_key].append(enriched_job)

    deduped: list[dict[str, Any]] = []
    duplicate_count = 0
    seen_role_keys: dict[str, dict[str, Any]] = {}

    for group_jobs in groups.values():
        best = max(group_jobs, key=_job_quality_score)
        replaced = False
        role_key = str(best.get("role_key") or "")
        if role_key and role_key in seen_role_keys:
            current = seen_role_keys[role_key]
            if _job_quality_score(best) > _job_quality_score(current):
                deduped.remove(current)
                deduped.append(best)
                seen_role_keys[role_key] = best
            duplicate_count += len(group_jobs)
            replaced = True

        if not replaced:
            deduped.append(best)
            if role_key:
                seen_role_keys[role_key] = best
            duplicate_count += max(0, len(group_jobs) - 1)

    return deduped, duplicate_count


_GH_ENV = os.environ.get("JOBRADAR_GREENHOUSE_COMPANIES", "").strip()
GREENHOUSE_COMPANIES: list[str] = _parse_company_list(_GH_ENV)
_GH_DISCOVERY_ENV = os.environ.get("JOBRADAR_GREENHOUSE_DISCOVERY_COMPANIES", "").strip()
GREENHOUSE_DISCOVERY_COMPANIES: list[str] = (
    _parse_company_list(_GH_DISCOVERY_ENV)
    if _GH_DISCOVERY_ENV
    else list(DEFAULT_GREENHOUSE_DISCOVERY_COMPANIES)
)
GREENHOUSE_MAX_COMPANIES = int(os.environ.get("JOBRADAR_GREENHOUSE_MAX_COMPANIES", "8"))
GREENHOUSE_MAX_JOBS = int(os.environ.get("JOBRADAR_GREENHOUSE_MAX_JOBS", "80"))

# ---------------------------------------------------------------------------
# Lever — public job boards
# ---------------------------------------------------------------------------
LEVER_SITE_BASE = "https://jobs.lever.co"
DEFAULT_LEVER_DISCOVERY_COMPANIES = [
    "mistral", "palantir",
]
LEVER_MAX_PER_COMPANY = int(os.environ.get("JOBRADAR_LEVER_MAX_PER_COMPANY", "8"))
_LEVER_ENV = os.environ.get("JOBRADAR_LEVER_COMPANIES", "").strip()
LEVER_COMPANIES: list[str] = _parse_company_list(_LEVER_ENV)
_LEVER_DISCOVERY_ENV = os.environ.get("JOBRADAR_LEVER_DISCOVERY_COMPANIES", "").strip()
LEVER_DISCOVERY_COMPANIES: list[str] = (
    _parse_company_list(_LEVER_DISCOVERY_ENV)
    if _LEVER_DISCOVERY_ENV
    else list(DEFAULT_LEVER_DISCOVERY_COMPANIES)
)
LEVER_MAX_COMPANIES = int(os.environ.get("JOBRADAR_LEVER_MAX_COMPANIES", "4"))
LEVER_MAX_JOBS = int(os.environ.get("JOBRADAR_LEVER_MAX_JOBS", "40"))

# ---------------------------------------------------------------------------
# Ashby — public job postings API
# Docs: https://developers.ashbyhq.com/docs/public-job-posting-api
# ---------------------------------------------------------------------------
ASHBY_API_BASE = "https://api.ashbyhq.com/posting-api/job-board"
DEFAULT_ASHBY_DISCOVERY_COMPANIES = [
    "ramp", "perplexity", "cursor", "runway", "replit",
]
_ASHBY_ENV = os.environ.get("JOBRADAR_ASHBY_COMPANIES", "").strip()
ASHBY_COMPANIES: list[str] = _parse_company_list(_ASHBY_ENV)
_ASHBY_DISCOVERY_ENV = os.environ.get("JOBRADAR_ASHBY_DISCOVERY_COMPANIES", "").strip()
ASHBY_DISCOVERY_COMPANIES: list[str] = (
    _parse_company_list(_ASHBY_DISCOVERY_ENV)
    if _ASHBY_DISCOVERY_ENV
    else list(DEFAULT_ASHBY_DISCOVERY_COMPANIES)
)
ASHBY_MAX_COMPANIES = int(os.environ.get("JOBRADAR_ASHBY_MAX_COMPANIES", "6"))
ASHBY_MAX_JOBS = int(os.environ.get("JOBRADAR_ASHBY_MAX_JOBS", "80"))


# ---------------------------------------------------------------------------
# HTML stripping (no external deps)
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Minimal HTML → plain text without external dependencies."""
    # Remove script/style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block-level tags with newlines for readability
    html = re.sub(r"<(br|p|div|li|h[1-6]|tr)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Remove all remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # Decode common HTML entities
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    # Collapse excessive whitespace
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# ---------------------------------------------------------------------------
# YC scraper
# ---------------------------------------------------------------------------
def _extract_json_array_after_marker(text: str, marker: str) -> list[dict[str, Any]]:
    marker_index = text.find(marker)
    if marker_index == -1:
        return []

    start = text.find("[", marker_index)
    if start == -1:
        return []

    depth = 0
    in_string = False
    escape = False
    end = -1
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                end = index + 1
                break

    if end == -1:
        return []

    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def _extract_title_from_html(page_html: str, fallback: str = "") -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title>(.*?)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return html.unescape(match.group(1)).strip()
    return fallback


def _extract_description_from_html(page_html: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r"<main[^>]*>([\s\S]*?)</main>",
        r"<body[^>]*>([\s\S]*?)</body>",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        text = _strip_html(html.unescape(match.group(1)))
        if text:
            return text[:8000]
    return ""

def _fetch_html(urls: list[str]) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MagnioJobRadar/1.0; +https://magnio.io)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            if resp.text:
                return resp.text
        except requests.RequestException as exc:
            log.warning("HTML fetch failed for %s: %s", url, exc)
    return ""

def _extract_yc_listing_jobs(page_html: str, limit: int) -> list[dict[str, Any]]:
    decoded = html.unescape(page_html)
    postings = _extract_json_array_after_marker(decoded, '"jobPostings":')
    if not postings:
        return []

    jobs: list[dict[str, Any]] = []
    for posting in postings[:limit]:
        job_id = str(posting.get("id") or uuid.uuid4().hex)
        relative_url = str(posting.get("url") or "").strip()
        absolute_url = urljoin(YC_SITE_BASE_URL, relative_url)
        title = str(posting.get("title") or "").strip()
        company = str(posting.get("companyName") or "").strip()
        company_batch = str(posting.get("companyBatchName") or "").strip()
        location = str(posting.get("location") or "").strip()
        salary = str(posting.get("salaryRange") or "").strip()
        role_family = str(posting.get("prettyRole") or "").strip()
        role_specific = str(posting.get("roleSpecificType") or "").strip()
        summary = str(posting.get("companyOneLiner") or "").strip()
        last_active = str(posting.get("lastActive") or "").strip()

        try:
            detail_html = _fetch_html([absolute_url])
        except Exception:
            detail_html = ""
        description = _extract_description_from_html(detail_html) if detail_html else ""
        if company_batch:
            summary = f"{summary} ({company_batch})".strip() if summary else company_batch
        if summary and summary not in description:
            description = f"{summary}\n\n{description}".strip()
        if role_family or role_specific or last_active:
            meta_bits = [bit for bit in [role_family, role_specific, last_active] if bit]
            description = ("\n".join([" • ".join(meta_bits), description]) if description else " • ".join(meta_bits)).strip()

        jobs.append(
            {
                "id": f"yc_{job_id}",
                "title": title,
                "company": company,
                "url": absolute_url,
                "source": "yc",
                "source_detail": "ycombinator_jobs_page",
                "company_slug": _normalize_job_text(company).replace(" ", "-"),
                "collection_lane": "discovery",
                "location": location,
                "remote": "remote" in location.lower(),
                "salary": salary,
                "jd_full": description[:8000],
                "scraped_at": datetime.datetime.utcnow().isoformat(),
                "status": "pending",
            }
        )

    return jobs


def scrape_yc_jobs(limit: int = 20) -> list[dict[str, Any]]:
    listing_html = _fetch_html([YC_PUBLIC_JOBS_URL, f"{YC_SITE_BASE_URL}/jobs"])
    if not listing_html:
        log.warning("YC public jobs page could not be loaded.")
        return []

    jobs = _extract_yc_listing_jobs(listing_html, limit)
    log.info("YC scraper: fetched %d jobs from public YC jobs page", len(jobs))
    return jobs


def scrape_yc_jobs_with_fallback(limit: int = 20) -> dict[str, Any]:
    """
    Fetch YC jobs from the public YC jobs page. Returns jobs plus source-level
    status metadata.
    """
    summary: dict[str, Any] = {
        "source": "yc",
        "status": "skipped",
        "strategy": None,
        "fetched": 0,
        "error": None,
        "fallback_used": False,
    }
    try:
        public_jobs = scrape_yc_jobs(limit=limit)
    except Exception as exc:
        public_jobs = []
        public_error = str(exc)
    else:
        public_error = None

    if public_jobs:
        summary.update(
            {
                "status": "ok",
                "strategy": "ycombinator_public_html",
                "fetched": len(public_jobs),
                "error": None,
                "fallback_used": False,
            }
        )
        return {"jobs": public_jobs, "summary": summary}

    summary.update(
        {
            "status": "failed" if public_error else "skipped",
            "strategy": "ycombinator_public_html",
            "fetched": 0,
            "error": public_error or "No YC jobs were fetched from the public YC jobs page.",
            "fallback_used": False,
        }
    )
    return {"jobs": [], "summary": summary}


# ---------------------------------------------------------------------------
# Greenhouse scraper
# ---------------------------------------------------------------------------

def scrape_greenhouse_jobs(
    companies: list[str] | None = None,
    *,
    lane: str = "watchlist",
) -> list[dict[str, Any]]:
    """
    Fetch jobs from Greenhouse public board API for each company slug.

    Board slugs are typically the company's lowercase name as it appears in
    their Greenhouse URL: https://boards.greenhouse.io/{slug}
    """
    targets = companies if companies is not None else GREENHOUSE_COMPANIES
    if not targets:
        log.info("Greenhouse scraper (%s): no companies configured — skipping.", lane)
        return []

    all_jobs: list[dict[str, Any]] = []

    for slug in targets:
        url = f"{GREENHOUSE_API_BASE}/{slug}/jobs?content=true"
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException:
            log.warning("Greenhouse: could not fetch jobs for slug '%s' — skipping.", slug)
            continue

        data = resp.json()
        gh_jobs: list[dict[str, Any]] = data.get("jobs") or []
        company_name: str = (data.get("meta") or {}).get("name") or slug.title()

        for gj in gh_jobs:
            job_id = str(gj.get("id") or uuid.uuid4().hex)
            raw_content: str = gj.get("content") or ""
            jd_text = _strip_html(raw_content)[:8000]

            offices: list[dict] = gj.get("offices") or []
            location = ", ".join(o.get("name", "") for o in offices if o.get("name"))

            title: str = gj.get("title") or ""

            all_jobs.append({
                "id": f"gh_{job_id}",
                "title": title,
                "company": company_name,
                "url": gj.get("absolute_url") or "",
                "source": "greenhouse",
                "source_detail": "public_api",
                "company_slug": slug,
                "collection_lane": lane,
                "location": location,
                "remote": "remote" in title.lower() or "remote" in location.lower(),
                "salary": "",
                "jd_full": jd_text,
                "scraped_at": datetime.datetime.utcnow().isoformat(),
                "status": "pending",
            })

    log.info(
        "Greenhouse scraper (%s): fetched %d jobs from %d companies",
        lane, len(all_jobs), len(targets),
    )
    return all_jobs


def scrape_greenhouse_watchlist_and_discovery(
    *,
    watchlist_companies: list[str] | None = None,
    discovery_companies: list[str] | None = None,
) -> dict[str, Any]:
    watchlist_targets = list(watchlist_companies if watchlist_companies is not None else GREENHOUSE_COMPANIES)
    discovery_targets = list(
        discovery_companies if discovery_companies is not None else GREENHOUSE_DISCOVERY_COMPANIES
    )
    watchlist_targets = _cap_companies(watchlist_targets, GREENHOUSE_MAX_COMPANIES)
    watchlist_seen = set(watchlist_targets)
    discovery_targets = [slug for slug in discovery_targets if slug not in watchlist_seen]
    discovery_targets = _cap_companies(
        discovery_targets,
        max(0, GREENHOUSE_MAX_COMPANIES - len(watchlist_targets)),
    )

    watchlist_jobs = scrape_greenhouse_jobs(watchlist_targets, lane="watchlist")
    discovery_jobs = scrape_greenhouse_jobs(discovery_targets, lane="discovery")

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for job in watchlist_jobs + discovery_jobs:
        job_id = str(job.get("id") or "").strip()
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        merged.append(job)

    merged = _cap_jobs(merged, GREENHOUSE_MAX_JOBS)

    return {
        "jobs": merged,
        "summary": {
            "source": "greenhouse",
            "status": "ok" if merged else ("skipped" if not (watchlist_targets or discovery_targets) else "failed"),
            "strategy": "public_api_watchlist_and_discovery",
            "fetched": len(merged),
            "watchlist_companies": len(watchlist_targets),
            "watchlist_fetched": len(watchlist_jobs),
            "discovery_companies": len(discovery_targets),
            "discovery_fetched": len(discovery_jobs),
            "error": None if merged or (watchlist_targets or discovery_targets) else "No Greenhouse companies configured.",
            "fallback_used": False,
        },
    }


# ---------------------------------------------------------------------------
# Lever scraper
# ---------------------------------------------------------------------------

def _extract_lever_company_name(page_html: str, slug: str) -> str:
    title_match = re.search(r"<title>(.*?)</title>", page_html, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        title = html.unescape(title_match.group(1)).strip()
        company = re.sub(r"\s+jobs?$", "", title, flags=re.IGNORECASE).strip()
        if company:
            return company
    return slug.replace("-", " ").title()


def _extract_lever_posting_blocks(page_html: str, max_jobs: int) -> list[dict[str, str]]:
    postings: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    pattern = re.compile(
        r'<div class="posting"[\s\S]*?<a class="posting-title" href="([^"]+)"[\s\S]*?<h5[^>]*>(.*?)</h5>[\s\S]*?<div class="posting-categories">([\s\S]*?)</div>',
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(page_html):
        url, title_html, categories_html = match.groups()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        categories = _strip_html(categories_html).replace("\xa0", " ").strip()
        location_match = re.search(
            r'<span[^>]*class="[^"]*\blocation\b[^"]*"[^>]*>(.*?)</span>',
            categories_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        commitment_match = re.search(
            r'<span[^>]*class="[^"]*\bcommitment\b[^"]*"[^>]*>(.*?)</span>',
            categories_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        workplace_match = re.search(
            r'<span[^>]*class="[^"]*\bworkplaceTypes\b[^"]*"[^>]*>(.*?)</span>',
            categories_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        postings.append(
            {
                "url": url,
                "title": _strip_html(title_html),
                "categories_text": categories,
                "location": _strip_html(location_match.group(1)) if location_match else "",
                "commitment": _strip_html(commitment_match.group(1)) if commitment_match else "",
                "workplace": _strip_html(workplace_match.group(1)) if workplace_match else "",
            }
        )
        if len(postings) >= max_jobs:
            break
    return postings


def _extract_lever_description(page_html: str) -> str:
    patterns = [
        r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<div class="content"[^>]*>([\s\S]*?)</div>',
        r'<div class="section-wrapper page-full-width"[^>]*>([\s\S]*?)</div>',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        text = _strip_html(html.unescape(match.group(1)))
        if text:
            return text[:8000]
    return ""


def scrape_lever_jobs(
    companies: list[str] | None = None,
    *,
    lane: str = "watchlist",
    max_jobs_per_company: int = LEVER_MAX_PER_COMPANY,
) -> list[dict[str, Any]]:
    targets = companies if companies is not None else LEVER_COMPANIES
    if not targets:
        log.info("Lever scraper (%s): no companies configured — skipping.", lane)
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MagnioJobRadar/1.0; +https://magnio.io)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    all_jobs: list[dict[str, Any]] = []

    for slug in targets:
        listing_url = f"{LEVER_SITE_BASE}/{slug}"
        try:
            resp = requests.get(listing_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException:
            log.warning("Lever: could not fetch board for slug '%s' — skipping.", slug)
            continue

        listing_html = resp.text
        company_name = _extract_lever_company_name(listing_html, slug)
        postings = _extract_lever_posting_blocks(listing_html, max_jobs=max_jobs_per_company)
        if not postings:
            log.warning("Lever: no postings found for slug '%s' — skipping.", slug)
            continue

        for posting in postings:
            parsed = urlparse(posting["url"])
            job_id = [part for part in parsed.path.split("/") if part]
            lever_job_id = job_id[-1] if job_id else uuid.uuid4().hex
            title = posting["title"] or "Lever Job"
            description_parts = [
                posting["categories_text"],
                posting["commitment"],
                posting["workplace"],
                posting["location"],
            ]
            description = "\n".join(part for part in description_parts if part).strip()
            lower_text = f"{title}\n{posting['location']}\n{posting['workplace']}\n{description}".lower()

            all_jobs.append(
                {
                    "id": f"lv_{lever_job_id}",
                    "title": title,
                    "company": company_name,
                    "url": posting["url"],
                    "source": "lever",
                    "source_detail": "public_html",
                    "company_slug": slug,
                    "collection_lane": lane,
                    "location": posting["location"],
                    "remote": "remote" in lower_text,
                    "salary": "",
                    "jd_full": description[:8000],
                    "scraped_at": datetime.datetime.utcnow().isoformat(),
                    "status": "pending",
                }
            )

    log.info(
        "Lever scraper (%s): fetched %d jobs from %d companies",
        lane, len(all_jobs), len(targets),
    )
    return all_jobs


def scrape_lever_watchlist_and_discovery(
    *,
    watchlist_companies: list[str] | None = None,
    discovery_companies: list[str] | None = None,
) -> dict[str, Any]:
    watchlist_targets = list(watchlist_companies if watchlist_companies is not None else LEVER_COMPANIES)
    discovery_targets = list(
        discovery_companies if discovery_companies is not None else LEVER_DISCOVERY_COMPANIES
    )
    watchlist_targets = _cap_companies(watchlist_targets, LEVER_MAX_COMPANIES)
    watchlist_seen = set(watchlist_targets)
    discovery_targets = [slug for slug in discovery_targets if slug not in watchlist_seen]
    discovery_targets = _cap_companies(
        discovery_targets,
        max(0, LEVER_MAX_COMPANIES - len(watchlist_targets)),
    )

    watchlist_jobs = scrape_lever_jobs(watchlist_targets, lane="watchlist")
    discovery_jobs = scrape_lever_jobs(discovery_targets, lane="discovery")

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for job in watchlist_jobs + discovery_jobs:
        job_id = str(job.get("id") or "").strip()
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        merged.append(job)

    merged = _cap_jobs(merged, LEVER_MAX_JOBS)

    return {
        "jobs": merged,
        "summary": {
            "source": "lever",
            "status": "ok" if merged else ("skipped" if not (watchlist_targets or discovery_targets) else "failed"),
            "strategy": "public_html_watchlist_and_discovery",
            "fetched": len(merged),
            "watchlist_companies": len(watchlist_targets),
            "watchlist_fetched": len(watchlist_jobs),
            "discovery_companies": len(discovery_targets),
            "discovery_fetched": len(discovery_jobs),
            "error": None if merged or (watchlist_targets or discovery_targets) else "No Lever companies configured.",
            "fallback_used": False,
        },
    }


# ---------------------------------------------------------------------------
# Ashby scraper
# ---------------------------------------------------------------------------

def _normalize_ashby_job(
    *,
    slug: str,
    company_name: str,
    lane: str,
    job: dict[str, Any],
) -> dict[str, Any]:
    job_id = str(job.get("id") or uuid.uuid4().hex)
    title = str(job.get("title") or "").strip()
    location = str(job.get("location") or "").strip()
    workplace_type = str(job.get("workplaceType") or "").strip()
    is_remote = bool(job.get("isRemote"))
    compensation = (job.get("compensation") or {}).get("scrapeableCompensationSalarySummary") or ""
    description_plain = (job.get("descriptionPlain") or "").strip()
    if not description_plain:
        description_plain = _strip_html(job.get("descriptionHtml") or "")
    if workplace_type and workplace_type.lower() not in location.lower():
        location = f"{location} · {workplace_type}".strip(" ·")
    remote = workplace_type.lower() == "remote" or (
        is_remote and workplace_type.lower() not in {"hybrid", "onsite"}
    )

    return {
        "id": f"ah_{job_id}",
        "title": title,
        "company": company_name,
        "url": job.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}/{job_id}",
        "source": "ashby",
        "source_detail": "posting_api",
        "company_slug": slug,
        "collection_lane": lane,
        "location": location,
        "remote": remote,
        "salary": compensation,
        "jd_full": description_plain[:8000],
        "scraped_at": datetime.datetime.utcnow().isoformat(),
        "status": "pending",
    }


def scrape_ashby_jobs(
    companies: list[str] | None = None,
    *,
    lane: str = "watchlist",
) -> list[dict[str, Any]]:
    targets = companies if companies is not None else ASHBY_COMPANIES
    if not targets:
        log.info("Ashby scraper (%s): no companies configured — skipping.", lane)
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MagnioJobRadar/1.0; +https://magnio.io)",
        "Accept": "application/json,text/plain,*/*",
    }
    all_jobs: list[dict[str, Any]] = []

    for slug in targets:
        url = f"{ASHBY_API_BASE}/{slug}?includeCompensation=true"
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException:
            log.warning("Ashby: could not fetch jobs for slug '%s' — skipping.", slug)
            continue

        data = resp.json()
        ashby_jobs: list[dict[str, Any]] = data.get("jobs") or []
        if not ashby_jobs:
            continue

        company_name = slug.title()
        sample_url = ashby_jobs[0].get("jobUrl") or ""
        if sample_url:
            parsed = urlparse(sample_url)
            parts = [part for part in parsed.path.split("/") if part]
            if parts:
                company_name = parts[0]

        for job in ashby_jobs:
            if job.get("isListed") is False:
                continue
            all_jobs.append(
                _normalize_ashby_job(
                    slug=slug,
                    company_name=company_name,
                    lane=lane,
                    job=job,
                )
            )

    log.info(
        "Ashby scraper (%s): fetched %d jobs from %d companies",
        lane, len(all_jobs), len(targets),
    )
    return all_jobs


def scrape_ashby_watchlist_and_discovery(
    *,
    watchlist_companies: list[str] | None = None,
    discovery_companies: list[str] | None = None,
) -> dict[str, Any]:
    watchlist_targets = list(watchlist_companies if watchlist_companies is not None else ASHBY_COMPANIES)
    discovery_targets = list(
        discovery_companies if discovery_companies is not None else ASHBY_DISCOVERY_COMPANIES
    )
    watchlist_targets = _cap_companies(watchlist_targets, ASHBY_MAX_COMPANIES)
    watchlist_seen = set(watchlist_targets)
    discovery_targets = [slug for slug in discovery_targets if slug not in watchlist_seen]
    discovery_targets = _cap_companies(
        discovery_targets,
        max(0, ASHBY_MAX_COMPANIES - len(watchlist_targets)),
    )

    watchlist_jobs = scrape_ashby_jobs(watchlist_targets, lane="watchlist")
    discovery_jobs = scrape_ashby_jobs(discovery_targets, lane="discovery")

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for job in watchlist_jobs + discovery_jobs:
        job_id = str(job.get("id") or "").strip()
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        merged.append(job)

    merged = _cap_jobs(merged, ASHBY_MAX_JOBS)

    return {
        "jobs": merged,
        "summary": {
            "source": "ashby",
            "status": "ok" if merged else ("skipped" if not (watchlist_targets or discovery_targets) else "failed"),
            "strategy": "posting_api_watchlist_and_discovery",
            "fetched": len(merged),
            "watchlist_companies": len(watchlist_targets),
            "watchlist_fetched": len(watchlist_jobs),
            "discovery_companies": len(discovery_targets),
            "discovery_fetched": len(discovery_jobs),
            "error": None if merged or (watchlist_targets or discovery_targets) else "No Ashby companies configured.",
            "fallback_used": False,
        },
    }


# ---------------------------------------------------------------------------
# Hacker News scraper
# ---------------------------------------------------------------------------

def scrape_hn_jobs(limit: int = 40) -> list[dict[str, Any]]:
    url = "https://hacker-news.firebaseio.com/v0/user/whoishiring.json"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        data = resp.json()
    except Exception as exc:
        log.warning("HN scraper: failed to load whoishiring user - %s", exc)
        return []
        
    thread_id = None
    for item_id in data.get("submitted", [])[:10]:
        try:
            item = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                timeout=min(REQUEST_TIMEOUT_SECONDS, 10),
            ).json()
            if item and item.get("title", "").startswith("Ask HN: Who is hiring?"):
                thread_id = item_id
                break
        except:
            pass
            
    if not thread_id:
        log.warning("HN scraper: couldn't find a recent Who is Hiring thread.")
        return []
        
    try:
        thread = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{thread_id}.json",
            timeout=min(REQUEST_TIMEOUT_SECONDS, 10),
        ).json()
    except:
        return []
        
    kids = thread.get("kids", [])[:limit]
    jobs: list[dict[str, Any]] = []
    
    for kid_id in kids:
        try:
            comment = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json",
                timeout=min(REQUEST_TIMEOUT_SECONDS, 10),
            ).json()
        except:
            continue
            
        if not comment or comment.get("deleted") or not comment.get("text"):
            continue
            
        text_html = comment.get("text", "")
        clean_text = _strip_html(text_html)
        by = comment.get("by", "unknown")
        
        lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
        first_line = lines[0][:100] if lines else f"HN Opportunity from {by}"
        
        jobs.append({
            "id": f"hn_{kid_id}",
            "title": first_line,
            "company": f"HN Poster: {by}",
            "url": f"https://news.ycombinator.com/item?id={kid_id}",
            "source": "hackernews",
            "source_detail": "firebase_api",
            "company_slug": str(by).lower(),
            "collection_lane": "discovery",
            "location": "",
            "remote": "remote" in clean_text.lower(),
            "salary": "",
            "jd_full": clean_text[:8000],
            "scraped_at": datetime.datetime.utcnow().isoformat(),
            "status": "pending",
        })
        
    log.info("HN scraper: fetched %d jobs from thread %s", len(jobs), thread_id)
    return jobs

def scrape_hn_with_fallback(limit: int = 40) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "source": "hackernews",
        "status": "skipped",
        "strategy": None,
        "fetched": 0,
        "error": None,
        "fallback_used": False,
    }
    try:
        jobs = scrape_hn_jobs(limit=limit)
    except Exception as exc:
        jobs = []
        error = str(exc)
    else:
        error = None

    if jobs:
        summary.update({
            "status": "ok",
            "strategy": "firebase_api",
            "fetched": len(jobs),
            "error": None,
        })
        return {"jobs": jobs, "summary": summary}

    summary.update({
        "status": "failed" if error else "skipped",
        "strategy": "firebase_api",
        "fetched": 0,
        "error": error or "No HN jobs fetched.",
    })
    return {"jobs": [], "summary": summary}


# ---------------------------------------------------------------------------
# Workable — public apply API
# Apply page: https://apply.workable.com/{slug}/
# ---------------------------------------------------------------------------
WORKABLE_API_BASE = "https://apply.workable.com/api/v3/accounts"

DEFAULT_WORKABLE_DISCOVERY_COMPANIES = []

_WORKABLE_ENV = os.environ.get("JOBRADAR_WORKABLE_COMPANIES", "").strip()
WORKABLE_COMPANIES: list[str] = _parse_company_list(_WORKABLE_ENV)
_WORKABLE_DISCOVERY_ENV = os.environ.get("JOBRADAR_WORKABLE_DISCOVERY_COMPANIES", "").strip()
WORKABLE_DISCOVERY_COMPANIES: list[str] = (
    _parse_company_list(_WORKABLE_DISCOVERY_ENV)
    if _WORKABLE_DISCOVERY_ENV
    else list(DEFAULT_WORKABLE_DISCOVERY_COMPANIES)
)
WORKABLE_MAX_COMPANIES = int(os.environ.get("JOBRADAR_WORKABLE_MAX_COMPANIES", "4"))
WORKABLE_MAX_JOBS = int(os.environ.get("JOBRADAR_WORKABLE_MAX_JOBS", "40"))

REQUEST_TIMEOUT_SECONDS = int(os.environ.get("JOBRADAR_REQUEST_TIMEOUT_SECONDS", "12"))


def _cap_companies(companies: list[str], cap: int) -> list[str]:
    if cap <= 0:
        return []
    return companies[:cap]


def _cap_jobs(jobs: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    if cap <= 0:
        return []
    return jobs[:cap]


def scrape_workable_jobs(
    companies: list[str] | None = None,
    *,
    lane: str = "watchlist",
) -> list[dict[str, Any]]:
    """
    Fetch jobs from Workable public apply API for each company slug.

    Slugs match the company's Workable URL: https://apply.workable.com/{slug}/
    """
    targets = companies if companies is not None else WORKABLE_COMPANIES
    if not targets:
        log.info("Workable scraper (%s): no companies configured — skipping.", lane)
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MagnioJobRadar/1.0; +https://magnio.io)",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    all_jobs: list[dict[str, Any]] = []

    for slug in targets:
        list_url = f"{WORKABLE_API_BASE}/{slug}/jobs"
        try:
            resp = requests.post(
                list_url,
                json={"query": "", "location": [], "department": [], "worktype": [], "remote": []},
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except requests.RequestException:
            log.warning("Workable: could not fetch jobs for slug '%s' — skipping.", slug)
            continue

        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            log.warning("Workable: non-JSON response for slug '%s' — skipping.", slug)
            continue
        job_listings: list[dict[str, Any]] = data.get("results") or []
        if not job_listings:
            continue

        # Derive a readable company name from the first job URL if possible
        company_name = slug.replace("-", " ").title()

        for listing in job_listings:
            shortcode = str(listing.get("shortcode") or "").strip()
            if not shortcode:
                continue

            # Fetch full job details for the complete description
            detail_url = f"{WORKABLE_API_BASE}/{slug}/jobs/{shortcode}"
            try:
                detail_resp = requests.get(detail_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
                detail_resp.raise_for_status()
                detail = detail_resp.json()
            except requests.RequestException:
                detail = listing

            title = str(detail.get("title") or listing.get("title") or "").strip()
            location_raw = detail.get("location") or listing.get("location")
            if isinstance(location_raw, dict):
                city = str(location_raw.get("city") or "").strip()
                country = str(location_raw.get("country") or "").strip()
                location = ", ".join(p for p in [city, country] if p)
            elif isinstance(location_raw, str):
                location = location_raw.strip()
            else:
                location = ""
            is_remote = bool(detail.get("remote") or listing.get("remote"))

            description_html = str(detail.get("description") or "")
            requirements_html = str(detail.get("requirements") or "")
            benefits_html = str(detail.get("benefits") or "")
            jd_parts = [
                _strip_html(description_html),
                _strip_html(requirements_html),
                _strip_html(benefits_html),
            ]
            jd_text = "\n\n".join(p for p in jd_parts if p)[:8000]

            job_url = f"https://apply.workable.com/{slug}/j/{shortcode}/"
            lower_text = f"{title} {location}".lower()

            all_jobs.append({
                "id": f"wk_{shortcode}",
                "title": title,
                "company": company_name,
                "url": job_url,
                "source": "workable",
                "source_detail": "apply_api",
                "company_slug": slug,
                "collection_lane": lane,
                "location": location,
                "remote": is_remote or "remote" in lower_text,
                "salary": "",
                "jd_full": jd_text,
                "scraped_at": datetime.datetime.utcnow().isoformat(),
                "status": "pending",
            })

    log.info(
        "Workable scraper (%s): fetched %d jobs from %d companies",
        lane, len(all_jobs), len(targets),
    )
    return all_jobs


def scrape_workable_watchlist_and_discovery(
    *,
    watchlist_companies: list[str] | None = None,
    discovery_companies: list[str] | None = None,
) -> dict[str, Any]:
    watchlist_targets = list(watchlist_companies if watchlist_companies is not None else WORKABLE_COMPANIES)
    discovery_targets = list(
        discovery_companies if discovery_companies is not None else WORKABLE_DISCOVERY_COMPANIES
    )
    watchlist_targets = _cap_companies(watchlist_targets, WORKABLE_MAX_COMPANIES)
    watchlist_seen = set(watchlist_targets)
    discovery_targets = [slug for slug in discovery_targets if slug not in watchlist_seen]
    discovery_targets = _cap_companies(
        discovery_targets,
        max(0, WORKABLE_MAX_COMPANIES - len(watchlist_targets)),
    )

    watchlist_jobs = scrape_workable_jobs(watchlist_targets, lane="watchlist")
    discovery_jobs = scrape_workable_jobs(discovery_targets, lane="discovery")

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for job in watchlist_jobs + discovery_jobs:
        job_id = str(job.get("id") or "").strip()
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        merged.append(job)

    merged = _cap_jobs(merged, WORKABLE_MAX_JOBS)

    return {
        "jobs": merged,
        "summary": {
            "source": "workable",
            "status": "ok" if merged else ("skipped" if not (watchlist_targets or discovery_targets) else "failed"),
            "strategy": "apply_api_watchlist_and_discovery",
            "fetched": len(merged),
            "watchlist_companies": len(watchlist_targets),
            "watchlist_fetched": len(watchlist_jobs),
            "discovery_companies": len(discovery_targets),
            "discovery_fetched": len(discovery_jobs),
            "error": None if merged or (watchlist_targets or discovery_targets) else "No Workable companies configured.",
            "fallback_used": False,
        },
    }


# ---------------------------------------------------------------------------
# Firestore writer
# ---------------------------------------------------------------------------

def write_jobs_to_firestore(
    jobs: list[dict[str, Any]],
    *,
    overwrite_existing: bool = False,
) -> dict[str, int]:
    """
    Write job documents to Firestore ``jobs_raw`` collection.
    Skips documents that already exist unless *overwrite_existing* is True.
    Returns write statistics.
    """
    if not jobs:
        return {"written": 0, "deduped_in_batch": 0, "skipped_existing": 0}

    db = get_firestore_client()
    collection = db.collection("jobs_raw")
    deduped_jobs, deduped_in_batch = dedupe_jobs(jobs)
    written = 0
    skipped_existing = 0

    def _chunked(values: list[str], size: int = 10) -> list[list[str]]:
        return [values[i:i + size] for i in range(0, len(values), size)]

    if not overwrite_existing:
        refs = [collection.document(job["id"]) for job in deduped_jobs]
        existing_ids = {snap.id for snap in db.get_all(refs) if snap.exists}

        dedupe_keys = sorted({str(job.get("dedupe_key") or "") for job in deduped_jobs if job.get("dedupe_key")})
        role_keys = sorted({str(job.get("role_key") or "") for job in deduped_jobs if job.get("role_key")})

        existing_dedupe_keys: set[str] = set()
        existing_role_keys: set[str] = set()
        for chunk in _chunked(dedupe_keys):
            docs = collection.where("dedupe_key", "in", chunk).stream()
            existing_dedupe_keys.update(str((doc.to_dict() or {}).get("dedupe_key") or "") for doc in docs)
        for chunk in _chunked(role_keys):
            docs = collection.where("role_key", "in", chunk).stream()
            existing_role_keys.update(str((doc.to_dict() or {}).get("role_key") or "") for doc in docs)

        jobs_to_write = []
        for job in deduped_jobs:
            if job["id"] in existing_ids:
                skipped_existing += 1
                continue
            dedupe_key = str(job.get("dedupe_key") or "")
            role_key = str(job.get("role_key") or "")
            if dedupe_key and dedupe_key in existing_dedupe_keys:
                skipped_existing += 1
                continue
            if role_key and role_key in existing_role_keys:
                skipped_existing += 1
                continue
            jobs_to_write.append(job)
    else:
        jobs_to_write = deduped_jobs

    batch = db.batch()
    for job in jobs_to_write:
        batch.set(collection.document(job["id"]), job)
        written += 1
    if written:
        batch.commit()

    log.info(
        "Firestore: wrote %d new job documents to jobs_raw (%d deduped in batch, %d skipped existing)",
        written,
        deduped_in_batch,
        skipped_existing,
    )
    return {
        "written": written,
        "deduped_in_batch": deduped_in_batch,
        "skipped_existing": skipped_existing,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_scraper(
    yc_limit: int = 40,
    hn_limit: int = 40,
    greenhouse_companies: list[str] | None = None,
    greenhouse_discovery_companies: list[str] | None = None,
    lever_companies: list[str] | None = None,
    lever_discovery_companies: list[str] | None = None,
    ashby_companies: list[str] | None = None,
    ashby_discovery_companies: list[str] | None = None,
    workable_companies: list[str] | None = None,
    workable_discovery_companies: list[str] | None = None,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Scrape all configured sources and persist to Firestore. Returns a summary."""
    _empty: dict[str, Any] = {"jobs": [], "summary": {}}

    try:
        yc_result = scrape_yc_jobs_with_fallback(limit=yc_limit)
    except Exception:
        log.exception("YC scraper failed — continuing without YC jobs")
        yc_result = _empty
    yc_jobs = yc_result["jobs"]

    if hn_limit > 0:
        try:
            hn_result = scrape_hn_with_fallback(limit=hn_limit)
        except Exception:
            log.exception("HN scraper failed — continuing without HN jobs")
            hn_result = _empty
    else:
        hn_result = {
            "jobs": [],
            "summary": {
                "source": "hackernews",
                "status": "skipped",
                "strategy": "disabled",
                "fetched": 0,
                "error": "HN scraping disabled for this run.",
                "fallback_used": False,
            },
        }
    hn_jobs = hn_result["jobs"]

    try:
        gh_result = scrape_greenhouse_watchlist_and_discovery(
            watchlist_companies=greenhouse_companies,
            discovery_companies=greenhouse_discovery_companies,
        )
    except Exception:
        log.exception("Greenhouse scraper failed — continuing without GH jobs")
        gh_result = _empty
    gh_jobs = gh_result["jobs"]

    try:
        lever_result = scrape_lever_watchlist_and_discovery(
            watchlist_companies=lever_companies,
            discovery_companies=lever_discovery_companies,
        )
    except Exception:
        log.exception("Lever scraper failed — continuing without Lever jobs")
        lever_result = _empty
    lever_jobs = lever_result["jobs"]

    try:
        ashby_result = scrape_ashby_watchlist_and_discovery(
            watchlist_companies=ashby_companies,
            discovery_companies=ashby_discovery_companies,
        )
    except Exception:
        log.exception("Ashby scraper failed — continuing without Ashby jobs")
        ashby_result = _empty
    ashby_jobs = ashby_result["jobs"]

    try:
        workable_result = scrape_workable_watchlist_and_discovery(
            watchlist_companies=workable_companies,
            discovery_companies=workable_discovery_companies,
        )
    except Exception:
        log.exception("Workable scraper failed — continuing without Workable jobs")
        workable_result = _empty
    workable_jobs = workable_result["jobs"]
    all_jobs = yc_jobs + hn_jobs + gh_jobs + lever_jobs + ashby_jobs + workable_jobs
    write_stats = write_jobs_to_firestore(all_jobs, overwrite_existing=overwrite)

    return {
        "yc_fetched": len(yc_jobs),
        "hackernews_fetched": len(hn_jobs),
        "greenhouse_fetched": len(gh_jobs),
        "lever_fetched": len(lever_jobs),
        "ashby_fetched": len(ashby_jobs),
        "workable_fetched": len(workable_jobs),
        "total_fetched": len(all_jobs),
        "new_written": write_stats["written"],
        "deduped_in_batch": write_stats["deduped_in_batch"],
        "skipped_existing": write_stats["skipped_existing"],
        "sources": {
            "yc": yc_result["summary"],
            "hackernews": hn_result["summary"],
            "greenhouse": gh_result["summary"],
            "lever": lever_result["summary"],
            "ashby": ashby_result["summary"],
            "workable": workable_result["summary"],
        },
    }
