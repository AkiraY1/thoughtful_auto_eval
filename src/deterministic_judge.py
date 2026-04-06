"""Deterministically judge extracted OpenAI-style messages with llm_api.infer."""

from __future__ import annotations

import argparse
import json
import shutil
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


def _is_openai_message(obj: Any) -> bool:
    return isinstance(obj, dict) and "role" in obj and "content" in obj


def _normalize_messages_output(raw: Any) -> list[dict[str, Any]]:
    """
    Normalize parser output into per-item message blocks.

    Accepted shapes:
    - [{"role": "...", "content": "..."}]  # one block per message
    - [[{...}, {...}], ...]                 # one block per list
    - [{"messages": [{...}, ...]}, ...]     # one block per object
    """
    if not isinstance(raw, list):
        raise ValueError("extracted_messages.json must be a JSON list.")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        response_id = str(idx)
        messages: list[dict[str, Any]] = []

        if _is_openai_message(item):
            messages = [item]
        elif isinstance(item, list):
            if not all(_is_openai_message(x) for x in item):
                raise ValueError(
                    f"Item {idx} is a list, but not all entries are OpenAI-style messages."
                )
            messages = item
        elif isinstance(item, dict) and isinstance(item.get("messages"), list):
            if "response_id" in item:
                response_id = str(item["response_id"])
            if not all(_is_openai_message(x) for x in item["messages"]):
                raise ValueError(
                    f"Item {idx} has 'messages', but entries are not OpenAI-style messages."
                )
            messages = item["messages"]
        else:
            raise ValueError(
                f"Unsupported item shape at index {idx}; expected message, list of messages, or object with 'messages'."
            )

        normalized.append({"response_id": response_id, "messages": messages})

    return normalized


def _run_parser(parser_script: Path, responses_json: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        temp_parser = temp_dir / "parse_responses.py"
        temp_input = temp_dir / "responses.json"
        extracted_path = temp_dir / "extracted_messages.json"

        shutil.copy2(parser_script, temp_parser)
        shutil.copy2(responses_json, temp_input)

        # Contract expected from the generated parser:
        #   python3 parse_responses.py
        # It should read responses.json and write extracted_messages.json.
        cmd = [sys.executable, str(temp_parser)]
        result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "Parser script failed.\n"
                f"Command: {' '.join(cmd)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        if result.stdout.strip() or result.stderr.strip():
            raise RuntimeError(
                "Parser script produced stdout/stderr output, but it should be silent on success.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        if not extracted_path.exists():
            raise FileNotFoundError(
                f"Parser did not write expected output file: {extracted_path}"
            )

        extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
        return _normalize_messages_output(extracted)


def _messages_to_block_text(messages: list[dict[str, Any]]) -> str:
    lines = []
    for msg in messages:
        role = str(msg.get("role", "")).strip() or "unknown"
        content = str(msg.get("content", "")).strip()
        lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def _build_user_prompt(rubric: str, message_block_text: str) -> str:
    return (
        "Apply the rubric below to evaluate this single extracted message block.\n\n"
        "RUBRIC:\n"
        "-----\n"
        f"{rubric}\n"
        "-----\n\n"
        "MESSAGE BLOCK TO EVALUATE:\n"
        "-----\n"
        f"{message_block_text}\n"
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
        messages = item["messages"]
        message_block_text = _messages_to_block_text(messages)
        judge_output = infer(
            model=args.model,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(rubric_text, message_block_text),
            temperature=0.0,
            top_p=1.0,
            max_tokens=args.max_tokens,
        )
        judged.append(
            {
                "response_id": response_id,
                "messages": messages,
                "judge_output": judge_output,
            }
        )

    output_path = Path(args.output_json).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(judged, indent=2), encoding="utf-8")
    print(f"Wrote {len(judged)} judgments to {output_path}")


if __name__ == "__main__":
    main()
