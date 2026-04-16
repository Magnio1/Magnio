"""
JobRadar API routes.

All endpoints are protected by the same x-task-token header used by the
admin leads panel (TASKS_API_TOKEN env var).

Endpoints
---------
GET  /jobs                  — list curated jobs (enriched + raw merged)
POST /jobs/pipeline/run     — trigger scrape → score → rank pipeline
GET  /jobs/pipeline/runs    — list recent pipeline runs
POST /jobs/{job_id}/status  — update job status (approved/bypassed/saved)
POST /jobs/chat             — streaming Advisor chat with job context
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.firebase_client import get_firestore_client
from api.jobs_pipeline import get_curated_jobs, run_pipeline
from api.openrouter_client import chat_completion_stream

log = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _require_token(req: Request) -> None:
    expected = os.environ.get("TASKS_API_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="TASKS_API_TOKEN not configured.")
    if req.headers.get("x-task-token", "") != expected:
        raise HTTPException(status_code=401, detail="Unauthorized.")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StatusUpdate(BaseModel):
    status: Literal["approved", "bypassed", "saved", "pending", "scored"]
    bypass_reason: Optional[str] = None


class JobChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class JobChatRequest(BaseModel):
    job_id: str
    messages: list[JobChatMessage]


class PipelineRunRequest(BaseModel):
    yc_limit: int = 40
    hn_limit: int = 0
    score_limit: int = 40
    top_n: int = 10


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_jobs(req: Request, limit: int = 20, status: Optional[str] = None):
    """Return curated jobs sorted by fit_score descending."""
    _require_token(req)
    try:
        jobs = get_curated_jobs(limit=limit, status_filter=status)
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as exc:
        log.error("list_jobs error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/pipeline/run")
async def trigger_pipeline(req: Request, body: PipelineRunRequest = PipelineRunRequest()):
    """
    Trigger a full pipeline run: scrape → score → rank → log.
    This can take 2-5 minutes depending on job count and Claude latency.
    Returns pipeline run metadata (not the full shortlist).
    """
    _require_token(req)
    try:
        summary = run_pipeline(
            yc_limit=body.yc_limit,
            hn_limit=body.hn_limit,
            score_limit=body.score_limit,
            top_n=body.top_n,
        )
        # Exclude the shortlist payload from the response (use GET /jobs for that)
        return {
            "run_id": summary["run_id"],
            "started_at": summary["started_at"],
            "completed_at": summary["completed_at"],
            "scrape_summary": summary["scrape_summary"],
            "total_scored": summary["total_scored"],
            "shortlist_count": summary["shortlist_count"],
        }
    except Exception as exc:
        log.error("pipeline run error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pipeline/runs")
async def list_pipeline_runs(req: Request, limit: int = 10):
    """Return recent pipeline run metadata sorted by started_at descending."""
    _require_token(req)
    try:
        db = get_firestore_client()
        docs = (
            db.collection("pipeline_runs")
            .order_by("started_at", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        runs = [doc.to_dict() for doc in docs]
        return {"runs": runs}
    except Exception as exc:
        log.error("list_pipeline_runs error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{job_id}/status")
async def update_job_status(job_id: str, body: StatusUpdate, req: Request):
    """Update the status of a job in jobs_raw (approve / bypass / save)."""
    _require_token(req)
    try:
        db = get_firestore_client()
        update: dict[str, Any] = {"status": body.status}
        if body.bypass_reason:
            update["bypass_reason"] = body.bypass_reason
        db.collection("jobs_raw").document(job_id).update(update)
        return {"ok": True, "job_id": job_id, "status": body.status}
    except Exception as exc:
        log.error("update_job_status error for %s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat")
async def job_chat(body: JobChatRequest, req: Request):
    """
    Streaming Advisor chat pre-loaded with full job context.
    Right panel of the triage dashboard.

    The system prompt includes the full job posting, fit score, red flags,
    strengths, positioning note, and outreach draft so Sebastian can ask
    any question about the job without re-pasting context.
    """
    _require_token(req)

    # Load job data from Firestore — fetch both collections in parallel
    db = get_firestore_client()
    with ThreadPoolExecutor(max_workers=2) as pool:
        raw_future = pool.submit(db.collection("jobs_raw").document(body.job_id).get)
        enc_future = pool.submit(db.collection("jobs_enriched").document(body.job_id).get)
        raw_snap = raw_future.result()
        enc_snap = enc_future.result()

    raw: dict[str, Any] = raw_snap.to_dict() if raw_snap.exists else {}
    enc: dict[str, Any] = enc_snap.to_dict() if enc_snap.exists else {}

    red_flags_text = "\n".join(f"  - {rf}" for rf in (enc.get("red_flags") or [])) or "  None detected"
    strengths_text = "\n".join(f"  - {s}" for s in (enc.get("strengths") or [])) or "  N/A"
    jd_excerpt = (raw.get("jd_full") or "")[:3000]

    job_context = f"""## Job Being Evaluated

Title:          {raw.get("title", "Unknown")}
Company:        {raw.get("company", "Unknown")}
Location:       {raw.get("location", "") or "Not listed"}
Salary:         {raw.get("salary", "") or "Not listed"}
Source:         {raw.get("source", "")}
URL:            {raw.get("url", "")}
Fit Score:      {enc.get("fit_score", "N/A")}/100
Recommendation: {enc.get("recommendation", "N/A")}

Red Flags:
{red_flags_text}

Strengths:
{strengths_text}

Positioning Note:
  {enc.get("positioning_note", "")}

Outreach Draft:
  {enc.get("outreach_draft", "")}

Job Description (excerpt):
{jd_excerpt}"""

    system_prompt = f"""You are JobRadar Advisor — Sebastian Rosales's precise, professional, and highly competent technical career advisor.

You speak with clarity, confidence, and directness. Your tone is calm and professional, never overly casual or emotional. You act like a senior engineering mentor who values accuracy and strategy over warmth.

You have deep, detailed knowledge of Sebastian's background:
- Actus and CIC: production agentic systems with deterministic routing, 24-intent orchestration, hybrid RAG, audit-safe outputs, $500K+ credit recovery, 95%+ billing accuracy, and 100% enterprise adoption.
- Magnio: multi-model orchestration with judge synthesis, hybrid RAG, arena mode, and lead automation.
- His preference for building real systems (architecture, tradeoffs, production delivery) over syntax-heavy live coding or pure configuration work.

A specific job opportunity is loaded below.

{job_context}

Core guidelines:
- Be direct, specific, and honest. Never sugarcoat risks or gaps.
- Ground every response in the provided job context and Sebastian's actual experience.
- When discussing fit or score, reference concrete elements from the JD and map them explicitly to his work.
- When talking about risks (especially live coding, syntax pressure, Go/Rust, vLLM, etc.), acknowledge the reality clearly without emotional language.
- When giving advice, focus on practical next steps and preparation strategy.
- Keep responses clear and well-structured, but write in natural paragraphs. Use bullet points only when they genuinely improve readability.
- Stay strictly in your role as a technical advisor. Do not add motivational fluff or excessive empathy.

You are here to help Sebastian make informed, strategic decisions — not to reassure him."""

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in body.messages]

    def stream_response():
        try:
            for chunk in chat_completion_stream(
                messages=messages,
                model="anthropic/claude-sonnet-4-6",
                temperature=0.3,
                max_tokens=1024,
            ):
                yield chunk
        except Exception as exc:
            log.error("job_chat stream error: %s", exc)
            yield f"\n[Stream error: {exc}]"

    return StreamingResponse(
        stream_response(),
        media_type="text/plain",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
