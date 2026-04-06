#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 /path/to/rubric.json /path/to/responses.json /path/to/output.json"
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set."
  echo "Export it first, e.g.:"
  echo "  export ANTHROPIC_API_KEY='...'"
  exit 1
fi

RUBRIC_SOURCE="$1"
RESPONSES_SOURCE="$2"
JUDGE_OUTPUT_SOURCE="$3"

TASK_DIR="src/harbor_rubric_refine_task/environment"
TASK_RUBRIC_PATH="$TASK_DIR/rubric.json"
TASK_RESPONSES_PATH="$TASK_DIR/responses.json"
TASK_OUTPUT_PATH="$TASK_DIR/output.json"
TASK_AGENT_NOTES_PATH="$TASK_DIR/agent_notes.md"
TASK_OLD_RUBRICS_DIR="$TASK_DIR/old_rubrics"

for required_path in "$RUBRIC_SOURCE" "$RESPONSES_SOURCE" "$JUDGE_OUTPUT_SOURCE"; do
  if [[ ! -f "$required_path" ]]; then
    echo "Input file not found: $required_path"
    exit 1
  fi
done

if [[ ! -d "$TASK_DIR" ]]; then
  echo "Task environment directory not found: $TASK_DIR"
  exit 1
fi

# Clean stale files while preserving task source files.
shopt -s nullglob dotglob
for entry in "$TASK_DIR"/*; do
  name="$(basename "$entry")"
  if [[ "$name" == "Dockerfile" || "$name" == "skills" || "$name" == "agent_notes.md" || "$name" == "old_rubrics" ]]; then
    continue
  fi
  rm -rf "$entry"
done
shopt -u nullglob dotglob

mkdir -p "$TASK_OLD_RUBRICS_DIR"

if [[ ! -f "$TASK_AGENT_NOTES_PATH" ]]; then
  cat > "$TASK_AGENT_NOTES_PATH" <<'EOF'
# Agent Notes (Append Only)

<!-- APPEND_ONLY_TEMPLATE: do not edit or remove this header block. -->

EOF
fi

cp "$RUBRIC_SOURCE" "$TASK_RUBRIC_PATH"
cp "$RESPONSES_SOURCE" "$TASK_RESPONSES_PATH"
cp "$JUDGE_OUTPUT_SOURCE" "$TASK_OUTPUT_PATH"

harbor run \
  -p src/harbor_rubric_refine_task \
  --env modal \
  --force-build \
  --agent claude-code \
  --model anthropic/claude-opus-4-1 \
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --artifact /app/agent_eval.json \
  --artifact /app/agent_notes.md \
  --artifact /app/rubric.json \
  --artifact /app/old_rubrics \
  --yes

python3 - <<'PY'
import glob
import json
import os
import sys

result_candidates = glob.glob("jobs/*/harbor_rubric_refine_task__*/result.json")
if not result_candidates:
    print("Could not find refine trial result.json after Harbor run.")
    sys.exit(1)

latest_result = max(result_candidates, key=os.path.getmtime)
with open(latest_result, "r", encoding="utf-8") as f:
    data = json.load(f)

if data.get("exception_info") is not None:
    message = data["exception_info"].get("exception_message", "unknown error")
    print(f"Refinement Harbor trial failed: {message}")
    print(f"See: {latest_result}")
    sys.exit(1)

artifacts_dir = os.path.join(os.path.dirname(latest_result), "artifacts")
required = [
    os.path.join(artifacts_dir, "agent_eval.json"),
    os.path.join(artifacts_dir, "agent_notes.md"),
    os.path.join(artifacts_dir, "rubric.json"),
    os.path.join(artifacts_dir, "old_rubrics"),
]
missing = [p for p in required if not os.path.exists(p)]
if missing:
    print("Refinement completed but required artifacts are missing:")
    for path in missing:
        print(f"- {path}")
    sys.exit(1)

print(f"Refinement artifacts verified in: {artifacts_dir}")
PY
