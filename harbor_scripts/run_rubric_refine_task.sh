#!/usr/bin/env bash
set -euo pipefail

# Suppress noisy upstream deprecation warnings from Harbor/Modal internals.
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::PendingDeprecationWarning}"

print_sha256() {
  local label="$1"
  local path="$2"
  if [[ -f "$path" ]]; then
    local digest
    digest="$(shasum -a 256 "$path" | awk '{print $1}')"
    echo "[hash] $label :: $path :: $digest"
  else
    echo "[hash] $label :: $path :: <missing>"
  fi
}

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 /path/to/rubric.json /path/to/responses.json /path/to/output.json [change_summary.json]"
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
CHANGE_SUMMARY_SOURCE="${4:-}"

TASK_DIR="src/harbor_rubric_refine_task/environment"
TASK_RUBRIC_PATH="$TASK_DIR/rubric.json"
TASK_RESPONSES_PATH="$TASK_DIR/responses.json"
TASK_OUTPUT_PATH="$TASK_DIR/output.json"
TASK_AGENT_NOTES_PATH="$TASK_DIR/agent_notes.md"
TASK_CHANGE_SUMMARY_PATH="$TASK_DIR/change_summary.json"
TASK_OLD_RUBRICS_DIR="$TASK_DIR/old_rubrics"
TASK_OLD_RUBRICS_KEEP="$TASK_OLD_RUBRICS_DIR/.gitkeep"

for required_path in "$RUBRIC_SOURCE" "$RESPONSES_SOURCE" "$JUDGE_OUTPUT_SOURCE"; do
  if [[ ! -f "$required_path" ]]; then
    echo "Input file not found: $required_path"
    exit 1
  fi
done

if [[ -n "$CHANGE_SUMMARY_SOURCE" && ! -f "$CHANGE_SUMMARY_SOURCE" ]]; then
  echo "change_summary input file not found: $CHANGE_SUMMARY_SOURCE"
  exit 1
fi

if [[ ! -d "$TASK_DIR" ]]; then
  echo "Task environment directory not found: $TASK_DIR"
  exit 1
fi

# Clean stale files while preserving task source files.
shopt -s nullglob dotglob
for entry in "$TASK_DIR"/*; do
  name="$(basename "$entry")"
  if [[ "$name" == "Dockerfile" || "$name" == "skills" || "$name" == "agent_notes.md" || "$name" == "change_summary.json" || "$name" == "old_rubrics" ]]; then
    continue
  fi
  rm -rf "$entry"
done
shopt -u nullglob dotglob

mkdir -p "$TASK_OLD_RUBRICS_DIR"
touch "$TASK_OLD_RUBRICS_KEEP"

if [[ ! -f "$TASK_AGENT_NOTES_PATH" ]]; then
  cat > "$TASK_AGENT_NOTES_PATH" <<'EOF'
# Agent Notes (Append Only)

<!-- APPEND_ONLY_TEMPLATE: do not edit or remove this header block. -->

EOF
fi

if [[ -n "$CHANGE_SUMMARY_SOURCE" ]]; then
  cp "$CHANGE_SUMMARY_SOURCE" "$TASK_CHANGE_SUMMARY_PATH"
elif [[ ! -f "$TASK_CHANGE_SUMMARY_PATH" ]]; then
  echo "[]" > "$TASK_CHANGE_SUMMARY_PATH"
fi

cp "$RUBRIC_SOURCE" "$TASK_RUBRIC_PATH"
cp "$RESPONSES_SOURCE" "$TASK_RESPONSES_PATH"
cp "$JUDGE_OUTPUT_SOURCE" "$TASK_OUTPUT_PATH"

print_sha256 "refine_input.rubric.source" "$RUBRIC_SOURCE"
print_sha256 "refine_input.rubric.task_copy" "$TASK_RUBRIC_PATH"
print_sha256 "refine_input.responses.source" "$RESPONSES_SOURCE"
print_sha256 "refine_input.responses.task_copy" "$TASK_RESPONSES_PATH"
print_sha256 "refine_input.output.source" "$JUDGE_OUTPUT_SOURCE"
print_sha256 "refine_input.output.task_copy" "$TASK_OUTPUT_PATH"
print_sha256 "refine_input.agent_notes.template" "$TASK_AGENT_NOTES_PATH"
print_sha256 "refine_input.change_summary.task_copy" "$TASK_CHANGE_SUMMARY_PATH"

harbor run \
  -p src/harbor_rubric_refine_task \
  --env modal \
  --agent claude-code \
  --model anthropic/claude-opus-4-1 \
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --artifact /app/agent_eval.json \
  --artifact /app/agent_notes.md \
  --artifact /app/change_summary.json \
  --artifact /app/rubric.json \
  --artifact /app/old_rubrics \
  --yes

python3 - <<'PY'
import glob
import json
import os
import shutil
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
    os.path.join(artifacts_dir, "change_summary.json"),
    os.path.join(artifacts_dir, "rubric.json"),
    os.path.join(artifacts_dir, "old_rubrics"),
]
missing = [p for p in required if not os.path.exists(p)]
if missing:
    print("Refinement completed but required artifacts are missing:")
    for path in missing:
        print(f"- {path}")
    sys.exit(1)

# Also maintain a stable pointer + mirror for downstream tools/UI.
latest_pointer = os.path.join("jobs", "latest_harbor_rubric_refine_artifacts.txt")
with open(latest_pointer, "w", encoding="utf-8") as f:
    f.write(artifacts_dir + "\n")

stable_dir = os.path.join("jobs", "latest_harbor_rubric_refine_artifacts")
if os.path.exists(stable_dir):
    shutil.rmtree(stable_dir)
os.makedirs(stable_dir, exist_ok=True)
for name in ["agent_eval.json", "agent_notes.md", "change_summary.json", "rubric.json"]:
    shutil.copy2(os.path.join(artifacts_dir, name), os.path.join(stable_dir, name))
shutil.copytree(
    os.path.join(artifacts_dir, "old_rubrics"),
    os.path.join(stable_dir, "old_rubrics"),
    dirs_exist_ok=True,
)

print(f"Refinement artifacts verified in: {artifacts_dir}")
print(f"Stable artifacts mirror: {stable_dir}")
print(f"Stable artifacts pointer: {latest_pointer}")
PY
