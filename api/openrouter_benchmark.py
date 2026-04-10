from __future__ import annotations

import json
import time
from typing import Any

from api.openrouter_client import chat_completion, extract_message_text, list_models

DEFAULT_JUDGE_MODEL = "openai/gpt-5.1"
FAST_PROVIDER_PREF = {"sort": "latency", "allow_fallbacks": True}

BENCHMARK_PROMPTS: dict[str, list[str]] = {
  "technical": [
    "Design a simple benchmark runner that rotates candidate LLMs, scores them, and writes ranked results to a config file.",
    "Debug why a React input loses focus after every keystroke when a nested component is recreated on render.",
  ],
  "business": [
    "A 12-person business runs operations through email and spreadsheets. Propose the first automation system to build, the architecture, and a 30-day rollout plan.",
    "Estimate the scope, stack, and delivery phases for a lightweight internal request-tracking tool for a 5-person team.",
  ],
  "legal": [
    "Is a contingent $30/hour contract fair for building an agentic LLM system with hybrid RAG? Answer practically and identify assumptions.",
    "What should a solo consultant check before signing a client NDA that includes broad IP assignment and confidentiality terms?",
  ],
  "travel": [
    "If a summer trip accidentally turned into Copenhagen, Oslo, or Helsinki, how would you choose based on vibe, logistics, and budget?",
    "Plan a 4-day city break in Europe for someone who wants walkability, design, and good cafes without extreme cost.",
  ],
  "advisor": [
    "What is the best first AI service I should offer as a solo consultant?",
    "How should a small business approach AI without creating operational chaos?",
  ],
}

CATEGORY_MODEL_DISCOVERY_MAP = {
  "technical": "technology",
  "business": "technology",
  "legal": "legal",
  "travel": "trivia",
  "advisor": "technology",
}


def now_iso() -> str:
  return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_float(value: Any) -> float | None:
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def _extract_model_metadata(item: dict[str, Any]) -> dict[str, Any]:
  pricing = item.get("pricing") or {}
  model_id = str(item.get("id") or "").strip()
  return {
    "id": model_id,
    "name": item.get("name") or model_id,
    "provider": model_id.split("/", 1)[0] if "/" in model_id else model_id,
    "contextLength": item.get("context_length") or item.get("contextLength"),
    "inputCostPerToken": _safe_float(pricing.get("prompt")) or _safe_float(pricing.get("input")),
    "outputCostPerToken": _safe_float(pricing.get("completion")) or _safe_float(pricing.get("output")),
    "architecture": item.get("architecture"),
    "topProvider": item.get("top_provider"),
    "perRequestLimits": item.get("per_request_limits"),
  }


def discover_models(
  category: str,
  *,
  candidate_count: int,
  max_input_cost_per_token: float | None = None,
  min_context_length: int = 0,
  allow_providers: set[str] | None = None,
  deny_providers: set[str] | None = None,
) -> list[dict[str, Any]]:
  openrouter_category = CATEGORY_MODEL_DISCOVERY_MAP.get(category, category)
  seen_providers: set[str] = set()
  candidates: list[dict[str, Any]] = []

  for item in list_models(openrouter_category):
    metadata = _extract_model_metadata(item)
    model_id = metadata["id"]
    if not model_id or ":free" in model_id:
      continue

    provider = metadata["provider"]
    if allow_providers and provider not in allow_providers:
      continue
    if deny_providers and provider in deny_providers:
      continue
    if provider in seen_providers:
      continue

    context_length = metadata.get("contextLength") or 0
    if min_context_length and context_length and int(context_length) < min_context_length:
      continue

    input_cost = metadata.get("inputCostPerToken")
    if max_input_cost_per_token is not None and input_cost is not None and input_cost > max_input_cost_per_token:
      continue

    candidates.append(metadata)
    seen_providers.add(provider)
    if len(candidates) >= candidate_count:
      break

  return candidates


def run_candidate(model_id: str, prompt: str) -> dict[str, Any]:
  started = time.perf_counter()
  try:
    payload = chat_completion(
      model=model_id,
      messages=[
        {
          "role": "system",
          "content": "Answer directly, practically, and with clear reasoning. Do not mention benchmarking.",
        },
        {"role": "user", "content": prompt},
      ],
      temperature=0.2,
      max_tokens=900,
      provider=FAST_PROVIDER_PREF,
    )
    answer = extract_message_text(payload)
    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = payload.get("usage") or {}
    return {
      "status": "ok",
      "modelId": model_id,
      "answer": answer,
      "latencyMs": latency_ms,
      "inputTokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
      "outputTokens": usage.get("completion_tokens") or usage.get("output_tokens"),
    }
  except Exception as exc:
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
      "status": "error",
      "modelId": model_id,
      "error": str(exc),
      "latencyMs": latency_ms,
    }


def estimate_run_cost(response: dict[str, Any], candidate: dict[str, Any]) -> float | None:
  input_cost = candidate.get("inputCostPerToken")
  output_cost = candidate.get("outputCostPerToken")
  input_tokens = response.get("inputTokens")
  output_tokens = response.get("outputTokens")
  if input_cost is None or output_cost is None or input_tokens is None or output_tokens is None:
    return None
  return float(input_tokens) * float(input_cost) + float(output_tokens) * float(output_cost)


def judge_prompt(category: str, prompt: str, responses: list[dict[str, Any]], *, judge_model: str) -> dict[str, Any]:
  candidates_block = []
  for item in responses:
    candidates_block.append(
      f"Model: {item['modelId']}\n"
      f"LatencyMs: {item.get('latencyMs')}\n"
      f"Answer:\n{item.get('answer', '')}\n"
    )

  payload = chat_completion(
    model=judge_model,
    messages=[
      {
        "role": "system",
        "content": (
          "You are benchmarking answer quality by category.\n"
          "Return valid JSON only with keys winnerModelId and scores.\n"
          "scores must be a list of objects with modelId, usefulness, groundedness, clarity, decisiveness, notes.\n"
          "Use 1-10 integer scores.\n"
        ),
      },
      {
        "role": "user",
        "content": (
          f"Category: {category}\n\n"
          f"Prompt:\n{prompt}\n\n"
          "Candidate responses:\n\n"
          + "\n---\n".join(candidates_block)
        ),
      },
    ],
    temperature=0,
    max_tokens=1400,
    provider=FAST_PROVIDER_PREF,
  )
  text = extract_message_text(payload).strip()
  try:
    return json.loads(text)
  except json.JSONDecodeError as exc:
    raise RuntimeError(f"Judge returned invalid JSON: {text[:400]}") from exc


def score_benchmark_run(
  category: str,
  *,
  candidate_count: int,
  judge_model: str,
  prompts_per_category: int | None = None,
  max_input_cost_per_token: float | None = None,
  min_context_length: int = 0,
) -> dict[str, Any]:
  prompts = BENCHMARK_PROMPTS.get(category)
  if not prompts:
    raise ValueError(f"No benchmark prompts configured for category '{category}'")
  if prompts_per_category is not None:
    prompts = prompts[: max(1, prompts_per_category)]

  print(f"[benchmark] discovering candidates for {category}")
  candidates = discover_models(
    category,
    candidate_count=candidate_count,
    max_input_cost_per_token=max_input_cost_per_token,
    min_context_length=min_context_length,
  )
  if len(candidates) < 2:
    raise RuntimeError(f"Not enough candidate models available for category '{category}'")
  print(f"[benchmark] {category}: discovered {len(candidates)} candidates")

  model_stats: dict[str, dict[str, Any]] = {
    item["id"]: {
      **item,
      "wins": 0,
      "scoreTotal": 0,
      "scoreCount": 0,
      "latencyTotalMs": 0,
      "latencyCount": 0,
      "promptCount": 0,
      "errors": 0,
      "estimatedCostTotal": 0.0,
      "estimatedCostCount": 0,
    }
    for item in candidates
  }
  prompt_runs: list[dict[str, Any]] = []

  for index, prompt in enumerate(prompts, start=1):
    print(f"[benchmark] {category}: prompt {index}/{len(prompts)}")
    responses = [run_candidate(item["id"], prompt) for item in candidates]
    successful = [item for item in responses if item["status"] == "ok" and item.get("answer")]
    for result in responses:
      stats = model_stats[result["modelId"]]
      stats["promptCount"] += 1
      stats["latencyTotalMs"] += result.get("latencyMs") or 0
      stats["latencyCount"] += 1
      if result["status"] != "ok":
        stats["errors"] += 1
        continue
      candidate = next((item for item in candidates if item["id"] == result["modelId"]), None)
      cost = estimate_run_cost(result, candidate or {})
      result["estimatedCost"] = cost
      if cost is not None:
        stats["estimatedCostTotal"] += cost
        stats["estimatedCostCount"] += 1

    if len(successful) < 2:
      prompt_runs.append({"prompt": prompt, "status": "insufficient_candidates", "responses": responses})
      print(f"[benchmark] {category}: prompt {index}/{len(prompts)} skipped, insufficient successful candidates")
      continue

    judged = judge_prompt(category, prompt, successful, judge_model=judge_model)
    winner_model_id = judged.get("winnerModelId")
    if winner_model_id in model_stats:
      model_stats[winner_model_id]["wins"] += 1

    scores = judged.get("scores") or []
    for score in scores:
      model_id = score.get("modelId")
      if model_id not in model_stats:
        continue
      total = int(score.get("usefulness", 0)) + int(score.get("groundedness", 0)) + int(score.get("clarity", 0)) + int(score.get("decisiveness", 0))
      model_stats[model_id]["scoreTotal"] += total
      model_stats[model_id]["scoreCount"] += 1

    prompt_runs.append(
      {
        "prompt": prompt,
        "status": "ok",
        "winnerModelId": winner_model_id,
        "responses": responses,
        "judge": judged,
      }
    )
    print(f"[benchmark] {category}: prompt {index}/{len(prompts)} winner = {winner_model_id}")

  ranked_models = []
  total_prompt_runs = len(prompts)
  for stats in model_stats.values():
    avg_score = (stats["scoreTotal"] / stats["scoreCount"]) if stats["scoreCount"] else 0.0
    avg_latency = (stats["latencyTotalMs"] / stats["latencyCount"]) if stats["latencyCount"] else None
    avg_cost = (stats["estimatedCostTotal"] / stats["estimatedCostCount"]) if stats["estimatedCostCount"] else None
    win_rate = (stats["wins"] / total_prompt_runs) if total_prompt_runs else 0.0
    ranked_models.append(
      {
        "id": stats["id"],
        "name": stats["name"],
        "provider": stats["provider"],
        "contextLength": stats.get("contextLength"),
        "inputCostPerToken": stats.get("inputCostPerToken"),
        "outputCostPerToken": stats.get("outputCostPerToken"),
        "wins": stats["wins"],
        "winRate": round(win_rate, 4),
        "score": round(avg_score, 2),
        "avgLatencyMs": round(avg_latency, 1) if avg_latency is not None else None,
        "avgEstimatedCost": round(avg_cost, 8) if avg_cost is not None else None,
        "promptCount": stats["promptCount"],
        "errors": stats["errors"],
      }
    )

  ranked_models.sort(
    key=lambda item: (
      item["score"],
      item["winRate"],
      -float(item["avgLatencyMs"] or 0),
      -float(item["avgEstimatedCost"] or 0),
    ),
    reverse=True,
  )

  return {
    "category": category,
    "generatedAt": now_iso(),
    "judgeModelId": judge_model,
    "candidateCount": len(candidates),
    "rankedModels": ranked_models,
    "promptRuns": prompt_runs,
  }


def should_promote_category(
  current_entry: dict[str, Any] | None,
  challenger_entry: dict[str, Any],
  *,
  min_prompt_count: int = 2,
  min_win_rate_delta: float = 0.05,
  max_avg_latency_ms: float | None = None,
  max_avg_estimated_cost: float | None = None,
) -> tuple[bool, str]:
  ranked = challenger_entry.get("rankedModels") or []
  if not ranked:
    return False, "no_ranked_models"

  top = ranked[0]
  if int(top.get("promptCount") or 0) < min_prompt_count:
    return False, "insufficient_prompt_count"
  if max_avg_latency_ms is not None and top.get("avgLatencyMs") is not None and float(top["avgLatencyMs"]) > max_avg_latency_ms:
    return False, "latency_over_limit"
  if max_avg_estimated_cost is not None and top.get("avgEstimatedCost") is not None and float(top["avgEstimatedCost"]) > max_avg_estimated_cost:
    return False, "cost_over_limit"

  if not current_entry:
    return True, "no_existing_ranking"

  current_ranked = current_entry.get("rankedModels") or []
  if not current_ranked:
    return True, "existing_ranking_empty"

  current_top = current_ranked[0]
  challenger_win_rate = float(top.get("winRate") or 0.0)
  current_win_rate = float(current_top.get("winRate") or 0.0)
  if top.get("id") == current_top.get("id"):
    return True, "same_top_model_refresh"
  if challenger_win_rate - current_win_rate < min_win_rate_delta:
    return False, "win_rate_delta_too_small"
  return True, "promotion_threshold_met"
