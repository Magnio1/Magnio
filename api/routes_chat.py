from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.chat_analytics import (
  get_chat_analytics_summary,
  get_feedback_for_run,
  get_model_win_trends,
  get_recent_evaluation_cases,
  init_chat_analytics_db,
  record_chat_error,
  record_chat_run,
  resolve_chat_analytics_target,
  submit_chat_feedback,
)
from api.model_rankings import get_ranked_models_for_category
from api.magnio_knowledge import KNOWLEDGE_BASE, build_context, hybrid_search
from api.openrouter_client import (
  chat_completion,
  chat_completion_stream,
  extract_message_text,
  list_models,
  openrouter_configured,
)
from api.vertex_ai_client import (
  resolve_vertex_location,
  resolve_vertex_project,
  vertex_configured,
  vertex_extract_json,
  vertex_generate_content,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])

FAST_PROVIDER_PREF = {"sort": "latency", "allow_fallbacks": True}
VALID_LLM_PROVIDERS = {"openrouter", "vertex"}
DEFAULT_OPENROUTER_JUDGE_MODEL = "openai/gpt-5.1"
DEFAULT_OPENROUTER_ADVISOR_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_VERTEX_JUDGE_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_ADVISOR_MODEL = "gemini-2.5-flash"
OPPORTUNITY_RENDER_WORD_TARGET = 900

OPENROUTER_CATEGORY_LABELS = {
  "academia": "Academia",
  "dating": "Dating & Social",
  "finance": "Finance",
  "health": "Health",
  "legal": "Legal",
  "marketing": "Marketing",
  "programming": "Programming",
  "roleplay": "Roleplay",
  "science": "Science",
  "technology": "Technology",
  "travel": "Travel & Leisure",
  "translation": "Translation",
  "trivia": "Trivia",
}

DEFAULT_CATEGORY_MODELS = {
  "programming": [
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.1",
    "google/gemini-3-flash-preview",
  ],
  "technology": [
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.1",
    "google/gemini-3-flash-preview",
  ],
  "marketing": [
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.1",
    "google/gemini-3-flash-preview",
  ],
  "finance": [
    "openai/gpt-5.1",
    "anthropic/claude-sonnet-4.6",
    "google/gemini-3-flash-preview",
  ],
  "dating": [
    "anthropic/claude-sonnet-4.6",
    "google/gemini-3-flash-preview",
    "openai/gpt-5.1",
  ],
  "travel": [
    "google/gemini-3-flash-preview",
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.1",
  ],
  "legal": [
    "openai/gpt-5.1",
    "anthropic/claude-sonnet-4.6",
    "google/gemini-3-flash-preview",
  ],
}

OPENROUTER_RANKING_CATEGORIES = {
  "academia",
  "finance",
  "health",
  "legal",
  "marketing",
  "programming",
  "roleplay",
  "science",
  "technology",
  "translation",
  "trivia",
}

VERTEX_JUDGE_RESPONSE_SCHEMA = {
  "type": "object",
  "required": ["winnerModelId", "confidence", "rationale", "scores", "synthesis"],
  "properties": {
    "winnerModelId": {"type": "string"},
    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    "rationale": {"type": "string"},
    "scores": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["modelId", "usefulness", "groundedness", "clarity", "decisiveness", "notes"],
        "properties": {
          "modelId": {"type": "string"},
          "usefulness": {"type": "integer", "minimum": 1, "maximum": 10},
          "groundedness": {"type": "integer", "minimum": 1, "maximum": 10},
          "clarity": {"type": "integer", "minimum": 1, "maximum": 10},
          "decisiveness": {"type": "integer", "minimum": 1, "maximum": 10},
          "notes": {"type": "string"},
        },
      },
    },
    "synthesis": {"type": "string"},
  },
}

ADVISOR_FACT_EXTRACTION_SCHEMA = {
  "type": "object",
  "required": ["facts"],
  "properties": {
    "facts": {
      "type": "array",
      "minItems": 1,
      "maxItems": 10,
      "items": {
        "type": "object",
        "required": ["text", "citations"],
        "properties": {
          "text": {"type": "string"},
          "citations": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
          },
        },
      },
    }
  },
}

ADVISOR_FIT_RESPONSE_SCHEMA = {
  "type": "object",
  "required": ["overall_fit", "strengths", "gaps", "interview_answer"],
  "properties": {
    "overall_fit": {"type": "string"},
    "strengths": {
      "type": "array",
      "minItems": 1,
      "maxItems": 3,
      "items": {
        "type": "object",
        "required": ["text", "citations"],
        "properties": {
          "text": {"type": "string"},
          "citations": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
          },
        },
      },
    },
    "gaps": {
      "type": "array",
      "minItems": 1,
      "maxItems": 2,
      "items": {
        "type": "object",
        "required": ["text", "citations"],
        "properties": {
          "text": {"type": "string"},
          "citations": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
          },
        },
      },
    },
    "interview_answer": {
      "type": "object",
      "required": ["text", "citations"],
      "properties": {
        "text": {"type": "string"},
        "citations": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string"},
        },
      },
    },
  },
}

ADVISOR_OPPORTUNITY_RESPONSE_SCHEMA = {
  "type": "object",
  "required": [
    "overall_fit",
    "scorecard",
    "strongest_evidence",
    "gaps_or_risks",
    "role_reality_check",
    "pursuit_decision",
    "positioning_strategy",
    "do_not_overclaim",
    "final_verdict",
  ],
  "properties": {
    "overall_fit": {
      "type": "object",
      "required": ["text", "citations"],
      "properties": {
        "text": {"type": "string"},
        "citations": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string"},
        },
      },
    },
    "scorecard": {
      "type": "array",
      "minItems": 5,
      "maxItems": 6,
      "items": {
        "type": "object",
        "required": ["dimension", "score", "evidence_text", "evidence_citations", "inference_text"],
        "properties": {
          "dimension": {"type": "string"},
          "score": {"type": "string"},
          "evidence_text": {"type": "string"},
          "evidence_citations": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
          },
          "inference_text": {"type": "string"},
        },
      },
    },
    "strongest_evidence": {
      "type": "array",
      "minItems": 2,
      "maxItems": 4,
      "items": {
        "type": "object",
        "required": ["text", "citations"],
        "properties": {
          "text": {"type": "string"},
          "citations": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
          },
        },
      },
    },
    "gaps_or_risks": {
      "type": "array",
      "minItems": 2,
      "maxItems": 3,
      "items": {
        "type": "object",
        "required": ["text", "citations", "inference_text"],
        "properties": {
          "text": {"type": "string"},
          "citations": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
          },
          "inference_text": {"type": "string"},
        },
      },
    },
    "signal_analysis": {"type": "string"},
    "role_decomposition": {"type": "string"},
    "strategic_value": {"type": "string"},
    "hire_signal": {"type": "string"},
    "temperature_classification": {"type": "string"},
    "role_reality_check": {
      "type": "object",
      "required": ["text", "citations", "inference_text"],
      "properties": {
        "text": {"type": "string"},
        "citations": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string"},
        },
        "inference_text": {"type": "string"},
      },
    },
    "pursuit_decision": {
      "type": "object",
      "required": ["decision", "text", "citations"],
      "properties": {
        "decision": {"type": "string", "enum": ["Strong pursue", "Selective pursue", "Pass"]},
        "text": {"type": "string"},
        "citations": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string"},
        },
      },
    },
    "positioning_strategy": {
      "type": "object",
      "required": ["text", "citations"],
      "properties": {
        "text": {"type": "string"},
        "citations": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string"},
        },
      },
    },
    "do_not_overclaim": {
      "type": "array",
      "minItems": 2,
      "maxItems": 4,
      "items": {"type": "string"},
    },
    "final_verdict": {"type": "string"},
  },
}

FIT_ANALYSIS_PRIORITY_CHUNK_IDS = ("K37", "K38", "K39", "K40", "K45", "K46", "K47", "K48", "K49", "K50", "K51", "K52", "K53", "K54", "K55", "K56", "K43")
FIT_ANALYSIS_PRIORITY_SOURCES = ("09-sebastian-profile.json",)


class ChatAskRequest(BaseModel):
  query: str = Field(min_length=2, max_length=8000)
  mode: Literal["auto", "arena", "advisor"] = "auto"


class ChatFeedbackRequest(BaseModel):
  runId: str = Field(min_length=8, max_length=120)
  vote: Literal["up", "down"]
  note: str | None = Field(default=None, max_length=2000)


class ChatSuggestRequest(BaseModel):
  answer: str = Field(min_length=10, max_length=10000)
  topic_label: str = Field(min_length=1, max_length=200)
  mode: Literal["auto", "arena", "advisor"] = "auto"


def _resolve_provider(env_name: str, *, default: Literal["openrouter", "vertex"] = "openrouter") -> Literal["openrouter", "vertex"]:
  configured = os.environ.get(env_name, "").strip().lower()
  if configured in VALID_LLM_PROVIDERS:
    return configured  # type: ignore[return-value]
  return default


def _resolve_advisor_provider() -> Literal["openrouter", "vertex"]:
  return _resolve_provider("MAGNIO_CHAT_ADVISOR_PROVIDER")


def _resolve_judge_provider() -> Literal["openrouter", "vertex"]:
  return _resolve_provider("MAGNIO_CHAT_JUDGE_PROVIDER")


def _resolve_advisor_model(provider: Literal["openrouter", "vertex"]) -> str:
  if provider == "vertex":
    return os.environ.get("MAGNIO_CHAT_VERTEX_ADVISOR_MODEL", "").strip() or DEFAULT_VERTEX_ADVISOR_MODEL
  return os.environ.get("MAGNIO_CHAT_ADVISOR_MODEL", "").strip() or DEFAULT_OPENROUTER_ADVISOR_MODEL


def _resolve_judge_model(provider: Literal["openrouter", "vertex"]) -> str:
  if provider == "vertex":
    return os.environ.get("MAGNIO_CHAT_VERTEX_JUDGE_MODEL", "").strip() or DEFAULT_VERTEX_JUDGE_MODEL
  return os.environ.get("MAGNIO_CHAT_JUDGE_MODEL", "").strip() or DEFAULT_OPENROUTER_JUDGE_MODEL


def _provider_configured(provider: Literal["openrouter", "vertex"]) -> bool:
  if provider == "vertex":
    return vertex_configured()
  return openrouter_configured()


def _provider_not_configured_message(provider: Literal["openrouter", "vertex"]) -> str:
  if provider == "vertex":
    return (
      "Vertex AI is not configured. Set MAGNIO_VERTEX_PROJECT or GOOGLE_CLOUD_PROJECT "
      "and authenticate with Application Default Credentials."
    )
  return "OpenRouter API key is not configured. Set MAGNIO_OPENROUTER_API_KEY or OPENROUTER_API_KEY."


def _word_count_text(text: str) -> int:
  return len([part for part in text.strip().split() if part])


def _citation_suffix(citations: list[str]) -> str:
  clean = []
  seen: set[str] = set()
  for citation in citations:
    normalized = str(citation).strip()
    if not normalized or normalized in seen:
      continue
    clean.append(normalized)
    seen.add(normalized)
  if not clean:
    return ""
  return "".join(f"[{citation}]" for citation in clean)


def _truncate_rendered_tail(text: str, max_words: int) -> tuple[str, int]:
  clean = str(text or "").strip()
  if not clean:
    return "", 0
  matches = list(re.finditer(r"\S+", clean))
  if len(matches) <= max_words:
    return clean, len(matches)
  cutoff = matches[max_words - 1].end()
  trimmed = clean[:cutoff].rstrip(",;:- \n\t")
  if trimmed and trimmed[-1] not in ".!?":
    trimmed += "..."
  return trimmed, max_words


def _normalize_structured_item(
  item: Any,
  *,
  allowed_citations: set[str],
  require_citations: bool,
) -> dict[str, Any] | None:
  if not isinstance(item, dict):
    return None

  text = str(item.get("text") or "").strip()
  if not text:
    return None

  citations = []
  for citation in item.get("citations") or []:
    normalized = str(citation).strip()
    if normalized in allowed_citations and normalized not in citations:
      citations.append(normalized)

  if require_citations and not citations:
    return None

  return {
    "text": text,
    "citations": citations,
  }


def _normalize_structured_scorecard_item(item: Any, *, allowed_citations: set[str]) -> dict[str, Any] | None:
  if not isinstance(item, dict):
    return None

  dimension = str(item.get("dimension") or "").strip()
  score = str(item.get("score") or "").strip()
  evidence_text = str(item.get("evidence_text") or "").strip()
  inference_text = str(item.get("inference_text") or "").strip()
  if not dimension or not score or not evidence_text or not inference_text:
    return None

  evidence_citations: list[str] = []
  for citation in item.get("evidence_citations") or []:
    normalized = str(citation).strip()
    if normalized in allowed_citations and normalized not in evidence_citations:
      evidence_citations.append(normalized)

  if not evidence_citations:
    return None

  return {
    "dimension": dimension,
    "score": score,
    "evidence_text": evidence_text,
    "evidence_citations": evidence_citations,
    "inference_text": inference_text,
  }


def _normalize_structured_risk_item(item: Any, *, allowed_citations: set[str]) -> dict[str, Any] | None:
  if not isinstance(item, dict):
    return None

  text = str(item.get("text") or "").strip()
  inference_text = str(item.get("inference_text") or "").strip()
  if not text or not inference_text:
    return None

  normalized = _normalize_structured_item(
    {"text": text, "citations": item.get("citations") or []},
    allowed_citations=allowed_citations,
    require_citations=True,
  )
  if normalized is None:
    return None

  normalized["inference_text"] = inference_text
  return normalized


def _coerce_structured_object(value: Any, *, list_key: str | None = None) -> dict[str, Any]:
  if isinstance(value, dict):
    return value
  if list_key and isinstance(value, list):
    return {list_key: value}
  return {}


def _render_structured_fit_answer(payload: dict[str, Any]) -> str:
  overall = str(payload.get("overall_fit") or "").strip()
  strengths = payload.get("strengths") or []
  gaps = payload.get("gaps") or []
  interview_answer = _coerce_structured_object(payload.get("interview_answer"))

  lines: list[str] = []
  if overall:
    lines.append("1. Overall fit")
    lines.append(overall)

  if strengths:
    lines.append("")
    lines.append("2. Top 3 strengths")
    for item in strengths:
      lines.append(f"- {item['text']}{_citation_suffix(item['citations'])}")

  if gaps:
    lines.append("")
    lines.append("3. Top 2 gaps")
    for item in gaps:
      suffix = _citation_suffix(item["citations"])
      lines.append(f"- {item['text']}{suffix}")

  interview_text = str(interview_answer.get("text") or "").strip()
  if interview_text:
    lines.append("")
    lines.append("4. 60-second interview answer")
    lines.append(f"{interview_text}{_citation_suffix(interview_answer.get('citations') or [])}")

  return "\n".join(lines).strip()


def _render_structured_opportunity_answer(payload: dict[str, Any]) -> str:
  overall_fit = _coerce_structured_object(payload.get("overall_fit"))
  scorecard = payload.get("scorecard") or []
  strongest_evidence = payload.get("strongest_evidence") or []
  gaps_or_risks = payload.get("gaps_or_risks") or []
  role_reality_check = _coerce_structured_object(payload.get("role_reality_check"))
  pursuit_decision = _coerce_structured_object(payload.get("pursuit_decision"))
  positioning_strategy = _coerce_structured_object(payload.get("positioning_strategy"))
  do_not_overclaim = payload.get("do_not_overclaim") or []

  lines: list[str] = []
  section_number = 1

  overall_text = str(overall_fit.get("text") or "").strip()
  if overall_text:
    lines.append(f"{section_number}. Overall fit")
    lines.append(f"{overall_text}{_citation_suffix(overall_fit.get('citations') or [])}")
    section_number += 1

  if scorecard:
    lines.append("")
    lines.append(f"{section_number}. Opportunity scorecard")
    for item in scorecard:
      lines.append(f"- {item['dimension']} — {item['score']}")
      lines.append(f"  Evidence: {item['evidence_text']}{_citation_suffix(item['evidence_citations'])}")
      lines.append(f"  {item['inference_text']}")
    section_number += 1

  if strongest_evidence:
    lines.append("")
    lines.append(f"{section_number}. Strongest evidence for fit")
    for item in strongest_evidence:
      lines.append(f"- {item['text']}{_citation_suffix(item['citations'])}")
    section_number += 1

  if gaps_or_risks:
    lines.append("")
    lines.append(f"{section_number}. Biggest gaps or mismatch risks")
    for item in gaps_or_risks:
      lines.append(f"- Evidence: {item['text']}{_citation_suffix(item['citations'])}")
      lines.append(f"  {item['inference_text']}")
    section_number += 1

  optional_sections = [
    ("signal_analysis", "Legitimacy & signal analysis"),
    ("role_decomposition", "Role decomposition"),
    ("strategic_value", "Strategic value"),
    ("hire_signal", "Hire signal"),
    ("temperature_classification", "Lead temperature"),
  ]
  for key, title in optional_sections:
    text = str(payload.get(key) or "").strip()
    if not text:
      continue
    lines.append("")
    lines.append(f"{section_number}. {title}")
    lines.append(text)
    section_number += 1

  reality_text = str(role_reality_check.get("text") or "").strip()
  if reality_text:
    lines.append("")
    lines.append(f"{section_number}. Role reality check")
    lines.append(f"Evidence: {reality_text}{_citation_suffix(role_reality_check.get('citations') or [])}")
    lines.append(str(role_reality_check.get("inference_text") or "").strip())
    section_number += 1

  pursuit_text = str(pursuit_decision.get("text") or "").strip()
  if pursuit_text:
    lines.append("")
    lines.append(f"{section_number}. Pursue / selective pursue / pass")
    lines.append(
      f"{str(pursuit_decision.get('decision') or '').strip()} — "
      f"{pursuit_text}{_citation_suffix(pursuit_decision.get('citations') or [])}"
    )
    section_number += 1

  positioning_text = str(positioning_strategy.get("text") or "").strip()
  if positioning_text:
    lines.append("")
    lines.append(f"{section_number}. 60-second positioning strategy")
    lines.append(f"{positioning_text}{_citation_suffix(positioning_strategy.get('citations') or [])}")
    section_number += 1

  if do_not_overclaim:
    lines.append("")
    lines.append(f"{section_number}. What not to overclaim")
    for item in do_not_overclaim:
      clean = str(item).strip()
      if clean:
        lines.append(f"- {clean}")
    section_number += 1

  final_verdict = str(payload.get("final_verdict") or "").strip()
  if final_verdict:
    lines.append("")
    lines.append(f"{section_number}. Final verdict")
    lines.append(final_verdict)

  return "\n".join(lines).strip()


def _compact_structured_opportunity_payload(
  payload: dict[str, Any],
  *,
  target_words: int = OPPORTUNITY_RENDER_WORD_TARGET,
) -> dict[str, Any]:
  compact = dict(payload)
  rendered = _render_structured_opportunity_answer(compact)
  truncated_rendered, rendered_word_count = _truncate_rendered_tail(rendered, target_words)
  compact["rendered"] = truncated_rendered
  compact["renderedWordCount"] = rendered_word_count
  return compact


def _normalize_query(text: str) -> str:
  return re.sub(r"\s+", " ", text.lower()).strip()


def _advisor_score(normalized_query: str) -> int:
  patterns = [
    r"\bmagnio\b",
    r"\bsebastian\b",
    r"\bhow (do|does) (you|magnio) work\b",
    r"\bservices?\b",
    r"\bengagement\b",
    r"\bproposal\b",
    r"\bcase stud",
    r"\broi\b",
    r"\bsavings\b",
    r"\bloss prevented\b",
    r"\bai immersion\b",
    r"\bai adoption\b",
    r"\bwhere should (we|i) start\b",
    r"\bworkflow audit\b",
    r"\bpilot\b",
    r"\broadmap\b",
    r"\boperating model\b",
    r"\blead\b",
    r"\bqualified prospect\b",
    r"\bfractional\b",
    r"\bconsult(ing|ant|ancy)\b",
    r"\badvis(or|ory)\b",
    r"\brecruit(er|ing)\b",
    r"\blawyer\b",
    r"\battorney\b",
    r"\bcfo\b",
    r"\bagency\b",
    r"\bside business\b",
    r"\bkeep(ing)? your job\b",
  ]
  return sum(2 if re.search(pattern, normalized_query) else 0 for pattern in patterns)


def _arena_score(normalized_query: str) -> int:
  patterns = [
    r"\bcode\b",
    r"\btypescript\b",
    r"\bpython\b",
    r"\breact\b",
    r"\bjavascript\b",
    r"\bdebug\b",
    r"\bapi\b",
    r"\bsql\b",
    r"\bcompare\b",
    r"\bexplain\b",
    r"\bimplement\b",
    r"\bwrite\b",
    r"\barchitecture\b",
    r"\bprompt\b",
  ]
  return sum(1 if re.search(pattern, normalized_query) else 0 for pattern in patterns)


def _resolve_mode(query: str, requested_mode: str) -> Literal["arena", "advisor"]:
  if requested_mode in {"arena", "advisor"}:
    return requested_mode

  profile_id = str(_advisor_query_profile(query).get("id") or "").strip()
  if profile_id in ARENA_GROUNDED_PROFILE_IDS:
    return "advisor"

  normalized_query = _normalize_query(query)
  advisor_score = _advisor_score(normalized_query)
  arena_score = _arena_score(normalized_query)
  if advisor_score > 0 and advisor_score >= arena_score:
    return "advisor"
  return "arena"


def _infer_category(query: str) -> tuple[str, list[str]]:
  normalized_query = _normalize_query(query)

  biotech_due_diligence_patterns = [
    r"\bbiopharma\b",
    r"\bbiotech\b",
    r"\bpharma\b",
    r"\bpipeline asset\b",
    r"\bphase [1234]\b",
    r"\bphase (i|ii|iii|iv)\b",
    r"\btrial(s)?\b",
    r"\bclinical development\b",
    r"\bregistrational\b",
    r"\bdue diligence\b",
    r"\binvest(ment|or|ing)?\b",
    r"\bcapital\b",
    r"\brisk profile\b",
    r"\bseries [a-d]\b",
  ]
  biotech_due_diligence_score = sum(
    1 for pattern in biotech_due_diligence_patterns if re.search(pattern, normalized_query)
  )
  if biotech_due_diligence_score >= 3:
    return (
      "finance",
      [
        "Detected biotech investment due-diligence language, so routed to Finance & Business."
      ],
    )

  dating_preference_patterns = [
    r"\bmy type\b",
    r"\bideal partner\b",
    r"\blooking for (a|an)\b",
    r"\bwhere can i meet\b",
    r"\bbest city to meet\b",
    r"\bbest place to meet\b",
    r"\bchances to meet\b",
    r"\bfind (a )?(girlfriend|boyfriend|partner|wife|husband)\b",
    r"\b(single )?(girls?|women|guys?|men)\b",
  ]
  if any(re.search(pattern, normalized_query) for pattern in dating_preference_patterns):
    return (
      "dating",
      ["Detected partner-preference or meeting-people language, so routed to Dating & Social."],
    )

  rules = [
    (
      "programming",
      [
        r"\btypescript\b",
        r"\bjavascript\b",
        r"\bpython\b",
        r"\breact\b",
        r"\bnode\b",
        r"\bapi\b",
        r"\bdebug\b",
        r"\bcode\b",
        r"\bsql\b",
        r"\bbug\b",
        r"\brefactor\b",
      ],
      "Detected code and implementation language terms.",
    ),
    (
      "dating",
      [
        r"\bdating\b",
        r"\bdate\b",
        r"\bdating scene\b",
        r"\bsingles?\b",
        r"\bromantic\b",
        r"\brelationship(s)?\b",
        r"\bmeet people\b",
        r"\bmeeting people\b",
        r"\bmatchmaking\b",
        r"\bflirting\b",
      ],
      "Detected dating and social-scene language.",
    ),
    (
      "travel",
      [
        r"\btravel\b",
        r"\btrip\b",
        r"\bvacation\b",
        r"\bholiday\b",
        r"\bitinerary\b",
        r"\bdestination\b",
        r"\bvisit\b",
        r"\bflight\b",
        r"\bhotel\b",
        r"\bairbnb\b",
        r"\bparis\b",
        r"\blisbon\b",
        r"\bmadrid\b",
        r"\boslo\b",
        r"\brome\b",
        r"\bbarcelona\b",
        r"\blondon\b",
      ],
      "Detected travel and destination-planning language.",
    ),
    (
      "legal",
      [r"\blegal\b", r"\bcontract\b", r"\bnda\b", r"\bregulat", r"\bcompliance\b", r"\bterms\b"],
      "Detected legal or compliance language.",
    ),
    (
      "finance",
      [
        r"\bfinance\b",
        r"\bbudget\b",
        r"\broi\b",
        r"\bmargin\b",
        r"\bcash\b",
        r"\bforecast\b",
        r"\bpricing\b",
        r"\bdue diligence\b",
        r"\binvest(ment|or|ing)?\b",
        r"\bcapital\b",
        r"\bvaluation\b",
        r"\brunway\b",
        r"\bcompany\b",
        r"\brisk profile\b",
        r"\bseries [a-d]\b",
      ],
      "Detected finance and business-impact language.",
    ),
    (
      "marketing",
      [r"\bmarketing\b", r"\bseo\b", r"\bbrand\b", r"\bcampaign\b", r"\bcopy\b", r"\bgrowth\b"],
      "Detected marketing and go-to-market language.",
    ),
    (
      "translation",
      [r"\btranslate\b", r"\btranslation\b", r"\bspanish\b", r"\benglish\b"],
      "Detected translation language.",
    ),
    (
      "health",
      [
        r"\bhealth\b",
        r"\bmedical\b",
        r"\bclinical\b",
        r"\btrial(s)?\b",
        r"\bpatient(s)?\b",
        r"\bbiopharma\b",
        r"\bbiotech\b",
        r"\bpharma\b",
      ],
      "Detected health-related language.",
    ),
    (
      "science",
      [
        r"\bscience\b",
        r"\bphysics\b",
        r"\bchemistry\b",
        r"\bbiology\b",
        r"\bdrug\b",
        r"\bmolecule\b",
        r"\bphase [1234]\b",
        r"\bphase (i|ii|iii|iv)\b",
        r"\bregistrational\b",
      ],
      "Detected science-related language.",
    ),
    (
      "academia",
      [r"\bresearch\b", r"\bpaper\b", r"\bthesis\b", r"\bacademic\b"],
      "Detected academic or research language.",
    ),
    (
      "roleplay",
      [r"\broleplay\b", r"\bcharacter\b", r"\bstory\b", r"\bfiction\b"],
      "Detected storytelling or roleplay language.",
    ),
    (
      "trivia",
      [r"\btrivia\b", r"\bquiz\b", r"\bfacts?\b"],
      "Detected trivia-oriented language.",
    ),
  ]

  for category, patterns, reason in rules:
    if any(re.search(pattern, normalized_query) for pattern in patterns):
      return category, [reason]

  return "technology", ["Defaulted to the technology category for a general-purpose knowledge task."]


def _arena_system_prompt(category: str, *, grounded: bool = False) -> str:
  category_label = OPENROUTER_CATEGORY_LABELS.get(category, category.title())
  base = (
    f"You are one candidate answer model inside Magnio Arena for a {category_label} request.\n"
    "Write the strongest answer you can.\n"
    "Rules:\n"
    "- Be direct and concrete.\n"
    "- State assumptions briefly when the prompt is underspecified.\n"
    "- Prefer useful structure over generic exposition.\n"
    "- Keep fluff low.\n"
    "- If there are tradeoffs, name them clearly.\n"
    "- Do not mention model rankings, judges, or that you are part of a comparison."
  )
  if grounded:
    base += (
      "\n- When retrieved evidence is supplied, use it as the source of truth for Sebastian/project claims."
      "\n- Cite only the exact allowed chunk ids provided in the user message."
      "\n- Never invent chunk ids, placeholder citations, or unsupported evidence."
    )
  if category != "dating":
    return base

  return (
    base
    + "\n"
    + "Dating & Social guardrails:\n"
    + "- Keep the advice respectful, non-coercive, and compatibility-oriented.\n"
    + "- Do not optimize for targeting people by ethnicity, nationality, body type, or stereotype.\n"
    + "- If the user frames the request in objectifying, fetishizing, or manipulative terms, redirect to healthier variables such as shared values, lifestyle fit, dating culture, communication norms, safety, language, and social openness.\n"
    + "- You may compare cities on dating culture, social density, cost, safety, walkability, international openness, and relationship-fit factors.\n"
    + "- Do not give pickup-artist, coercive, deceptive, or exploitative tactics."
  )


def _advisor_system_prompt() -> str:
  return (
    "You are Magnio Advisor.\n"
    "Use the provided Magnio knowledge base as the source of truth for Magnio-specific claims.\n"
    "You may make clearly labeled inferences from the knowledge base, but do not invent case-study details.\n"
    "Default to practical operator guidance, not consultancy theater.\n"
    "Match the user's scale and stage. If the user sounds solo, early-stage, or local-service, keep the answer lean and concrete.\n"
    "Do not force Magnio sales language when the user is simply asking how to start.\n"
    "Only use phrases like workflow audit, engagement shape, or pilot rubric when the user's situation is operationally complex or they ask about hiring Magnio.\n"
    "For career transition or side-business questions, focus on wedge, offer design, first clients, conflict guardrails, and transition triggers.\n"
    "When useful, structure the answer as:\n"
    "1. diagnosis\n"
    "2. recommended entry point\n"
    "3. short execution path\n"
    "4. suggested engagement shape\n"
    "Cite knowledge chunks inline using bracketed ids like [K3].\n"
    "Avoid generic AI theater language."
  )


def _advisor_opportunity_system_prompt() -> str:
  return (
    "You are Magnio Advisor producing a job-opportunity evaluation.\n"
    "The user's supplied job description or role framing is first-class input, but it is not retrieved evidence about Sebastian.\n"
    "Separate two claim types clearly:\n"
    "1. Retrieved evidence: claims about Sebastian's documented work. These must cite chunk ids inline like [K39].\n"
    "2. JD-based inference: claims inferred from the wording, structure, or implied operating model of the job description. These must be explicitly labeled as '(JD inference)' and must not use chunk-id citations.\n"
    "If you make a compensation or market-range statement without retrieved evidence, label it '(Market/JD inference)' and do not attach chunk citations.\n"
    "Never present inference as if it were retrieved evidence.\n"
    "If a section mixes both, split it into separate sentences or bullets.\n"
    "Do not use markdown tables for opportunity analysis, because they hide evidence versus inference labeling.\n"
    "Prefer numbered sections with compact bullets.\n"
    "Follow the user's requested output structure as closely as possible.\n"
    "Be direct, hiring-manager oriented, and low-fluff."
  )


def _advisor_fact_extraction_system_prompt() -> str:
  return (
    "You extract only supported facts from retrieved context.\n"
    "Return valid JSON only.\n"
    "Each fact must be directly supported by the supplied chunks.\n"
    "Every fact must include one or more chunk ids from the supplied context.\n"
    "Do not infer unstated skills, tools, or deployments.\n"
    "Do not write recommendations, summaries, or opinions.\n"
    "Prefer concrete production evidence such as deployment, orchestration, RAG, evaluation, guardrails, auditability, Cloud Run, and Vertex AI when present."
  )


def _advisor_fit_synthesis_system_prompt() -> str:
  return (
    "You are Magnio Advisor producing a structured fit evaluation.\n"
    "Return valid JSON only.\n"
    "Use only the extracted facts and retrieved chunk ids provided in the prompt.\n"
    "Do not use prior knowledge.\n"
    "overall_fit may include inline chunk-id citations inside the string.\n"
    "Every factual strength must cite at least one retrieved chunk id.\n"
    "If a gap is not explicitly stated, phrase it as 'not evidenced in retrieved material'.\n"
    "Avoid duplicate strengths.\n"
    "The interview answer must sound spoken, concise, and natural.\n"
    "Keep the rendered output under 1000 words total.\n"
    "No citations outside the supplied chunk ids."
  )


def _advisor_opportunity_synthesis_system_prompt() -> str:
  return (
    "You are Magnio Advisor producing a structured job-opportunity evaluation.\n"
    "Return valid JSON only.\n"
    "Use only the user task, the extracted facts, and the supplied chunk ids.\n"
    "Do not use prior knowledge.\n"
    "Retrieved evidence about Sebastian must appear only in fields that carry chunk citations.\n"
    "JD-based or market-based interpretation must appear in inference_text fields or plain advisory strings only.\n"
    "Each inference_text must start with '(JD inference)' or '(Market/JD inference)'.\n"
    "Do not attach chunk citations to inference-only claims.\n"
    "If a gap is missing from the retrieved evidence, phrase it as 'not evidenced in retrieved material'.\n"
    "Prefer the scorecard dimensions the user asked for.\n"
    "overall_fit, strongest_evidence, pursuit_decision, and positioning_strategy must be concise and executive.\n"
    "positioning_strategy must sound spoken, concise, and natural.\n"
    "Keep the rendered answer under 900 words total.\n"
    "Keep strongest_evidence and gaps_or_risks short, non-duplicative, and scannable.\n"
    "Keep scorecard evidence_text and inference_text to one short sentence each.\n"
    "If the user explicitly asked for legitimacy analysis, role decomposition, strategic value, hire signal, or lead temperature, populate those optional fields.\n"
    "final_verdict must start exactly with 'Final verdict: '.\n"
    "No citations outside the supplied chunk ids."
  )


def _advisor_fit_stream_render_system_prompt() -> str:
  return (
    "You are Magnio Advisor producing a rendered fit evaluation.\n"
    "Return plain markdown/text only. Do not return JSON.\n"
    "Use only the extracted facts and allowed chunk ids supplied by the user.\n"
    "Do not use prior knowledge.\n"
    "Follow the user's requested structure when possible.\n"
    "Every factual strength or gap must cite one or more allowed chunk ids inline.\n"
    "If a gap is not explicit in the facts, phrase it as 'not evidenced in retrieved material'.\n"
    "Avoid duplicate strengths.\n"
    "The interview answer must sound spoken, concise, and natural.\n"
    "Keep the overall response compact."
  )


def _advisor_opportunity_stream_render_system_prompt() -> str:
  return (
    "You are Magnio Advisor producing a rendered job-opportunity evaluation.\n"
    "Return plain markdown/text only. Do not return JSON.\n"
    "Use only the user task, extracted facts, and allowed chunk ids supplied in the prompt.\n"
    "Do not use prior knowledge.\n"
    "Claims about Sebastian's documented work must carry inline chunk citations.\n"
    "JD-based inference must be labeled '(JD inference)'.\n"
    "Market or compensation inference must be labeled '(Market/JD inference)'.\n"
    "Do not attach chunk citations to inference-only claims.\n"
    "If evidence is missing, say 'not evidenced in retrieved material'.\n"
    "Follow the user's requested output structure as closely as possible.\n"
    "Prefer polished markdown with readable headings, short paragraphs, and compact bullets.\n"
    "A compact markdown table is allowed for the scorecard when it improves readability.\n"
    "Keep the answer substantial but controlled, and prioritize finishing the later sections and final verdict.\n"
    "If you need to compress, shorten detail before dropping structure.\n"
    "Be direct, hiring-manager oriented, and low-fluff."
  )


def _advisor_query_profile(query: str) -> dict[str, Any]:
  normalized_query = _normalize_query(query)

  opportunity_analysis_terms = [
    r"\bjob description\b",
    r"\bopportunity scoring\b",
    r"\bcompensation fit\b",
    r"\bcareer leverage\b",
    r"\bownership\b",
    r"\blearning / growth\b",
    r"\blearning\b",
    r"\blegitimacy\b",
    r"\bsignal analysis\b",
    r"\brole decomposition\b",
    r"\blead temperature\b",
    r"\bresponse strategy\b",
    r"\bfinal verdict\b",
    r"\bstrong pursue\b",
    r"\bselective pursue\b",
    r"\bskip\b",
    r"\bhot\b",
    r"\bwarm\b",
    r"\bcold\b",
    r"\bapply or not\b",
    r"\bpursue aggressively\b",
    r"\bhigh[- ]quality opportunity\b",
    r"\bbureaucratic role\b",
  ]
  fit_analysis_terms = [
    r"\bfit\b",
    r"\bfit for\b",
    r"\bstrong fit\b",
    r"\binterview\b",
    r"\bvertex ai\b",
    r"\bgoogle cloud\b",
    r"\bagentic ai role\b",
    r"\btop 3 strengths\b",
    r"\btop 2 gaps\b",
    r"\boverall fit\b",
    r"\b60-second\b",
    r"\b60 second\b",
  ]

  website_terms = [
    r"\bwebsite\b",
    r"\bsite\b",
    r"\blanding page\b",
    r"\bhomepage\b",
  ]
  solo_service_terms = [
    r"\bsolo\b",
    r"\bfreelanc",
    r"\bone[- ]person\b",
    r"\bsmall business\b",
    r"\blocal business\b",
    r"\bservice business\b",
    r"\bpersonal trainer\b",
    r"\btrainer\b",
    r"\bcoach\b",
    r"\bgym\b",
  ]
  starting_terms = [
    r"\bstart(ing)?\b",
    r"\blaunch\b",
    r"\bfrom scratch\b",
    r"\bfirst\b",
  ]
  side_practice_terms = [
    r"\bside business\b",
    r"\bside practice\b",
    r"\bkeep(ing)? your job\b",
    r"\bday job\b",
    r"\bwhile employed\b",
    r"\bwhile keeping your job\b",
    r"\bfull[- ]time\b",
    r"\bevenings?\b",
    r"\bweekends?\b",
    r"\bquit\b",
    r"\bgive notice\b",
    r"\bsalary\b",
  ]
  professional_terms = [
    r"\bcpa\b",
    r"\baccount(ant|ing)\b",
    r"\bbookkeeping\b",
    r"\btax\b",
    r"\bconsult(ing|ant)?\b",
    r"\bagency\b",
  ]
  consulting_transition_terms = [
    r"\bfractional\b",
    r"\badvis(or|ory)\b",
    r"\bconsult(ing|ant|ancy)\b",
    r"\brecruit(er|ing)\b",
    r"\blawyer\b",
    r"\battorney\b",
    r"\bcfo\b",
    r"\bagency\b",
    r"\boperator\b",
    r"\bretainer\b",
    r"\bclients?\b",
    r"\bservice line\b",
    r"\bpractice\b",
  ]

  website_hit = any(re.search(pattern, normalized_query) for pattern in website_terms)
  solo_service_hit = any(re.search(pattern, normalized_query) for pattern in solo_service_terms)
  starting_hit = any(re.search(pattern, normalized_query) for pattern in starting_terms)
  side_practice_hit = any(re.search(pattern, normalized_query) for pattern in side_practice_terms)
  professional_hit = any(re.search(pattern, normalized_query) for pattern in professional_terms)
  consulting_transition_hit = any(re.search(pattern, normalized_query) for pattern in consulting_transition_terms)
  opportunity_analysis_hit = any(re.search(pattern, normalized_query) for pattern in opportunity_analysis_terms)
  fit_analysis_hit = any(re.search(pattern, normalized_query) for pattern in fit_analysis_terms)

  if opportunity_analysis_hit:
    return {
      "id": "opportunity_analysis",
      "retrievalQuery": (
        f"{query} Sebastian Rosales Magnio CIC Actus Google Cloud Vertex AI "
        "agentic systems audit-safe analytics financial ERP deterministic-first "
        "RAG orchestration evaluation guardrails observability Firestore FastAPI Firebase "
        "data engineering ETL data quality monitoring backend APIs scalable services system design"
      ),
      "preferredFocus": ["fit", "proof", "agentic", "operations"],
      "preferredChunkIds": list(FIT_ANALYSIS_PRIORITY_CHUNK_IDS),
      "preferredSources": list(FIT_ANALYSIS_PRIORITY_SOURCES),
      "instructions": (
        "This is a job-opportunity evaluation request for Sebastian Rosales.\n"
        "Treat the supplied job description or role framing as first-class input, not as a generic fit check.\n"
        "Prefer resume and project evidence first, especially Magnio, CIC, Actus, and architecture material.\n"
        "Compare the role's implied day-to-day work, leverage, data/backend depth, and career upside against the retrieved evidence.\n"
        "Follow the user's requested output structure closely when possible.\n"
        "Use only retrieved evidence for claims and cite chunk ids inline.\n"
        "Separate retrieved evidence about Sebastian from JD-based inference about the role.\n"
        "Label JD-only implications explicitly.\n"
        "If a gap is not directly evidenced, phrase it as not evidenced in the retrieved material.\n"
        "Be direct, hiring-manager oriented, and avoid recycling the default fit-analysis template."
      ),
    }

  if fit_analysis_hit:
    return {
      "id": "fit_analysis",
      "retrievalQuery": (
        f"{query} Sebastian Rosales Magnio CIC Actus Google Cloud Vertex AI "
        "agentic systems audit-safe analytics financial ERP deterministic-first "
        "RAG orchestration evaluation guardrails observability Firestore FastAPI Firebase"
      ),
      "preferredFocus": ["fit", "proof", "agentic", "operations"],
      "preferredChunkIds": list(FIT_ANALYSIS_PRIORITY_CHUNK_IDS),
      "preferredSources": list(FIT_ANALYSIS_PRIORITY_SOURCES),
      "instructions": (
        "This is a fit-evaluation request for Sebastian Rosales.\n"
        "Prefer resume and project evidence first, especially Magnio, CIC, Actus, and Vertex-related material.\n"
        "Use only retrieved evidence for claims.\n"
        "If a gap is not directly evidenced, phrase it as not evidenced in the retrieved material.\n"
        "The final answer should be executive, concise, and interview-ready."
      ),
    }

  if website_hit and (solo_service_hit or starting_hit):
    return {
      "id": "starter_site",
      "retrievalQuery": (
        f"{query} solo service business website booking intake proof testimonials pricing packages "
        "faq assistant follow-up messages payments version one"
      ),
      "preferredFocus": ["starter_site"],
      "instructions": (
        "This is a solo or small-service-business website question.\n"
        "Answer like a practical launch advisor for a founder, not like a transformation consultant.\n"
        "Prefer sections such as: best path, recommended stack, pages and funnel, first AI layer, what to postpone, and first 30 days.\n"
        "Name concrete tools when useful.\n"
        "Optimize for booked consultations, paid intro sessions, or captured leads.\n"
        "Recommend only one narrow AI layer after the site, booking flow, intake, and proof are in place."
      ),
    }

  if consulting_transition_hit and (side_practice_hit or starting_hit or solo_service_hit or professional_hit):
    return {
      "id": "career_transition",
      "retrievalQuery": (
        f"{query} consulting side business while employed fractional advisory retainer first clients "
        "offer design niche wedge non-solicit confidentiality transition trigger revenue pipeline "
        "salary replacement employer overlap"
      ),
      "preferredFocus": ["career_transition", "side_practice"],
      "instructions": (
        "This is a career-transition or consulting side-business question.\n"
        "Answer like an operator helping someone package existing expertise into a focused advisory offer while they still have a job.\n"
        "Focus on the consulting wedge, offer design, who to sell to first, employment and confidentiality guardrails, simple delivery model, and a transition trigger.\n"
        "Use role-specific examples when the role is obvious, such as lawyers, recruiters, fractional CFOs, or agency operators.\n"
        "Do not drift into generic website advice unless the user asked for a site."
      ),
    }

  if side_practice_hit or (professional_hit and solo_service_hit and starting_hit):
    return {
      "id": "side_practice",
      "retrievalQuery": (
        f"{query} side practice while employed day job employment agreement conflict of interest "
        "licensing firm registration niche offer validation evenings weekends transition trigger "
        "monthly revenue target separate employer resources credit background"
      ),
      "preferredFocus": ["side_practice"],
      "instructions": (
        "This is a side-practice question from someone keeping a job while starting a professional service business.\n"
        "Answer like a pragmatic operator helping them sequence the move safely.\n"
        "Focus on niche choice, compliance and employment guardrails, first clients, lean operating setup, and a transition trigger.\n"
        "Use website or tool recommendations only if they materially support the side-practice plan.\n"
        "Do not default into website-launch advice unless the user explicitly asks about the website."
      ),
    }

  return {
    "id": "default",
    "retrievalQuery": query,
    "preferredFocus": [],
    "instructions": (
      "Answer with grounded guidance and cite chunk ids inline.\n"
      "Use the default advisory structure only when it helps the user."
    ),
  }


ARENA_GROUNDED_PROFILE_IDS = {"fit_analysis", "opportunity_analysis"}


def _arena_grounding_bundle(query: str) -> dict[str, Any] | None:
  profile = _advisor_query_profile(query)
  if str(profile.get("id") or "").strip() not in ARENA_GROUNDED_PROFILE_IDS:
    return None

  retrieval = hybrid_search(
    profile["retrievalQuery"],
    limit=6,
    preferred_focus=profile.get("preferredFocus") or [],
    preferred_chunk_ids=profile.get("preferredChunkIds") or [],
    preferred_sources=profile.get("preferredSources") or [],
  )
  if not retrieval:
    return None

  allowed_citations = sorted(
    {
      str(item.get("id") or "").strip()
      for item in retrieval
      if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
  )
  if not allowed_citations:
    return None

  return {
    "profile": profile,
    "retrieval": retrieval,
    "retrievalItems": _serialize_retrieval_items(retrieval),
    "context": build_context(retrieval),
    "allowedCitations": allowed_citations,
  }


def _arena_grounding_rules(profile_id: str) -> list[str]:
  base_rules = [
    "- Use only the retrieved evidence for claims about Sebastian, Magnio, CIC, Actus, or related projects.",
    "- Cite only the exact allowed chunk ids inline, such as [K37].",
    "- Do not invent chunk ids, placeholder citations, or unsupported project details.",
    "- If the evidence does not support a claim, say 'not evidenced in retrieved material'.",
  ]

  if profile_id == "opportunity_analysis":
    return [
      *base_rules,
      "- Label role interpretation and job-description implications as '(JD inference)'.",
      "- Label compensation or market assumptions as '(Market/JD inference)'.",
      "- Do not attach chunk citations to inference-only claims.",
    ]

  return base_rules


def _arena_grounding_response_template(profile_id: str, *, judge: bool) -> str:
  if profile_id == "opportunity_analysis":
    if judge:
      return (
        "Preferred response format:\n"
        "1. Short verdict\n"
        "2. Opportunity scorecard\n"
        "3. Strongest evidence for fit\n"
        "4. Biggest gaps or mismatch risks\n"
        "5. Pursue / selective pursue / pass\n"
        "6. Final verdict\n"
        "Keep it concise, evidence-first, and under about 420 words when possible."
      )
    return (
      "Preferred candidate format:\n"
      "1. Short verdict\n"
      "2. Top 3 evidence-backed reasons\n"
      "3. Top 2 gaps or risks\n"
      "4. Final verdict\n"
      "Keep it concise and under about 260 words."
    )

  if judge:
    return (
      "Preferred response format:\n"
      "1. Overall fit\n"
      "2. Top 3 strengths\n"
      "3. Top 2 gaps\n"
      "4. 60-second interview answer\n"
      "Keep it concise and under about 320 words when possible."
    )
  return (
    "Preferred candidate format:\n"
    "1. Overall fit\n"
    "2. Top 3 strengths\n"
    "3. Top 2 gaps\n"
    "4. 60-second interview answer\n"
    "Keep it concise and under about 220 words."
  )


def _arena_compact_response_template(query: str, *, judge: bool) -> str:
  normalized_query = _normalize_query(query)
  words = len(query.split())
  lines = query.count("\n")
  strategy_patterns = [
    r"\boverall strategy\b",
    r"\bpositioning\b",
    r"\bclient acquisition\b",
    r"\brisk management\b",
    r"\btransition plan\b",
    r"\bmindset\b",
    r"\bconsulting\b",
    r"\bagency\b",
    r"\bfirst clients?\b",
    r"\bwhile still working\b",
    r"\bfull[- ]time job\b",
    r"\bparallel\b",
    r"\b90[- ]day\b",
    r"\bplan\b",
  ]
  strategy_score = sum(1 for pattern in strategy_patterns if re.search(pattern, normalized_query))
  is_long_strategy_prompt = strategy_score >= 3 or (words >= 120 and lines >= 4)
  if not is_long_strategy_prompt:
    return ""

  if judge:
    return (
      "Preferred response format:\n"
      "1. Short verdict\n"
      "2. Core strategy\n"
      "3. Top 3 moves\n"
      "4. Top 2 risks to avoid\n"
      "5. 90-day plan\n"
      "6. Final recommendation\n"
      "Rules:\n"
      "- Keep the full answer under about 450 words.\n"
      "- Use at most 2 bullets per section when bullets help.\n"
      "- Prioritize completeness over detail.\n"
      "- If the user's prompt asked for many sections, compress rather than expanding."
    )

  return (
    "Preferred candidate format:\n"
    "1. Short verdict\n"
    "2. Core strategy\n"
    "3. Top 2 moves\n"
    "4. Biggest risk\n"
    "5. Final recommendation\n"
    "Rules:\n"
    "- Keep the full answer under about 260 words.\n"
    "- Use short bullets or short paragraphs only.\n"
    "- Prioritize completeness over detail."
  )


def _build_arena_candidate_user_prompt(query: str, grounding: dict[str, Any] | None) -> str:
  compact_template = _arena_compact_response_template(query, judge=False)
  if not grounding:
    if compact_template:
      return f"{query}\n\n{compact_template}"
    return query

  profile = grounding["profile"]
  profile_id = str(profile.get("id") or "").strip()
  rules = _arena_grounding_rules(profile_id)
  return (
    f"User question:\n{query}\n\n"
    "Retrieved evidence:\n"
    f"{grounding['context']}\n\n"
    "Allowed chunk ids:\n"
    f"{', '.join(grounding['allowedCitations'])}\n\n"
    "Grounding rules:\n"
    + "\n".join(rules)
    + "\n\n"
    + _arena_grounding_response_template(profile_id, judge=False)
    + ("\n\n" + compact_template if compact_template else "")
    + "\n\nFollow the user's requested structure when possible."
  )


def _build_arena_judge_user_prompt(
  *,
  query: str,
  category: str,
  candidates: list[dict[str, Any]],
  grounding: dict[str, Any] | None,
) -> str:
  compact_template = _arena_compact_response_template(query, judge=True)
  prompt = (
    f"User question:\n{query}\n\n"
    f"OpenRouter category: {OPENROUTER_CATEGORY_LABELS.get(category, category.title())}\n\n"
  )
  if grounding:
    profile = grounding["profile"]
    profile_id = str(profile.get("id") or "").strip()
    prompt += (
      "Retrieved evidence:\n"
      f"{grounding['context']}\n\n"
      "Allowed chunk ids:\n"
      f"{', '.join(grounding['allowedCitations'])}\n\n"
      "Grounding rules:\n"
      + "\n".join(_arena_grounding_rules(profile_id))
      + "\n\n"
      + _arena_grounding_response_template(profile_id, judge=True)
      + "\n\n"
    )
  if compact_template:
    prompt += compact_template + "\n\n"
  prompt += "Candidate answers:\n\n" + "\n\n---\n\n".join(_judge_candidate_blocks(candidates))
  return prompt


def _judge_system_prompt(category: str) -> str:
  base = (
    "You are the judge model for Magnio Arena.\n"
    "Evaluate each candidate on a 1-10 scale for usefulness, groundedness, clarity, and decisiveness.\n"
    "Groundedness rewards accurate scoping, explicit assumptions, and low hallucination risk.\n"
    "Pick one winning model id, explain why, and write a final synthesis answer for the user.\n"
    "Return exactly two blocks in this order:\n"
    "<JUDGE_JSON>\n"
    "{...valid JSON...}\n"
    "</JUDGE_JSON>\n"
    "<SYNTHESIS>\n"
    "...markdown answer...\n"
    "</SYNTHESIS>\n"
    "Do not include the synthesis inside the JSON block.\n"
    "JSON schema:\n"
    "{\n"
    '  "winnerModelId": "model-id",\n'
    '  "confidence": "low|medium|high",\n'
    '  "rationale": "short explanation",\n'
    '  "scores": [\n'
    "    {\n"
    '      "modelId": "model-id",\n'
    '      "usefulness": 1,\n'
    '      "groundedness": 1,\n'
    '      "clarity": 1,\n'
    '      "decisiveness": 1,\n'
    '      "notes": "short explanation"\n'
    "    }\n"
    "  ]\n"
    "}"
  )
  if category != "dating":
    return base

  return (
    base
    + "\n"
    + "For Dating & Social prompts, strongly prefer candidates that remain respectful, avoid fetishization or manipulation, and redirect toward compatibility-based guidance without becoming preachy or refusing benign advice."
  )


def _judge_system_prompt_structured(category: str) -> str:
  base = (
    "You are the judge model for Magnio Arena.\n"
    "Evaluate each candidate on a 1-10 scale for usefulness, groundedness, clarity, and decisiveness.\n"
    "Groundedness rewards accurate scoping, explicit assumptions, and low hallucination risk.\n"
    "Pick one winning model id, explain why, and write a final synthesis answer for the user.\n"
    "Return JSON only. Do not wrap the JSON in markdown or code fences.\n"
    "The synthesis field must contain the full final markdown answer for the user."
  )
  if category != "dating":
    return base

  return (
    base
    + "\n"
    + "For Dating & Social prompts, strongly prefer candidates that remain respectful, avoid fetishization or manipulation, and redirect toward compatibility-based guidance without becoming preachy or refusing benign advice."
  )


def _dating_guardrail_notes(query: str) -> list[str]:
  normalized_query = _normalize_query(query)
  notes: list[str] = []

  if any(
    re.search(pattern, normalized_query)
    for pattern in [
      r"\bblond(e)?\b",
      r"\bskinny\b",
      r"\btall\b",
      r"\bshort\b",
      r"\bbody type\b",
      r"\basian\b",
      r"\blatina?\b",
      r"\bwhite girls?\b",
      r"\bblack girls?\b",
      r"\bscandinavian\b",
      r"\bbaltic\b",
    ]
  ):
    notes.append("Applied respectful dating guardrail because the prompt focused on demographic or body-type targeting.")

  if any(
    re.search(pattern, normalized_query)
    for pattern in [
      r"\bmanipulat",
      r"\bpickup\b",
      r"\bseduc",
      r"\bconvince her\b",
      r"\bmake (her|them) want\b",
      r"\bbody count\b",
      r"\bscore\b",
      r"\bget laid\b",
    ]
  ):
    notes.append("Applied non-coercion dating guardrail because the prompt suggested manipulative or exploitative framing.")

  return notes


def _choose_ranked_models(
  category: str,
  *,
  arena_size: int,
  grounding: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
  grounded_profile_id = str((grounding or {}).get("profile", {}).get("id") or "").strip()
  if grounded_profile_id in ARENA_GROUNDED_PROFILE_IDS:
    fallback_models = DEFAULT_CATEGORY_MODELS.get(category) or DEFAULT_CATEGORY_MODELS["technology"]
    return [
      {
        "id": model_id,
        "name": model_id,
        "provider": model_id.split("/", 1)[0],
      }
      for model_id in fallback_models[:arena_size]
    ]

  file_ranked_models = get_ranked_models_for_category(category)
  if file_ranked_models:
    return [
      {
        "id": item["id"],
        "name": str(item.get("name") or item["id"]),
        "provider": str(item.get("provider") or item["id"].split("/", 1)[0]),
      }
      for item in file_ranked_models[:arena_size]
    ]

  chosen: list[dict[str, str]] = []
  ranking_category = category if category in OPENROUTER_RANKING_CATEGORIES else None

  # For Magnio-only categories without a native OpenRouter ranking bucket,
  # prefer a curated stable pool instead of the general models list.
  if ranking_category is None:
    fallback_models = DEFAULT_CATEGORY_MODELS.get(category) or DEFAULT_CATEGORY_MODELS["technology"]
    return [
      {
        "id": model_id,
        "name": model_id,
        "provider": model_id.split("/", 1)[0],
      }
      for model_id in fallback_models[:arena_size]
    ]

  try:
    ranked_models = list_models(ranking_category)
  except Exception:
    ranked_models = []

  seen_providers: set[str] = set()
  for item in ranked_models:
    model_id = str(item.get("id") or "").strip()
    if not model_id or ":free" in model_id:
      continue

    provider = model_id.split("/", 1)[0]
    if provider in seen_providers:
      continue

    chosen.append(
      {
        "id": model_id,
        "name": str(item.get("name") or model_id),
        "provider": provider,
      }
    )
    seen_providers.add(provider)

    if len(chosen) >= arena_size:
      return chosen

  fallback_models = DEFAULT_CATEGORY_MODELS.get(category) or DEFAULT_CATEGORY_MODELS["technology"]
  for model_id in fallback_models:
    provider = model_id.split("/", 1)[0]
    if any(item["id"] == model_id for item in chosen):
      continue
    chosen.append(
      {
        "id": model_id,
        "name": model_id,
        "provider": provider,
      }
    )
    if len(chosen) >= arena_size:
      break

  return chosen[:arena_size]


def _fallback_models_for_category(category: str, *, arena_size: int, exclude: set[str] | None = None) -> list[dict[str, str]]:
  excluded = exclude or set()
  fallback_models = DEFAULT_CATEGORY_MODELS.get(category) or DEFAULT_CATEGORY_MODELS["technology"]
  chosen: list[dict[str, str]] = []

  for model_id in fallback_models:
    if model_id in excluded:
      continue
    chosen.append(
      {
        "id": model_id,
        "name": model_id,
        "provider": model_id.split("/", 1)[0],
      }
    )
    if len(chosen) >= arena_size:
      break

  return chosen


def _clip_for_judge(text: str, *, max_chars: int = 3200) -> str:
  clean = text.strip()
  if len(clean) <= max_chars:
    return clean
  return clean[: max_chars - 3].rstrip() + "..."


def _extract_json(text: str) -> dict[str, Any]:
  cleaned = text.strip()
  if cleaned.startswith("```"):
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

  try:
    return json.loads(cleaned)
  except json.JSONDecodeError:
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
      raise
    return json.loads(match.group(0))


def _json_repair_system_prompt() -> str:
  return (
    "You repair malformed JSON.\n"
    "Return valid JSON only.\n"
    "Preserve the original keys, values, and wording whenever possible.\n"
    "If the source is truncated, complete the structure conservatively without inventing new sections."
  )


def _repair_json_with_model(raw_text: str, *, model: str) -> dict[str, Any]:
  payload = chat_completion(
    model=model,
    messages=[
      {
        "role": "system",
        "content": _json_repair_system_prompt(),
      },
      {
        "role": "user",
        "content": raw_text,
      },
    ],
    temperature=0,
    max_tokens=1800,
    provider=FAST_PROVIDER_PREF,
  )
  return _extract_json(extract_message_text(payload))


def _run_structured_json_completion(
  *,
  provider: Literal["openrouter", "vertex"],
  model: str,
  system_prompt: str,
  user_prompt: str,
  max_tokens: int,
  response_schema: dict[str, Any],
) -> dict[str, Any]:
  if provider == "vertex":
    payload = vertex_generate_content(
      model=model,
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
      ],
      temperature=0,
      max_tokens=max_tokens,
      response_mime_type="application/json",
      response_json_schema=response_schema,
    )
    try:
      return vertex_extract_json(payload)
    except RuntimeError:
      raw_text = str(payload.get("text") or "").strip()
      if not raw_text:
        raise RuntimeError("Vertex AI returned an empty structured response.")
      try:
        return _extract_json(raw_text)
      except json.JSONDecodeError:
        repair_payload = vertex_generate_content(
          model=model,
          messages=[
            {"role": "system", "content": _json_repair_system_prompt()},
            {"role": "user", "content": raw_text},
          ],
          temperature=0,
          max_tokens=max_tokens,
          response_mime_type="application/json",
          response_json_schema=response_schema,
        )
        try:
          return vertex_extract_json(repair_payload)
        except RuntimeError:
          return _extract_json(str(repair_payload.get("text") or "").strip())

  try:
    payload = chat_completion(
      model=model,
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
      ],
      temperature=0,
      max_tokens=max_tokens,
      provider=FAST_PROVIDER_PREF,
      response_format={
        "type": "json_schema",
        "json_schema": {
          "name": "magnio_structured_response",
          "strict": True,
          "schema": response_schema,
        },
      },
      plugins=[{"id": "response-healing"}],
    )
  except RuntimeError:
    payload = chat_completion(
      model=model,
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
      ],
      temperature=0,
      max_tokens=max_tokens,
      provider=FAST_PROVIDER_PREF,
    )
  content = extract_message_text(payload)
  try:
    return _extract_json(content)
  except json.JSONDecodeError:
    return _repair_json_with_model(content, model=model)


def _extract_tagged_block(text: str, tag: str) -> str | None:
  match = re.search(fr"<{tag}>\s*(.*?)\s*</{tag}>", text, re.DOTALL | re.IGNORECASE)
  if not match:
    return None
  return match.group(1).strip()


def _extract_judge_payload(text: str, *, model: str) -> dict[str, Any]:
  json_block = _extract_tagged_block(text, "JUDGE_JSON")
  synthesis_block = _extract_tagged_block(text, "SYNTHESIS")

  source = json_block or text
  try:
    parsed = _extract_json(source)
  except json.JSONDecodeError:
    parsed = _repair_json_with_model(source, model=model)

  if synthesis_block:
    parsed["synthesis"] = synthesis_block

  return parsed


def _fallback_supported_facts(retrieval: list[dict[str, Any]]) -> list[dict[str, Any]]:
  facts: list[dict[str, Any]] = []
  for item in retrieval[:6]:
    if not isinstance(item, dict):
      continue
    fact_text = str(item.get("title") or "").strip()
    citation = str(item.get("id") or "").strip()
    if not fact_text or not citation:
      continue
    facts.append({"text": fact_text, "citations": [citation]})
  return facts


def _fallback_fit_analysis_structured_answer(retrieval: list[dict[str, Any]]) -> dict[str, Any]:
  retrieval_by_id = {
    str(item.get("id") or "").strip(): item
    for item in retrieval
    if isinstance(item, dict) and str(item.get("id") or "").strip()
  }

  def has(chunk_id: str) -> bool:
    return chunk_id in retrieval_by_id

  def item(text: str, citations: list[str]) -> dict[str, Any]:
    return {"text": text, "citations": [citation for citation in citations if has(citation)]}

  strengths: list[dict[str, Any]] = []
  if has("K39"):
    strengths.append(
      item(
        "Audit-safe analytics over financial and ERP data, using deterministic-first design and RAG-grounded reasoning.",
        ["K39"],
      )
    )
  if has("K38"):
    strengths.append(
      item(
        "Multi-model orchestration, parallel evaluation, and judge-based synthesis are demonstrated in Magnio.",
        ["K38"],
      )
    )
  if has("K43"):
    strengths.append(
      item(
        "Magnio includes a Google-native Vertex AI path for grounded advisory flows and evaluation while keeping provider choice reversible.",
        ["K43"],
      )
    )
  if len(strengths) < 3 and has("K37"):
    strengths.append(
      item(
        "Sebastian's documented profile centers on production-grade agentic workflows, LLM orchestration, and end-to-end delivery.",
        ["K37"],
      )
    )
  if len(strengths) < 3 and has("K44"):
    strengths.append(
      item(
        "The architectural through-line is reliable AI systems with guardrails, deterministic logic, and ambiguity handling.",
        ["K44"],
      )
    )

  gaps = [
    item(
      "Depth in native GCP data services beyond Firebase and Firestore is not evidenced in retrieved material.",
      [citation for citation in ["K41", "K43"] if has(citation)] or [citation for citation in ["K37", "K38"] if has(citation)],
    ),
    item(
      "Large-scale Vertex-native training or MLOps pipelines are not evidenced in retrieved material.",
      [citation for citation in ["K43", "K37"] if has(citation)] or [citation for citation in retrieval_by_id.keys()][:1],
    ),
  ]

  interview_citations = [citation for citation in ["K38", "K39", "K43"] if has(citation)] or [citation for citation in ["K37"] if has(citation)]
  interview_text = (
    "I’ve built production AI systems that combine RAG, orchestration, and validation to solve real workflows. "
    "In finance-adjacent systems work, I used deterministic and RAG-grounded analytics over financial and ERP data to keep outputs audit-safe. "
    "In Magnio, I built multi-model routing and evaluation, and I added a Vertex AI path for grounded advisory flows and judging. "
    "My focus is building reliable systems that improve decisions in production, not just demos."
  )

  structured = {
    "overall_fit": (
      "Strong fit. Sebastian demonstrates direct experience building production-grade agentic systems on Google Cloud, "
      "including RAG, orchestration, evaluation, and audit-safe analytics [K37][K38][K39][K43]."
    ),
    "strengths": [entry for entry in strengths if entry["citations"]][:3],
    "gaps": [entry for entry in gaps if entry["citations"]][:2],
    "interview_answer": {
      "text": interview_text,
      "citations": interview_citations,
    },
    "extracted_facts": _fallback_supported_facts(retrieval),
  }
  structured["rendered"] = _render_structured_fit_answer(structured)
  structured["renderedWordCount"] = _word_count_text(structured["rendered"])
  return structured


def _fallback_opportunity_analysis_structured_answer(query: str, retrieval: list[dict[str, Any]]) -> dict[str, Any]:
  retrieval_by_id = {
    str(item.get("id") or "").strip(): item
    for item in retrieval
    if isinstance(item, dict) and str(item.get("id") or "").strip()
  }
  normalized_query = _normalize_query(query)

  def has(chunk_id: str) -> bool:
    return chunk_id in retrieval_by_id

  def evidence_item(text: str, citations: list[str]) -> dict[str, Any]:
    return {
      "text": text,
      "citations": [citation for citation in citations if has(citation)],
    }

  def scorecard_item(
    dimension: str,
    score: str,
    evidence_text: str,
    citations: list[str],
    inference_text: str,
  ) -> dict[str, Any]:
    return {
      "dimension": dimension,
      "score": score,
      "evidence_text": evidence_text,
      "evidence_citations": [citation for citation in citations if has(citation)],
      "inference_text": inference_text,
    }

  def risk_item(text: str, citations: list[str], inference_text: str) -> dict[str, Any]:
    return {
      "text": text,
      "citations": [citation for citation in citations if has(citation)],
      "inference_text": inference_text,
    }

  kg_role = any(term in normalized_query for term in ["knowledge graph", "neo4j", "neptune", "cypher", "graph-rag"])
  university_role = any(term in normalized_query for term in ["university", "higher education", "academic", "committee"])

  overall = evidence_item(
    (
      "Sebastian is a strong production AI systems candidate with clear evidence in RAG, orchestration, "
      "guardrails, and measurable delivery, but role-specific specialist depth still depends on the job's hard requirements."
    ),
    [citation for citation in ["K37", "K38", "K39", "K44", "K43"] if has(citation)],
  )

  scorecard: list[dict[str, Any]] = [
    scorecard_item(
      "Technical fit",
      "Strong core / partial specialization fit" if kg_role else "Strong",
      "Sebastian has documented production RAG, orchestration, deterministic validation, and audit-safe analytics.",
      [citation for citation in ["K39", "K38", "K44"] if has(citation)],
      (
        "(JD inference) The core technical risk is any mandatory specialization that is not shown in the retrieved material."
      ),
    ),
    scorecard_item(
      "Career leverage",
      "High",
      "His documented pattern is end-to-end ownership of production systems with measurable operational outcomes.",
      [citation for citation in ["K39", "K44", "K37"] if has(citation)],
      "(JD inference) The role is valuable if it expands production scope rather than narrowing him into coordination work.",
    ),
    scorecard_item(
      "Ownership / impact",
      "High",
      "Sebastian has evidence of architecting, delivering, and operationalizing systems rather than only advising on them.",
      [citation for citation in ["K37", "K39", "K41"] if has(citation)],
      "(JD inference) Clarify whether the job still gives builder-level ownership once enterprise process is factored in.",
    ),
    scorecard_item(
      "Growth potential",
      "Moderate to high",
      "His documented work shows a repeatable pattern of ramping into complex domains through reliable system design.",
      [citation for citation in ["K44", "K37", "K38"] if has(citation)],
      "(JD inference) Growth is strongest when the role deepens an adjacent capability rather than replacing builder work with governance.",
    ),
    scorecard_item(
      "Risk",
      "High" if kg_role or university_role else "Moderate",
      "The retrieved material is strong on production AI systems but does not prove every possible domain-specific requirement.",
      [citation for citation in ["K37", "K41", "K44"] if has(citation)],
      (
        "(JD inference) Any hard requirement centered on a specialty stack or bureaucracy-heavy operating model becomes the main interview risk."
      ),
    ),
  ]
  if has("K39"):
    scorecard.append(
      scorecard_item(
        "Compensation fit",
        "Requires validation",
        "Sebastian's retrieved evidence shows high-impact production work, but it does not include explicit compensation expectations.",
        [citation for citation in ["K39", "K37"] if has(citation)],
        "(Market/JD inference) Compensation fit depends on the actual band, equity mix, and location demands in the role.",
      )
    )

  strongest_evidence = [
    evidence_item(
      (
        "Actus demonstrates an end-to-end copilot product with contextual follow-up suggestions, visible orchestration, and multi-step workflows over hybrid RAG."
        if has("K45") or has("K46")
        else (
          "Actus demonstrates hybrid RAG, deterministic routing, and multi-step workflows for high-stakes financial decision support."
          if has("K40")
          else "Finance-adjacent production systems demonstrate deterministic validation and RAG-grounded decision support."
        )
      ),
      [citation for citation in ["K40", "K45", "K46"] if has(citation)] or [citation for citation in ["K39"] if has(citation)],
    ),
    evidence_item(
      "Magnio demonstrates multi-model routing, grounded retrieval, evaluation, and judge-based synthesis in production.",
      [citation for citation in ["K38", "K43"] if has(citation)],
    ),
    evidence_item(
      "The architectural through-line across the projects is reliable AI systems with guardrails and ambiguity handling.",
      [citation for citation in ["K44", "K37"] if has(citation)],
    ),
  ]

  gaps_or_risks = [
    risk_item(
      "Role-specific specialist tooling or domain depth beyond the documented stack is not evidenced in retrieved material.",
      [citation for citation in ["K37", "K41"] if has(citation)],
      (
        "(JD inference) If the role treats that specialization as the architectural spine, this becomes a real screening risk rather than a trainable edge."
      ),
    ),
    risk_item(
      "Exact compensation targets, relocation preferences, and enterprise-client appetite are not evidenced in retrieved material.",
      [citation for citation in ["K37"] if has(citation)] or [citation for citation in ["K41"] if has(citation)],
      "(Market/JD inference) Those factors can change whether a technically credible role is actually worth pursuing.",
    ),
  ]
  if kg_role:
    gaps_or_risks.insert(
      0,
      risk_item(
        "Knowledge-graph-native tools and ontology design are not evidenced in retrieved material.",
        [citation for citation in ["K37", "K41"] if has(citation)] or [citation for citation in ["K38"] if has(citation)],
        "(JD inference) If Graph-RAG is the centerpiece rather than an adjacent capability, the role is only a selective pursue.",
      ),
    )
  gaps_or_risks = [item for item in gaps_or_risks if item["citations"]][:3]

  role_reality_check = {
    "text": (
      "Retrieved evidence supports Sebastian as a production builder across RAG, orchestration, evaluation, and reliable system delivery."
    ),
    "citations": [citation for citation in ["K38", "K39", "K44", "K37"] if has(citation)],
    "inference_text": (
      "(JD inference) The opportunity is strongest when it needs a builder-architect and weaker when it centers on a specialist stack not shown in the retrieved material."
    ),
  }

  decision = "Selective pursue"
  if university_role:
    decision = "Pass"
  pursuit_decision = {
    "decision": decision,
    "text": (
      "Pursue only if the interview confirms the team needs a production AI builder with room to ramp into the missing specialization, not a finished niche specialist on day one."
      if decision == "Selective pursue"
      else "Pass unless the role is substantially more builder-oriented than the job description suggests."
    ),
    "citations": [citation for citation in ["K37", "K39", "K44"] if has(citation)] or [citation for citation in retrieval_by_id.keys()][:1],
  }

  positioning_strategy = evidence_item(
    (
      "Lead with production RAG, orchestration, deterministic validation, and measurable operational results. "
      "Frame any missing specialist domain as an adjacent ramp, and avoid implying depth that is not documented."
    ),
    [citation for citation in ["K39", "K38", "K44", "K37"] if has(citation)],
  )

  structured = {
    "overall_fit": overall,
    "scorecard": [item for item in scorecard if item["evidence_citations"]][:6],
    "strongest_evidence": [item for item in strongest_evidence if item["citations"]][:4],
    "gaps_or_risks": gaps_or_risks[:3],
    "role_reality_check": role_reality_check,
    "pursuit_decision": pursuit_decision,
    "positioning_strategy": positioning_strategy,
    "do_not_overclaim": [
      "Do not claim specialist tooling, domain depth, or deployments that are not in the retrieved material.",
      "Do not blur JD interpretation with evidence from Sebastian's documented work.",
      "Do not present compensation assumptions as facts.",
    ],
    "extracted_facts": _fallback_supported_facts(retrieval),
  }
  if university_role:
    structured["signal_analysis"] = (
      "(JD inference) The role reads as governance-heavy and likely slower-moving than Sebastian's documented builder environments."
    )
  if kg_role:
    structured["hire_signal"] = (
      "(JD inference) Hire or lean-hire only if the team treats knowledge-graph depth as rampable; otherwise the gap is likely disqualifying."
    )
  structured["final_verdict"] = (
    "Final verdict: Selective pursue — strong production GenAI fit, but the role-specific specialization needs to be negotiable."
    if decision == "Selective pursue"
    else "Final verdict: Pass — the role looks too specialized or governance-heavy relative to the documented builder profile."
  )
  return _compact_structured_opportunity_payload(structured)


def _structured_fit_answer_complete(payload: dict[str, Any]) -> bool:
  overall_fit = str(payload.get("overall_fit") or "").strip()
  strengths = payload.get("strengths") or []
  gaps = payload.get("gaps") or []
  interview_answer = _coerce_structured_object(payload.get("interview_answer"))
  interview_text = str(interview_answer.get("text") or "").strip()

  if not overall_fit or overall_fit.endswith("["):
    return False
  if len(strengths) < 3 or len(gaps) < 2:
    return False
  if not interview_text or interview_text.endswith("["):
    return False
  return True


def _structured_opportunity_answer_complete(payload: dict[str, Any]) -> bool:
  overall_fit = _coerce_structured_object(payload.get("overall_fit"))
  scorecard = payload.get("scorecard") or []
  strongest_evidence = payload.get("strongest_evidence") or []
  gaps_or_risks = payload.get("gaps_or_risks") or []
  role_reality_check = _coerce_structured_object(payload.get("role_reality_check"))
  pursuit_decision = _coerce_structured_object(payload.get("pursuit_decision"))
  positioning_strategy = _coerce_structured_object(payload.get("positioning_strategy"))
  final_verdict = str(payload.get("final_verdict") or "").strip()

  if not str(overall_fit.get("text") or "").strip():
    return False
  if len(scorecard) < 5 or len(strongest_evidence) < 2 or len(gaps_or_risks) < 2:
    return False
  if not str(role_reality_check.get("text") or "").strip():
    return False
  if not str(pursuit_decision.get("decision") or "").strip() or not str(pursuit_decision.get("text") or "").strip():
    return False
  if not str(positioning_strategy.get("text") or "").strip():
    return False
  if not final_verdict.startswith("Final verdict: "):
    return False
  return True


def _extract_supported_facts(
  *,
  query: str,
  retrieval: list[dict[str, Any]],
  provider: Literal["openrouter", "vertex"],
  model: str,
) -> list[dict[str, Any]]:
  allowed_citations = {
    str(item.get("id") or "").strip()
    for item in retrieval
    if isinstance(item, dict) and str(item.get("id") or "").strip()
  }
  if not allowed_citations:
    return []

  user_prompt = (
    f"User task:\n{query}\n\n"
    "Retrieved chunks:\n"
    f"{build_context(retrieval)}\n\n"
    "Extract 5 to 8 concise supported facts that are directly relevant to the user's task.\n"
    "Each fact must cite one or more chunk ids from the retrieved chunks only."
  )
  payload = _run_structured_json_completion(
    provider=provider,
    model=model,
    system_prompt=_advisor_fact_extraction_system_prompt(),
    user_prompt=user_prompt,
    max_tokens=1200,
    response_schema=ADVISOR_FACT_EXTRACTION_SCHEMA,
  )
  payload = _coerce_structured_object(payload, list_key="facts")

  normalized: list[dict[str, Any]] = []
  for item in payload.get("facts") or []:
    parsed = _normalize_structured_item(
      item,
      allowed_citations=allowed_citations,
      require_citations=True,
    )
    if parsed is not None:
      normalized.append(parsed)

  return normalized or _fallback_supported_facts(retrieval)


def _run_structured_fit_analysis(
  *,
  query: str,
  retrieval: list[dict[str, Any]],
  provider: Literal["openrouter", "vertex"],
  model: str,
) -> dict[str, Any]:
  extracted_facts = _extract_supported_facts(
    query=query,
    retrieval=retrieval,
    provider=provider,
    model=model,
  )
  allowed_citations = {
    str(item.get("id") or "").strip()
    for item in retrieval
    if isinstance(item, dict) and str(item.get("id") or "").strip()
  }

  synthesis_prompt = (
    f"User task:\n{query}\n\n"
    "Retrieved chunk ids allowed for citation:\n"
    f"{', '.join(sorted(allowed_citations))}\n\n"
    "Extracted supported facts:\n"
    f"{json.dumps(extracted_facts, ensure_ascii=True, indent=2)}\n\n"
    "Return a structured fit evaluation.\n"
    "Rules:\n"
    "- overall_fit must be one sentence and may include inline chunk-id citations.\n"
    "- strengths must contain exactly 3 items unless evidence is insufficient.\n"
    "- gaps must contain exactly 2 items unless evidence is insufficient.\n"
    "- Every strength and gap must cite at least one allowed chunk id.\n"
    "- If a gap is not explicit in the facts, phrase it as 'not evidenced in retrieved material'.\n"
    "- Avoid duplicate strengths.\n"
    "- interview_answer must be 90 to 110 words, spoken, concise, and natural.\n"
    "- Keep the rendered output under 1000 words total.\n"
    "- Do not cite chunk ids that are not listed above."
  )
  payload = _run_structured_json_completion(
    provider=provider,
    model=model,
    system_prompt=_advisor_fit_synthesis_system_prompt(),
    user_prompt=synthesis_prompt,
    max_tokens=1400,
    response_schema=ADVISOR_FIT_RESPONSE_SCHEMA,
  )
  payload = _coerce_structured_object(payload)

  strengths: list[dict[str, Any]] = []
  for item in payload.get("strengths") or []:
    parsed = _normalize_structured_item(
      item,
      allowed_citations=allowed_citations,
      require_citations=True,
    )
    if parsed is not None and all(existing["text"] != parsed["text"] for existing in strengths):
      strengths.append(parsed)

  gaps: list[dict[str, Any]] = []
  for item in payload.get("gaps") or []:
    parsed = _normalize_structured_item(
      item,
      allowed_citations=allowed_citations,
      require_citations=True,
    )
    if parsed is not None and all(existing["text"] != parsed["text"] for existing in gaps):
      gaps.append(parsed)

  interview_answer = _normalize_structured_item(
    _coerce_structured_object(payload.get("interview_answer")),
    allowed_citations=allowed_citations,
    require_citations=True,
  ) or {"text": "", "citations": []}

  overall_fit = str(payload.get("overall_fit") or "").strip()
  structured = {
    "overall_fit": overall_fit,
    "strengths": strengths[:3],
    "gaps": gaps[:2],
    "interview_answer": interview_answer,
    "extracted_facts": extracted_facts,
  }
  structured["rendered"] = _render_structured_fit_answer(structured)
  structured["renderedWordCount"] = _word_count_text(structured["rendered"])
  if not _structured_fit_answer_complete(structured):
    return _fallback_fit_analysis_structured_answer(retrieval)
  return structured


def _run_structured_opportunity_analysis(
  *,
  query: str,
  retrieval: list[dict[str, Any]],
  provider: Literal["openrouter", "vertex"],
  model: str,
) -> dict[str, Any]:
  extracted_facts = _extract_supported_facts(
    query=query,
    retrieval=retrieval,
    provider=provider,
    model=model,
  )
  allowed_citations = {
    str(item.get("id") or "").strip()
    for item in retrieval
    if isinstance(item, dict) and str(item.get("id") or "").strip()
  }

  synthesis_prompt = (
    f"User task:\n{query}\n\n"
    "Retrieved chunk ids allowed for citation:\n"
    f"{', '.join(sorted(allowed_citations))}\n\n"
    "Extracted supported facts:\n"
    f"{json.dumps(extracted_facts, ensure_ascii=True, indent=2)}\n\n"
    "Return a structured opportunity evaluation.\n"
    "Rules:\n"
    "- overall_fit.text must be one or two sentences and evidence-backed.\n"
    "- overall_fit.citations must use only allowed chunk ids.\n"
    "- scorecard must contain 5 or 6 items and should use the dimensions requested by the user when present.\n"
    "- Every scorecard item must have evidence_text plus evidence_citations for Sebastian evidence.\n"
    "- Every scorecard item must have inference_text that starts with '(JD inference)' or '(Market/JD inference)'.\n"
    "- strongest_evidence must contain 2 to 4 non-duplicative items with citations.\n"
    "- gaps_or_risks must contain 2 or 3 items. Each item must cite Sebastian evidence and separate the role risk into inference_text.\n"
    "- role_reality_check must separate Sebastian evidence from JD inference.\n"
    "- pursuit_decision.decision must be Strong pursue, Selective pursue, or Pass.\n"
    "- pursuit_decision.text must be concise and evidence-backed; pursuit_decision.citations must use only allowed chunk ids.\n"
    "- positioning_strategy must sound spoken, concise, and natural, and stay under 70 words.\n"
    "- Keep the rendered answer under 900 words total.\n"
    "- Keep scorecard evidence_text and inference_text to one short sentence each.\n"
    "- Keep strongest_evidence and gaps_or_risks short and non-duplicative.\n"
    "- If the user explicitly asked for legitimacy/signal analysis, role decomposition, strategic value, hire signal, or lead temperature, populate those optional fields.\n"
    "- do_not_overclaim should contain 2 to 4 short bullets with no citations.\n"
    "- final_verdict must start exactly with 'Final verdict: '.\n"
    "- Do not cite chunk ids that are not listed above.\n"
    "- Never attach chunk citations to inference-only claims."
  )
  payload = _run_structured_json_completion(
    provider=provider,
    model=model,
    system_prompt=_advisor_opportunity_synthesis_system_prompt(),
    user_prompt=synthesis_prompt,
    max_tokens=2400,
    response_schema=ADVISOR_OPPORTUNITY_RESPONSE_SCHEMA,
  )
  payload = _coerce_structured_object(payload)

  overall_fit = _normalize_structured_item(
    _coerce_structured_object(payload.get("overall_fit")),
    allowed_citations=allowed_citations,
    require_citations=True,
  ) or {"text": "", "citations": []}

  scorecard: list[dict[str, Any]] = []
  for item in payload.get("scorecard") or []:
    parsed = _normalize_structured_scorecard_item(item, allowed_citations=allowed_citations)
    if parsed is not None and all(existing["dimension"] != parsed["dimension"] for existing in scorecard):
      scorecard.append(parsed)

  strongest_evidence: list[dict[str, Any]] = []
  for item in payload.get("strongest_evidence") or []:
    parsed = _normalize_structured_item(
      item,
      allowed_citations=allowed_citations,
      require_citations=True,
    )
    if parsed is not None and all(existing["text"] != parsed["text"] for existing in strongest_evidence):
      strongest_evidence.append(parsed)

  gaps_or_risks: list[dict[str, Any]] = []
  for item in payload.get("gaps_or_risks") or []:
    parsed = _normalize_structured_risk_item(item, allowed_citations=allowed_citations)
    if parsed is not None and all(existing["text"] != parsed["text"] for existing in gaps_or_risks):
      gaps_or_risks.append(parsed)

  role_reality_check = _normalize_structured_risk_item(
    _coerce_structured_object(payload.get("role_reality_check")),
    allowed_citations=allowed_citations,
  ) or {"text": "", "citations": [], "inference_text": ""}

  pursuit_decision = _coerce_structured_object(payload.get("pursuit_decision"))
  pursuit_decision_text = str(pursuit_decision.get("text") or "").strip()
  normalized_pursuit = _normalize_structured_item(
    {"text": pursuit_decision_text, "citations": pursuit_decision.get("citations") or []},
    allowed_citations=allowed_citations,
    require_citations=True,
  ) or {"text": "", "citations": []}
  normalized_pursuit["decision"] = str(pursuit_decision.get("decision") or "").strip()

  positioning_strategy = _normalize_structured_item(
    _coerce_structured_object(payload.get("positioning_strategy")),
    allowed_citations=allowed_citations,
    require_citations=True,
  ) or {"text": "", "citations": []}

  do_not_overclaim = [
    str(item).strip()
    for item in payload.get("do_not_overclaim") or []
    if str(item).strip()
  ][:4]

  structured = {
    "overall_fit": overall_fit,
    "scorecard": scorecard[:6],
    "strongest_evidence": strongest_evidence[:4],
    "gaps_or_risks": gaps_or_risks[:3],
    "role_reality_check": role_reality_check,
    "pursuit_decision": normalized_pursuit,
    "positioning_strategy": positioning_strategy,
    "do_not_overclaim": do_not_overclaim,
    "final_verdict": str(payload.get("final_verdict") or "").strip(),
    "extracted_facts": extracted_facts,
  }

  for optional_key in (
    "signal_analysis",
    "role_decomposition",
    "strategic_value",
    "hire_signal",
    "temperature_classification",
  ):
    value = str(payload.get(optional_key) or "").strip()
    if value:
      structured[optional_key] = value

  structured = _compact_structured_opportunity_payload(structured)
  if not _structured_opportunity_answer_complete(structured):
    return _fallback_opportunity_analysis_structured_answer(query, retrieval)
  return structured


def _fallback_judge(candidates: list[dict[str, Any]]) -> dict[str, Any]:
  winner = candidates[0]
  scores = []
  for index, candidate in enumerate(candidates):
    base = 8 if index == 0 else 7
    scores.append(
      {
        "modelId": candidate["modelId"],
        "usefulness": base,
        "groundedness": base,
        "clarity": base,
        "decisiveness": base,
        "notes": "Fallback selection used because the judge response was unavailable.",
      }
    )

  return {
    "winnerModelId": winner["modelId"],
    "confidence": "low",
    "rationale": "Judge fallback used. Returning the highest-ranked successful candidate.",
    "scores": scores,
    "synthesis": winner["content"],
  }


def _run_candidate(
  model: dict[str, str],
  query: str,
  category: str,
  grounding: dict[str, Any] | None = None,
) -> dict[str, Any]:
  started = time.perf_counter()
  try:
    payload = chat_completion(
      model=model["id"],
      messages=[
        {"role": "system", "content": _arena_system_prompt(category, grounded=grounding is not None)},
        {"role": "user", "content": _build_arena_candidate_user_prompt(query, grounding)},
      ],
      temperature=0.35,
      max_tokens=1400,
      provider=FAST_PROVIDER_PREF,
    )
    content = extract_message_text(payload)
    if not content:
      raise RuntimeError("Model returned an empty response.")

    usage = payload.get("usage") or {}
    return {
      "modelId": model["id"],
      "modelName": model["name"],
      "provider": model["provider"],
      "content": content,
      "latencyMs": int((time.perf_counter() - started) * 1000),
      "status": "ok",
      "usage": {
        "promptTokens": usage.get("prompt_tokens"),
        "completionTokens": usage.get("completion_tokens"),
        "totalTokens": usage.get("total_tokens"),
      },
    }
  except Exception as exc:
    return {
      "modelId": model["id"],
      "modelName": model["name"],
      "provider": model["provider"],
      "content": "",
      "latencyMs": int((time.perf_counter() - started) * 1000),
      "status": "error",
      "error": str(exc),
    }


def _judge_candidate_blocks(candidates: list[dict[str, Any]]) -> list[str]:
  candidate_blocks = []
  for candidate in candidates:
    candidate_blocks.append(
      f"Model ID: {candidate['modelId']}\n"
      f"Model Name: {candidate['modelName']}\n"
      f"Response:\n{_clip_for_judge(candidate['content'])}"
    )
  return candidate_blocks


def _stream_openrouter_text(
  *,
  model: str,
  messages: list[dict[str, Any]],
  temperature: float,
  max_tokens: int,
  provider: dict[str, Any] | None = None,
) -> Iterator[str]:
  for chunk in chat_completion_stream(
    model=model,
    messages=messages,
    temperature=temperature,
    max_tokens=max_tokens,
    provider=provider,
  ):
    if chunk:
      yield chunk


def _iter_rendered_text_chunks(text: str, *, max_chars: int = 160) -> Iterator[str]:
  clean = text.strip()
  if not clean:
    return

  start = 0
  while start < len(clean):
    end = min(start + max_chars, len(clean))
    if end < len(clean):
      split = clean.rfind(" ", start, end)
      if split > start:
        end = split + 1
    yield clean[start:end]
    start = end


def _stream_judge_synthesis_text(
  *,
  query: str,
  category: str,
  candidates: list[dict[str, Any]],
  judge_model: str,
  grounding: dict[str, Any] | None = None,
) -> Iterator[str]:
  system_prompt = (
    "You are the final synthesis writer for Magnio Arena.\n"
    "Write only the final answer for the user in markdown.\n"
    "Use the strongest ideas from the candidate answers, resolve conflicts clearly, and be decisive.\n"
    "Do not mention models, judging, rankings, or that multiple candidates were compared."
  )
  if grounding:
    system_prompt += (
      "\nWhen retrieved evidence is supplied, use it as the source of truth for Sebastian/project claims."
      "\nCite only the allowed chunk ids provided by the user."
      "\nNever invent chunk ids, placeholder citations, or unsupported evidence."
      "\nIf a claim is not supported by retrieved evidence, say 'not evidenced in retrieved material'."
    )
  user_prompt = _build_arena_judge_user_prompt(
    query=query,
    category=category,
    candidates=candidates,
    grounding=grounding,
  )

  yield from _stream_openrouter_text(
    model=judge_model,
    messages=[
      {"role": "system", "content": system_prompt},
      {"role": "user", "content": user_prompt},
    ],
    temperature=0,
    max_tokens=2200,
    provider=FAST_PROVIDER_PREF,
  )


def _judge_candidates(
  query: str,
  category: str,
  candidates: list[dict[str, Any]],
  grounding: dict[str, Any] | None = None,
) -> dict[str, Any]:
  judge_provider = _resolve_judge_provider()
  judge_model = _resolve_judge_model(judge_provider)

  messages = [
    {
      "role": "user",
      "content": _build_arena_judge_user_prompt(
        query=query,
        category=category,
        candidates=candidates,
        grounding=grounding,
      ),
    }
  ]

  if judge_provider == "vertex":
    payload = vertex_generate_content(
      model=judge_model,
      messages=[
        {
          "role": "system",
          "content": _judge_system_prompt_structured(category)
          + (
            "\nWhen retrieved evidence is supplied, prefer candidates that use only allowed chunk ids correctly,"
            " clearly label inference, and avoid unsupported evidence."
            if grounding
            else ""
          ),
        },
        *messages,
      ],
      temperature=0,
      max_tokens=2800,
      response_mime_type="application/json",
      response_json_schema=VERTEX_JUDGE_RESPONSE_SCHEMA,
    )
    parsed = vertex_extract_json(payload)
    parsed["judgeModelId"] = judge_model
    return parsed

  payload = chat_completion(
    model=judge_model,
    messages=[
      {
        "role": "system",
        "content": _judge_system_prompt(category)
        + (
          "\nWhen retrieved evidence is supplied, prefer candidates that use only allowed chunk ids correctly,"
          " clearly label inference, and avoid unsupported evidence."
          if grounding
          else ""
        ),
      },
      *messages,
    ],
    temperature=0,
    max_tokens=2600,
    provider=FAST_PROVIDER_PREF,
  )

  content = extract_message_text(payload)
  parsed = _extract_judge_payload(content, model=judge_model)
  parsed["judgeModelId"] = judge_model
  return parsed


def _local_advisor_fallback(
  query: str,
  retrieval: list[dict[str, Any]],
  profile: dict[str, Any],
  *,
  provider_label: str,
) -> str:
  titles = ", ".join(chunk["title"] for chunk in retrieval[:3])
  if profile.get("id") == "career_transition":
    return (
      f"{provider_label} is not configured yet, so this is a retrieval-only draft.\n\n"
      "Best current guidance:\n"
      "- Turn your current expertise into one narrow consulting wedge instead of a broad firm pitch.\n"
      "- Keep employer overlap risk low by separating clients, materials, and communications.\n"
      "- Leave only after you have a stable offer, repeatable delivery, and a visible pipeline.\n\n"
      f"Most relevant knowledge pulled for this question: {titles}.\n\n"
      f"Original question: {query}"
    )
  if profile.get("id") == "side_practice":
    return (
      f"{provider_label} is not configured yet, so this is a retrieval-only draft.\n\n"
      "Best current guidance:\n"
      "- Keep the job, pick one narrow offer, and validate with a few paying clients before building a larger practice.\n"
      "- Review employer restrictions, licensing, and keep employer resources completely separate.\n"
      "- Set a transition trigger in advance instead of quitting on momentum alone.\n\n"
      f"Most relevant knowledge pulled for this question: {titles}.\n\n"
      f"Original question: {query}"
    )
  if profile.get("id") == "starter_site":
    return (
      f"{provider_label} is not configured yet, so this is a retrieval-only draft.\n\n"
      "Best current guidance:\n"
      "- Start with a simple service-business site that gets people to book, not a custom AI product.\n"
      "- Put the basics in place first: offer clarity, proof, booking, intake, and a clear call to action.\n"
      "- Add one narrow AI layer later, such as an FAQ assistant or follow-up draft flow.\n\n"
      f"Most relevant knowledge pulled for this question: {titles}.\n\n"
      f"Original question: {query}"
    )
  return (
    f"{provider_label} is not configured yet, so this is a retrieval-only draft.\n\n"
    "Best current guidance:\n"
    "- Start with a workflow audit and choose one measurable pilot.\n"
    "- Use AI where the handoffs and repetitive decisions are expensive, not where the process is still undefined.\n"
    "- Move from discovery to pilot, then harden the system only after the pilot proves speed, quality, or margin impact.\n\n"
    f"Most relevant knowledge pulled for this question: {titles}.\n\n"
    f"Original question: {query}"
  )


def _serialize_retrieval_items(retrieval: list[dict[str, Any]]) -> list[dict[str, Any]]:
  return [
    {
      "id": item["id"],
      "title": item["title"],
      "excerpt": str(item["body"])[:220].rstrip() + ("..." if len(str(item["body"])) > 220 else ""),
      "score": item["score"],
      "tags": item["tags"],
      "source": item.get("source"),
    }
    for item in retrieval
  ]


def _stream_json_line(payload: dict[str, Any]) -> str:
  return json.dumps(payload, separators=(",", ":")) + "\n"


def _attach_observability(response: dict[str, Any], *, query: str, requested_mode: str, latency_ms: int) -> dict[str, Any]:
  response["latencyMs"] = latency_ms
  response["runId"] = None
  response["feedback"] = None

  try:
    run_id = record_chat_run(
      query=query,
      requested_mode=requested_mode,
      response=response,
      latency_ms=latency_ms,
    )
    response["runId"] = run_id
    response["feedback"] = get_feedback_for_run(run_id)
  except Exception as exc:
    warnings = list(response.get("warnings") or [])
    warnings.append(f"Analytics logging failed: {exc}")
    response["warnings"] = warnings

  return response


def _run_advisor(query: str, requested_mode: str) -> dict[str, Any]:
  profile = _advisor_query_profile(query)
  retrieval = hybrid_search(
    profile["retrievalQuery"],
    limit=6 if profile.get("id") in {"fit_analysis", "opportunity_analysis"} else 4,
    preferred_focus=profile.get("preferredFocus") or [],
    preferred_chunk_ids=profile.get("preferredChunkIds") or [],
    preferred_sources=profile.get("preferredSources") or [],
  )
  retrieval_items = [
    {
      "id": item["id"],
      "title": item["title"],
      "excerpt": str(item["body"])[:220].rstrip() + ("..." if len(str(item["body"])) > 220 else ""),
      "score": item["score"],
      "tags": item["tags"],
      "source": item.get("source"),
    }
    for item in retrieval
  ]
  warnings: list[str] = []
  advisor_provider = _resolve_advisor_provider()

  if not _provider_configured(advisor_provider):
    warnings.append(f"{_provider_not_configured_message(advisor_provider)} Returned a retrieval-only fallback answer.")
    return {
      "requestedMode": requested_mode,
      "resolvedMode": "advisor",
      "answer": _local_advisor_fallback(
        query,
        retrieval,
        profile,
        provider_label="Vertex AI" if advisor_provider == "vertex" else "OpenRouter",
      ),
      "topic": {"id": "advisor", "label": "Magnio Advisor"},
      "retrieval": retrieval_items,
      "candidates": [],
      "judge": None,
      "diagnostics": {
        "strategy": "Hybrid advisor RAG",
        "evaluationType": "single_model",
        "advisorModelId": f"{advisor_provider}:local-fallback",
        "answerModelId": "local-fallback",
        "selectedModels": [],
      },
      "warnings": warnings,
    }

  advisor_model = _resolve_advisor_model(advisor_provider)
  context = build_context(retrieval)
  structured_answer: dict[str, Any] | None = None

  try:
    if profile.get("id") == "fit_analysis":
      try:
        structured_answer = _run_structured_fit_analysis(
          query=query,
          retrieval=retrieval,
          provider=advisor_provider,
          model=advisor_model,
        )
      except Exception as exc:
        structured_answer = _fallback_fit_analysis_structured_answer(retrieval)
        if not str(structured_answer.get("rendered") or "").strip():
          warnings.append(f"Advisor structured synthesis fell back ({advisor_provider}): {exc}")
      if int(structured_answer.get("renderedWordCount") or 0) > 1000:
        warnings.append("Structured fit answer exceeded the 1000-word target.")
      answer = str(structured_answer.get("rendered") or "").strip()
    elif profile.get("id") == "opportunity_analysis":
      try:
        structured_answer = _run_structured_opportunity_analysis(
          query=query,
          retrieval=retrieval,
          provider=advisor_provider,
          model=advisor_model,
        )
      except Exception as exc:
        structured_answer = _fallback_opportunity_analysis_structured_answer(query, retrieval)
        if not str(structured_answer.get("rendered") or "").strip():
          warnings.append(f"Advisor structured opportunity synthesis fell back ({advisor_provider}): {exc}")
      if int(structured_answer.get("renderedWordCount") or 0) > OPPORTUNITY_RENDER_WORD_TARGET:
        warnings.append("Structured opportunity answer exceeded the compact target.")
      answer = str(structured_answer.get("rendered") or "").strip()
    else:
      system_prompt = (
        _advisor_opportunity_system_prompt()
        if profile.get("id") == "opportunity_analysis"
        else _advisor_system_prompt()
      )
      response_contract = (
        "Answer with retrieved-evidence claims and JD-based inference clearly separated.\n"
        "- Use chunk citations only for retrieved evidence about Sebastian.\n"
        "- For scored items, prefer the pattern 'Evidence: ... [K39]' and 'Inference: ...'.\n"
        "- Prefix job-description implications with '(JD inference)'.\n"
        "- Prefix compensation or market assumptions with '(Market/JD inference)'.\n"
        "- Do not use markdown tables; use bullets or short subsections so labels stay explicit.\n"
        "- Follow the user's requested section structure when possible."
        if profile.get("id") == "opportunity_analysis"
        else "Answer with grounded guidance and cite chunk ids inline."
      )
      messages = [
        {"role": "system", "content": system_prompt},
        {
          "role": "user",
          "content": (
            f"User question:\n{query}\n\n"
            "Advisor lens:\n"
            f"{profile['instructions']}\n\n"
            "Magnio knowledge base:\n"
            f"{context}\n\n"
            f"{response_contract}"
          ),
        },
      ]
      if advisor_provider == "vertex":
        payload = vertex_generate_content(
          model=advisor_model,
          messages=messages,
          temperature=0.3,
          max_tokens=1100,
        )
        answer = str(payload.get("text") or "").strip()
      else:
        payload = chat_completion(
          model=advisor_model,
          messages=messages,
          temperature=0.3,
          max_tokens=1100,
          provider=FAST_PROVIDER_PREF,
        )
        answer = extract_message_text(payload)
    if not answer:
      raise RuntimeError("Advisor model returned an empty response.")
  except Exception as exc:
    warnings.append(f"Advisor model failed ({advisor_provider}): {exc}")
    answer = _local_advisor_fallback(
      query,
      retrieval,
      profile,
      provider_label="Vertex AI" if advisor_provider == "vertex" else "OpenRouter",
    )
    advisor_model = "local-fallback"

  return {
    "requestedMode": requested_mode,
    "resolvedMode": "advisor",
    "answer": answer,
    "topic": {"id": "advisor", "label": "Magnio Advisor"},
    "retrieval": retrieval_items,
    "candidates": [],
    "judge": None,
    "diagnostics": {
      "strategy": (
        "Hybrid advisor RAG with extracted-fact structured synthesis"
        if profile.get("id") == "fit_analysis"
        else (
          "Hybrid advisor RAG with extracted-fact structured opportunity synthesis"
          if profile.get("id") == "opportunity_analysis"
          else "Hybrid advisor RAG"
        )
      ),
      "evaluationType": "single_model",
      "advisorModelId": advisor_model,
      "answerModelId": advisor_model,
      "selectedModels": [],
    },
    "warnings": warnings,
    "structuredAnswer": structured_answer,
  }


def _run_arena(query: str, requested_mode: str) -> dict[str, Any]:
  if not openrouter_configured():
    raise HTTPException(
      status_code=503,
      detail="OpenRouter API key is not configured. Set MAGNIO_OPENROUTER_API_KEY or OPENROUTER_API_KEY.",
    )

  category, category_reasons = _infer_category(query)
  if category == "dating":
    category_reasons = [*category_reasons, *_dating_guardrail_notes(query)]
  grounding = _arena_grounding_bundle(query)
  retrieval_items = list(grounding["retrievalItems"]) if grounding else []
  arena_size = max(2, min(int(os.environ.get("MAGNIO_CHAT_ARENA_SIZE", "3")), 5))
  selected_models = _choose_ranked_models(category, arena_size=arena_size, grounding=grounding)
  if len(selected_models) < 2:
    raise HTTPException(status_code=502, detail="Unable to resolve enough ranked models for the arena.")

  with ThreadPoolExecutor(max_workers=len(selected_models)) as executor:
    results = list(executor.map(lambda item: _run_candidate(item, query, category, grounding), selected_models))

  successful = [result for result in results if result["status"] == "ok"]
  warnings = [result["error"] for result in results if result["status"] == "error"]

  if not successful:
    attempted_model_ids = {model["id"] for model in selected_models}
    retry_models = _fallback_models_for_category(
      category,
      arena_size=arena_size,
      exclude=attempted_model_ids,
    )
    if retry_models:
      with ThreadPoolExecutor(max_workers=len(retry_models)) as executor:
        retry_results = list(executor.map(lambda item: _run_candidate(item, query, category, grounding), retry_models))

      results.extend(retry_results)
      successful = [result for result in results if result["status"] == "ok"]
      warnings.extend(result["error"] for result in retry_results if result["status"] == "error")

      if successful:
        selected_models.extend(retry_models)
        warnings.append("Primary arena model pool failed, so Magnio retried with a curated fallback pool.")

  if not successful:
    raise HTTPException(status_code=502, detail="All arena model calls failed.")

  if len(successful) == 1:
    judge = _fallback_judge(successful)
    warnings.append("Only one arena model succeeded, so the final answer was not fully judged.")
  else:
    try:
      judge = _judge_candidates(query, category, successful, grounding)
    except Exception as exc:
      warnings.append(f"Judge model failed: {exc}")
      judge = _fallback_judge(successful)

  final_answer = str(judge.get("synthesis") or successful[0]["content"]).strip()

  normalized_scores = []
  for score in judge.get("scores") or []:
    total = (
      int(score.get("usefulness", 0))
      + int(score.get("groundedness", 0))
      + int(score.get("clarity", 0))
      + int(score.get("decisiveness", 0))
    )
    normalized_scores.append(
      {
        "modelId": score.get("modelId"),
        "usefulness": score.get("usefulness"),
        "groundedness": score.get("groundedness"),
        "clarity": score.get("clarity"),
        "decisiveness": score.get("decisiveness"),
        "total": total,
        "notes": score.get("notes"),
      }
    )

  return {
    "requestedMode": requested_mode,
    "resolvedMode": "arena",
    "answer": final_answer,
    "topic": {
      "id": category,
      "label": OPENROUTER_CATEGORY_LABELS.get(category, category.title()),
      "reasoning": category_reasons,
    },
    "retrieval": retrieval_items,
    "candidates": results,
    "judge": {
      "winnerModelId": judge.get("winnerModelId"),
      "confidence": judge.get("confidence"),
      "rationale": judge.get("rationale"),
      "scores": normalized_scores,
      "judgeModelId": judge.get("judgeModelId", "fallback"),
    },
    "diagnostics": {
      "strategy": "Category-ranked arena with judge synthesis",
      "evaluationType": "arena",
      "advisorModelId": None,
      "answerModelId": None,
      "selectedModels": [model["id"] for model in selected_models],
      "groundingMode": "retrieved_evidence" if grounding else "none",
    },
    "warnings": warnings,
  }


def _stream_advisor_response(query: str, requested_mode: str) -> Iterator[str]:
  started = time.perf_counter()
  warnings: list[str] = []

  try:
    profile = _advisor_query_profile(query)
    retrieval = hybrid_search(
      profile["retrievalQuery"],
      limit=6 if profile.get("id") in {"fit_analysis", "opportunity_analysis"} else 4,
      preferred_focus=profile.get("preferredFocus") or [],
      preferred_chunk_ids=profile.get("preferredChunkIds") or [],
      preferred_sources=profile.get("preferredSources") or [],
    )
    retrieval_items = _serialize_retrieval_items(retrieval)
    advisor_provider = _resolve_advisor_provider()
    advisor_model = _resolve_advisor_model(advisor_provider)
    structured_answer: dict[str, Any] | None = None

    yield _stream_json_line(
      {
        "type": "started",
        "requestedMode": requested_mode,
        "resolvedMode": "advisor",
        "topic": {"id": "advisor", "label": "Magnio Advisor"},
        "diagnostics": {
          "strategy": "Hybrid advisor RAG",
          "evaluationType": "single_model",
          "advisorModelId": advisor_model,
          "answerModelId": advisor_model,
          "selectedModels": [],
        },
      }
    )

    if retrieval_items:
      yield _stream_json_line({"type": "retrieval", "items": retrieval_items})

    if not _provider_configured(advisor_provider):
      warnings.append(
        f"{_provider_not_configured_message(advisor_provider)} Returned a retrieval-only fallback answer."
      )
      answer = _local_advisor_fallback(
        query,
        retrieval,
        profile,
        provider_label="Vertex AI" if advisor_provider == "vertex" else "OpenRouter",
      )
      advisor_model = "local-fallback"
    else:
      context = build_context(retrieval)
      answer = ""

      try:
        if profile.get("id") == "fit_analysis":
          yield _stream_json_line(
            {"type": "status", "phase": "analysis", "message": "Extracting supported evidence."}
          )
          if advisor_provider == "openrouter":
            extracted_facts = _extract_supported_facts(
              query=query,
              retrieval=retrieval,
              provider=advisor_provider,
              model=advisor_model,
            )
            allowed_citations = sorted(
              {
                str(item.get("id") or "").strip()
                for item in retrieval
                if isinstance(item, dict) and str(item.get("id") or "").strip()
              }
            )
            stream_prompt = (
              f"User task:\n{query}\n\n"
              "Allowed chunk ids:\n"
              f"{', '.join(allowed_citations)}\n\n"
              "Extracted supported facts:\n"
              f"{json.dumps(extracted_facts, ensure_ascii=True, indent=2)}\n\n"
              "Return exactly 4 numbered sections:\n"
              "1. Overall fit\n"
              "2. Top 3 strengths\n"
              "3. Top 2 gaps\n"
              "4. 60-second interview answer\n\n"
              "Rules:\n"
              "- Every factual strength or gap must cite allowed chunk ids inline.\n"
              "- If a gap is not explicit in the facts, phrase it as 'not evidenced in retrieved material'.\n"
              "- The interview answer must sound spoken, concise, and natural.\n"
              "- Keep the output under 1000 words when possible."
            )
            yield _stream_json_line(
              {"type": "status", "phase": "generation", "message": "Streaming fit synthesis."}
            )
            answer_chunks: list[str] = []
            for chunk in _stream_openrouter_text(
              model=advisor_model,
              messages=[
                {"role": "system", "content": _advisor_fit_stream_render_system_prompt()},
                {"role": "user", "content": stream_prompt},
              ],
              temperature=0.2,
              max_tokens=1100,
              provider=FAST_PROVIDER_PREF,
            ):
              answer_chunks.append(chunk)
              yield _stream_json_line({"type": "answer_delta", "text": chunk})
            answer = "".join(answer_chunks).strip()
            if _word_count_text(answer) > 1000:
              warnings.append("Structured fit answer exceeded the 1000-word target.")
          else:
            structured_answer = _run_structured_fit_analysis(
              query=query,
              retrieval=retrieval,
              provider=advisor_provider,
              model=advisor_model,
            )
            if int(structured_answer.get("renderedWordCount") or 0) > 1000:
              warnings.append("Structured fit answer exceeded the 1000-word target.")
            answer = str(structured_answer.get("rendered") or "").strip()
            for chunk in _iter_rendered_text_chunks(answer):
              yield _stream_json_line({"type": "answer_delta", "text": chunk})
        elif profile.get("id") == "opportunity_analysis":
          yield _stream_json_line(
            {"type": "status", "phase": "analysis", "message": "Extracting supported evidence."}
          )
          if advisor_provider == "openrouter":
            extracted_facts = _extract_supported_facts(
              query=query,
              retrieval=retrieval,
              provider=advisor_provider,
              model=advisor_model,
            )
            allowed_citations = sorted(
              {
                str(item.get("id") or "").strip()
                for item in retrieval
                if isinstance(item, dict) and str(item.get("id") or "").strip()
              }
            )
            stream_prompt = (
              f"User task:\n{query}\n\n"
              "Allowed chunk ids:\n"
              f"{', '.join(allowed_citations)}\n\n"
              "Extracted supported facts:\n"
              f"{json.dumps(extracted_facts, ensure_ascii=True, indent=2)}\n\n"
              "Return a rendered opportunity evaluation that follows the user's requested structure.\n"
              "Rules:\n"
              "- Use chunk citations only for Sebastian evidence.\n"
              "- Label role interpretation as '(JD inference)'.\n"
              "- Label compensation or market assumptions as '(Market/JD inference)'.\n"
              "- If evidence is missing, say 'not evidenced in retrieved material'.\n"
              "- Keep the answer polished and readable, not overly compressed.\n"
              "- Prefer readable headings and short paragraphs; a compact markdown table is allowed for the scorecard.\n"
              "- Prioritize finishing the later sections and the final verdict.\n"
              "- End with a line that starts exactly with 'Final verdict: '."
            )
            yield _stream_json_line(
              {"type": "status", "phase": "generation", "message": "Streaming opportunity synthesis."}
            )
            answer_chunks: list[str] = []
            for chunk in _stream_openrouter_text(
              model=advisor_model,
              messages=[
                {"role": "system", "content": _advisor_opportunity_stream_render_system_prompt()},
                {"role": "user", "content": stream_prompt},
              ],
              temperature=0.2,
              max_tokens=2600,
              provider=FAST_PROVIDER_PREF,
            ):
              answer_chunks.append(chunk)
              yield _stream_json_line({"type": "answer_delta", "text": chunk})
            answer = "".join(answer_chunks).strip()
          else:
            structured_answer = _run_structured_opportunity_analysis(
              query=query,
              retrieval=retrieval,
              provider=advisor_provider,
              model=advisor_model,
            )
            if int(structured_answer.get("renderedWordCount") or 0) > OPPORTUNITY_RENDER_WORD_TARGET:
              warnings.append("Structured opportunity answer exceeded the compact target.")
            yield _stream_json_line(
              {"type": "status", "phase": "generation", "message": "Streaming opportunity synthesis."}
            )
            answer = str(structured_answer.get("rendered") or "").strip()
            for chunk in _iter_rendered_text_chunks(answer):
              yield _stream_json_line({"type": "answer_delta", "text": chunk})
        else:
          system_prompt = _advisor_system_prompt()
          messages = [
            {"role": "system", "content": system_prompt},
            {
              "role": "user",
              "content": (
                f"User question:\n{query}\n\n"
                "Advisor lens:\n"
                f"{profile['instructions']}\n\n"
                "Magnio knowledge base:\n"
                f"{context}\n\n"
                "Answer with grounded guidance and cite chunk ids inline."
              ),
            },
          ]
          yield _stream_json_line(
            {"type": "status", "phase": "generation", "message": "Generating grounded answer."}
          )
          if advisor_provider == "openrouter":
            answer_chunks: list[str] = []
            for chunk in chat_completion_stream(
              model=advisor_model,
              messages=messages,
              temperature=0.3,
              max_tokens=1100,
              provider=FAST_PROVIDER_PREF,
            ):
              answer_chunks.append(chunk)
              yield _stream_json_line({"type": "answer_delta", "text": chunk})
            answer = "".join(answer_chunks).strip()
          else:
            payload = vertex_generate_content(
              model=advisor_model,
              messages=messages,
              temperature=0.3,
              max_tokens=1100,
            )
            answer = str(payload.get("text") or "").strip()

        if not answer:
          raise RuntimeError("Advisor model returned an empty response.")
      except Exception as exc:
        warnings.append(f"Advisor model failed ({advisor_provider}): {exc}")
        answer = _local_advisor_fallback(
          query,
          retrieval,
          profile,
          provider_label="Vertex AI" if advisor_provider == "vertex" else "OpenRouter",
        )
        advisor_model = "local-fallback"

    response = {
      "requestedMode": requested_mode,
      "resolvedMode": "advisor",
      "answer": answer,
      "topic": {"id": "advisor", "label": "Magnio Advisor"},
      "retrieval": retrieval_items,
      "candidates": [],
      "judge": None,
      "diagnostics": {
        "strategy": (
          "Hybrid advisor RAG with extracted-fact streamed fit synthesis"
          if profile.get("id") == "fit_analysis" and advisor_provider == "openrouter"
          else (
            "Hybrid advisor RAG with extracted-fact streamed opportunity synthesis"
            if profile.get("id") == "opportunity_analysis" and advisor_provider == "openrouter"
            else (
              "Hybrid advisor RAG with extracted-fact structured synthesis"
              if profile.get("id") == "fit_analysis"
              else (
                "Hybrid advisor RAG with extracted-fact structured opportunity synthesis"
                if profile.get("id") == "opportunity_analysis"
                else "Hybrid advisor RAG"
              )
            )
          )
        ),
        "evaluationType": "single_model",
        "advisorModelId": advisor_model,
        "answerModelId": advisor_model,
        "selectedModels": [],
      },
      "warnings": warnings,
      "structuredAnswer": structured_answer,
    }
    latency_ms = int((time.perf_counter() - started) * 1000)
    final_response = _attach_observability(
      response,
      query=query,
      requested_mode=requested_mode,
      latency_ms=latency_ms,
    )
    yield _stream_json_line({"type": "complete", "response": final_response})
  except HTTPException as exc:
    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
      record_chat_error(
        query=query,
        requested_mode=requested_mode,
        resolved_mode="advisor",
        error=str(exc.detail),
        latency_ms=latency_ms,
      )
    except Exception:
      pass
    yield _stream_json_line({"type": "error", "detail": str(exc.detail), "latencyMs": latency_ms})
  except Exception as exc:
    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
      record_chat_error(
        query=query,
        requested_mode=requested_mode,
        resolved_mode="advisor",
        error=str(exc),
        latency_ms=latency_ms,
      )
    except Exception:
      pass
    yield _stream_json_line(
      {"type": "error", "detail": f"Unexpected chat error: {exc}", "latencyMs": latency_ms}
    )


def _stream_arena_response(query: str, requested_mode: str) -> Iterator[str]:
  started = time.perf_counter()
  warnings: list[str] = []

  try:
    if not openrouter_configured():
      raise HTTPException(
        status_code=503,
        detail="OpenRouter API key is not configured. Set MAGNIO_OPENROUTER_API_KEY or OPENROUTER_API_KEY.",
      )

    category, category_reasons = _infer_category(query)
    if category == "dating":
      category_reasons = [*category_reasons, *_dating_guardrail_notes(query)]
    grounding = _arena_grounding_bundle(query)
    retrieval_items = list(grounding["retrievalItems"]) if grounding else []

    arena_size = max(2, min(int(os.environ.get("MAGNIO_CHAT_ARENA_SIZE", "3")), 5))
    selected_models = _choose_ranked_models(category, arena_size=arena_size, grounding=grounding)
    if len(selected_models) < 2:
      raise HTTPException(status_code=502, detail="Unable to resolve enough ranked models for the arena.")

    yield _stream_json_line(
      {
        "type": "started",
        "requestedMode": requested_mode,
        "resolvedMode": "arena",
        "topic": {
          "id": category,
          "label": OPENROUTER_CATEGORY_LABELS.get(category, category.title()),
          "reasoning": category_reasons,
        },
        "diagnostics": {
          "strategy": "Category-ranked arena with judge synthesis",
          "evaluationType": "arena",
          "advisorModelId": None,
          "answerModelId": None,
          "selectedModels": [model["id"] for model in selected_models],
          "groundingMode": "retrieved_evidence" if grounding else "none",
        },
      }
    )
    if retrieval_items:
      yield _stream_json_line({"type": "retrieval", "items": retrieval_items})
    yield _stream_json_line(
      {"type": "status", "phase": "candidates", "message": "Running arena candidates in parallel."}
    )

    results_by_model: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=len(selected_models)) as executor:
      futures = [executor.submit(_run_candidate, model, query, category, grounding) for model in selected_models]
      for future in as_completed(futures):
        result = future.result()
        results_by_model[result["modelId"]] = result
        if result["status"] == "error" and result.get("error"):
          warnings.append(str(result["error"]))
        yield _stream_json_line({"type": "candidate", "candidate": result})

    successful = [result for result in results_by_model.values() if result["status"] == "ok"]

    if not successful:
      attempted_model_ids = {model["id"] for model in selected_models}
      retry_models = _fallback_models_for_category(
        category,
        arena_size=arena_size,
        exclude=attempted_model_ids,
      )
      if retry_models:
        selected_models.extend(retry_models)
        yield _stream_json_line(
          {
            "type": "status",
            "phase": "retry",
            "message": "Primary candidate pool failed. Retrying with fallback models.",
          }
        )
        with ThreadPoolExecutor(max_workers=len(retry_models)) as executor:
          retry_futures = [
            executor.submit(_run_candidate, model, query, category, grounding)
            for model in retry_models
          ]
          for future in as_completed(retry_futures):
            result = future.result()
            results_by_model[result["modelId"]] = result
            if result["status"] == "error" and result.get("error"):
              warnings.append(str(result["error"]))
            yield _stream_json_line({"type": "candidate", "candidate": result})

        successful = [result for result in results_by_model.values() if result["status"] == "ok"]
        if successful:
          warnings.append(
            "Primary arena model pool failed, so Magnio retried with a curated fallback pool."
          )

    if not successful:
      raise HTTPException(status_code=502, detail="All arena model calls failed.")

    judge_provider = _resolve_judge_provider()
    judge_model = _resolve_judge_model(judge_provider)
    final_answer = ""

    if len(successful) == 1:
      judge = _fallback_judge(successful)
      warnings.append("Only one arena model succeeded, so the final answer was not fully judged.")
      for chunk in _iter_rendered_text_chunks(str(successful[0].get("content") or "")):
        final_answer += chunk
        yield _stream_json_line({"type": "answer_delta", "text": chunk})
    else:
      yield _stream_json_line(
        {"type": "status", "phase": "judge", "message": "Scoring candidates and synthesizing final answer."}
      )
      if judge_provider == "openrouter":
        with ThreadPoolExecutor(max_workers=1) as executor:
          judge_future = executor.submit(_judge_candidates, query, category, successful, grounding)
          try:
            for chunk in _stream_judge_synthesis_text(
              query=query,
              category=category,
              candidates=successful,
              judge_model=judge_model,
              grounding=grounding,
            ):
              final_answer += chunk
              yield _stream_json_line({"type": "answer_delta", "text": chunk})
          except Exception as exc:
            warnings.append(f"Judge synthesis stream failed: {exc}")

          try:
            judge = judge_future.result()
          except Exception as exc:
            warnings.append(f"Judge model failed: {exc}")
            judge = _fallback_judge(successful)
      else:
        try:
          judge = _judge_candidates(query, category, successful, grounding)
        except Exception as exc:
          warnings.append(f"Judge model failed: {exc}")
          judge = _fallback_judge(successful)

    judge_synthesis = str(judge.get("synthesis") or "").strip()
    if judge_synthesis:
      final_answer = judge_synthesis
    elif not final_answer:
      final_answer = str(successful[0]["content"]).strip()
      for chunk in _iter_rendered_text_chunks(final_answer):
        yield _stream_json_line({"type": "answer_delta", "text": chunk})

    judge["synthesis"] = final_answer
    normalized_scores = []
    for score in judge.get("scores") or []:
      total = (
        int(score.get("usefulness", 0))
        + int(score.get("groundedness", 0))
        + int(score.get("clarity", 0))
        + int(score.get("decisiveness", 0))
      )
      normalized_scores.append(
        {
          "modelId": score.get("modelId"),
          "usefulness": score.get("usefulness"),
          "groundedness": score.get("groundedness"),
          "clarity": score.get("clarity"),
          "decisiveness": score.get("decisiveness"),
          "total": total,
          "notes": score.get("notes"),
        }
      )

    ordered_results = [
      results_by_model[model["id"]]
      for model in selected_models
      if model["id"] in results_by_model
    ]

    response = {
      "requestedMode": requested_mode,
      "resolvedMode": "arena",
      "answer": final_answer,
      "topic": {
        "id": category,
        "label": OPENROUTER_CATEGORY_LABELS.get(category, category.title()),
        "reasoning": category_reasons,
      },
      "retrieval": retrieval_items,
      "candidates": ordered_results,
      "judge": {
        "winnerModelId": judge.get("winnerModelId"),
        "confidence": judge.get("confidence"),
        "rationale": judge.get("rationale"),
        "scores": normalized_scores,
        "judgeModelId": judge.get("judgeModelId", "fallback"),
      },
      "diagnostics": {
        "strategy": (
          "Category-ranked arena with streamed judge synthesis"
          if judge_provider == "openrouter"
          else "Category-ranked arena with judge synthesis"
        ),
        "evaluationType": "arena",
        "advisorModelId": None,
        "answerModelId": None,
        "selectedModels": [model["id"] for model in selected_models],
        "groundingMode": "retrieved_evidence" if grounding else "none",
      },
      "warnings": warnings,
    }
    latency_ms = int((time.perf_counter() - started) * 1000)
    final_response = _attach_observability(
      response,
      query=query,
      requested_mode=requested_mode,
      latency_ms=latency_ms,
    )
    yield _stream_json_line({"type": "complete", "response": final_response})
  except HTTPException as exc:
    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
      record_chat_error(
        query=query,
        requested_mode=requested_mode,
        resolved_mode="arena",
        error=str(exc.detail),
        latency_ms=latency_ms,
      )
    except Exception:
      pass
    yield _stream_json_line({"type": "error", "detail": str(exc.detail), "latencyMs": latency_ms})
  except Exception as exc:
    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
      record_chat_error(
        query=query,
        requested_mode=requested_mode,
        resolved_mode="arena",
        error=str(exc),
        latency_ms=latency_ms,
      )
    except Exception:
      pass
    yield _stream_json_line(
      {"type": "error", "detail": f"Unexpected chat error: {exc}", "latencyMs": latency_ms}
    )


@router.get("/health")
def chat_health() -> dict[str, Any]:
  init_chat_analytics_db()
  advisor_provider = _resolve_advisor_provider()
  judge_provider = _resolve_judge_provider()
  return {
    "ok": True,
    "openrouterConfigured": openrouter_configured(),
    "vertexConfigured": vertex_configured(),
    "vertexProject": resolve_vertex_project() or None,
    "vertexLocation": resolve_vertex_location(),
    "knowledgeChunkCount": len(KNOWLEDGE_BASE),
    "judgeProvider": judge_provider,
    "judgeModelId": _resolve_judge_model(judge_provider),
    "advisorProvider": advisor_provider,
    "advisorModelId": _resolve_advisor_model(advisor_provider),
    "analyticsDbPath": resolve_chat_analytics_target(),
  }


@router.get("/analytics/summary")
def chat_analytics_summary() -> dict[str, Any]:
  return get_chat_analytics_summary()


@router.get("/analytics/model-trends")
def chat_model_trends(limit: int = 30) -> dict[str, Any]:
  safe_limit = max(1, min(limit, 100))
  return {"trends": get_model_win_trends(limit=safe_limit)}


@router.post("/suggest")
def chat_suggest(payload: ChatSuggestRequest) -> dict[str, Any]:
  provider = _resolve_advisor_provider()
  model = _resolve_advisor_model(provider)

  system_prompt = (
    "You are a career advisor assistant. Given an answer about a career topic, "
    "generate exactly 3 short, specific follow-up questions the user might want to ask next. "
    "Return ONLY valid JSON: {\"suggestions\": [\"question 1\", \"question 2\", \"question 3\"]}. "
    "No extra keys. No markdown. No explanation."
  )
  user_prompt = (
    f"Topic: {payload.topic_label}\n\n"
    f"Answer (excerpt):\n{payload.answer[:2500]}\n\n"
    "Generate 3 follow-up questions."
  )

  suggest_schema = {
    "type": "object",
    "properties": {
      "suggestions": {
        "type": "array",
        "items": {"type": "string"},
      }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
  }

  try:
    if provider == "vertex":
      raw_payload = vertex_generate_content(
        model=model,
        messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=300,
        response_mime_type="application/json",
        response_json_schema=suggest_schema,
      )
      try:
        parsed = vertex_extract_json(raw_payload)
      except RuntimeError:
        parsed = _extract_json(str(raw_payload.get("text") or "").strip())
    else:
      raw_payload = chat_completion(
        model=model,
        messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=300,
        provider=FAST_PROVIDER_PREF,
        response_format={
          "type": "json_schema",
          "json_schema": {
            "name": "suggest_response",
            "strict": True,
            "schema": suggest_schema,
          },
        },
      )
      parsed = _extract_json(extract_message_text(raw_payload))

    suggestions = parsed.get("suggestions") or []
    if isinstance(suggestions, list) and suggestions:
      return {"suggestions": [str(s).strip() for s in suggestions[:3] if s]}
  except Exception:
    pass

  return {"suggestions": []}


@router.get("/evaluations/recent")
def chat_recent_evaluations(limit: int = 20) -> dict[str, Any]:
  return get_recent_evaluation_cases(limit=limit)


@router.post("/feedback")
def chat_feedback(payload: ChatFeedbackRequest) -> dict[str, Any]:
  try:
    feedback = submit_chat_feedback(run_id=payload.runId.strip(), vote=payload.vote, note=payload.note)
  except KeyError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  return {"ok": True, "feedback": feedback}


@router.post("/ask/stream")
def chat_ask_stream(payload: ChatAskRequest) -> StreamingResponse:
  query = payload.query.strip()
  if not query:
    raise HTTPException(status_code=400, detail="Query is required.")

  resolved_mode = _resolve_mode(query, payload.mode)
  event_stream = (
    _stream_advisor_response(query, payload.mode)
    if resolved_mode == "advisor"
    else _stream_arena_response(query, payload.mode)
  )

  return StreamingResponse(
    event_stream,
    media_type="application/x-ndjson",
    headers={
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  )


@router.post("/ask")
def chat_ask(payload: ChatAskRequest) -> dict[str, Any]:
  started = time.perf_counter()
  query = payload.query.strip()
  if not query:
    raise HTTPException(status_code=400, detail="Query is required.")

  resolved_mode = _resolve_mode(query, payload.mode)
  try:
    if resolved_mode == "advisor":
      response = _run_advisor(query, payload.mode)
    else:
      response = _run_arena(query, payload.mode)

    latency_ms = int((time.perf_counter() - started) * 1000)
    return _attach_observability(
      response,
      query=query,
      requested_mode=payload.mode,
      latency_ms=latency_ms,
    )
  except HTTPException as exc:
    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
      record_chat_error(
        query=query,
        requested_mode=payload.mode,
        resolved_mode=resolved_mode,
        error=str(exc.detail),
        latency_ms=latency_ms,
      )
    except Exception:
      pass
    raise
  except Exception as exc:
    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
      record_chat_error(
        query=query,
        requested_mode=payload.mode,
        resolved_mode=resolved_mode,
        error=str(exc),
        latency_ms=latency_ms,
      )
    except Exception:
      pass
    raise HTTPException(status_code=500, detail=f"Unexpected chat error: {exc}") from exc
