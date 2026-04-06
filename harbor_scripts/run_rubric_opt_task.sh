#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 /path/to/systemPrompt.txt /path/to/responses.json"
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set."
  echo "Export it first, e.g.:"
  echo "  export ANTHROPIC_API_KEY='...'"
  exit 1
fi

SYSTEM_PROMPT_SOURCE="$1"
RESPONSES_JSON_SOURCE="$2"
LLM_API_SOURCE="src/llm_api.py"

TASK_DIR="src/harbor_rubric_opt_task/environment"
TASK_PROMPT_PATH="$TASK_DIR/system_prompt.txt"
TASK_RESPONSES_PATH="$TASK_DIR/responses.json"
TASK_LLM_API_PATH="$TASK_DIR/llm_api.py"

if [[ ! -f "$SYSTEM_PROMPT_SOURCE" ]]; then
  echo "System prompt file not found: $SYSTEM_PROMPT_SOURCE"
  exit 1
fi

if [[ ! -f "$RESPONSES_JSON_SOURCE" ]]; then
  echo "Responses JSON file not found: $RESPONSES_JSON_SOURCE"
  exit 1
fi

if [[ ! -f "$LLM_API_SOURCE" ]]; then
  echo "Expected llm_api.py not found: $LLM_API_SOURCE"
  exit 1
fi

TASK_PROMPT_BACKUP="$(mktemp)"
TASK_RESPONSES_BACKUP="$(mktemp)"
TASK_LLM_API_BACKUP="$(mktemp)"

HAD_EXISTING_TASK_PROMPT=0
HAD_EXISTING_TASK_RESPONSES=0
HAD_EXISTING_TASK_LLM_API=0

if [[ -f "$TASK_PROMPT_PATH" ]]; then
  cp "$TASK_PROMPT_PATH" "$TASK_PROMPT_BACKUP"
  HAD_EXISTING_TASK_PROMPT=1
fi

if [[ -f "$TASK_RESPONSES_PATH" ]]; then
  cp "$TASK_RESPONSES_PATH" "$TASK_RESPONSES_BACKUP"
  HAD_EXISTING_TASK_RESPONSES=1
fi

if [[ -f "$TASK_LLM_API_PATH" ]]; then
  cp "$TASK_LLM_API_PATH" "$TASK_LLM_API_BACKUP"
  HAD_EXISTING_TASK_LLM_API=1
fi

cleanup() {
  if [[ "$HAD_EXISTING_TASK_PROMPT" -eq 1 ]]; then
    cp "$TASK_PROMPT_BACKUP" "$TASK_PROMPT_PATH"
  else
    rm -f "$TASK_PROMPT_PATH"
  fi

  if [[ "$HAD_EXISTING_TASK_RESPONSES" -eq 1 ]]; then
    cp "$TASK_RESPONSES_BACKUP" "$TASK_RESPONSES_PATH"
  else
    rm -f "$TASK_RESPONSES_PATH"
  fi

  if [[ "$HAD_EXISTING_TASK_LLM_API" -eq 1 ]]; then
    cp "$TASK_LLM_API_BACKUP" "$TASK_LLM_API_PATH"
  else
    rm -f "$TASK_LLM_API_PATH"
  fi

  rm -f "$TASK_PROMPT_BACKUP" "$TASK_RESPONSES_BACKUP" "$TASK_LLM_API_BACKUP"
}
trap cleanup EXIT

cp "$SYSTEM_PROMPT_SOURCE" "$TASK_PROMPT_PATH"
cp "$RESPONSES_JSON_SOURCE" "$TASK_RESPONSES_PATH"
cp "$LLM_API_SOURCE" "$TASK_LLM_API_PATH"

HARBOR_ARGS=(
  run
  -p src/harbor_rubric_opt_task
  --env modal
  --force-build
  --agent claude-code
  --model anthropic/claude-opus-4-1
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
  --artifact /app/rubric.txt
  --artifact /app/parse_responses.py
  --yes
)

harbor "${HARBOR_ARGS[@]}"
