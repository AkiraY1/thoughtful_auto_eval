#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 /path/to/systemPrompt.txt /path/to/responses.json [iterations]"
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
ITERATIONS="${3:-1}"
LLM_API_SOURCE="src/llm_api.py"

if ! [[ "$ITERATIONS" =~ ^[0-9]+$ ]] || [[ "$ITERATIONS" -lt 1 ]]; then
  echo "iterations must be a positive integer. Got: $ITERATIONS"
  exit 1
fi

TASK_DIR="src/harbor_rubric_opt_task/environment"
TASK_PROMPT_PATH="$TASK_DIR/system_prompt.txt"
TASK_RESPONSES_PATH="$TASK_DIR/responses.json"
TASK_LLM_API_PATH="$TASK_DIR/llm_api.py"

if [[ ! -d "$TASK_DIR" ]]; then
  echo "Task environment directory not found: $TASK_DIR"
  exit 1
fi

# Remove any stale files from prior runs while keeping task source files.
shopt -s nullglob dotglob
for entry in "$TASK_DIR"/*; do
  name="$(basename "$entry")"
  if [[ "$name" == "Dockerfile" || "$name" == "skills" ]]; then
    continue
  fi
  rm -rf "$entry"
done
shopt -u nullglob dotglob

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
  --artifact /app/rubric.json
  --yes
)

harbor "${HARBOR_ARGS[@]}"

# Run deterministic judging immediately after Harbor completes.
LATEST_RUBRIC_ARTIFACT="$(
  ls -t jobs/*/harbor_rubric_opt_task__*/artifacts/rubric.json 2>/dev/null | head -n 1
)"

if [[ -z "${LATEST_RUBRIC_ARTIFACT:-}" ]]; then
  echo "Could not find rubric artifact after Harbor run."
  exit 1
fi

LATEST_ARTIFACTS_DIR="$(dirname "$LATEST_RUBRIC_ARTIFACT")"
LOOP_DIR="$LATEST_ARTIFACTS_DIR/optimization_loop"
mkdir -p "$LOOP_DIR"

CURRENT_RUBRIC_PATH="$LATEST_RUBRIC_ARTIFACT"
CURRENT_CHANGE_SUMMARY_PATH=""
STABLE_REFINE_DIR="jobs/latest_harbor_rubric_refine_artifacts"
STABLE_REFINE_POINTER="jobs/latest_harbor_rubric_refine_artifacts.txt"

echo "Starting optimization loop for $ITERATIONS iteration(s)."
for ((iter = 1; iter <= ITERATIONS; iter++)); do
  ITER_LABEL="$(printf "iter_%03d" "$iter")"
  ITER_DIR="$LOOP_DIR/$ITER_LABEL"
  mkdir -p "$ITER_DIR"

  RUBRIC_BEFORE_PATH="$ITER_DIR/rubric_before_refine.json"
  JUDGE_OUTPUT_PATH="$ITER_DIR/output.json"
  RUBRIC_AFTER_PATH="$ITER_DIR/rubric_after_refine.json"
  AGENT_EVAL_PATH="$ITER_DIR/agent_eval.json"
  AGENT_NOTES_PATH="$ITER_DIR/agent_notes.md"
  CHANGE_SUMMARY_PATH="$ITER_DIR/change_summary.json"
  OLD_RUBRICS_PATH="$ITER_DIR/old_rubrics"

  cp "$CURRENT_RUBRIC_PATH" "$RUBRIC_BEFORE_PATH"

  echo "[$ITER_LABEL] Running deterministic judge with rubric: $RUBRIC_BEFORE_PATH"
  ./harbor_scripts/run_deterministic_judge_list.sh \
    "$RUBRIC_BEFORE_PATH" \
    "$RESPONSES_JSON_SOURCE" \
    "$JUDGE_OUTPUT_PATH"

  echo "[$ITER_LABEL] Summarizing deterministic judge output: $JUDGE_OUTPUT_PATH"
  python3 src/summarize_judge_output.py --output-json "$JUDGE_OUTPUT_PATH"

  echo "[$ITER_LABEL] Running Harbor refinement task"
  if [[ -n "$CURRENT_CHANGE_SUMMARY_PATH" ]]; then
    ./harbor_scripts/run_rubric_refine_task.sh \
      "$RUBRIC_BEFORE_PATH" \
      "$RESPONSES_JSON_SOURCE" \
      "$JUDGE_OUTPUT_PATH" \
      "$CURRENT_CHANGE_SUMMARY_PATH"
  else
    ./harbor_scripts/run_rubric_refine_task.sh \
      "$RUBRIC_BEFORE_PATH" \
      "$RESPONSES_JSON_SOURCE" \
      "$JUDGE_OUTPUT_PATH"
  fi

  if [[ ! -d "$STABLE_REFINE_DIR" ]]; then
    echo "[$ITER_LABEL] Missing stable refine artifacts directory: $STABLE_REFINE_DIR"
    exit 1
  fi
  if [[ ! -f "$STABLE_REFINE_DIR/rubric.json" ]]; then
    echo "[$ITER_LABEL] Missing refined rubric in stable directory."
    exit 1
  fi

  cp "$STABLE_REFINE_DIR/rubric.json" "$RUBRIC_AFTER_PATH"
  cp "$STABLE_REFINE_DIR/agent_eval.json" "$AGENT_EVAL_PATH"
  cp "$STABLE_REFINE_DIR/agent_notes.md" "$AGENT_NOTES_PATH"
  cp "$STABLE_REFINE_DIR/change_summary.json" "$CHANGE_SUMMARY_PATH"
  rm -rf "$OLD_RUBRICS_PATH"
  cp -R "$STABLE_REFINE_DIR/old_rubrics" "$OLD_RUBRICS_PATH"

  CURRENT_RUBRIC_PATH="$RUBRIC_AFTER_PATH"
  CURRENT_CHANGE_SUMMARY_PATH="$CHANGE_SUMMARY_PATH"
  echo "[$ITER_LABEL] Completed."
done

FINAL_DIR="$LOOP_DIR/final"
mkdir -p "$FINAL_DIR"
cp "$CURRENT_RUBRIC_PATH" "$FINAL_DIR/rubric.json"
if [[ -n "$CURRENT_CHANGE_SUMMARY_PATH" ]]; then
  cp "$CURRENT_CHANGE_SUMMARY_PATH" "$FINAL_DIR/change_summary.json"
fi
cat > "$FINAL_DIR/metadata.json" <<EOF
{
  "iterations": $ITERATIONS,
  "final_rubric": "$FINAL_DIR/rubric.json",
  "final_change_summary": "$FINAL_DIR/change_summary.json",
  "loop_dir": "$LOOP_DIR",
  "stable_refine_pointer": "$STABLE_REFINE_POINTER"
}
EOF

echo "Optimization loop complete."
echo "Final optimized rubric: $FINAL_DIR/rubric.json"
