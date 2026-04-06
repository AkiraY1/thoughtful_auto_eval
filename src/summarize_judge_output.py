"""Summarize deterministic judge outputs and write back to output.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize judge output and rewrite output.json."
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to deterministic judge output.json.",
    )
    return parser.parse_args()


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    sorted_vals = sorted(values)
    rank = (len(sorted_vals) - 1) * p
    low = int(rank)
    high = min(low + 1, len(sorted_vals) - 1)
    frac = rank - low
    return float(sorted_vals[low] * (1.0 - frac) + sorted_vals[high] * frac)


def _coerce_judgments(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("judgments"), list):
        return raw["judgments"]
    raise ValueError("output.json must be a list or an object with a 'judgments' list.")


def main() -> None:
    args = _parse_args()
    output_path = Path(args.output_json).expanduser()
    if not output_path.exists():
        raise FileNotFoundError(f"Output file not found: {output_path}")

    raw = json.loads(output_path.read_text(encoding="utf-8"))
    judgments = _coerce_judgments(raw)

    final_scores: list[float] = []
    criterion_scores: dict[str, list[float]] = {}

    for item in judgments:
        judge_output = item.get("judge_output", {})
        final_score = judge_output.get("final_score")
        if isinstance(final_score, (int, float)):
            final_scores.append(float(final_score))

        criteria_results = judge_output.get("criteria_results", [])
        if isinstance(criteria_results, list):
            for result in criteria_results:
                if not isinstance(result, dict):
                    continue
                criterion = str(result.get("criterion", "")).strip()
                score = result.get("score")
                if not criterion or not isinstance(score, (int, float)):
                    continue
                criterion_scores.setdefault(criterion, []).append(float(score))

    item_count = len(judgments)
    mean_final_score = sum(final_scores) / len(final_scores) if final_scores else 0.0

    per_criterion_mean: dict[str, float] = {}
    for criterion, scores in criterion_scores.items():
        per_criterion_mean[criterion] = sum(scores) / len(scores) if scores else 0.0

    summary = {
        "item_count": item_count,
        "scored_item_count": len(final_scores),
        "mean_final_score": mean_final_score,
        "final_score_percentiles": {
            "p10": _percentile(final_scores, 0.10),
            "p25": _percentile(final_scores, 0.25),
            "p50": _percentile(final_scores, 0.50),
            "p75": _percentile(final_scores, 0.75),
            "p90": _percentile(final_scores, 0.90),
        },
        "per_criterion_mean": per_criterion_mean,
    }

    payload = {
        "summary": summary,
        "judgments": judgments,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Updated {output_path} with summary and {item_count} judgments.")


if __name__ == "__main__":
    main()
