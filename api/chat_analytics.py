from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api.firebase_client import get_firestore_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALID_BACKENDS = {"sqlite", "firestore", "dual"}
FIRESTORE_CASES_RECENT = "evaluation_cases_recent"
FIRESTORE_CASES_ARCHIVE = "evaluation_cases_archive"
FIRESTORE_ROLLUPS = "evaluation_rollups"
FIRESTORE_DAILY_ROLLUPS = "evaluation_rollups_daily"
FIRESTORE_HUMAN_REVIEWS = "human_reviews"
FIRESTORE_RPC_TIMEOUT_SECONDS = 5


def now_unix() -> int:
  return int(time.time())


def now_iso() -> str:
  return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_future(days: int) -> datetime:
  return datetime.now(timezone.utc) + timedelta(days=max(1, days))


def _truncate(text: str, *, max_chars: int) -> str:
  clean = (text or "").strip()
  if len(clean) <= max_chars:
    return clean
  return clean[: max_chars - 1].rstrip() + "…"


def _word_count(text: str) -> int:
  return len([part for part in (text or "").strip().split() if part])


def _counter_key(value: str | None) -> str:
  clean = re.sub(r"[^a-zA-Z0-9_-]+", "__", (value or "").strip()).strip("_")
  return clean or "unknown"


def resolve_chat_analytics_backend() -> str:
  configured = os.environ.get("MAGNIO_CHAT_ANALYTICS_BACKEND", "").strip().lower()
  if configured in VALID_BACKENDS:
    return configured
  return "sqlite"


def resolve_chat_analytics_db_path() -> Path:
  configured = os.environ.get("MAGNIO_CHAT_ANALYTICS_DB", "").strip()
  if configured:
    return Path(configured).expanduser().resolve()
  return PROJECT_ROOT / "data" / "chat_analytics.sqlite3"


def resolve_chat_analytics_target() -> str:
  backend = resolve_chat_analytics_backend()
  if backend == "sqlite":
    return str(resolve_chat_analytics_db_path())
  if backend == "firestore":
    return "firestore"
  return f"dual:{resolve_chat_analytics_db_path()}"


def _recent_ttl_days() -> int:
  raw = os.environ.get("MAGNIO_CHAT_RECENT_TTL_DAYS", "").strip()
  if not raw:
    return 30
  try:
    return max(1, int(raw))
  except ValueError:
    return 30


def _candidate_ttl_days() -> int:
  raw = os.environ.get("MAGNIO_CHAT_CANDIDATE_TTL_DAYS", "").strip()
  if not raw:
    return 14
  try:
    return max(1, int(raw))
  except ValueError:
    return 14


def _connect() -> sqlite3.Connection:
  db_path = resolve_chat_analytics_db_path()
  db_path.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(db_path)
  conn.row_factory = sqlite3.Row
  return conn


def _init_sqlite() -> Path:
  with _connect() as conn:
    conn.execute(
      """
      CREATE TABLE IF NOT EXISTS chat_runs (
        run_id TEXT PRIMARY KEY,
        created_at_utc TEXT NOT NULL,
        created_at_unix INTEGER NOT NULL,
        status TEXT NOT NULL,
        error TEXT,
        query TEXT NOT NULL,
        requested_mode TEXT NOT NULL,
        resolved_mode TEXT,
        topic_id TEXT,
        topic_label TEXT,
        strategy TEXT,
        selected_models_json TEXT NOT NULL,
        winner_model_id TEXT,
        judge_model_id TEXT,
        advisor_model_id TEXT,
        retrieval_ids_json TEXT NOT NULL,
        warnings_json TEXT NOT NULL,
        latency_ms INTEGER,
        answer_chars INTEGER,
        answer_preview TEXT
      )
      """
    )
    conn.execute(
      """
      CREATE TABLE IF NOT EXISTS chat_feedback (
        run_id TEXT PRIMARY KEY,
        vote TEXT NOT NULL,
        note TEXT,
        updated_at_utc TEXT NOT NULL,
        updated_at_unix INTEGER NOT NULL,
        FOREIGN KEY(run_id) REFERENCES chat_runs(run_id) ON DELETE CASCADE
      )
      """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_runs_created_at ON chat_runs(created_at_unix DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_runs_resolved_mode ON chat_runs(resolved_mode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_runs_topic_id ON chat_runs(topic_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_feedback_vote ON chat_feedback(vote)")
    conn.commit()
  return resolve_chat_analytics_db_path()


def _init_firestore() -> str:
  _firestore_get(get_firestore_client().collection(FIRESTORE_ROLLUPS).document("summary"))
  return "firestore"


def _firestore_module():
  from firebase_admin import firestore

  return firestore


def _firestore_get(doc_ref):
  return doc_ref.get(retry=None, timeout=FIRESTORE_RPC_TIMEOUT_SECONDS)


def _firestore_commit(batch) -> None:
  batch.commit(retry=None, timeout=FIRESTORE_RPC_TIMEOUT_SECONDS)


def _firestore_set(doc_ref, payload: dict[str, Any], *, merge: bool = False) -> None:
  doc_ref.set(payload, merge=merge, retry=None, timeout=FIRESTORE_RPC_TIMEOUT_SECONDS)


def _firestore_stream(query):
  return query.stream(retry=None, timeout=FIRESTORE_RPC_TIMEOUT_SECONDS)


def init_chat_analytics_db() -> str:
  backend = resolve_chat_analytics_backend()
  initialized: list[str] = []
  errors: list[str] = []

  if backend in {"sqlite", "dual"}:
    try:
      initialized.append(str(_init_sqlite()))
    except Exception as exc:
      errors.append(f"sqlite: {exc}")

  if backend in {"firestore", "dual"}:
    try:
      initialized.append(_init_firestore())
    except Exception as exc:
      errors.append(f"firestore: {exc}")

  if not initialized:
    raise RuntimeError("Chat analytics initialization failed: " + "; ".join(errors))

  return ", ".join(initialized)


def _extract_run_metadata(response: dict[str, Any]) -> dict[str, Any]:
  diagnostics = response.get("diagnostics") or {}
  topic = response.get("topic") or {}
  judge = response.get("judge") or {}
  retrieval = response.get("retrieval") or []
  warnings = response.get("warnings") or []
  answer = str(response.get("answer") or "")

  return {
    "diagnostics": diagnostics,
    "topic": topic,
    "judge": judge,
    "retrieval": retrieval,
    "warnings": warnings,
    "answer": answer,
    "retrieval_ids": [item.get("id") for item in retrieval if isinstance(item, dict)],
    "selected_models": diagnostics.get("selectedModels") or [],
    "score_cards": judge.get("scores") or [],
  }


def _record_chat_run_sqlite(
  *,
  run_id: str,
  created_at_utc: str,
  created_at_unix: int,
  query: str,
  requested_mode: str,
  response: dict[str, Any],
  latency_ms: int,
) -> None:
  _init_sqlite()
  metadata = _extract_run_metadata(response)
  diagnostics = metadata["diagnostics"]
  topic = metadata["topic"]
  judge = metadata["judge"]

  with _connect() as conn:
    conn.execute(
      """
      INSERT INTO chat_runs (
        run_id, created_at_utc, created_at_unix, status, error, query,
        requested_mode, resolved_mode, topic_id, topic_label, strategy,
        selected_models_json, winner_model_id, judge_model_id, advisor_model_id,
        retrieval_ids_json, warnings_json, latency_ms, answer_chars, answer_preview
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        run_id,
        created_at_utc,
        created_at_unix,
        "ok",
        None,
        query,
        requested_mode,
        response.get("resolvedMode"),
        topic.get("id"),
        topic.get("label"),
        diagnostics.get("strategy"),
        json.dumps(metadata["selected_models"]),
        judge.get("winnerModelId"),
        judge.get("judgeModelId"),
        diagnostics.get("advisorModelId"),
        json.dumps(metadata["retrieval_ids"]),
        json.dumps(metadata["warnings"]),
        latency_ms,
        len(metadata["answer"]),
        _truncate(metadata["answer"], max_chars=600),
      ),
    )
    conn.commit()


def _record_chat_error_sqlite(
  *,
  run_id: str,
  created_at_utc: str,
  created_at_unix: int,
  query: str,
  requested_mode: str,
  resolved_mode: str | None,
  error: str,
  latency_ms: int,
) -> None:
  _init_sqlite()
  with _connect() as conn:
    conn.execute(
      """
      INSERT INTO chat_runs (
        run_id, created_at_utc, created_at_unix, status, error, query,
        requested_mode, resolved_mode, topic_id, topic_label, strategy,
        selected_models_json, winner_model_id, judge_model_id, advisor_model_id,
        retrieval_ids_json, warnings_json, latency_ms, answer_chars, answer_preview
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        run_id,
        created_at_utc,
        created_at_unix,
        "error",
        error,
        query,
        requested_mode,
        resolved_mode,
        None,
        None,
        None,
        "[]",
        None,
        None,
        None,
        "[]",
        "[]",
        latency_ms,
        0,
        "",
      ),
    )
    conn.commit()


def _record_chat_run_firestore(
  *,
  run_id: str,
  created_at_utc: str,
  created_at_unix: int,
  query: str,
  requested_mode: str,
  response: dict[str, Any],
  latency_ms: int,
) -> None:
  db = get_firestore_client()
  firestore = _firestore_module()
  metadata = _extract_run_metadata(response)
  diagnostics = metadata["diagnostics"]
  topic = metadata["topic"]
  judge = metadata["judge"]
  answer = metadata["answer"]

  archive_ref = db.collection(FIRESTORE_CASES_ARCHIVE).document(run_id)
  summary_ref = db.collection(FIRESTORE_ROLLUPS).document("summary")
  daily_ref = db.collection(FIRESTORE_DAILY_ROLLUPS).document(created_at_utc[:10])

  recent_ref = db.collection(FIRESTORE_CASES_RECENT).document(run_id)
  recent_doc = {
    "runId": run_id,
    "createdAt": created_at_utc,
    "createdAtUnix": created_at_unix,
    "status": "ok",
    "requestedMode": requested_mode,
    "resolvedMode": response.get("resolvedMode"),
    "topicId": topic.get("id"),
    "topicLabel": topic.get("label"),
    "topicReasoning": topic.get("reasoning") or [],
    "query": query,
    "answer": answer,
    "queryWordCount": _word_count(query),
    "answerChars": len(answer),
    "latencyMs": latency_ms,
    "strategy": diagnostics.get("strategy"),
    "evaluationType": diagnostics.get("evaluationType"),
    "evaluation": {
      "evaluationType": diagnostics.get("evaluationType"),
      "answerModelId": diagnostics.get("answerModelId"),
      "winnerModelId": judge.get("winnerModelId"),
      "judgeModelId": judge.get("judgeModelId"),
      "confidence": judge.get("confidence"),
      "decisionRationale": judge.get("rationale"),
      "scoreCards": metadata["score_cards"],
    },
    "selectedModels": metadata["selected_models"],
    "winnerModelId": judge.get("winnerModelId"),
    "judgeModelId": judge.get("judgeModelId"),
    "advisorModelId": diagnostics.get("advisorModelId"),
    "answerModelId": diagnostics.get("answerModelId"),
    "retrievalIds": metadata["retrieval_ids"],
    "warnings": metadata["warnings"],
    "retentionTier": "recent",
    "expiresAt": _utc_future(_recent_ttl_days()),
  }

  archive_doc = {
    "runId": run_id,
    "createdAt": created_at_utc,
    "createdAtUnix": created_at_unix,
    "status": "ok",
    "requestedMode": requested_mode,
    "resolvedMode": response.get("resolvedMode"),
    "topicId": topic.get("id"),
    "topicLabel": topic.get("label"),
    "queryPreview": _truncate(query, max_chars=280),
    "answerPreview": _truncate(answer, max_chars=600),
    "queryWordCount": _word_count(query),
    "answerChars": len(answer),
    "latencyMs": latency_ms,
    "strategy": diagnostics.get("strategy"),
    "evaluationType": diagnostics.get("evaluationType"),
    "evaluation": {
      "evaluationType": diagnostics.get("evaluationType"),
      "answerModelId": diagnostics.get("answerModelId"),
      "winnerModelId": judge.get("winnerModelId"),
      "judgeModelId": judge.get("judgeModelId"),
      "confidence": judge.get("confidence"),
      "decisionRationale": judge.get("rationale"),
    },
    "selectedModels": metadata["selected_models"],
    "winnerModelId": judge.get("winnerModelId"),
    "judgeModelId": judge.get("judgeModelId"),
    "advisorModelId": diagnostics.get("advisorModelId"),
    "answerModelId": diagnostics.get("answerModelId"),
    "retrievalIds": metadata["retrieval_ids"],
    "warnings": metadata["warnings"],
    "retentionTier": "archive",
  }

  topic_key = _counter_key(topic.get("id"))
  model_key = _counter_key(judge.get("winnerModelId"))

  batch = db.batch()
  batch.set(recent_ref, recent_doc)
  batch.set(archive_ref, archive_doc)
  batch.set(
    summary_ref,
    {
      "updatedAt": firestore.SERVER_TIMESTAMP,
      "counts": {
        "totalRuns": firestore.Increment(1),
        "successfulRuns": firestore.Increment(1),
        "arenaRuns": firestore.Increment(1 if response.get("resolvedMode") == "arena" else 0),
        "advisorRuns": firestore.Increment(1 if response.get("resolvedMode") == "advisor" else 0),
      },
      "topicCounts": {topic_key: firestore.Increment(1)},
      "topicLabels": {topic_key: topic.get("label") or topic.get("id") or "Unknown"},
      "winningPerspectiveCounts": {model_key: firestore.Increment(1 if judge.get("winnerModelId") else 0)},
      "winningPerspectiveLabels": {model_key: judge.get("winnerModelId") or "unknown"},
    },
    merge=True,
  )
  batch.set(
    daily_ref,
    {
      "date": created_at_utc[:10],
      "updatedAt": firestore.SERVER_TIMESTAMP,
      "counts": {
        "totalRuns": firestore.Increment(1),
        "successfulRuns": firestore.Increment(1),
        "arenaRuns": firestore.Increment(1 if response.get("resolvedMode") == "arena" else 0),
        "advisorRuns": firestore.Increment(1 if response.get("resolvedMode") == "advisor" else 0),
      },
      "topicCounts": {topic_key: firestore.Increment(1)},
      "topicLabels": {topic_key: topic.get("label") or topic.get("id") or "Unknown"},
      "winningPerspectiveCounts": {model_key: firestore.Increment(1 if judge.get("winnerModelId") else 0)},
      "winningPerspectiveLabels": {model_key: judge.get("winnerModelId") or "unknown"},
    },
    merge=True,
  )
  _firestore_commit(batch)

  candidate_ttl = _utc_future(_candidate_ttl_days())
  for index, candidate in enumerate(response.get("candidates") or []):
    score_card = next(
      (
        item
        for item in metadata["score_cards"]
        if isinstance(item, dict) and item.get("modelId") == candidate.get("modelId")
      ),
      None,
    )
    perspective_ref = recent_ref.collection("perspectives").document(f"perspective_{index + 1}")
    _firestore_set(
      perspective_ref,
      {
        "runId": run_id,
        "perspectiveId": f"perspective_{index + 1}",
        "modelId": candidate.get("modelId"),
        "modelName": candidate.get("modelName"),
        "title": candidate.get("modelName"),
        "provider": candidate.get("provider"),
        "status": candidate.get("status"),
        "latencyMs": candidate.get("latencyMs"),
        "usage": candidate.get("usage") or {},
        "error": candidate.get("error"),
        "content": candidate.get("content") or "",
        "contentPreview": _truncate(str(candidate.get("content") or ""), max_chars=400),
        "scoreCard": score_card,
        "isWinner": judge.get("winnerModelId") == candidate.get("modelId"),
        "expiresAt": candidate_ttl,
      },
    )


def _record_chat_error_firestore(
  *,
  run_id: str,
  created_at_utc: str,
  created_at_unix: int,
  query: str,
  requested_mode: str,
  resolved_mode: str | None,
  error: str,
  latency_ms: int,
) -> None:
  db = get_firestore_client()
  firestore = _firestore_module()
  recent_ref = db.collection(FIRESTORE_CASES_RECENT).document(run_id)
  archive_ref = db.collection(FIRESTORE_CASES_ARCHIVE).document(run_id)
  summary_ref = db.collection(FIRESTORE_ROLLUPS).document("summary")
  daily_ref = db.collection(FIRESTORE_DAILY_ROLLUPS).document(created_at_utc[:10])

  error_doc = {
    "runId": run_id,
    "createdAt": created_at_utc,
    "createdAtUnix": created_at_unix,
    "status": "error",
    "error": error,
    "query": query,
    "queryPreview": _truncate(query, max_chars=280),
    "requestedMode": requested_mode,
    "resolvedMode": resolved_mode,
    "latencyMs": latency_ms,
  }

  batch = db.batch()
  batch.set(recent_ref, {**error_doc, "retentionTier": "recent", "expiresAt": _utc_future(_recent_ttl_days())})
  batch.set(archive_ref, {**error_doc, "retentionTier": "archive"})
  batch.set(
    summary_ref,
    {
      "updatedAt": firestore.SERVER_TIMESTAMP,
      "counts": {
        "totalRuns": firestore.Increment(1),
        "failedRuns": firestore.Increment(1),
      },
    },
    merge=True,
  )
  batch.set(
    daily_ref,
    {
      "date": created_at_utc[:10],
      "updatedAt": firestore.SERVER_TIMESTAMP,
      "counts": {
        "totalRuns": firestore.Increment(1),
        "failedRuns": firestore.Increment(1),
      },
    },
    merge=True,
  )
  _firestore_commit(batch)


def record_chat_run(*, query: str, requested_mode: str, response: dict[str, Any], latency_ms: int) -> str:
  run_id = str(uuid.uuid4())
  created_at_utc = now_iso()
  created_at_unix = now_unix()
  backend = resolve_chat_analytics_backend()
  successes = 0
  errors: list[str] = []

  if backend in {"sqlite", "dual"}:
    try:
      _record_chat_run_sqlite(
        run_id=run_id,
        created_at_utc=created_at_utc,
        created_at_unix=created_at_unix,
        query=query,
        requested_mode=requested_mode,
        response=response,
        latency_ms=latency_ms,
      )
      successes += 1
    except Exception as exc:
      errors.append(f"sqlite: {exc}")

  if backend in {"firestore", "dual"}:
    try:
      _record_chat_run_firestore(
        run_id=run_id,
        created_at_utc=created_at_utc,
        created_at_unix=created_at_unix,
        query=query,
        requested_mode=requested_mode,
        response=response,
        latency_ms=latency_ms,
      )
      successes += 1
    except Exception as exc:
      errors.append(f"firestore: {exc}")

  if not successes:
    raise RuntimeError("Chat analytics write failed: " + "; ".join(errors))

  return run_id


def record_chat_error(*, query: str, requested_mode: str, resolved_mode: str | None, error: str, latency_ms: int) -> str:
  run_id = str(uuid.uuid4())
  created_at_utc = now_iso()
  created_at_unix = now_unix()
  backend = resolve_chat_analytics_backend()
  successes = 0
  errors: list[str] = []

  if backend in {"sqlite", "dual"}:
    try:
      _record_chat_error_sqlite(
        run_id=run_id,
        created_at_utc=created_at_utc,
        created_at_unix=created_at_unix,
        query=query,
        requested_mode=requested_mode,
        resolved_mode=resolved_mode,
        error=error,
        latency_ms=latency_ms,
      )
      successes += 1
    except Exception as exc:
      errors.append(f"sqlite: {exc}")

  if backend in {"firestore", "dual"}:
    try:
      _record_chat_error_firestore(
        run_id=run_id,
        created_at_utc=created_at_utc,
        created_at_unix=created_at_unix,
        query=query,
        requested_mode=requested_mode,
        resolved_mode=resolved_mode,
        error=error,
        latency_ms=latency_ms,
      )
      successes += 1
    except Exception as exc:
      errors.append(f"firestore: {exc}")

  if not successes:
    raise RuntimeError("Chat analytics error write failed: " + "; ".join(errors))

  return run_id


def _submit_chat_feedback_sqlite(*, run_id: str, vote: str, note: str | None) -> dict[str, Any]:
  _init_sqlite()
  cleaned_vote = vote.strip().lower()
  if cleaned_vote not in {"up", "down"}:
    raise ValueError("vote must be 'up' or 'down'")

  cleaned_note = (note or "").strip() or None
  updated_at_utc = now_iso()
  updated_at_unix = now_unix()

  with _connect() as conn:
    row = conn.execute("SELECT run_id FROM chat_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
      raise KeyError("Unknown run_id")

    conn.execute(
      """
      INSERT INTO chat_feedback (run_id, vote, note, updated_at_utc, updated_at_unix)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(run_id) DO UPDATE SET
        vote = excluded.vote,
        note = excluded.note,
        updated_at_utc = excluded.updated_at_utc,
        updated_at_unix = excluded.updated_at_unix
      """,
      (run_id, cleaned_vote, cleaned_note, updated_at_utc, updated_at_unix),
    )
    conn.commit()

  return {
    "runId": run_id,
    "vote": cleaned_vote,
    "note": cleaned_note,
    "updatedAt": updated_at_utc,
  }


def _submit_chat_feedback_firestore(*, run_id: str, vote: str, note: str | None) -> dict[str, Any]:
  db = get_firestore_client()
  firestore = _firestore_module()
  cleaned_vote = vote.strip().lower()
  if cleaned_vote not in {"up", "down"}:
    raise ValueError("vote must be 'up' or 'down'")

  cleaned_note = (note or "").strip() or None
  updated_at_utc = now_iso()
  updated_at_unix = now_unix()

  recent_ref = db.collection(FIRESTORE_CASES_RECENT).document(run_id)
  archive_ref = db.collection(FIRESTORE_CASES_ARCHIVE).document(run_id)
  feedback_ref = db.collection(FIRESTORE_HUMAN_REVIEWS).document(run_id)
  summary_ref = db.collection(FIRESTORE_ROLLUPS).document("summary")
  daily_ref = db.collection(FIRESTORE_DAILY_ROLLUPS).document(updated_at_utc[:10])

  recent_doc = _firestore_get(recent_ref)
  if not recent_doc.exists:
    raise KeyError("Unknown run_id")

  previous_feedback_doc = _firestore_get(feedback_ref)
  previous_feedback = previous_feedback_doc.to_dict() if previous_feedback_doc.exists else None
  previous_vote = (previous_feedback or {}).get("vote")
  feedback_count_delta = 0 if previous_feedback else 1
  upvote_delta = (1 if cleaned_vote == "up" else 0) - (1 if previous_vote == "up" else 0)
  downvote_delta = (1 if cleaned_vote == "down" else 0) - (1 if previous_vote == "down" else 0)

  feedback_payload = {
    "runId": run_id,
    "vote": cleaned_vote,
    "note": cleaned_note,
    "updatedAt": updated_at_utc,
    "updatedAtUnix": updated_at_unix,
    "reviewType": "human_loop",
    "helpfulness": "helpful" if cleaned_vote == "up" else "needs_revision",
  }

  batch = db.batch()
  batch.set(feedback_ref, feedback_payload)
  batch.set(recent_ref, {"feedback": feedback_payload, "reviewSummary": feedback_payload}, merge=True)
  batch.set(archive_ref, {"feedback": feedback_payload, "reviewSummary": feedback_payload}, merge=True)
  batch.set(
    summary_ref,
    {
      "updatedAt": firestore.SERVER_TIMESTAMP,
      "counts": {
        "feedbackCount": firestore.Increment(feedback_count_delta),
        "upvotes": firestore.Increment(upvote_delta),
        "downvotes": firestore.Increment(downvote_delta),
      },
    },
    merge=True,
  )
  batch.set(
    daily_ref,
    {
      "date": updated_at_utc[:10],
      "updatedAt": firestore.SERVER_TIMESTAMP,
      "counts": {
        "feedbackCount": firestore.Increment(feedback_count_delta),
        "upvotes": firestore.Increment(upvote_delta),
        "downvotes": firestore.Increment(downvote_delta),
      },
    },
    merge=True,
  )
  _firestore_commit(batch)

  return feedback_payload


def submit_chat_feedback(*, run_id: str, vote: str, note: str | None) -> dict[str, Any]:
  backend = resolve_chat_analytics_backend()
  errors: list[str] = []
  result: dict[str, Any] | None = None

  if backend in {"sqlite", "dual"}:
    try:
      result = _submit_chat_feedback_sqlite(run_id=run_id, vote=vote, note=note)
    except Exception as exc:
      errors.append(f"sqlite: {exc}")

  if backend in {"firestore", "dual"}:
    try:
      result = _submit_chat_feedback_firestore(run_id=run_id, vote=vote, note=note)
    except Exception as exc:
      errors.append(f"firestore: {exc}")

  if result is None:
    message = "; ".join(errors)
    if "Unknown run_id" in message:
      raise KeyError("Unknown run_id")
    raise RuntimeError("Chat feedback write failed: " + message)

  return result


def _get_feedback_for_run_sqlite(run_id: str) -> dict[str, Any] | None:
  _init_sqlite()
  with _connect() as conn:
    row = conn.execute(
      "SELECT run_id, vote, note, updated_at_utc FROM chat_feedback WHERE run_id = ?",
      (run_id,),
    ).fetchone()
    if row is None:
      return None

  return {
    "runId": row["run_id"],
    "vote": row["vote"],
    "note": row["note"],
    "updatedAt": row["updated_at_utc"],
  }


def _get_feedback_for_run_firestore(run_id: str) -> dict[str, Any] | None:
  doc = _firestore_get(get_firestore_client().collection(FIRESTORE_HUMAN_REVIEWS).document(run_id))
  if not doc.exists:
    return None
  payload = doc.to_dict() or {}
  return {
    "runId": payload.get("runId") or run_id,
    "vote": payload.get("vote"),
    "note": payload.get("note"),
    "updatedAt": payload.get("updatedAt"),
  }


def get_feedback_for_run(run_id: str) -> dict[str, Any] | None:
  backend = resolve_chat_analytics_backend()
  if backend in {"firestore", "dual"}:
    try:
      feedback = _get_feedback_for_run_firestore(run_id)
      if feedback is not None:
        return feedback
    except Exception:
      if backend == "firestore":
        raise

  if backend in {"sqlite", "dual"}:
    return _get_feedback_for_run_sqlite(run_id)

  return None


def _sqlite_summary() -> dict[str, Any]:
  _init_sqlite()
  with _connect() as conn:
    totals = conn.execute(
      """
      SELECT
        COUNT(*) AS total_runs,
        COALESCE(SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END), 0) AS successful_runs,
        COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END), 0) AS failed_runs,
        COALESCE(SUM(CASE WHEN resolved_mode = 'arena' THEN 1 ELSE 0 END), 0) AS arena_runs,
        COALESCE(SUM(CASE WHEN resolved_mode = 'advisor' THEN 1 ELSE 0 END), 0) AS advisor_runs
      FROM chat_runs
      """
    ).fetchone()
    feedback = conn.execute(
      """
      SELECT
        COUNT(*) AS feedback_count,
        COALESCE(SUM(CASE WHEN vote = 'up' THEN 1 ELSE 0 END), 0) AS upvotes,
        COALESCE(SUM(CASE WHEN vote = 'down' THEN 1 ELSE 0 END), 0) AS downvotes
      FROM chat_feedback
      """
    ).fetchone()
    top_topics_rows = conn.execute(
      """
      SELECT topic_id, topic_label, COUNT(*) AS run_count
      FROM chat_runs
      WHERE status = 'ok' AND topic_id IS NOT NULL
      GROUP BY topic_id, topic_label
      ORDER BY run_count DESC, topic_id ASC
      LIMIT 5
      """
    ).fetchall()
    top_models_rows = conn.execute(
      """
      SELECT winner_model_id, COUNT(*) AS win_count
      FROM chat_runs
      WHERE status = 'ok' AND winner_model_id IS NOT NULL
      GROUP BY winner_model_id
      ORDER BY win_count DESC, winner_model_id ASC
      LIMIT 5
      """
    ).fetchall()

  return {
    "dbPath": str(resolve_chat_analytics_db_path()),
    "totalRuns": int(totals["total_runs"] or 0),
    "successfulRuns": int(totals["successful_runs"] or 0),
    "failedRuns": int(totals["failed_runs"] or 0),
    "arenaRuns": int(totals["arena_runs"] or 0),
    "advisorRuns": int(totals["advisor_runs"] or 0),
    "feedbackCount": int(feedback["feedback_count"] or 0),
    "upvotes": int(feedback["upvotes"] or 0),
    "downvotes": int(feedback["downvotes"] or 0),
    "topTopics": [
      {
        "topicId": row["topic_id"],
        "label": row["topic_label"] or row["topic_id"],
        "runCount": int(row["run_count"] or 0),
      }
      for row in top_topics_rows
    ],
    "topWinningModels": [
      {
        "modelId": row["winner_model_id"],
        "winCount": int(row["win_count"] or 0),
      }
      for row in top_models_rows
    ],
  }


def _sqlite_recent_cases(limit: int) -> list[dict[str, Any]]:
  _init_sqlite()
  safe_limit = max(1, min(limit, 100))
  with _connect() as conn:
    rows = conn.execute(
      """
      SELECT
        run_id,
        created_at_utc,
        status,
        query,
        requested_mode,
        resolved_mode,
        topic_id,
        topic_label,
        strategy,
        winner_model_id,
        judge_model_id,
        latency_ms,
        answer_preview
      FROM chat_runs
      ORDER BY created_at_unix DESC
      LIMIT ?
      """,
      (safe_limit,),
    ).fetchall()

    feedback_map = {
      row["run_id"]: row
      for row in conn.execute(
        """
        SELECT run_id, vote, note, updated_at_utc
        FROM chat_feedback
        WHERE run_id IN (
          SELECT run_id FROM chat_runs ORDER BY created_at_unix DESC LIMIT ?
        )
        """,
        (safe_limit,),
      ).fetchall()
    }

  return [
    {
      "runId": row["run_id"],
      "createdAt": row["created_at_utc"],
      "status": row["status"],
      "query": row["query"],
      "queryPreview": _truncate(str(row["query"] or ""), max_chars=220),
      "requestedMode": row["requested_mode"],
      "resolvedMode": row["resolved_mode"],
      "topicId": row["topic_id"],
      "topicLabel": row["topic_label"],
      "strategy": row["strategy"],
      "winnerModelId": row["winner_model_id"],
      "judgeModelId": row["judge_model_id"],
      "latencyMs": row["latency_ms"],
      "answerPreview": row["answer_preview"] or "",
      "review": (
        {
          "vote": feedback_map[row["run_id"]]["vote"],
          "note": feedback_map[row["run_id"]]["note"],
          "updatedAt": feedback_map[row["run_id"]]["updated_at_utc"],
        }
        if row["run_id"] in feedback_map
        else None
      ),
    }
    for row in rows
  ]


def _firestore_summary() -> dict[str, Any]:
  doc = _firestore_get(get_firestore_client().collection(FIRESTORE_ROLLUPS).document("summary"))
  payload = doc.to_dict() or {}
  counts = payload.get("counts") or {}
  topic_counts = payload.get("topicCounts") or {}
  topic_labels = payload.get("topicLabels") or {}
  model_counts = payload.get("winningPerspectiveCounts") or {}
  model_labels = payload.get("winningPerspectiveLabels") or {}

  top_topics = sorted(
    [
      {
        "topicId": topic_labels.get(key) or key,
        "label": topic_labels.get(key) or key,
        "runCount": int(value or 0),
      }
      for key, value in topic_counts.items()
    ],
    key=lambda item: (-item["runCount"], item["topicId"]),
  )[:5]

  top_models = sorted(
    [
      {
        "modelId": model_labels.get(key) or key,
        "winCount": int(value or 0),
      }
      for key, value in model_counts.items()
      if model_labels.get(key)
    ],
    key=lambda item: (-item["winCount"], item["modelId"]),
  )[:5]

  return {
    "dbPath": "firestore",
    "totalRuns": int(counts.get("totalRuns") or 0),
    "successfulRuns": int(counts.get("successfulRuns") or 0),
    "failedRuns": int(counts.get("failedRuns") or 0),
    "arenaRuns": int(counts.get("arenaRuns") or 0),
    "advisorRuns": int(counts.get("advisorRuns") or 0),
    "feedbackCount": int(counts.get("feedbackCount") or 0),
    "upvotes": int(counts.get("upvotes") or 0),
    "downvotes": int(counts.get("downvotes") or 0),
    "topTopics": top_topics,
    "topWinningModels": top_models,
  }


def _firestore_recent_cases(limit: int) -> list[dict[str, Any]]:
  safe_limit = max(1, min(limit, 100))
  docs = _firestore_stream(
    get_firestore_client()
    .collection(FIRESTORE_CASES_RECENT)
    .order_by("createdAtUnix", direction="DESCENDING")
    .limit(safe_limit)
  )

  cases: list[dict[str, Any]] = []
  for doc in docs:
    payload = doc.to_dict() or {}
    review = payload.get("reviewSummary")
    cases.append(
      {
        "runId": payload.get("runId") or doc.id,
        "createdAt": payload.get("createdAt"),
        "status": payload.get("status"),
        "query": payload.get("query"),
        "queryPreview": _truncate(str(payload.get("query") or payload.get("queryPreview") or ""), max_chars=220),
        "requestedMode": payload.get("requestedMode"),
        "resolvedMode": payload.get("resolvedMode"),
        "topicId": payload.get("topicId"),
        "topicLabel": payload.get("topicLabel"),
        "strategy": payload.get("strategy"),
        "evaluationType": payload.get("evaluationType") or (payload.get("evaluation") or {}).get("evaluationType"),
        "answerModelId": payload.get("answerModelId") or (payload.get("evaluation") or {}).get("answerModelId"),
        "winnerModelId": payload.get("winnerModelId") or (payload.get("evaluation") or {}).get("winnerModelId"),
        "judgeModelId": payload.get("judgeModelId") or (payload.get("evaluation") or {}).get("judgeModelId"),
        "latencyMs": payload.get("latencyMs"),
        "answerPreview": payload.get("answerPreview") or _truncate(str(payload.get("answer") or ""), max_chars=600),
        "review": (
          {
            "vote": review.get("vote"),
            "note": review.get("note"),
            "updatedAt": review.get("updatedAt"),
          }
          if isinstance(review, dict)
          else None
        ),
      }
    )

  return cases


def _sqlite_model_trends(limit: int) -> list[dict[str, Any]]:
  _init_sqlite()
  safe_limit = max(1, min(limit, 100))
  with _connect() as conn:
    rows = conn.execute(
      """
      SELECT winner_model_id, created_at_utc
      FROM chat_runs
      WHERE resolved_mode = 'arena'
        AND winner_model_id IS NOT NULL
        AND status = 'ok'
      ORDER BY created_at_unix DESC
      LIMIT ?
      """,
      (safe_limit,),
    ).fetchall()
  return [
    {"winnerModelId": row["winner_model_id"], "createdAt": row["created_at_utc"]}
    for row in rows
  ]


def _firestore_model_trends(limit: int) -> list[dict[str, Any]]:
  safe_limit = max(1, min(limit, 100))
  docs = _firestore_stream(
    get_firestore_client()
    .collection(FIRESTORE_CASES_RECENT)
    .where("resolvedMode", "==", "arena")
    .order_by("createdAtUnix", direction="DESCENDING")
    .limit(safe_limit)
  )
  trends: list[dict[str, Any]] = []
  for doc in docs:
    payload = doc.to_dict() or {}
    winner = payload.get("winnerModelId") or (payload.get("evaluation") or {}).get("winnerModelId")
    if winner:
      trends.append({"winnerModelId": winner, "createdAt": payload.get("createdAt")})
  return trends


def get_model_win_trends(*, limit: int = 30) -> list[dict[str, Any]]:
  backend = resolve_chat_analytics_backend()
  if backend in {"firestore", "dual"}:
    try:
      return _firestore_model_trends(limit)
    except Exception:
      if backend == "firestore":
        raise
  return _sqlite_model_trends(limit)


def get_chat_analytics_summary() -> dict[str, Any]:
  backend = resolve_chat_analytics_backend()
  if backend in {"firestore", "dual"}:
    try:
      return _firestore_summary()
    except Exception:
      if backend == "firestore":
        raise
  return _sqlite_summary()


def get_recent_evaluation_cases(*, limit: int = 20) -> dict[str, Any]:
  backend = resolve_chat_analytics_backend()
  if backend in {"firestore", "dual"}:
    try:
      return {
        "backend": "firestore",
        "cases": _firestore_recent_cases(limit),
      }
    except Exception:
      if backend == "firestore":
        raise

  return {
    "backend": "sqlite",
    "cases": _sqlite_recent_cases(limit),
  }
