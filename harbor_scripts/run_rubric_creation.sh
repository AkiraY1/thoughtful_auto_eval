#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set."
  echo "Export it first, e.g.:"
  echo "  export ANTHROPIC_API_KEY='...'"
  exit 1
fi

harbor run \
  -p harbor-cookbook/harbor_cookbook/recipes/simple-task \
  --env modal \
  --agent claude-code \
  --model anthropic/claude-opus-4-1 \
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --artifact /app/rubric.txt \
  --yes