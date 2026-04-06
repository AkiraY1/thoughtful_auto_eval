#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 /path/to/rubric.txt /path/to/input_list.json /path/to/output.json [model]"
  exit 1
fi

RUBRIC_PATH="$1"
INPUT_JSON_PATH="$2"
OUTPUT_JSON_PATH="$3"
MODEL_NAME="${4:-claude-opus-4-1}"

if [[ ! -f "$RUBRIC_PATH" ]]; then
  echo "Rubric file not found: $RUBRIC_PATH"
  exit 1
fi

if [[ ! -f "$INPUT_JSON_PATH" ]]; then
  echo "Input JSON file not found: $INPUT_JSON_PATH"
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set."
  echo "Export one of them before running this script."
  exit 1
fi

python3 src/deterministic_judge_list.py \
  --rubric "$RUBRIC_PATH" \
  --input-json "$INPUT_JSON_PATH" \
  --output-json "$OUTPUT_JSON_PATH" \
  --model "$MODEL_NAME"
