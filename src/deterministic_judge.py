"""Deterministically judge each item in a JSON list with llm_api.infer."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from llm_api import infer

DEFAULT_MODEL = "claude-opus-4-1"

JUDGE_SYSTEM_PROMPT = (
    "You are a strict, consistent evaluator. Apply the given rubric exactly. "
    "Return concise judgments with explicit scores and rationale."
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic judging on each object in a JSON list."
    )
    parser.add_argument("--rubric", required=True, help="Path to rubric.json.")
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to input JSON file. Must be a top-level list.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write judged outputs JSON.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Judge model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=700,
        help="Max generation tokens per judgment.",
    )
    return parser.parse_args()


def _require_file(path_str: str, label: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")
    return path


def _load_criteria(rubric_path: Path) -> list[dict[str, Any]]:
    raw = json.loads(rubric_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("rubric.json must be a non-empty JSON list of criteria.")

    criteria: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"rubric[{idx}] must be an object.")
        if "criterion" not in item or "scale" not in item:
            raise ValueError(f"rubric[{idx}] must include 'criterion' and 'scale'.")
        criterion = str(item["criterion"]).strip()
        scale = item["scale"]
        if not criterion:
            raise ValueError(f"rubric[{idx}].criterion must be non-empty.")
        if (
            not isinstance(scale, list)
            or len(scale) != 2
            or not all(isinstance(x, (int, float)) for x in scale)
        ):
            raise ValueError(
                f"rubric[{idx}].scale must be [min,max] with numeric values."
            )
        min_score = float(scale[0])
        max_score = float(scale[1])
        if min_score >= max_score:
            raise ValueError(f"rubric[{idx}].scale must satisfy min < max.")
        criteria.append(
            {"criterion": criterion, "scale": [min_score, max_score]}
        )
    return criteria


def _build_reasoning_prompt(criterion: str, scale: list[float], item_text: str) -> str:
    return (
        "You are on turn 1 of 2.\n"
        "Evaluate this single item for ONE criterion only.\n"
        "Think step-by-step and provide your reasoning only.\n"
        "Do not provide a final numeric score yet.\n\n"
        "CRITERION:\n"
        "-----\n"
        f"{criterion}\n"
        f"Allowed score range: {scale[0]} to {scale[1]}.\n"
        "-----\n\n"
        "ITEM TO EVALUATE:\n"
        "-----\n"
        f"{item_text}\n"
        "-----\n"
    )


def _build_score_prompt(reasoning: str, criterion: str, scale: list[float]) -> str:
    return (
        "You are on turn 2 of 2.\n"
        "Given your prior reasoning below, provide only the final numeric score for this criterion.\n"
        f"Criterion: {criterion}\n"
        f"Allowed score range: {scale[0]} to {scale[1]}.\n"
        "Return exactly one line in this format: SCORE: <number>\n\n"
        "PRIOR REASONING:\n"
        "-----\n"
        f"{reasoning}\n"
        "-----\n"
    )


def _extract_score(text: str) -> float | None:
    match = re.search(r"SCORE:\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))

    # Fallback: first numeric token in the response.
    fallback = re.search(r"-?\d+(?:\.\d+)?", text)
    if fallback:
        return float(fallback.group(0))
    return None


def main() -> None:
    args = _parse_args()
    rubric_path = _require_file(args.rubric, "Rubric")
    input_path = _require_file(args.input_json, "Input JSON")

    criteria = _load_criteria(rubric_path)

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Input JSON must be a top-level list.")

    judged: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        item_text = json.dumps(item, ensure_ascii=False, indent=2)
        criterion_results: list[dict[str, Any]] = []
        final_score = 0.0

        for criterion_item in criteria:
            criterion = str(criterion_item["criterion"])
            scale = criterion_item["scale"]
            reasoning = infer(
                model=args.model,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                user_prompt=_build_reasoning_prompt(criterion, scale, item_text),
                temperature=0.0,
                top_p=1.0,
                max_tokens=args.max_tokens,
            )
            score_raw = infer(
                model=args.model,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                user_prompt=_build_score_prompt(reasoning, criterion, scale),
                temperature=0.0,
                top_p=1.0,
                max_tokens=80,
            )
            score = _extract_score(score_raw)
            if score is None:
                score = 0.0
            # Enforce declared scale bounds.
            score = max(float(scale[0]), min(float(scale[1]), float(score)))
            final_score += score

            criterion_results.append(
                {
                    "criterion": criterion,
                    "scale": scale,
                    "reasoning": reasoning.strip(),
                    "score": score,
                    "score_raw": score_raw.strip(),
                }
            )

        judge_output = {
            "criteria_results": criterion_results,
            "final_score": final_score,
        }
        judged.append(
            {
                "item_index": idx,
                "item": item,
                "judge_output": judge_output,
            }
        )

    output_path = Path(args.output_json).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(judged, indent=2), encoding="utf-8")
    print(f"Wrote {len(judged)} judgments to {output_path}")


if __name__ == "__main__":
    main()
