from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any


def _load_google_genai():
  try:
    from google import genai
    from google.genai import types
  except ImportError as exc:
    raise RuntimeError(
      "google-genai is not installed. Add it to api/requirements.txt and reinstall backend dependencies."
    ) from exc

  return genai, types


def resolve_vertex_project() -> str:
  return (
    os.environ.get("MAGNIO_VERTEX_PROJECT", "").strip()
    or os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
  )


def resolve_vertex_location() -> str:
  return (
    os.environ.get("MAGNIO_VERTEX_LOCATION", "").strip()
    or os.environ.get("GOOGLE_CLOUD_LOCATION", "").strip()
    or "global"
  )


def resolve_vertex_api_version() -> str:
  return os.environ.get("MAGNIO_VERTEX_API_VERSION", "").strip() or "v1"


def vertex_configured() -> bool:
  return bool(resolve_vertex_project())


@lru_cache(maxsize=1)
def _get_client():
  project = resolve_vertex_project()
  if not project:
    raise RuntimeError("Vertex AI project is not configured. Set MAGNIO_VERTEX_PROJECT or GOOGLE_CLOUD_PROJECT.")

  genai, types = _load_google_genai()
  return genai.Client(
    vertexai=True,
    project=project,
    location=resolve_vertex_location(),
    http_options=types.HttpOptions(api_version=resolve_vertex_api_version()),
  )


def _coerce_text(value: Any) -> str:
  if isinstance(value, str):
    return value.strip()

  if isinstance(value, list):
    parts: list[str] = []
    for item in value:
      if isinstance(item, str):
        clean = item.strip()
        if clean:
          parts.append(clean)
        continue
      if not isinstance(item, dict):
        continue
      if item.get("type") not in {"text", "output_text"}:
        continue
      clean = str(item.get("text") or item.get("content") or "").strip()
      if clean:
        parts.append(clean)
    return "\n".join(parts).strip()

  if isinstance(value, dict):
    return str(value.get("text") or value.get("content") or "").strip()

  return str(value).strip()


def _messages_to_vertex(messages: list[dict[str, Any]]):
  _, types = _load_google_genai()
  system_parts: list[str] = []
  contents: list[Any] = []

  for message in messages:
    role = str(message.get("role") or "user").strip().lower()
    text = _coerce_text(message.get("content"))
    if not text:
      continue

    if role == "system":
      system_parts.append(text)
      continue

    vertex_role = "model" if role == "assistant" else "user"
    contents.append(
      types.Content(
        role=vertex_role,
        parts=[types.Part.from_text(text=text)],
      )
    )

  if not contents:
    raise ValueError("At least one non-system message is required for Vertex AI generation.")

  system_instruction = "\n\n".join(part for part in system_parts if part).strip() or None
  return system_instruction, contents


def _usage_dict(response: Any) -> dict[str, Any]:
  usage = getattr(response, "usage_metadata", None)
  if usage is None:
    return {}

  return {
    "prompt_tokens": getattr(usage, "prompt_token_count", None),
    "completion_tokens": getattr(usage, "candidates_token_count", None),
    "total_tokens": getattr(usage, "total_token_count", None),
  }


def vertex_generate_content(
  *,
  model: str,
  messages: list[dict[str, Any]],
  temperature: float | None = None,
  max_tokens: int | None = None,
  response_mime_type: str | None = None,
  response_json_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
  system_instruction, contents = _messages_to_vertex(messages)
  config: dict[str, Any] = {}

  if system_instruction:
    config["system_instruction"] = system_instruction
  if temperature is not None:
    config["temperature"] = temperature
  if max_tokens is not None:
    config["max_output_tokens"] = max_tokens
  if response_mime_type:
    config["response_mime_type"] = response_mime_type
  if response_json_schema:
    config["response_json_schema"] = response_json_schema

  response = _get_client().models.generate_content(
    model=model,
    contents=contents,
    config=config or None,
  )

  text = getattr(response, "text", None)
  parsed = getattr(response, "parsed", None)
  if hasattr(parsed, "model_dump"):
    parsed = parsed.model_dump(mode="json")

  return {
    "text": text.strip() if isinstance(text, str) else "",
    "parsed": parsed,
    "usage": _usage_dict(response),
  }


def vertex_extract_json(payload: dict[str, Any]) -> dict[str, Any]:
  parsed = payload.get("parsed")
  if isinstance(parsed, dict):
    return parsed

  text = str(payload.get("text") or "").strip()
  if not text:
    raise RuntimeError("Vertex AI returned an empty JSON response.")

  try:
    decoded = json.loads(text)
  except json.JSONDecodeError as exc:
    raise RuntimeError("Vertex AI returned malformed JSON.") from exc

  if not isinstance(decoded, dict):
    raise RuntimeError("Vertex AI returned JSON that was not an object.")

  return decoded
