from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


STOPWORDS = {
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "by",
  "for",
  "from",
  "how",
  "i",
  "if",
  "in",
  "into",
  "is",
  "it",
  "of",
  "on",
  "or",
  "our",
  "that",
  "the",
  "their",
  "them",
  "they",
  "this",
  "to",
  "we",
  "what",
  "when",
  "where",
  "who",
  "why",
  "with",
  "you",
  "your",
}

TERM_EXPANSIONS = {
  "agency": {"operator", "services", "retainer", "clients"},
  "ai": {"agentic", "automation", "copilot", "llm"},
  "automation": {"workflow", "ops", "process", "integration"},
  "booking": {"calendar", "scheduler", "intake", "consultation"},
  "consulting": {"advisory", "fractional", "retainer", "clients"},
  "cpa": {"accounting", "tax", "bookkeeping", "practice", "financials"},
  "cfo": {"finance", "fractional", "cash-flow", "forecasting"},
  "coach": {"trainer", "fitness", "service"},
  "credit": {"lending", "underwriting", "loan", "financials"},
  "crm": {"workflow", "operations", "approvals", "tracking"},
  "fractional": {"consulting", "advisory", "retainer", "clients"},
  "immersion": {"adoption", "enablement", "pilot", "rollout"},
  "job": {"employment", "salary", "income"},
  "lawyer": {"attorney", "counsel", "contracts", "advisory"},
  "lead": {"buyer", "prospect", "client"},
  "ops": {"operations", "workflow", "handoff"},
  "portal": {"intake", "submission", "self-service"},
  "rag": {"retrieval", "knowledge", "grounded"},
  "recruiter": {"recruiting", "talent", "hiring", "search"},
  "site": {"website", "landing", "homepage", "pages"},
  "trainer": {"coach", "fitness", "gym", "service"},
  "website": {"site", "landing", "homepage", "booking", "pages"},
  "workflow": {"process", "operations", "handoff", "approval"},
}

FOCUS_PATTERNS = {
  "ai_immersion": [
    r"\bai immersion\b",
    r"\bai adoption\b",
    r"\bwhere (do|should) (we|i) start\b",
    r"\bpilot\b",
    r"\brollout\b",
    r"\benablement\b",
    r"\broadmap\b",
  ],
  "agentic": [
    r"\bagent(ic)?\b",
    r"\borchestr",
    r"\bjudge model\b",
    r"\bmultiple models\b",
    r"\barena\b",
  ],
  "operations": [
    r"\bworkflow\b",
    r"\bprocess\b",
    r"\bops\b",
    r"\bapproval\b",
    r"\bhandoff\b",
    r"\bbottleneck\b",
  ],
  "fit": [
    r"\bfit\b",
    r"\bwho is this for\b",
    r"\bideal client\b",
    r"\bqualified lead\b",
    r"\bshould we hire\b",
  ],
  "proof": [
    r"\bcase stud",
    r"\bimpact\b",
    r"\broi\b",
    r"\bsavings\b",
    r"\bloss prevented\b",
  ],
  "engagement": [
    r"\bengagement\b",
    r"\bproposal\b",
    r"\bscope\b",
    r"\btimeline\b",
    r"\b30[\/-]60[\/-]90\b",
    r"\bdiscovery\b",
  ],
  "starter_site": [
    r"\bwebsite\b",
    r"\bsite\b",
    r"\blanding page\b",
    r"\bbook(ing)?\b",
    r"\bpersonal trainer\b",
    r"\btrainer\b",
    r"\bcoach\b",
    r"\bsolo\b",
    r"\blocal business\b",
    r"\bservice business\b",
  ],
  "side_practice": [
    r"\bside business\b",
    r"\bside practice\b",
    r"\bday job\b",
    r"\bkeep(ing)? your job\b",
    r"\bwhile employed\b",
    r"\bfull[- ]time job\b",
    r"\bevenings?\b",
    r"\bweekends?\b",
    r"\bmoonlight\b",
    r"\bquit\b",
    r"\bgive notice\b",
    r"\bcpa\b",
    r"\baccount(ant|ing)\b",
    r"\bbookkeeping\b",
    r"\btax prep\b",
  ],
  "career_transition": [
    r"\bfractional\b",
    r"\bconsult(ing|ant|ancy)\b",
    r"\badvis(or|ory)\b",
    r"\brecruit(er|ing)\b",
    r"\blawyer\b",
    r"\battorney\b",
    r"\bcfo\b",
    r"\bagency\b",
    r"\boperator\b",
    r"\bretainer\b",
    r"\bclients?\b",
    r"\bside business\b",
    r"\bside hustle\b",
    r"\bindependent\b",
  ],
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = PROJECT_ROOT / "content" / "chat"


@dataclass(frozen=True)
class KnowledgeChunk:
  id: str
  title: str
  body: str
  tags: tuple[str, ...]
  focus: tuple[str, ...]
  phrases: tuple[str, ...] = ()
  source: str = ""


def _fallback_chunks() -> list[KnowledgeChunk]:
  return [
    KnowledgeChunk(
      id="F1",
      title="Magnio fallback positioning",
      body=(
        "Magnio focuses on automation, rapid builds, production-ready systems, "
        "and practical AI immersion guidance."
      ),
      tags=("positioning", "automation", "ai"),
      focus=("fit", "ai_immersion"),
      phrases=("production-ready systems",),
      source="fallback",
    ),
    KnowledgeChunk(
      id="F2",
      title="Magnio fallback delivery",
      body=(
        "The preferred approach is to understand the workflow, shape the data, "
        "and then automate the highest-friction path instead of adding AI to a broken process."
      ),
      tags=("workflow", "delivery", "guardrails"),
      focus=("operations", "ai_immersion"),
      phrases=("highest-friction path",),
      source="fallback",
    ),
  ]


def _coerce_string_list(value: Any) -> tuple[str, ...]:
  if not isinstance(value, list):
    return ()
  return tuple(str(item).strip() for item in value if str(item).strip())


def _chunk_from_dict(item: dict[str, Any], source: str) -> KnowledgeChunk:
  return KnowledgeChunk(
    id=str(item["id"]).strip(),
    title=str(item["title"]).strip(),
    body=str(item["body"]).strip(),
    tags=_coerce_string_list(item.get("tags")),
    focus=_coerce_string_list(item.get("focus")),
    phrases=_coerce_string_list(item.get("phrases")),
    source=source,
  )


def _load_chunks_from_files() -> list[KnowledgeChunk]:
  files = sorted(CONTENT_DIR.glob("*.json"))
  if not files:
    return _fallback_chunks()

  chunks: list[KnowledgeChunk] = []
  for path in files:
    try:
      raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
      continue

    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
      continue

    for item in items:
      if not isinstance(item, dict):
        continue
      try:
        chunks.append(_chunk_from_dict(item, path.name))
      except Exception:
        continue

  return chunks or _fallback_chunks()


def _normalize_text(text: str) -> str:
  return re.sub(r"\s+", " ", text.lower()).strip()


def _tokenize(text: str) -> list[str]:
  return [
    token
    for token in re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower())
    if token not in STOPWORDS and len(token) > 1
  ]


def _expand_terms(tokens: Iterable[str]) -> set[str]:
  expanded = set(tokens)
  for token in list(expanded):
    expanded.update(TERM_EXPANSIONS.get(token, set()))
  return expanded


def _detect_focus(query: str) -> set[str]:
  normalized = _normalize_text(query)
  hits: set[str] = set()
  for focus, patterns in FOCUS_PATTERNS.items():
    if any(re.search(pattern, normalized) for pattern in patterns):
      hits.add(focus)
  return hits


KNOWLEDGE_BASE = _load_chunks_from_files()

_INDEX: list[dict[str, object]] = []
for chunk in KNOWLEDGE_BASE:
  title_tokens = _tokenize(chunk.title)
  body_tokens = _tokenize(chunk.body)
  _INDEX.append(
    {
      "chunk": chunk,
      "title_counts": Counter(title_tokens),
      "body_counts": Counter(body_tokens),
      "tag_set": set(chunk.tags),
      "focus_set": set(chunk.focus),
      "term_set": set(title_tokens) | set(body_tokens) | set(chunk.tags),
      "normalized_body": _normalize_text(chunk.body),
    }
  )


def hybrid_search(
  query: str,
  *,
  limit: int = 4,
  preferred_focus: Iterable[str] | None = None,
  preferred_chunk_ids: Iterable[str] | None = None,
  preferred_sources: Iterable[str] | None = None,
) -> list[dict[str, object]]:
  query_tokens = _tokenize(query)
  query_terms = _expand_terms(query_tokens)
  query_focus = _detect_focus(query)
  normalized_query = _normalize_text(query)
  preferred_focus_set = {str(item).strip() for item in (preferred_focus or []) if str(item).strip()}
  preferred_chunk_id_set = {str(item).strip() for item in (preferred_chunk_ids or []) if str(item).strip()}
  preferred_source_set = {str(item).strip() for item in (preferred_sources or []) if str(item).strip()}

  scored: list[dict[str, object]] = []
  for item in _INDEX:
    chunk = item["chunk"]
    title_counts = item["title_counts"]
    body_counts = item["body_counts"]
    tag_set = item["tag_set"]
    focus_set = item["focus_set"]
    term_set = item["term_set"]
    normalized_body = item["normalized_body"]

    assert isinstance(chunk, KnowledgeChunk)

    title_hits = sum(title_counts.get(term, 0) for term in query_terms)
    body_hits = sum(body_counts.get(term, 0) for term in query_terms)
    lexical_score = (title_hits * 2.8) + (body_hits * 1.15)
    tag_score = sum(1 for tag in tag_set if tag in query_terms) * 3.0
    focus_score = sum(1 for focus in focus_set if focus in query_focus) * 3.4
    coverage_score = len(term_set.intersection(query_terms)) * 0.35
    phrase_score = sum(
      1 for phrase in chunk.phrases if phrase and phrase in normalized_query
    ) * 4.0
    body_phrase_score = sum(
      1
      for phrase in chunk.phrases
      if phrase and phrase in normalized_body and phrase in normalized_query
    ) * 0.8
    preferred_focus_score = (
      sum(1 for focus in focus_set if focus in preferred_focus_set) * 8.0
      if preferred_focus_set
      else 0.0
    )
    preferred_chunk_score = 12.0 if chunk.id in preferred_chunk_id_set else 0.0
    preferred_source_score = 6.0 if chunk.source in preferred_source_set else 0.0

    score = (
      lexical_score
      + tag_score
      + focus_score
      + coverage_score
      + phrase_score
      + body_phrase_score
      + preferred_focus_score
      + preferred_chunk_score
      + preferred_source_score
    )
    if score <= 0:
      continue

    scored.append(
      {
        "id": chunk.id,
        "title": chunk.title,
        "body": chunk.body,
        "tags": list(chunk.tags),
        "score": round(score, 2),
        "source": chunk.source,
      }
    )

  if not scored:
    fallback_ids = {"K1", "K3", "K10", "K11"}
    return [
      {
        "id": chunk.id,
        "title": chunk.title,
        "body": chunk.body,
        "tags": list(chunk.tags),
        "score": 0.0,
        "source": chunk.source,
      }
      for chunk in KNOWLEDGE_BASE
      if chunk.id in fallback_ids
    ][:limit]

  scored.sort(key=lambda item: float(item["score"]), reverse=True)
  return scored[:limit]


def build_context(chunks: list[dict[str, object]]) -> str:
  parts: list[str] = []
  for chunk in chunks:
    parts.append(f"[{chunk['id']}] {chunk['title']}\n{chunk['body']}")
  return "\n\n".join(parts)
