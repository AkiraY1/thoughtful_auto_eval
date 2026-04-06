"""Deterministically judge each item in a JSON list with llm_api.infer."""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--rubric", required=True, help="Path to rubric.txt.")
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


def _build_user_prompt(rubric: str, item_text: str) -> str:
    return (
        "Apply the rubric below to evaluate this single item.\n\n"
        "RUBRIC:\n"
        "-----\n"
        f"{rubric}\n"
        "-----\n\n"
        "ITEM TO EVALUATE:\n"
        "-----\n"
        f"{item_text}\n"
        "-----\n\n"
        "Return JSON only with keys:\n"
        "- score (number)\n"
        "- rationale (string)\n"
        "- rubric_alignment (string)"
    )


def main() -> None:
    args = _parse_args()
    rubric_path = _require_file(args.rubric, "Rubric")
    input_path = _require_file(args.input_json, "Input JSON")

    rubric_text = rubric_path.read_text(encoding="utf-8").strip()
    if not rubric_text:
        raise ValueError(f"Rubric file is empty: {rubric_path}")

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Input JSON must be a top-level list.")

    judged: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        item_text = json.dumps(item, ensure_ascii=False, indent=2)
        judge_output = infer(
            model=args.model,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(rubric_text, item_text),
            temperature=0.0,
            top_p=1.0,
            max_tokens=args.max_tokens,
        )
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
