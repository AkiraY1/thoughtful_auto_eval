#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/systemPrompt.txt"
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set."
  echo "Export it first, e.g.:"
  echo "  export ANTHROPIC_API_KEY='...'"
  exit 1
fi

SYSTEM_PROMPT_SOURCE="$1"
TASK_PROMPT_PATH="src/harbor_rubric_task/environment/system_prompt.txt"

if [[ ! -f "$SYSTEM_PROMPT_SOURCE" ]]; then
  echo "Input file not found: $SYSTEM_PROMPT_SOURCE"
  exit 1
fi

TASK_PROMPT_BACKUP="$(mktemp)"
HAD_EXISTING_TASK_PROMPT=0
if [[ -f "$TASK_PROMPT_PATH" ]]; then
  cp "$TASK_PROMPT_PATH" "$TASK_PROMPT_BACKUP"
  HAD_EXISTING_TASK_PROMPT=1
fi

cleanup() {
  if [[ "$HAD_EXISTING_TASK_PROMPT" -eq 1 ]]; then
    cp "$TASK_PROMPT_BACKUP" "$TASK_PROMPT_PATH"
  else
    rm -f "$TASK_PROMPT_PATH"
  fi
  rm -f "$TASK_PROMPT_BACKUP"
}
trap cleanup EXIT

cp "$SYSTEM_PROMPT_SOURCE" "$TASK_PROMPT_PATH"

harbor run \
  -p src/harbor_rubric_task \
  --env modal \
  --force-build \
  --agent claude-code \
  --model anthropic/claude-opus-4-1 \
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --artifact /app/rubric.txt \
  --yes