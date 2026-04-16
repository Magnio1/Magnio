"""
JobRadar pipeline orchestrator.

Morning workflow
----------------
  1. Scrape YC + Greenhouse  →  jobs_raw  (status: pending)
  2. Score pending jobs with Claude  →  jobs_enriched
  3. Rank by fit_score; filter to top N with recommendation: pursue | review
  4. Mark shortlisted jobs in jobs_enriched (shortlisted: true)
  5. Log pipeline run metadata to pipeline_runs collection

Usage
-----
  from api.jobs_pipeline import run_pipeline, get_curated_jobs

  # trigger full run
  summary = run_pipeline()

  # fetch triage dashboard data
  jobs = get_curated_jobs(limit=20)
"""
from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from api.firebase_client import get_firestore_client
from api.jobs_scraper import build_job_dedupe_keys
from api.jobs_scraper import run_scraper
from api.jobs_prompt_builder import score_pending_jobs

log = logging.getLogger(__name__)


def _dedupe_curated_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for job in jobs:
        dedupe_key = str(job.get("dedupe_key") or "")
        role_key = str(job.get("role_key") or "")
        if not dedupe_key and not role_key:
            dedupe_key, role_key = build_job_dedupe_keys(job)
        key = dedupe_key or role_key or str(job.get("id") or "")
        existing = deduped.get(key)
        if existing is None or job.get("fit_score", 0) >= existing.get("fit_score", 0):
            deduped[key] = job
    result = list(deduped.values())
    # Sort first by the day it was evaluated (YYYY-MM-DD), then by fit_score descending.
    # This guarantees the newest batch always sits at the top of the dashboard,
    # ranked perfectly by score within that daily batch.
    result.sort(
        key=lambda x: (
            str(x.get("enriched_at") or x.get("scraped_at") or "")[:10],
            x.get("fit_score", 0)
        ),
        reverse=True
    )
    return result


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_pipeline(
    *,
    yc_limit: int = 40,
    hn_limit: int = 0,
    greenhouse_companies: list[str] | None = None,
    score_limit: int = 40,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Full pipeline: scrape → score → rank → log.

    Returns a summary dict (run metadata + curated shortlist).
    The shortlist is ordered: pursue first (by score desc), then review.
    """
    run_id = uuid.uuid4().hex
    started_at = datetime.datetime.utcnow().isoformat()
    log.info("Pipeline run %s started at %s", run_id, started_at)

    # 1. Scrape
    scrape_summary = run_scraper(
        yc_limit=yc_limit,
        hn_limit=hn_limit,
        greenhouse_companies=greenhouse_companies,
    )

    # 2. Score pending jobs
    enriched = score_pending_jobs(limit=score_limit)

    # 3. Rank: pursue first, then review; each group sorted by fit_score desc
    pursue = sorted(
        [e for e in enriched if e.get("recommendation") == "pursue"],
        key=lambda x: x.get("fit_score", 0),
        reverse=True,
    )
    review = sorted(
        [e for e in enriched if e.get("recommendation") == "review"],
        key=lambda x: x.get("fit_score", 0),
        reverse=True,
    )
    ranked = (pursue + review)[:top_n]

    # 4. Mark shortlisted jobs in Firestore
    db = get_firestore_client()
    for item in ranked:
        try:
            db.collection("jobs_enriched").document(item["job_id"]).update({"shortlisted": True})
        except Exception as exc:
            log.warning("Could not mark job %s as shortlisted: %s", item.get("job_id"), exc)

    # 5. Log pipeline run
    completed_at = datetime.datetime.utcnow().isoformat()
    run_doc: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "scrape_summary": scrape_summary,
        "total_scored": len(enriched),
        "shortlist_count": len(ranked),
        "shortlist_job_ids": [s["job_id"] for s in ranked],
    }
    db.collection("pipeline_runs").document(run_id).set(run_doc)
    log.info(
        "Pipeline run %s complete: %d scored, %d shortlisted",
        run_id, len(enriched), len(ranked),
    )

    return {**run_doc, "shortlist": ranked}


# ---------------------------------------------------------------------------
# Dashboard data fetcher
# ---------------------------------------------------------------------------

def get_curated_jobs(limit: int = 20, *, status_filter: str | None = None) -> list[dict[str, Any]]:
    """
    Return merged job data (raw + enriched) sorted by fit_score descending.
    Used by the triage dashboard to render job cards.

    Parameters
    ----------
    limit : int
        Max number of jobs to return.
    status_filter : str | None
        If set, only return jobs with jobs_raw.status == this value.
        e.g. "pending", "approved", "bypassed", "scored"
    """
    db = get_firestore_client()
    raw_col = db.collection("jobs_raw")
    enriched_col = db.collection("jobs_enriched")
    fetch_limit = max(limit * 4, 40)

    # Fetch newest enriched jobs (instead of all-time highest scores)
    try:
        enriched_query = (
            enriched_col
            .order_by("enriched_at", direction="DESCENDING")
            .limit(fetch_limit)
        )
        enriched_docs = list(enriched_query.stream())
    except Exception as exc:
        # Fallback if Firestore composite index isn't ready yet
        log.warning("Ordered query failed (%s); falling back to unordered fetch.", exc)
        enriched_docs = list(enriched_col.limit(fetch_limit).stream())

    result: list[dict[str, Any]] = []
    raw_refs = []
    enriched_rows: list[tuple[str, dict[str, Any]]] = []

    for enc_doc in enriched_docs:
        enc: dict[str, Any] = enc_doc.to_dict() or {}
        job_id = enc.get("job_id") or enc_doc.id
        enriched_rows.append((job_id, enc))
        raw_refs.append(raw_col.document(job_id))

    raw_docs = list(db.get_all(raw_refs)) if raw_refs else []
    raw_by_id: dict[str, dict[str, Any]] = {
        snap.id: (snap.to_dict() or {})
        for snap in raw_docs
        if snap.exists
    }

    for job_id, enc in enriched_rows:
        raw: dict[str, Any] = raw_by_id.get(job_id, {})

        # Optional status filter applied against raw data
        if status_filter and raw.get("status") != status_filter:
            continue

        merged = {**raw, **enc, "id": job_id}
        result.append(merged)

    return _dedupe_curated_jobs(result)[:limit]
