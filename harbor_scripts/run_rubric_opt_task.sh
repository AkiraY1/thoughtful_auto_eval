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

if [[ $# -lt 2 || $# -gt 6 ]]; then
  echo "Usage (new): $0 /path/to/systemPrompt.txt /path/to/responses.json [full_eval_responses.json] [iterations] [rubric_creation_skill.md] [rubric_refinement_skill.md]"
  echo "Usage (legacy): $0 /path/to/systemPrompt.txt /path/to/responses.json [iterations] [rubric_creation_skill.md] [rubric_refinement_skill.md] [full_eval_responses.json]"
  echo ""
  echo "Note: full_eval_responses.json is only used at the very end for local deterministic judging."
  echo "It is NOT copied into Harbor task environment and NOT uploaded to Harbor."
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
ARG3="${3:-}"
ARG4="${4:-}"
ARG5="${5:-}"
ARG6="${6:-}"
RUBRIC_CREATION_SKILL_OVERRIDE=""
RUBRIC_REFINEMENT_SKILL_OVERRIDE=""
FULL_EVAL_RESPONSES_JSON_SOURCE=""
ITERATIONS="1"
MODEL_NAME="${RUBRIC_OPT_MODEL:-anthropic/claude-opus-4-1}"

# New preferred order:
#   1) system prompt
#   2) optimization responses
#   3) full eval responses (optional, json)
#   4) iterations (optional)
#   5) rubric creation skill override (optional)
#   6) rubric refinement skill override (optional)
#
# Legacy compatibility:
#   if arg3 is numeric, treat it as iterations and keep old ordering.
if [[ -n "$ARG3" ]]; then
  if [[ "$ARG3" =~ ^[0-9]+$ ]]; then
    ITERATIONS="$ARG3"
    RUBRIC_CREATION_SKILL_OVERRIDE="$ARG4"
    RUBRIC_REFINEMENT_SKILL_OVERRIDE="$ARG5"
    FULL_EVAL_RESPONSES_JSON_SOURCE="$ARG6"
  else
    FULL_EVAL_RESPONSES_JSON_SOURCE="$ARG3"
    ITERATIONS="${ARG4:-1}"
    RUBRIC_CREATION_SKILL_OVERRIDE="$ARG5"
    RUBRIC_REFINEMENT_SKILL_OVERRIDE="$ARG6"
  fi
fi

if ! [[ "$ITERATIONS" =~ ^[0-9]+$ ]] || [[ "$ITERATIONS" -lt 1 ]]; then
  echo "iterations must be a positive integer. Got: $ITERATIONS"
  exit 1
fi

if [[ "$MODEL_NAME" != "anthropic/claude-sonnet-4-6" && "$MODEL_NAME" != "anthropic/claude-opus-4-1" ]]; then
  echo "Unsupported RUBRIC_OPT_MODEL: $MODEL_NAME"
  echo "Allowed: anthropic/claude-sonnet-4-6, anthropic/claude-opus-4-1"
  exit 1
fi

TASK_DIR="src/harbor_rubric_opt_task/environment"
TASK_PROMPT_PATH="$TASK_DIR/system_prompt.txt"
TASK_RESPONSES_PATH="$TASK_DIR/responses.json"
TASK_LLM_API_PATH="$TASK_DIR/llm_api.py"
TASK_RUBRIC_CREATION_SKILL_PATH="$TASK_DIR/skills/rubric_creation/SKILL.md"
REFINE_TASK_DIR="src/harbor_rubric_refine_task/environment"
REFINE_OLD_RUBRICS_DIR="$REFINE_TASK_DIR/old_rubrics"
REFINE_RUBRIC_SKILL_PATH="$REFINE_TASK_DIR/skills/rubric_refinement/SKILL.md"
LATEST_REFINE_ARTIFACTS_DIR="jobs/latest_harbor_rubric_refine_artifacts"
LATEST_REFINE_ARTIFACTS_POINTER="jobs/latest_harbor_rubric_refine_artifacts.txt"

if [[ ! -d "$TASK_DIR" ]]; then
  echo "Task environment directory not found: $TASK_DIR"
  exit 1
fi

if [[ ! -d "$REFINE_TASK_DIR" ]]; then
  echo "Refine task environment directory not found: $REFINE_TASK_DIR"
  exit 1
fi

if [[ -n "$RUBRIC_CREATION_SKILL_OVERRIDE" && ! -f "$RUBRIC_CREATION_SKILL_OVERRIDE" ]]; then
  echo "Rubric creation skill override not found: $RUBRIC_CREATION_SKILL_OVERRIDE"
  exit 1
fi

if [[ -n "$RUBRIC_REFINEMENT_SKILL_OVERRIDE" && ! -f "$RUBRIC_REFINEMENT_SKILL_OVERRIDE" ]]; then
  echo "Rubric refinement skill override not found: $RUBRIC_REFINEMENT_SKILL_OVERRIDE"
  exit 1
fi

if [[ -n "$FULL_EVAL_RESPONSES_JSON_SOURCE" && ! -f "$FULL_EVAL_RESPONSES_JSON_SOURCE" ]]; then
  echo "Full eval responses JSON not found: $FULL_EVAL_RESPONSES_JSON_SOURCE"
  exit 1
fi

if [[ -n "$FULL_EVAL_RESPONSES_JSON_SOURCE" ]]; then
  python3 - "$FULL_EVAL_RESPONSES_JSON_SOURCE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
raw = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(raw, list):
    raise SystemExit(f"full_eval_responses.json must be a top-level JSON list. Got: {type(raw).__name__}")
print(f"Validated full eval dataset format (list) with {len(raw)} entries: {path}")
PY
fi

# Fresh-start cleanup for stateful environment + local artifact pointers.
rm -rf "$LATEST_REFINE_ARTIFACTS_DIR"
rm -f "$LATEST_REFINE_ARTIFACTS_POINTER"

# Reset refine task environment stateful files/directories.
rm -f "$REFINE_TASK_DIR/rubric.json" "$REFINE_TASK_DIR/responses.json" "$REFINE_TASK_DIR/output.json" "$REFINE_TASK_DIR/change_summary.json"
rm -f "$REFINE_TASK_DIR/agent_notes.md"
rm -rf "$REFINE_OLD_RUBRICS_DIR"
mkdir -p "$REFINE_OLD_RUBRICS_DIR"
touch "$REFINE_OLD_RUBRICS_DIR/.gitkeep"

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
TASK_RUBRIC_CREATION_SKILL_BACKUP="$(mktemp)"
REFINE_RUBRIC_SKILL_BACKUP="$(mktemp)"

HAD_EXISTING_TASK_PROMPT=0
HAD_EXISTING_TASK_RESPONSES=0
HAD_EXISTING_TASK_LLM_API=0
HAD_EXISTING_TASK_RUBRIC_CREATION_SKILL=0
HAD_EXISTING_REFINE_RUBRIC_SKILL=0

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

if [[ -f "$TASK_RUBRIC_CREATION_SKILL_PATH" ]]; then
  cp "$TASK_RUBRIC_CREATION_SKILL_PATH" "$TASK_RUBRIC_CREATION_SKILL_BACKUP"
  HAD_EXISTING_TASK_RUBRIC_CREATION_SKILL=1
fi

if [[ -f "$REFINE_RUBRIC_SKILL_PATH" ]]; then
  cp "$REFINE_RUBRIC_SKILL_PATH" "$REFINE_RUBRIC_SKILL_BACKUP"
  HAD_EXISTING_REFINE_RUBRIC_SKILL=1
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

  if [[ "$HAD_EXISTING_TASK_RUBRIC_CREATION_SKILL" -eq 1 ]]; then
    cp "$TASK_RUBRIC_CREATION_SKILL_BACKUP" "$TASK_RUBRIC_CREATION_SKILL_PATH"
  fi

  if [[ "$HAD_EXISTING_REFINE_RUBRIC_SKILL" -eq 1 ]]; then
    cp "$REFINE_RUBRIC_SKILL_BACKUP" "$REFINE_RUBRIC_SKILL_PATH"
  fi

  rm -f "$TASK_PROMPT_BACKUP" "$TASK_RESPONSES_BACKUP" "$TASK_LLM_API_BACKUP" "$TASK_RUBRIC_CREATION_SKILL_BACKUP" "$REFINE_RUBRIC_SKILL_BACKUP"
}
trap cleanup EXIT

cp "$SYSTEM_PROMPT_SOURCE" "$TASK_PROMPT_PATH"
cp "$RESPONSES_JSON_SOURCE" "$TASK_RESPONSES_PATH"
cp "$LLM_API_SOURCE" "$TASK_LLM_API_PATH"

if [[ -n "$RUBRIC_CREATION_SKILL_OVERRIDE" ]]; then
  cp "$RUBRIC_CREATION_SKILL_OVERRIDE" "$TASK_RUBRIC_CREATION_SKILL_PATH"
fi

if [[ -n "$RUBRIC_REFINEMENT_SKILL_OVERRIDE" ]]; then
  cp "$RUBRIC_REFINEMENT_SKILL_OVERRIDE" "$REFINE_RUBRIC_SKILL_PATH"
fi

print_sha256 "opt_input.system_prompt.source" "$SYSTEM_PROMPT_SOURCE"
print_sha256 "opt_input.system_prompt.task_copy" "$TASK_PROMPT_PATH"
print_sha256 "opt_input.responses.source" "$RESPONSES_JSON_SOURCE"
print_sha256 "opt_input.responses.task_copy" "$TASK_RESPONSES_PATH"
print_sha256 "opt_input.llm_api.source" "$LLM_API_SOURCE"
print_sha256 "opt_input.llm_api.task_copy" "$TASK_LLM_API_PATH"
print_sha256 "opt_input.rubric_creation_skill.task_copy" "$TASK_RUBRIC_CREATION_SKILL_PATH"
print_sha256 "opt_input.rubric_refinement_skill.task_copy" "$REFINE_RUBRIC_SKILL_PATH"
if [[ -n "$FULL_EVAL_RESPONSES_JSON_SOURCE" ]]; then
  print_sha256 "opt_input.full_eval_responses.source" "$FULL_EVAL_RESPONSES_JSON_SOURCE"
  echo "Full eval dataset is reserved for final local eval only (not sent to Harbor): $FULL_EVAL_RESPONSES_JSON_SOURCE"
fi

HARBOR_ARGS=(
  run
  -p src/harbor_rubric_opt_task
  --env modal
  --agent claude-code
  --model "$MODEL_NAME"
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
  ITER_TIMINGS_PATH="$ITER_DIR/timings.json"

  ITER_START_TS="$(date +%s)"
  cp "$CURRENT_RUBRIC_PATH" "$RUBRIC_BEFORE_PATH"
  print_sha256 "$ITER_LABEL.rubric_before_refine" "$RUBRIC_BEFORE_PATH"
  if [[ -n "$CURRENT_CHANGE_SUMMARY_PATH" ]]; then
    print_sha256 "$ITER_LABEL.change_summary_before_refine" "$CURRENT_CHANGE_SUMMARY_PATH"
  fi

  echo "[$ITER_LABEL] Running deterministic judge with rubric: $RUBRIC_BEFORE_PATH"
  JUDGING_START_TS="$(date +%s)"
  ./harbor_scripts/run_deterministic_judge_list.sh \
    "$RUBRIC_BEFORE_PATH" \
    "$RESPONSES_JSON_SOURCE" \
    "$JUDGE_OUTPUT_PATH" \
    "${MODEL_NAME#anthropic/}"

  echo "[$ITER_LABEL] Summarizing deterministic judge output: $JUDGE_OUTPUT_PATH"
  python3 src/summarize_judge_output.py --output-json "$JUDGE_OUTPUT_PATH"
  print_sha256 "$ITER_LABEL.judge_output_summarized" "$JUDGE_OUTPUT_PATH"
  JUDGING_END_TS="$(date +%s)"

  echo "[$ITER_LABEL] Running Harbor refinement task"
  REFINE_START_TS="$(date +%s)"
  if [[ -n "$CURRENT_CHANGE_SUMMARY_PATH" ]]; then
    RUBRIC_REFINE_MODEL="$MODEL_NAME" ./harbor_scripts/run_rubric_refine_task.sh \
      "$RUBRIC_BEFORE_PATH" \
      "$RESPONSES_JSON_SOURCE" \
      "$JUDGE_OUTPUT_PATH" \
      "$CURRENT_CHANGE_SUMMARY_PATH"
  else
    RUBRIC_REFINE_MODEL="$MODEL_NAME" ./harbor_scripts/run_rubric_refine_task.sh \
      "$RUBRIC_BEFORE_PATH" \
      "$RESPONSES_JSON_SOURCE" \
      "$JUDGE_OUTPUT_PATH"
  fi
  REFINE_END_TS="$(date +%s)"

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

  ITER_END_TS="$(date +%s)"
  JUDGING_DURATION_SEC=$((JUDGING_END_TS - JUDGING_START_TS))
  REFINEMENT_DURATION_SEC=$((REFINE_END_TS - REFINE_START_TS))
  ITERATION_DURATION_SEC=$((ITER_END_TS - ITER_START_TS))

  cat > "$ITER_TIMINGS_PATH" <<EOF
{
  "iteration_label": "$ITER_LABEL",
  "judging_duration_sec": $JUDGING_DURATION_SEC,
  "refinement_duration_sec": $REFINEMENT_DURATION_SEC,
  "iteration_duration_sec": $ITERATION_DURATION_SEC
}
EOF

  echo "[$ITER_LABEL] Timing: judging=${JUDGING_DURATION_SEC}s refinement=${REFINEMENT_DURATION_SEC}s total=${ITERATION_DURATION_SEC}s"
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
  "stable_refine_pointer": "$STABLE_REFINE_POINTER",
  "full_eval_responses_source": "$FULL_EVAL_RESPONSES_JSON_SOURCE",
  "full_eval_output": "$FINAL_DIR/full_eval_output.json",
  "full_eval_summary": "$FINAL_DIR/full_eval_summary.json"
}
EOF

echo "Optimization loop complete."
echo "Final optimized rubric: $FINAL_DIR/rubric.json"

if [[ -n "$FULL_EVAL_RESPONSES_JSON_SOURCE" ]]; then
  FINAL_FULL_EVAL_OUTPUT_PATH="$FINAL_DIR/full_eval_output.json"
  FINAL_FULL_EVAL_SUMMARY_PATH="$FINAL_DIR/full_eval_summary.json"
  FINAL_FULL_EVAL_STATS_PATH="$FINAL_DIR/full_eval_stats.txt"

  echo "Running final local deterministic eval on full dataset: $FULL_EVAL_RESPONSES_JSON_SOURCE"
  ./harbor_scripts/run_deterministic_judge_list.sh \
    "$FINAL_DIR/rubric.json" \
    "$FULL_EVAL_RESPONSES_JSON_SOURCE" \
    "$FINAL_FULL_EVAL_OUTPUT_PATH" \
    "${MODEL_NAME#anthropic/}"

  echo "Summarizing final full-dataset eval output: $FINAL_FULL_EVAL_OUTPUT_PATH"
  python3 src/summarize_judge_output.py --output-json "$FINAL_FULL_EVAL_OUTPUT_PATH"

  python3 - "$FINAL_FULL_EVAL_OUTPUT_PATH" "$FINAL_FULL_EVAL_SUMMARY_PATH" "$FINAL_FULL_EVAL_STATS_PATH" <<'PY'
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
stats_path = Path(sys.argv[3])

payload = json.loads(output_path.read_text(encoding="utf-8"))
summary = payload.get("summary", {})
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

item_count = int(summary.get("item_count", 0) or 0)
scored_item_count = int(summary.get("scored_item_count", 0) or 0)
mean_final_score = float(summary.get("mean_final_score", 0.0) or 0.0)
percentiles = summary.get("final_score_percentiles", {}) or {}
per_criterion = summary.get("per_criterion_mean", {}) or {}

lines = []
lines.append("=== FINAL FULL-DATASET EVAL SUMMARY ===")
lines.append(f"item_count: {item_count}")
lines.append(f"scored_item_count: {scored_item_count}")
coverage = (scored_item_count / item_count * 100.0) if item_count else 0.0
lines.append(f"scored_coverage_pct: {coverage:.2f}")
lines.append(f"mean_final_score: {mean_final_score:.6f}")
lines.append(
    "final_score_percentiles: "
    f"p10={float(percentiles.get('p10', 0.0) or 0.0):.6f}, "
    f"p25={float(percentiles.get('p25', 0.0) or 0.0):.6f}, "
    f"p50={float(percentiles.get('p50', 0.0) or 0.0):.6f}, "
    f"p75={float(percentiles.get('p75', 0.0) or 0.0):.6f}, "
    f"p90={float(percentiles.get('p90', 0.0) or 0.0):.6f}"
)
lines.append("per_criterion_mean:")
for criterion, score in sorted(per_criterion.items(), key=lambda kv: kv[0].lower()):
    lines.append(f"  - {criterion}: {float(score):.6f}")

stats_text = "\n".join(lines)
stats_path.write_text(stats_text + "\n", encoding="utf-8")
print(stats_text)
print("")
print(f"Saved full eval output: {output_path}")
print(f"Saved full eval summary: {summary_path}")
print(f"Saved full eval stats text: {stats_path}")
PY
fi
