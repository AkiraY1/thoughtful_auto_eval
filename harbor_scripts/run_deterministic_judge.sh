#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 5 ]]; then
  echo "Usage: $0 /path/to/rubric.txt /path/to/parse_responses.py /path/to/responses.json /path/to/output.json [model]"
  exit 1
fi

RUBRIC_PATH="$1"
PARSER_SCRIPT_PATH="$2"
RESPONSES_JSON_PATH="$3"
OUTPUT_JSON_PATH="$4"
MODEL_NAME="${5:-claude-opus-4-1}"

if [[ ! -f "$RUBRIC_PATH" ]]; then
  echo "Rubric file not found: $RUBRIC_PATH"
  exit 1
fi

if [[ ! -f "$PARSER_SCRIPT_PATH" ]]; then
  echo "Parser script not found: $PARSER_SCRIPT_PATH"
  exit 1
fi

if [[ ! -f "$RESPONSES_JSON_PATH" ]]; then
  echo "Responses JSON not found: $RESPONSES_JSON_PATH"
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set."
  echo "Export one of them before running this script."
  exit 1
fi

python3 src/deterministic_judge.py \
  --rubric "$RUBRIC_PATH" \
  --parser-script "$PARSER_SCRIPT_PATH" \
  --responses-json "$RESPONSES_JSON_PATH" \
  --output-json "$OUTPUT_JSON_PATH" \
  --model "$MODEL_NAME"
