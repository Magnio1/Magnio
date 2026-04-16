"""
JobRadar prompt builder + Claude scorer.

For each pending job in Firestore ``jobs_raw``:
  1. Loads Sebastian's knowledge nodes from ``content/chat/`` (lazy, cached).
  2. Assembles a structured scoring prompt with full JD + profile context.
  3. Calls Claude Sonnet 4.6 via OpenRouter.
  4. Parses the structured JSON response.
  5. Writes enriched result to Firestore ``jobs_enriched``.
  6. Marks the job as "scored" in ``jobs_raw``.

Configuration
-------------
JOBRADAR_SCORER_MODEL   — default: anthropic/claude-sonnet-4-6
JOBRADAR_MAX_JD_CHARS   — max JD characters sent to Claude (default: 6000)
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from api.firebase_client import get_firestore_client
from api.openrouter_client import chat_completion, extract_message_text

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCORER_MODEL = os.environ.get("JOBRADAR_SCORER_MODEL", "anthropic/claude-sonnet-4-6").strip()
MAX_JD_CHARS = int(os.environ.get("JOBRADAR_MAX_JD_CHARS", "6000"))

# ---------------------------------------------------------------------------
# Red-flag patterns (Sebastian-specific; encoded once here)
# ---------------------------------------------------------------------------
RED_FLAG_PATTERNS = [
    "contract-to-hire without clear conversion terms or timeline",
    "configurator-not-builder role — implementing vendor tools rather than building systems",
    "no AI-native scope — using AI to marginally improve existing processes, not building AI products",
    "pure management or team-lead role without hands-on engineering ownership",
    "hiring-manager hesitation signals — excessive focus on process over outcomes, vague or shifting scope",
    "heavy ML research / model training focus rather than applied production systems engineering",
    "staff-augmentation or body-shop engagement model with no product ownership",
    "no agentic or orchestration scope — traditional SWE role with AI bolted on as a buzzword",
]

# ---------------------------------------------------------------------------
# Profile context (lazy-loaded from content/chat/*.json, cached in memory)
# ---------------------------------------------------------------------------
_CONTENT_DIR = Path(__file__).resolve().parents[1] / "content" / "chat"
_PROFILE_CONTEXT: str = ""


def _load_profile_context() -> str:
    """
    Build a flat profile context string from Sebastian's knowledge chunks.
    Loads chunks tagged with focus: fit | proof | operations | agentic.
    """
    chunks: list[str] = []
    for path in sorted(_CONTENT_DIR.glob("*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            focus = item.get("focus") or []
            if any(f in focus for f in ("fit", "proof", "operations", "agentic")):
                chunk_id = item.get("id", "?")
                title = item.get("title", "")
                body = item.get("body", "")
                chunks.append(f"[{chunk_id}] {title}\n{body}")

    return "\n\n".join(chunks)


def _get_profile_context() -> str:
    global _PROFILE_CONTEXT
    if not _PROFILE_CONTEXT:
        _PROFILE_CONTEXT = _load_profile_context()
    return _PROFILE_CONTEXT


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_scoring_prompt(job: dict[str, Any]) -> str:
    jd = (job.get("jd_full") or "")[:MAX_JD_CHARS]
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    salary = job.get("salary", "")
    source = job.get("source", "")
    url = job.get("url", "")

    profile = _get_profile_context()
    red_flags_list = "\n".join(f"- {rf}" for rf in RED_FLAG_PATTERNS)

    return f"""You are a precise job fit evaluator for Sebastian Rosales, an AI systems engineer.
Your role: evaluate job opportunities with honesty and specificity — no generic career advice.

## SEBASTIAN'S PROFILE & POSITIONING

{profile}

## RED FLAG PATTERNS — WATCH CAREFULLY

{red_flags_list}

## JOB TO EVALUATE

Title:    {title}
Company:  {company}
Location: {location}
Salary:   {salary or "not listed"}
Source:   {source}
URL:      {url}

--- Job Description ---
{jd or "(No description provided)"}
--- End ---

## YOUR TASK

Evaluate this job for Sebastian and return ONLY a valid JSON object with this exact structure:

{{
  "fit_score": <integer 0-100>,
  "summary": "<2-3 sentences: honest fit assessment, what makes this strong or weak for Sebastian specifically>",
  "red_flags": ["<specific flag detected in this JD>", ...],
  "strengths": ["<specific strength match between Sebastian and this role>", ...],
  "positioning_note": "<1-2 sentences: how Sebastian should frame Actus / Magnio / CIC for THIS specific role>",
  "outreach_draft": "<2-3 sentence personalized cold-outreach opening for this role>",
  "recommendation": "<exactly one of: pursue | review | bypass>"
}}

Scoring guide:
  85-100  Exceptional — AI systems engineer, agentic workflows, production delivery, measurable impact scope
  70-84   Strong — most criteria met, minor gaps easily addressed
  55-69   Mixed — worth reviewing if pipeline is thin; flag gaps explicitly
  40-54   Weak — significant misalignment; only pursue if context changes
  0-39    Bypass — configurator role, no AI scope, contract-only, or clear deal-breaker flags

Respond with ONLY the JSON object. No preamble, no trailing explanation."""


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

def score_job(job: dict[str, Any]) -> dict[str, Any]:
    """Call Claude to score a single job. Returns enriched data dict."""
    prompt = _build_scoring_prompt(job)
    try:
        response = chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=SCORER_MODEL,
            temperature=0.2,
            max_tokens=1024,
        )
        raw_text = extract_message_text(response)

        # Extract the first JSON object from the response
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if not json_match:
            raise ValueError("No JSON block found in Claude response")
        result: dict[str, Any] = json.loads(json_match.group(0))

    except Exception as exc:
        log.error("Scoring failed for job %s: %s", job.get("id"), exc)
        result = {
            "fit_score": 50,
            "summary": "Automated scoring failed — manual review required.",
            "red_flags": [],
            "strengths": [],
            "positioning_note": "",
            "outreach_draft": "",
            "recommendation": "review",
        }

    result["enriched_at"] = datetime.datetime.utcnow().isoformat()
    result["job_id"] = job["id"]
    return result


# ---------------------------------------------------------------------------
# Batch scorer
# ---------------------------------------------------------------------------

def _select_jobs_for_scoring(jobs: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if not jobs or limit <= 0:
        return []

    jobs = sorted(jobs, key=lambda job: str(job.get("scraped_at") or ""), reverse=True)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        source = str(job.get("source") or "unknown")
        grouped[source].append(job)

    source_order = sorted(
        grouped.keys(),
        key=lambda source: str(grouped[source][0].get("scraped_at") or ""),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    while len(selected) < limit:
        made_progress = False
        for source in source_order:
            bucket = grouped[source]
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            made_progress = True
            if len(selected) >= limit:
                break
        if not made_progress:
            break

    return selected

def score_pending_jobs(limit: int = 30) -> list[dict[str, Any]]:
    """
    Fetch pending jobs from ``jobs_raw``, score each with Claude,
    write results to ``jobs_enriched``, mark source jobs as "scored".
    Returns list of enriched dicts.
    """
    db = get_firestore_client()
    raw_col = db.collection("jobs_raw")
    enriched_col = db.collection("jobs_enriched")

    pending_stream = raw_col.where("status", "==", "pending").stream()
    jobs = [doc.to_dict() for doc in pending_stream]
    jobs = _select_jobs_for_scoring(jobs, limit)

    if not jobs:
        log.info("No pending jobs to score.")
        return []

    max_workers = min(8, len(jobs))
    source_counts: dict[str, int] = defaultdict(int)
    for job in jobs:
        source_counts[str(job.get("source") or "unknown")] += 1
    log.info("Scoring %d pending jobs with %s (%d workers)...", len(jobs), SCORER_MODEL, max_workers)
    log.info("Scoring batch source mix: %s", dict(source_counts))
    enriched: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_job = {pool.submit(score_job, job): job for job in jobs}
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                enriched_data = future.result()
            except Exception as exc:
                log.error("Scoring future failed for %s: %s", job.get("id"), exc)
                continue
            enriched_col.document(job["id"]).set(enriched_data)
            raw_col.document(job["id"]).update({"status": "scored"})
            enriched.append(enriched_data)
            log.info(
                "Scored %s | score=%s | recommendation=%s",
                job.get("id"),
                enriched_data.get("fit_score"),
                enriched_data.get("recommendation"),
            )

    return enriched
