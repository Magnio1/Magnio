from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from api.firebase_client import get_firestore_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RANKINGS_PATH = PROJECT_ROOT / "data" / "openrouter_model_rankings.json"
DEFAULT_FIRESTORE_COLLECTION = "model_rankings"
DEFAULT_FIRESTORE_DOCUMENT = "current"
FIRESTORE_RPC_TIMEOUT_SECONDS = 5


def resolve_model_rankings_backend() -> str:
  configured = os.environ.get("MAGNIO_CHAT_MODEL_RANKINGS_BACKEND", "").strip().lower()
  if configured in {"json", "firestore", "dual"}:
    return configured
  return "json"


def resolve_model_rankings_path() -> Path:
  configured = os.environ.get("MAGNIO_CHAT_MODEL_RANKINGS_PATH", "").strip()
  if not configured:
    return DEFAULT_RANKINGS_PATH
  path = Path(configured)
  if not path.is_absolute():
    path = PROJECT_ROOT / configured
  return path


def _firestore_ref():
  collection_name = os.environ.get("MAGNIO_CHAT_MODEL_RANKINGS_COLLECTION", "").strip() or DEFAULT_FIRESTORE_COLLECTION
  document_name = os.environ.get("MAGNIO_CHAT_MODEL_RANKINGS_DOCUMENT", "").strip() or DEFAULT_FIRESTORE_DOCUMENT
  return get_firestore_client().collection(collection_name).document(document_name)


def _firestore_get(doc_ref):
  return doc_ref.get(retry=None, timeout=FIRESTORE_RPC_TIMEOUT_SECONDS)


def _firestore_set(doc_ref, payload: dict[str, Any]) -> None:
  doc_ref.set(payload, retry=None, timeout=FIRESTORE_RPC_TIMEOUT_SECONDS)


def _load_model_rankings_json() -> dict[str, Any]:
  path = resolve_model_rankings_path()
  if not path.exists():
    return {}

  try:
    payload = json.loads(path.read_text(encoding="utf-8"))
  except Exception:
    return {}

  if not isinstance(payload, dict):
    return {}
  return payload


def _load_model_rankings_firestore() -> dict[str, Any]:
  try:
    snapshot = _firestore_get(_firestore_ref())
  except Exception:
    return {}
  if not snapshot.exists:
    return {}
  payload = snapshot.to_dict() or {}
  return payload if isinstance(payload, dict) else {}


def load_model_rankings() -> dict[str, Any]:
  backend = resolve_model_rankings_backend()
  if backend in {"firestore", "dual"}:
    payload = _load_model_rankings_firestore()
    if payload:
      return payload
    if backend == "firestore":
      return {}
  return _load_model_rankings_json()


def _save_model_rankings_json(payload: dict[str, Any]) -> Path:
  path = resolve_model_rankings_path()
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
  return path


def _save_model_rankings_firestore(payload: dict[str, Any]) -> None:
  _firestore_set(_firestore_ref(), payload)


def save_model_rankings(payload: dict[str, Any]) -> Path:
  backend = resolve_model_rankings_backend()
  wrote_json = False
  json_path = resolve_model_rankings_path()

  if backend in {"json", "dual"}:
    json_path = _save_model_rankings_json(payload)
    wrote_json = True

  if backend in {"firestore", "dual"}:
    _save_model_rankings_firestore(payload)

  if not wrote_json and backend == "firestore":
    # Keep a local snapshot when asked to operate in Firestore-only mode from tooling.
    json_path = _save_model_rankings_json(payload)
  return json_path


def get_ranked_models_for_category(category: str) -> list[dict[str, Any]]:
  payload = load_model_rankings()
  categories = payload.get("categories")
  if not isinstance(categories, dict):
    return []

  entry = categories.get(category)
  if not isinstance(entry, dict):
    return []

  models = entry.get("rankedModels")
  if not isinstance(models, list):
    return []

  normalized: list[dict[str, Any]] = []
  for item in models:
    if not isinstance(item, dict):
      continue
    model_id = str(item.get("id") or "").strip()
    if not model_id:
      continue
    normalized.append(
      {
        "id": model_id,
        "name": str(item.get("name") or model_id),
        "provider": str(item.get("provider") or model_id.split("/", 1)[0]),
        "score": item.get("score"),
        "winRate": item.get("winRate"),
        "avgLatencyMs": item.get("avgLatencyMs"),
        "avgEstimatedCost": item.get("avgEstimatedCost"),
        "promptCount": item.get("promptCount"),
      }
    )
  return normalized
