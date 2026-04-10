import os
import sys

from firebase_admin import credentials, db
import firebase_admin


def normalize_email(email: str) -> str:
  return email.strip().lower()


def normalize_email_key(email: str) -> str:
  return normalize_email(email).replace(".", "_")


def init_firebase_admin() -> None:
  if firebase_admin._apps:
    return
  database_url = os.environ.get("FIREBASE_DATABASE_URL")
  if not database_url:
    raise RuntimeError("Missing FIREBASE_DATABASE_URL env var")
  cred = credentials.ApplicationDefault()
  firebase_admin.initialize_app(cred, {"databaseURL": database_url})


def main() -> int:
  try:
    init_firebase_admin()
  except Exception as exc:
    print(f"Failed to initialize Firebase: {exc}")
    return 1

  leads = db.reference("leads").get() or {}
  index_ref = db.reference("lead_index").child("email")
  updated = 0

  for lead_id, lead in leads.items():
    if not isinstance(lead, dict):
      continue
    email = (lead.get("contact") or {}).get("email")
    if not email:
      continue
    key = normalize_email_key(email)
    index_ref.child(key).set(lead_id)
    updated += 1

  print(f"Backfill complete. Updated {updated} lead_index entries.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
