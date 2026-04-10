import json
import os
import threading
import time
from collections.abc import Iterator
from typing import Any, Dict, Optional

import requests

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 0.75
RETRIABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}
RETRIABLE_REQUEST_EXCEPTIONS = (
  requests.exceptions.SSLError,
  requests.exceptions.ConnectionError,
  requests.exceptions.Timeout,
)

_MODELS_CACHE_LOCK = threading.Lock()
_MODELS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _build_headers(*, require_auth: bool, json_content: bool = True) -> dict[str, str]:
  api_key = (
    os.environ.get("MAGNIO_OPENROUTER_API_KEY", "").strip()
    or os.environ.get("OPENROUTER_API_KEY", "").strip()
  )

  if require_auth and not api_key:
    raise RuntimeError(
      "Missing OpenRouter API key. Set MAGNIO_OPENROUTER_API_KEY or OPENROUTER_API_KEY."
    )

  headers: dict[str, str] = {}
  if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
  if json_content:
    headers["Content-Type"] = "application/json"

  referer = (
    os.environ.get("MAGNIO_OPENROUTER_REFERER", "").strip()
    or os.environ.get("OPENROUTER_HTTP_REFERER", "").strip()
    or "http://localhost:5173"
  )
  title = os.environ.get("MAGNIO_OPENROUTER_TITLE", "").strip() or "Magnio Chat"

  if referer:
    headers["HTTP-Referer"] = referer
  if title:
    headers["X-Title"] = title

  return headers


def openrouter_configured() -> bool:
  return bool(
    os.environ.get("MAGNIO_OPENROUTER_API_KEY", "").strip()
    or os.environ.get("OPENROUTER_API_KEY", "").strip()
  )


def _resolve_retry_count() -> int:
  raw = os.environ.get("MAGNIO_OPENROUTER_MAX_RETRIES", "").strip()
  if not raw:
    return DEFAULT_MAX_RETRIES
  try:
    return max(0, int(raw))
  except ValueError:
    return DEFAULT_MAX_RETRIES


def _retry_delay_seconds(attempt_index: int) -> float:
  base = DEFAULT_RETRY_BACKOFF_SECONDS
  return base * (2 ** attempt_index)


def _request_with_retries(
  method: str,
  url: str,
  *,
  timeout: float,
  retry_count: int | None = None,
  **kwargs: Any,
) -> requests.Response:
  retries = _resolve_retry_count() if retry_count is None else max(0, retry_count)
  last_exc: Exception | None = None

  for attempt in range(retries + 1):
    try:
      response = requests.request(method, url, timeout=timeout, **kwargs)
    except RETRIABLE_REQUEST_EXCEPTIONS as exc:
      last_exc = exc
      if attempt >= retries:
        raise
      time.sleep(_retry_delay_seconds(attempt))
      continue

    if response.status_code in RETRIABLE_STATUS_CODES and attempt < retries:
      response.close()
      time.sleep(_retry_delay_seconds(attempt))
      continue

    return response

  if last_exc:
    raise last_exc
  raise RuntimeError("OpenRouter request failed before a response was available.")


def list_models(category: Optional[str] = None, *, ttl_seconds: int = 900) -> list[dict[str, Any]]:
  cache_key = (category or "__all__").lower()
  now = time.time()

  with _MODELS_CACHE_LOCK:
    cached = _MODELS_CACHE.get(cache_key)
    if cached and cached[0] > now:
      return cached[1]

  params: dict[str, str] = {"output_modalities": "text"}
  if category:
    params["category"] = category

  response = _request_with_retries(
    "GET",
    f"{OPENROUTER_API_BASE}/models",
    headers=_build_headers(require_auth=False, json_content=False),
    params=params,
    timeout=30,
  )
  if not response.ok:
    raise RuntimeError(
      f"OpenRouter model listing failed ({response.status_code}): {response.text[:300]}"
    )

  payload = response.json()
  models = payload.get("data") or []

  with _MODELS_CACHE_LOCK:
    _MODELS_CACHE[cache_key] = (now + ttl_seconds, models)

  return models


def chat_completion(
  *,
  messages: list[dict[str, Any]],
  model: Optional[str] = None,
  models: Optional[list[str]] = None,
  temperature: Optional[float] = None,
  max_tokens: Optional[int] = None,
  provider: Optional[dict[str, Any]] = None,
  response_format: Optional[dict[str, Any]] = None,
  plugins: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
  if not model and not models:
    raise ValueError("Either model or models must be provided.")

  payload: dict[str, Any] = {"messages": messages}
  if models:
    payload["models"] = models
  else:
    payload["model"] = model
  if temperature is not None:
    payload["temperature"] = temperature
  if max_tokens is not None:
    payload["max_tokens"] = max_tokens
  if provider:
    payload["provider"] = provider
  if response_format:
    payload["response_format"] = response_format
  if plugins:
    payload["plugins"] = plugins

  response = _request_with_retries(
    "POST",
    f"{OPENROUTER_API_BASE}/chat/completions",
    headers=_build_headers(require_auth=True),
    json=payload,
    timeout=90,
  )
  if not response.ok:
    raise RuntimeError(
      f"OpenRouter chat completion failed ({response.status_code}): {response.text[:500]}"
    )
  return response.json()


def _coerce_delta_text(value: Any) -> str:
  if isinstance(value, str):
    return value

  if isinstance(value, list):
    parts: list[str] = []
    for item in value:
      if isinstance(item, str):
        parts.append(item)
        continue
      if not isinstance(item, dict):
        continue
      if item.get("type") not in {"text", "output_text"}:
        continue
      text = str(item.get("text") or item.get("content") or "")
      if text:
        parts.append(text)
    return "".join(parts)

  if isinstance(value, dict):
    return str(value.get("text") or value.get("content") or "")

  return ""


def chat_completion_stream(
  *,
  messages: list[dict[str, Any]],
  model: Optional[str] = None,
  models: Optional[list[str]] = None,
  temperature: Optional[float] = None,
  max_tokens: Optional[int] = None,
  provider: Optional[dict[str, Any]] = None,
) -> Iterator[str]:
  if not model and not models:
    raise ValueError("Either model or models must be provided.")

  payload: dict[str, Any] = {"messages": messages, "stream": True}
  if models:
    payload["models"] = models
  else:
    payload["model"] = model
  if temperature is not None:
    payload["temperature"] = temperature
  if max_tokens is not None:
    payload["max_tokens"] = max_tokens
  if provider:
    payload["provider"] = provider

  response = _request_with_retries(
    "POST",
    f"{OPENROUTER_API_BASE}/chat/completions",
    headers=_build_headers(require_auth=True),
    json=payload,
    timeout=120,
    stream=True,
  )
  if not response.ok:
    raise RuntimeError(
      f"OpenRouter chat completion failed ({response.status_code}): {response.text[:500]}"
    )

  for raw_line in response.iter_lines(decode_unicode=False):
    if not raw_line:
      continue

    try:
      line = raw_line.decode("utf-8")
    except UnicodeDecodeError:
      line = raw_line.decode("utf-8", errors="replace")

    if not line:
      continue
    if not line.startswith("data:"):
      continue

    data = line[5:].strip()
    if not data or data == "[DONE]":
      continue

    try:
      chunk = json.loads(data)
    except json.JSONDecodeError:
      continue

    choice = (chunk.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    text = _coerce_delta_text(delta.get("content"))
    if text:
      yield text


def extract_message_text(payload: dict[str, Any]) -> str:
  choice = (payload.get("choices") or [{}])[0]
  message = choice.get("message") or {}
  content = message.get("content")

  if isinstance(content, str):
    return content.strip()

  if isinstance(content, list):
    parts: list[str] = []
    for item in content:
      if isinstance(item, str):
        parts.append(item)
        continue
      if not isinstance(item, dict):
        continue
      if item.get("type") in {"text", "output_text"}:
        parts.append(str(item.get("text") or item.get("content") or "").strip())
    return "\n".join(part for part in parts if part).strip()

  return ""
