#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from api.model_rankings import load_model_rankings, save_model_rankings
from api.openrouter_benchmark import (
  BENCHMARK_PROMPTS,
  DEFAULT_JUDGE_MODEL,
  now_iso,
  score_benchmark_run,
  should_promote_category,
)
from api.openrouter_client import openrouter_configured


def main() -> int:
  parser = argparse.ArgumentParser(description="Benchmark OpenRouter models and write category rankings.")
  parser.add_argument("--categories", nargs="*", default=sorted(BENCHMARK_PROMPTS.keys()))
  parser.add_argument("--candidate-count", type=int, default=5)
  parser.add_argument("--prompts-per-category", type=int, default=None)
  parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
  parser.add_argument("--min-prompt-count", type=int, default=2)
  parser.add_argument("--min-win-rate-delta", type=float, default=0.05)
  parser.add_argument("--max-avg-latency-ms", type=float, default=None)
  parser.add_argument("--max-avg-estimated-cost", type=float, default=None)
  parser.add_argument("--dry-run", action="store_true")
  args = parser.parse_args()

  if not openrouter_configured():
    raise SystemExit("OpenRouter is not configured. Set MAGNIO_OPENROUTER_API_KEY or OPENROUTER_API_KEY.")

  current_payload = load_model_rankings()
  next_payload = {
    "version": 2,
    "generatedAt": now_iso(),
    "judgeModelId": args.judge_model,
    "categories": dict(current_payload.get("categories") or {}),
  }
  failures: list[dict[str, str]] = []

  for category in args.categories:
    try:
      challenger = score_benchmark_run(
        category,
        candidate_count=max(2, args.candidate_count),
        judge_model=args.judge_model,
        prompts_per_category=max(1, args.prompts_per_category) if args.prompts_per_category else None,
      )
    except Exception as exc:
      failures.append({"category": category, "error": str(exc)})
      print(f"[benchmark] {category}: failed | error={exc}")
      continue
    current_entry = (next_payload["categories"] or {}).get(category)
    should_promote, reason = should_promote_category(
      current_entry,
      challenger,
      min_prompt_count=max(1, args.min_prompt_count),
      min_win_rate_delta=max(0.0, args.min_win_rate_delta),
      max_avg_latency_ms=args.max_avg_latency_ms,
      max_avg_estimated_cost=args.max_avg_estimated_cost,
    )

    challenger["promotionDecision"] = {
      "accepted": should_promote,
      "reason": reason,
    }

    if should_promote:
      next_payload["categories"][category] = challenger

    top_model = (challenger.get("rankedModels") or [{}])[0].get("id")
    print(f"[benchmark] {category}: top model = {top_model} | promote={should_promote} | reason={reason}")

  if args.dry_run:
    print("[benchmark] dry-run enabled; rankings were not written")
    if failures:
      print(f"[benchmark] dry-run completed with {len(failures)} category failure(s)")
    return 0

  output_path = save_model_rankings(next_payload)
  print(f"[benchmark] wrote rankings to {output_path}")
  if failures:
    print(f"[benchmark] completed with {len(failures)} category failure(s)")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
