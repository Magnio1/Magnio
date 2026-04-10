import os
import re
import time
import secrets
import hashlib
import hmac
import base64
from urllib.parse import urlencode
from typing import Optional, Literal

import requests
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from firebase_admin import db

from api.firebase_client import initialize_firebase_admin

router = APIRouter()


def _init_firebase_admin() -> None:
  initialize_firebase_admin(require_database_url=True)


Timeline = Literal[
  "ASAP (Emergency)",
  "1–2 weeks",
  "1-2 weeks",
  "1 month",
  "2–3 months",
  "2-3 months",
  "Exploratory (No rush)",
]


class LeadIn(BaseModel):
  name: str = Field(min_length=1, max_length=120)
  email: EmailStr
  company: Optional[str] = Field(default=None, max_length=160)
  problem: str = Field(min_length=10, max_length=4000)
  timeline: Timeline


class IntakeIn(BaseModel):
  leadId: str = Field(min_length=8, max_length=64)
  token: str = Field(min_length=16, max_length=200)
  email: Optional[EmailStr] = None
  budgetRange: Optional[str] = Field(default=None, max_length=120)
  timeline: Optional[str] = Field(default=None, max_length=120)
  goals: str = Field(min_length=10, max_length=2000)
  constraints: Optional[str] = Field(default=None, max_length=2000)


def spam_like(text: str) -> bool:
  if len(text.strip()) < 10:
    return True
  if re.search(r"(bitcoin|casino|porn|viagra|seo\s+back|backlinks|crypto)", text, re.I):
    return True
  return False


def normalize_timeline(t: str) -> str:
  # Normalize en-dash variants to a stable set
  return (
    t.replace("–", "-")
    .replace("1–2 weeks", "1-2 weeks")
    .replace("2–3 months", "2-3 months")
    .strip()
  )


def map_timeline(timeline: str) -> tuple[str, int, str]:
  # returns (priority, slaHours, route)
  t = normalize_timeline(timeline)
  if t == "ASAP (Emergency)":
    return ("urgent", 4, "hot")
  if t == "1-2 weeks":
    return ("high", 24, "standard")
  if t == "1 month":
    return ("medium", 48, "standard")
  if t == "2-3 months":
    return ("low", 72, "standard")
  if t == "Exploratory (No rush)":
    return ("exploratory", 120, "nurture")
  return ("medium", 48, "standard")


def clamp(value: int, min_value: int, max_value: int) -> int:
  return max(min_value, min(value, max_value))


def now_unix() -> int:
  return int(time.time())


def now_iso() -> str:
  return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_email(email: str) -> str:
  return email.strip().lower()


def normalize_email_key(email: str) -> str:
  return normalize_email(email).replace(".", "_")


def compute_next_action(tier: str, priority: str) -> str:
  if tier == "hot" or priority == "urgent":
    return "schedule_call"
  if tier == "warm":
    return "request_details"
  return "send_case_study"


def generate_intake_token() -> tuple[str, str]:
  token = secrets.token_urlsafe(32)
  token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
  return token, token_hash


def get_intake_ttl_seconds() -> int:
  raw = os.environ.get("INTAKE_TOKEN_TTL_HOURS", "").strip()
  if not raw:
    return 168 * 3600
  try:
    hours = int(raw)
  except ValueError:
    return 168 * 3600
  return max(1, hours) * 3600


def token_preview(token: str) -> str:
  if len(token) < 8:
    return token
  return f"{token[:4]}...{token[-4:]}"


def build_url_with_params(base: str, params: dict) -> str:
  separator = "&" if "?" in base else "?"
  return f"{base}{separator}{urlencode(params)}"


def extract_calcom_uids(payload: dict) -> list[str]:
  nested_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
  candidates = [
    payload.get("uid"),
    payload.get("bookingUid"),
    payload.get("rescheduleUid"),
    nested_payload.get("uid"),
    nested_payload.get("bookingUid"),
    nested_payload.get("rescheduleUid"),
  ]
  return [uid for uid in candidates if isinstance(uid, str) and uid.strip()]

def log_event(rtdb_root, lead_id: str, event_type: str, data: Optional[dict] = None) -> None:
  payload = {
    "type": event_type,
    "createdAt": now_unix(),
    "createdAtIso": now_iso(),
    "data": data or {},
  }
  rtdb_root.child(lead_id).child("events").push(payload)


def issue_intake_token(rtdb_root, lead_id: str, event_type: str) -> tuple[str, str]:
  token, token_hash = generate_intake_token()
  rtdb_root.child(lead_id).child("intake").update(
    {
      "tokenHash": token_hash,
      "tokenCreatedAt": now_unix(),
      "tokenCreatedAtIso": now_iso(),
      "tokenUsedAt": None,
      "tokenUsedAtIso": None,
    }
  )
  preview = token_preview(token)
  log_event(rtdb_root, lead_id, event_type, {"tokenPreview": preview})
  return token, preview


def require_tasks_token(req: Request) -> None:
  token = os.environ.get("TASKS_API_TOKEN", "").strip()
  if not token:
    raise HTTPException(status_code=500, detail="TASKS_API_TOKEN not set")
  header = req.headers.get("x-task-token", "")
  if header != token:
    raise HTTPException(status_code=401, detail="Unauthorized")

def extract_tags(text: str) -> list[str]:
  keywords = {
    "automation": r"\b(automation|automate|workflow|orchestrat)\b",
    "ai": r"\b(ai|ml|machine learning|llm|gpt)\b",
    "data": r"\b(data|analytics|bi|dashboard|etl|pipeline)\b",
    "integration": r"\b(integration|integrate|api|sync)\b",
    "ops": r"\b(ops|operations|back office|process)\b",
    "cost_savings": r"\b(cost|savings|reduce spend|expense)\b",
    "revenue": r"\b(revenue|sales|growth|conversion)\b",
  }
  tags = []
  for tag, pattern in keywords.items():
    if re.search(pattern, text, re.I):
      tags.append(tag)
  return tags


def score_lead(problem: str, timeline: str) -> dict:
  normalized_timeline = normalize_timeline(timeline)
  text = problem.strip()

  urgency_map = {
    "ASAP (Emergency)": 25,
    "1-2 weeks": 20,
    "1 month": 14,
    "2-3 months": 8,
    "Exploratory (No rush)": 2,
  }
  urgency = urgency_map.get(normalized_timeline, 10)

  impact = 0
  if re.search(r"\$\s?\d", text):
    impact += 10
  if re.search(r"\b(\d+)\s?(k|m|million)\b", text, re.I):
    impact += 6
  if re.search(r"\b(revenue|churn|cost|profit|margin|savings)\b", text, re.I):
    impact += 6
  impact = clamp(impact, 0, 20)

  fit = 0
  if re.search(r"\b(automation|automate|workflow|orchestrat)\b", text, re.I):
    fit += 8
  if re.search(r"\b(ai|ml|machine learning|llm|gpt)\b", text, re.I):
    fit += 6
  if re.search(r"\b(data|analytics|bi|dashboard|etl|pipeline)\b", text, re.I):
    fit += 6
  if re.search(r"\b(integration|integrate|api|sync)\b", text, re.I):
    fit += 6
  fit = clamp(fit, 0, 20)

  clarity = 0
  if len(text) >= 120:
    clarity += 6
  if len(text) >= 280:
    clarity += 6
  if re.search(r"\b(because|so that|therefore|due to|goal|objective)\b", text, re.I):
    clarity += 3
  clarity = clamp(clarity, 0, 15)

  readiness = 0
  if re.search(r"\b(ready|need|urgent|asap|proposal|budget|decision)\b", text, re.I):
    readiness += 6
  if re.search(r"\b(call|meeting|scope|timeline)\b", text, re.I):
    readiness += 4
  readiness = clamp(readiness, 0, 10)

  risk = 0
  if spam_like(text):
    risk = 30

  score = clamp(urgency + impact + fit + clarity + readiness - risk, 0, 100)
  tier = "nurture"
  if score >= 75:
    tier = "hot"
  elif score >= 50:
    tier = "warm"

  tags = extract_tags(text)
  summary_bits = []
  if urgency >= 20:
    summary_bits.append("Urgent timeline")
  if impact >= 12:
    summary_bits.append("Clear impact")
  if fit >= 12:
    summary_bits.append("Strong fit signals")
  if not summary_bits:
    summary_bits.append("Initial fit to be verified")
  summary = ". ".join(summary_bits) + "."

  return {
    "score": score,
    "tier": tier,
    "tags": tags,
    "summary": summary,
    "signals": {
      "urgency": urgency,
      "impact": impact,
      "fit": fit,
      "clarity": clarity,
      "readiness": readiness,
      "risk": risk,
    },
  }


def send_slack_notification(lead_id: str, doc: dict) -> dict:
  webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
  if not webhook_url:
    return {"status": "skipped", "sentAt": None, "reason": "missing_webhook"}

  calcom_url = os.environ.get("CALCOM_BOOKING_URL", "").strip()
  analysis = doc.get("analysis", {})
  contact = doc.get("contact", {})
  next_action = doc.get("nextAction")
  follow_up_at = doc.get("followUpAtIso") or doc.get("followUpAt")
  text = (
    f"New lead ({analysis.get('tier', 'n/a')}, score {analysis.get('score', 'n/a')}): "
    f"{contact.get('name', 'Unknown')} - {contact.get('company') or 'No company'}\n"
    f"Problem: {doc.get('request', {}).get('problem', '')[:180]}…\n"
    f"Lead ID: {lead_id}"
  )
  if next_action:
    text += f"\nNext action: {next_action}"
  if follow_up_at:
    text += f"\nFollow-up by: {follow_up_at}"
  if calcom_url:
    text += f"\nBook a call: {calcom_url}"

  res = requests.post(webhook_url, json={"text": text}, timeout=10)
  if res.ok:
    return {"status": "sent", "sentAt": int(time.time())}
  return {"status": "failed", "sentAt": None, "error": res.text[:200]}


def get_email_api_key() -> str:
  return os.environ.get("RESEND_API_KEY", "").strip()


def get_from_email() -> str:
  return os.environ.get("RESEND_FROM_EMAIL", "").strip()


def get_admin_to_email() -> str:
  return os.environ.get("RESEND_TO_EMAIL", "").strip()


def send_resend_email(to_email: str, subject: str, body: str) -> dict:
  api_key = get_email_api_key()
  from_email = get_from_email()
  if not api_key or not from_email or not to_email:
    return {"status": "skipped", "sentAt": None, "reason": "missing_resend_env"}

  payload = {
    "from": from_email,
    "to": [to_email],
    "subject": subject,
    "text": body,
  }
  res = requests.post(
    "https://api.resend.com/emails",
    headers={
      "Authorization": f"Bearer {api_key}",
      "Content-Type": "application/json",
    },
    json=payload,
    timeout=10,
  )
  if res.status_code in (200, 201):
    return {"status": "sent", "sentAt": int(time.time())}
  return {"status": "failed", "sentAt": None, "error": res.text[:200]}


def send_email_notification(lead_id: str, doc: dict) -> dict:
  to_email = get_admin_to_email()
  if not get_email_api_key() or not get_from_email() or not to_email:
    return {"status": "skipped", "sentAt": None, "reason": "missing_resend_env"}

  calcom_url = os.environ.get("CALCOM_BOOKING_URL", "").strip()
  analysis = doc.get("analysis", {})
  contact = doc.get("contact", {})
  next_action = doc.get("nextAction")
  follow_up_at = doc.get("followUpAtIso") or doc.get("followUpAt")
  subject = (
    f"New Lead ({analysis.get('tier', 'n/a')}) - "
    f"{contact.get('company') or contact.get('name', 'Unknown')}"
  )
  body = (
    f"Lead ID: {lead_id}\n"
    f"Name: {contact.get('name', 'Unknown')}\n"
    f"Email: {contact.get('email', 'n/a')}\n"
    f"Company: {contact.get('company') or 'n/a'}\n"
    f"Score: {analysis.get('score', 'n/a')} ({analysis.get('tier', 'n/a')})\n"
    f"Tags: {', '.join(analysis.get('tags', [])) or 'n/a'}\n"
    f"Summary: {analysis.get('summary', 'n/a')}\n"
    f"Next action: {next_action or 'n/a'}\n"
    f"Follow-up by: {follow_up_at or 'n/a'}\n\n"
    f"Problem:\n{doc.get('request', {}).get('problem', '')}\n"
  )
  if calcom_url:
    body += f"\nBook a call: {calcom_url}\n"

  return send_resend_email(to_email, subject, body)


def send_lead_auto_reply(doc: dict) -> dict:
  enabled = os.environ.get("RESEND_LEAD_AUTOREPLY_ENABLED", "").strip() == "1"
  if not enabled or not get_email_api_key() or not get_from_email():
    return {"status": "skipped", "sentAt": None, "reason": "disabled_or_missing_env"}

  contact = doc.get("contact", {})
  to_email = contact.get("email")
  if not to_email:
    return {"status": "skipped", "sentAt": None, "reason": "missing_contact_email"}

  calcom_url = os.environ.get("CALCOM_BOOKING_URL", "").strip()
  subject = "We got your request - next steps"
  body = (
    f"Hi {contact.get('name', 'there')},\n\n"
    "Thanks for reaching out. We're reviewing your request and will reply shortly.\n"
  )
  if calcom_url:
    body += f"\nIf you want to move fast, you can book a call here: {calcom_url}\n"
  body += "\n- Magnio\n"

  return send_resend_email(to_email, subject, body)


def send_intake_email(lead_id: str, doc: dict, token: str) -> dict:
  enabled = os.environ.get("RESEND_INTAKE_ENABLED", "").strip() == "1"
  base_url = os.environ.get("INTAKE_FORM_BASE_URL", "").strip() or "/#intake"
  if not enabled or not get_email_api_key() or not get_from_email():
    return {"status": "skipped", "sentAt": None, "reason": "disabled_or_missing_env"}

  contact = doc.get("contact", {})
  to_email = contact.get("email")
  if not to_email:
    return {"status": "skipped", "sentAt": None, "reason": "missing_contact_email"}

  intake_url = build_url_with_params(base_url, {"leadId": lead_id, "token": token, "email": to_email})
  subject = "Quick intake before our call"
  body = (
    f"Hi {contact.get('name', 'there')},\n\n"
    "Thanks for booking. To make the call productive, please share a few details here:\n"
    f"{intake_url}\n\n"
    "It takes about 2 minutes.\n\n"
    "- Magnio\n"
  )

  return send_resend_email(to_email, subject, body)


def send_lead_followup_reminder(doc: dict) -> dict:
  enabled = os.environ.get("RESEND_FOLLOWUP_ENABLED", "").strip() == "1"
  if not enabled or not get_email_api_key() or not get_from_email():
    return {"status": "skipped", "sentAt": None, "reason": "disabled_or_missing_env"}

  contact = doc.get("contact", {})
  to_email = contact.get("email")
  if not to_email:
    return {"status": "skipped", "sentAt": None, "reason": "missing_contact_email"}

  calcom_url = os.environ.get("CALCOM_BOOKING_URL", "").strip()
  subject = "Quick follow-up"
  body = (
    f"Hi {contact.get('name', 'there')},\n\n"
    "Just checking in on your request. Happy to help if you want to move forward.\n"
  )
  if calcom_url:
    body += f"\nYou can book a call here: {calcom_url}\n"
  body += "\n- Magnio\n"

  return send_resend_email(to_email, subject, body)

def extract_calcom_email(payload: dict) -> Optional[str]:
  direct = payload.get("email") or payload.get("attendeeEmail") or payload.get("attendee_email")
  if direct:
    return normalize_email(direct)

  nested_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
  booking = payload.get("booking") or payload.get("event") or {}
  attendee = booking.get("attendee") or {}
  if attendee.get("email"):
    return normalize_email(attendee["email"])

  attendees = booking.get("attendees") or payload.get("attendees") or nested_payload.get("attendees") or []
  if isinstance(attendees, list):
    for item in attendees:
      if isinstance(item, dict) and item.get("email"):
        return normalize_email(item["email"])

  responses = booking.get("responses") or payload.get("responses") or nested_payload.get("responses") or {}
  if isinstance(responses, dict):
    for key, value in responses.items():
      if isinstance(value, dict):
        label = (value.get("label") or value.get("name") or "").lower()
        if "email" in label:
          v = value.get("value") or value.get("answer")
          if isinstance(v, str):
            return normalize_email(v)
      if not (isinstance(key, str) and "email" in key.lower()):
        continue
      if isinstance(value, str):
        return normalize_email(value)
      if isinstance(value, dict):
        for field in ("value", "answer"):
          if isinstance(value.get(field), str):
            return normalize_email(value[field])
  if isinstance(responses, list):
    for item in responses:
      if not isinstance(item, dict):
        continue
      label = (item.get("label") or item.get("name") or "").lower()
      if "email" in label:
        value = item.get("value") or item.get("answer")
        if isinstance(value, str):
          return normalize_email(value)

  nested_direct = nested_payload.get("email") or nested_payload.get("attendeeEmail")
  if nested_direct:
    return normalize_email(nested_direct)

  if isinstance(nested_payload.get("payload"), dict):
    return extract_calcom_email(nested_payload.get("payload"))

  return None



@router.post("/lead")
async def create_lead(body: LeadIn, req: Request):
  if spam_like(body.problem):
    raise HTTPException(status_code=400, detail="Message looks invalid")

  _init_firebase_admin()
  rtdb = db.reference("leads")
  priority, sla_hours, route = map_timeline(body.timeline)
  analysis = score_lead(body.problem, body.timeline)
  next_action = compute_next_action(analysis["tier"], priority)
  follow_up_at = now_unix() + (sla_hours * 3600)
  intake_token, intake_token_hash = generate_intake_token()
  intake_preview = token_preview(intake_token)

  doc = {
    "source": "website_form",
    "createdAt": now_unix(),
    "createdAtIso": now_iso(),
    "status": "new",
    "priority": priority,
    "slaHours": sla_hours,
    "route": route,
    "nextAction": next_action,
    "followUpAt": follow_up_at,
    "followUpAtIso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(follow_up_at)),
    "contact": {
      "name": body.name.strip(),
      "email": normalize_email(body.email),
      "company": (body.company or "").strip() or None,
    },
    "request": {
      "timelineRaw": body.timeline,
      "timeline": normalize_timeline(body.timeline),
      "problem": body.problem.strip(),
      "userAgent": req.headers.get("user-agent"),
      "ipHint": req.headers.get("x-forwarded-for") or (req.client.host if req.client else None),
      "status": "new",
    },
    "analysis": {
      "status": "completed",
      **analysis,
    },
    "intake": {
      "tokenHash": intake_token_hash,
      "tokenCreatedAt": now_unix(),
      "tokenCreatedAtIso": now_iso(),
    },
    "notifications": {
      "email": {"status": "pending", "sentAt": None},
      "slack": {"status": "pending", "sentAt": None},
      "leadEmail": {"status": "pending", "sentAt": None},
    },
    "followup": {
      "calcom": {"status": "none", "eventId": None, "scheduledAt": None},
    },
  }

  ref = rtdb.push(doc)
  lead_id = ref.key
  db.reference("lead_index").child("email").child(normalize_email_key(doc["contact"]["email"])).set(lead_id)

  email_result = send_email_notification(lead_id, doc)
  slack_result = send_slack_notification(lead_id, doc)
  lead_reply_result = send_lead_auto_reply(doc)

  ref.child("notifications").update(
    {
      "email": email_result,
      "slack": slack_result,
      "leadEmail": lead_reply_result,
    }
  )
  log_event(rtdb, lead_id, "lead_created", {"priority": priority, "tier": analysis["tier"]})
  log_event(rtdb, lead_id, "INTAKE_TOKEN_CREATED", {"tokenPreview": intake_preview})

  return {
    "ok": True,
    "leadId": lead_id,
    "priority": priority,
    "slaHours": sla_hours,
    "score": analysis["score"],
    "tier": analysis["tier"],
  }


@router.post("/webhooks/calcom")
async def calcom_webhook(req: Request):
  raw_body = await req.body()
  secret = os.environ.get("CALCOM_WEBHOOK_SECRET", "").strip()
  if secret:
    if os.environ.get("CALCOM_WEBHOOK_DEBUG") == "1":
      headers = {k.lower(): v for k, v in req.headers.items()}
      print(f"[calcom_webhook] headers={headers} secret_len={len(secret)}")
    header_secret = req.headers.get("X-Calcom-Secret") or req.headers.get("X-Calcom-Webhook-Secret")
    signature = req.headers.get("x-cal-signature-256") or req.headers.get("X-Cal-Signature-256")
    if header_secret == secret:
      pass
    elif signature:
      digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
      computed_hex = digest.hex()
      computed_b64 = base64.b64encode(digest).decode("utf-8")
      sig = signature.strip()
      if os.environ.get("CALCOM_WEBHOOK_DEBUG") == "1":
        print(f"[calcom_webhook] sig_header={sig} computed_hex={computed_hex[:12]} computed_b64={computed_b64[:12]}")
      if not (hmac.compare_digest(computed_hex, sig) or hmac.compare_digest(computed_b64, sig)):
        raise HTTPException(status_code=401, detail="Invalid Cal.com signature")
    else:
      raise HTTPException(status_code=401, detail="Invalid Cal.com secret")
  else:
    if os.environ.get("MAGNIO_ENV") != "dev":
      raise HTTPException(status_code=500, detail="CALCOM_WEBHOOK_SECRET not set")

  payload = await req.json()
  payload_root = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
  nested_payload = payload_root.get("payload") if isinstance(payload_root.get("payload"), dict) else None
  event_type = payload.get("eventType") or payload.get("triggerEvent") or payload.get("type")
  uid = payload.get("uid") or payload.get("bookingUid") or payload_root.get("uid")
  if not event_type or not uid:
    raise HTTPException(status_code=400, detail="Missing eventType or uid")

  event_key = f"{event_type}:{uid}"
  lead_id = (
    (payload.get("metadata") or {}).get("leadId")
    or (payload_root.get("metadata") or {}).get("leadId")
    or ((nested_payload or {}).get("metadata") or {}).get("leadId")
  )

  email = None
  if not lead_id:
    email = (
      payload.get("email")
      or payload_root.get("email")
      or payload_root.get("attendeeEmail")
      or (payload_root.get("attendees") or [{}])[0].get("email")
    )
    if not email:
      email = extract_calcom_email(payload_root) or (extract_calcom_email(nested_payload) if nested_payload else None)
    if email:
      email = normalize_email(email)

  _init_firebase_admin()
  rtdb = db.reference()

  if not lead_id and email:
    lead_id = (
      rtdb.child("lead_index").child("email").child(normalize_email_key(email)).get()
    )
    if os.environ.get("CALCOM_WEBHOOK_DEBUG") == "1":
      print(f"[calcom_webhook] email={email} lead_index={lead_id}")

  if not lead_id and email:
    leads = rtdb.child("leads").get() or {}
    for candidate_id, lead in leads.items():
      if not isinstance(lead, dict):
        continue
      contact = lead.get("contact") or {}
      if normalize_email(contact.get("email", "")) == email:
        lead_id = candidate_id
        break
    if os.environ.get("CALCOM_WEBHOOK_DEBUG") == "1":
      print(f"[calcom_webhook] email_scan={lead_id}")

  if lead_id:
    lead = rtdb.child("leads").child(lead_id).get()
    if not lead:
      lead_id = None

  if not lead_id:
    rtdb.child("unmatched_calcom_events").child(event_key).set(
      {
        "payload": payload,
        "receivedAt": now_unix(),
        "reason": "lead_not_found",
        "extractedEmail": email,
        "emailKey": normalize_email_key(email) if email else None,
      }
    )
    return {"ok": True, "status": "unmatched_stored"}

  calcom_events_ref = (
    rtdb.child("leads").child(lead_id).child("followup").child("calcom").child("events")
  )
  if calcom_events_ref.child(event_key).get():
    return {"status": "duplicate_ignored"}

  calcom_status = "unknown"
  if event_type == "BOOKING_CREATED":
    calcom_status = "scheduled"
  elif event_type == "BOOKING_CANCELLED":
    calcom_status = "cancelled"
  elif event_type == "BOOKING_RESCHEDULED":
    calcom_status = "rescheduled"

  calcom_events_ref.child(event_key).set(payload)
  rtdb.child("leads").child(lead_id).child("followup").child("calcom").update(
    {
      "eventType": event_type,
      "status": calcom_status,
      "uid": uid,
      "updatedAt": now_unix(),
    }
  )

  if event_type == "BOOKING_CREATED":
    rtdb.child("leads").child(lead_id).child("request").update({"status": "meeting_scheduled"})
  elif event_type == "BOOKING_CANCELLED":
    rtdb.child("leads").child(lead_id).child("request").update({"status": "meeting_cancelled"})
  elif event_type == "BOOKING_RESCHEDULED":
    rtdb.child("leads").child(lead_id).child("request").update({"status": "meeting_rescheduled"})

  if event_type == "BOOKING_CREATED":
    lead = rtdb.child("leads").child(lead_id).get() or {}
    token, _preview = issue_intake_token(rtdb.child("leads"), lead_id, "INTAKE_TOKEN_REGENERATED")
    intake_result = send_intake_email(lead_id, lead, token)
    rtdb.child("leads").child(lead_id).child("notifications").child("intake").set(intake_result)
    log_event(rtdb.child("leads"), lead_id, "calcom_booking_created", {"eventType": event_type})
    if intake_result.get("status") == "sent":
      log_event(rtdb.child("leads"), lead_id, "intake_email_sent")

  return {"ok": True, "leadId": lead_id, "eventKey": event_key}


@router.post("/intake")
async def create_intake(body: IntakeIn):
  _init_firebase_admin()
  rtdb = db.reference("leads")
  lead_ref = rtdb.child(body.leadId)
  lead = lead_ref.get()
  if not lead:
    raise HTTPException(status_code=404, detail="Lead not found")

  contact = (lead.get("contact") or {})
  if body.email:
    if contact.get("email", "").strip().lower() != body.email.lower().strip():
      raise HTTPException(status_code=403, detail="Email does not match lead")

  intake = lead.get("intake") or {}
  token_hash = (intake.get("tokenHash") or "").strip()
  if not body.token or not token_hash:
    raise HTTPException(status_code=403, detail="Invalid intake token")

  body_hash = hashlib.sha256(body.token.strip().encode("utf-8")).hexdigest()
  if body_hash != token_hash:
    raise HTTPException(status_code=403, detail="Invalid intake token")

  token_created_at = intake.get("tokenCreatedAt")
  if not isinstance(token_created_at, int):
    raise HTTPException(status_code=403, detail="Invalid intake token")
  ttl_seconds = get_intake_ttl_seconds()
  if now_unix() - token_created_at > ttl_seconds:
    log_event(rtdb, body.leadId, "INTAKE_TOKEN_EXPIRED")
    raise HTTPException(status_code=403, detail="Intake token expired")

  allow_resubmit = os.environ.get("INTAKE_ALLOW_RESUBMIT", "").strip() == "1"
  if intake.get("tokenUsedAt") and not allow_resubmit:
    raise HTTPException(status_code=403, detail="Intake already submitted")

  intake = {
    "budgetRange": body.budgetRange,
    "timeline": body.timeline,
    "goals": body.goals.strip(),
    "constraints": (body.constraints or "").strip() or None,
    "submittedAt": now_unix(),
    "submittedAtIso": now_iso(),
  }

  intake_updates = {
    **intake,
    "tokenUsedAt": now_unix(),
    "tokenUsedAtIso": now_iso(),
  }
  if not allow_resubmit:
    intake_updates["tokenHash"] = None
  lead_ref.child("intake").update(intake_updates)
  lead_ref.update({"status": "prepared"})
  if intake.get("tokenUsedAt") and allow_resubmit:
    log_event(rtdb, body.leadId, "INTAKE_RESUBMITTED")
  else:
    log_event(rtdb, body.leadId, "INTAKE_SUBMITTED")
  return {"ok": True}


@router.post("/tasks/followup-reminders")
async def send_followup_reminders(req: Request):
  require_tasks_token(req)

  _init_firebase_admin()
  rtdb = db.reference("leads")
  leads = rtdb.get() or {}
  now_ts = now_unix()
  cutoff = now_ts - (48 * 3600)
  notified = []

  for lead_id, lead in leads.items():
    if not isinstance(lead, dict):
      continue
    analysis = lead.get("analysis") or {}
    if analysis.get("tier") != "hot":
      continue
    if (lead.get("followup") or {}).get("calcom", {}).get("status") in ("scheduled", "rescheduled"):
      continue
    if lead.get("createdAt", now_ts) > cutoff:
      continue
    reminders = lead.get("reminders") or {}
    if (reminders.get("followup48h") or {}).get("sentAt"):
      continue

    result = send_lead_followup_reminder(lead)
    rtdb.child(lead_id).child("reminders").child("followup48h").set(result)
    notified.append(lead_id)

  return {"ok": True, "notified": notified}


@router.post("/admin/leads/{lead_id}/intake-token")
async def regenerate_intake_token(lead_id: str, req: Request):
  require_tasks_token(req)

  _init_firebase_admin()
  leads_ref = db.reference("leads")
  lead = leads_ref.child(lead_id).get()
  if not lead:
    raise HTTPException(status_code=404, detail="Lead not found")

  intake_token, _preview = issue_intake_token(leads_ref, lead_id, "INTAKE_TOKEN_REGENERATED")
  base_url = os.environ.get("INTAKE_FORM_BASE_URL", "").strip() or "/#intake"
  intake_url = build_url_with_params(base_url, {"leadId": lead_id, "token": intake_token})
  return {"leadId": lead_id, "intakeUrl": intake_url}


@router.get("/admin/leads")
async def list_leads(req: Request, limit: int = Query(default=50, ge=1, le=500)):
  require_tasks_token(req)
  try:
    _init_firebase_admin()
    rtdb = db.reference("leads")
    leads = rtdb.get() or {}
  except Exception as exc:
    raise HTTPException(
      status_code=503,
      detail=(
        "Failed to read leads from Firebase. "
        "Reauthenticate Application Default Credentials with "
        "`gcloud auth application-default login` or configure a service account."
      ),
    ) from exc

  if not isinstance(leads, dict):
    raise HTTPException(status_code=502, detail="Unexpected leads payload from Firebase")

  rows = []
  for lead_id, lead in leads.items():
    if not isinstance(lead, dict):
      continue
    contact = lead.get("contact") or {}
    analysis = lead.get("analysis") or {}
    followup = (lead.get("followup") or {}).get("calcom") or {}
    request = lead.get("request") or {}
    intake = lead.get("intake") or {}
    rows.append(
      {
        "id": lead_id,
        "createdAt": lead.get("createdAt"),
        "createdAtIso": lead.get("createdAtIso"),
        "name": contact.get("name"),
        "email": contact.get("email"),
        "company": contact.get("company"),
        "priority": lead.get("priority"),
        "nextAction": lead.get("nextAction"),
        "tier": analysis.get("tier"),
        "score": analysis.get("score"),
        "status": lead.get("status"),
        "requestStatus": request.get("status"),
        "problem": request.get("problem"),
        "timeline": request.get("timeline"),
        "goals": intake.get("goals"),
        "calcomStatus": followup.get("status"),
        "calcomEventType": followup.get("eventType"),
        "updatedAt": followup.get("updatedAt"),
      }
    )

  rows.sort(key=lambda r: r.get("createdAt") or 0, reverse=True)
  return {"items": rows[:limit], "count": len(rows)}


def notify_admin_action(lead_id: str, action: str, details: Optional[dict] = None, lead: Optional[dict] = None) -> None:
  webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
  if not webhook_url:
    return
  contact = (lead or {}).get("contact") or {}
  name = contact.get("name") or "Unknown"
  email = contact.get("email") or "no-email"
  payload = {
    "text": (
      f"Admin action: {action}\n"
      f"Lead: {name} <{email}> ({lead_id})\n"
      f"Details: {details or {}}"
    )
  }
  try:
    requests.post(webhook_url, json=payload, timeout=10)
  except Exception:
    pass


@router.post("/admin/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, req: Request):
  require_tasks_token(req)
  body = await req.json()
  status = (body.get("status") or "").strip()
  if status not in ("qualified", "lost"):
    raise HTTPException(status_code=400, detail="Invalid status")

  _init_firebase_admin()
  lead_ref = db.reference("leads").child(lead_id)
  lead = lead_ref.get()
  if not lead:
    raise HTTPException(status_code=404, detail="Lead not found")

  lead_ref.update({"status": status})
  log_event(db.reference("leads"), lead_id, "ADMIN_STATUS_UPDATED", {"status": status})
  notify_admin_action(lead_id, "status_updated", {"status": status}, lead)
  return {"ok": True}


@router.post("/admin/leads/{lead_id}/request-details")
async def request_details(lead_id: str, req: Request):
  require_tasks_token(req)
  body = await req.json()
  message = (body.get("message") or "").strip()

  _init_firebase_admin()
  lead_ref = db.reference("leads").child(lead_id)
  lead = lead_ref.get()
  if not lead:
    raise HTTPException(status_code=404, detail="Lead not found")

  contact = (lead.get("contact") or {})
  to_email = contact.get("email")
  if not to_email:
    raise HTTPException(status_code=400, detail="Missing lead email")

  if not get_email_api_key() or not get_from_email():
    raise HTTPException(status_code=500, detail="Resend not configured")

  subject = "Quick question before we proceed"
  body_text = (
    f"Hi {contact.get('name', 'there')},\n\n"
    "Thanks for reaching out. Could you share a few more details so we can scope this correctly?\n"
  )
  if message:
    body_text += f"\n{message}\n"
  body_text += "\n— Magnio\n"

  result = send_resend_email(to_email, subject, body_text)
  if result.get("status") != "sent":
    raise HTTPException(status_code=500, detail="Resend send failed")

  lead_ref.update({"nextAction": "request_details"})
  log_event(db.reference("leads"), lead_id, "ADMIN_REQUEST_DETAILS")
  notify_admin_action(lead_id, "request_details", None, lead)
  return {"ok": True}


@router.post("/admin/leads/{lead_id}/follow-up")
async def schedule_follow_up(lead_id: str, req: Request):
  require_tasks_token(req)
  body = await req.json()
  hours = body.get("hours")
  if not isinstance(hours, int) or hours < 1 or hours > 720:
    raise HTTPException(status_code=400, detail="Invalid hours")

  _init_firebase_admin()
  lead_ref = db.reference("leads").child(lead_id)
  lead = lead_ref.get()
  if not lead:
    raise HTTPException(status_code=404, detail="Lead not found")

  follow_up_at = now_unix() + (hours * 3600)
  lead_ref.update(
    {
      "followUpAt": follow_up_at,
      "followUpAtIso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(follow_up_at)),
      "nextAction": "follow_up",
    }
  )
  log_event(db.reference("leads"), lead_id, "ADMIN_FOLLOWUP_SET", {"hours": hours})
  notify_admin_action(lead_id, "follow_up_set", {"hours": hours}, lead)
  return {"ok": True}
