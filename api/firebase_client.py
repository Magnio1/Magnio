from __future__ import annotations

import json
import os
from typing import Any

import firebase_admin
from firebase_admin import credentials


def _resolve_credentials():
  raw_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
  if raw_json:
    try:
      return credentials.Certificate(json.loads(raw_json))
    except json.JSONDecodeError as exc:
      raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc

  raw_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON_PATH", "").strip()
  if raw_path:
    return credentials.Certificate(raw_path)

  return credentials.ApplicationDefault()


def initialize_firebase_admin(*, require_database_url: bool = False):
  if firebase_admin._apps:
    return firebase_admin.get_app()

  options: dict[str, Any] = {}
  database_url = os.environ.get("FIREBASE_DATABASE_URL", "").strip()
  if require_database_url and not database_url:
    raise RuntimeError("Missing FIREBASE_DATABASE_URL env var")
  if database_url:
    options["databaseURL"] = database_url

  try:
    cred = _resolve_credentials()
    firebase_admin.initialize_app(cred, options)
  except Exception as exc:
    raise RuntimeError("Failed to initialize Firebase Admin credentials") from exc

  return firebase_admin.get_app()


def get_firestore_client():
  # Some shared Anaconda installs are missing the protobuf native library
  # required by google-cloud-firestore's C extension. Force the pure-Python
  # implementation so local Firestore access still works reliably.
  os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
  from firebase_admin import firestore

  initialize_firebase_admin()
  return firestore.client()
