"""Deterministically judge parsed responses using a rubric and llm_api.infer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
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
        description="Run deterministic per-response judging from rubric + parser script."
    )
    parser.add_argument("--responses-json", required=True, help="Path to raw responses JSON.")
    parser.add_argument("--parser-script", required=True, help="Path to parse_responses.py.")
    parser.add_argument("--rubric", required=True, help="Path to rubric.txt.")
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write judged responses JSON.",
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


def _run_parser(parser_script: Path, responses_json: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as td:
        parsed_path = Path(td) / "parsed_responses.json"

        # Contract expected from the generated parser:
        #   python parse_responses.py --input <responses_json> --output <parsed_path>
        cmd = [
            sys.executable,
            str(parser_script),
            "--input",
            str(responses_json),
            "--output",
            str(parsed_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "Parser script failed.\n"
                f"Command: {' '.join(cmd)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        if not parsed_path.exists():
            raise FileNotFoundError(
                f"Parser did not write output file: {parsed_path}"
            )

        parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
        if not isinstance(parsed, list):
            raise ValueError("Parsed output must be a JSON list.")

        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(parsed):
            if isinstance(item, dict):
                response_id = str(item.get("response_id", idx))
                response_text = str(item.get("response_text", "")).strip()
            else:
                response_id = str(idx)
                response_text = str(item).strip()
            if not response_text:
                continue
            normalized.append(
                {
                    "response_id": response_id,
                    "response_text": response_text,
                }
            )
        return normalized


def _build_user_prompt(rubric: str, response_text: str) -> str:
    return (
        "Apply the rubric below to evaluate this single model response.\n\n"
        "RUBRIC:\n"
        "-----\n"
        f"{rubric}\n"
        "-----\n\n"
        "MODEL RESPONSE TO EVALUATE:\n"
        "-----\n"
        f"{response_text}\n"
        "-----\n\n"
        "Return JSON only with keys:\n"
        "- score (number)\n"
        "- rationale (string)\n"
        "- rubric_alignment (string)"
    )


def main() -> None:
    args = _parse_args()
    responses_json = _require_file(args.responses_json, "Responses JSON")
    parser_script = _require_file(args.parser_script, "Parser script")
    rubric_path = _require_file(args.rubric, "Rubric")

    rubric_text = rubric_path.read_text(encoding="utf-8").strip()
    if not rubric_text:
        raise ValueError(f"Rubric file is empty: {rubric_path}")

    parsed = _run_parser(parser_script=parser_script, responses_json=responses_json)
    judged: list[dict[str, Any]] = []

    for item in parsed:
        response_id = item["response_id"]
        response_text = item["response_text"]
        judge_output = infer(
            model=args.model,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(rubric_text, response_text),
            temperature=0.0,
            top_p=1.0,
            max_tokens=args.max_tokens,
        )
        judged.append(
            {
                "response_id": response_id,
                "response_text": response_text,
                "judge_output": judge_output,
            }
        )

    output_path = Path(args.output_json).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(judged, indent=2), encoding="utf-8")
    print(f"Wrote {len(judged)} judgments to {output_path}")


if __name__ == "__main__":
    main()
