# Thoughtful Auto-Eval

## Demo Videos

![v2 Demo Part 1](assets/demo_v2_part1.gif)
<p><em>Rubric optimization (beginning of workflow)</em></p>

![v2 Demo Part 2](assets/demo_v2_part2.gif)
<p><em>Rubric optimization (during the optimization process)</em></p>

## Table of Contents

- [Task Description](#task-description)
- [File Structure](#file-structure)
- [Methods](#methods)
- [Usage](#usage)
  - [Prerequisites](#prerequisites)
  - [v1: Single-pass rubric creation](#v1-single-pass-rubric-creation)
  - [v2: Iterative rubric optimization](#v2-iterative-rubric-optimization)
- [Possible Improvements](#possible-improvements)
- [Auto-Eval Alternatives](#auto-eval-alternatives)

## Task Description

Create an auto-eval system with x inputs and y inputs.

Current practical framing in this repo:
- **Input:** a `systemPrompt.txt` plus evaluation data (JSON responses/messages).
- **Output:** an evaluation rubric and (optionally) an iteratively refined rubric loop that improves judging quality.

## File Structure

```text
thoughtful_auto_eval/
├── README.md
├── pyproject.toml
├── streamlit_app_rubric_simple.py         # v1 streamlit app
├── streamlit_app_rubric_opt.py            # v2 streamlit app
├── harbor_scripts/
│   ├── run_rubric_task.sh                 # v1 entrypoint
│   ├── run_rubric_opt_task.sh             # v2 entrypoint
│   ├── run_rubric_refine_task.sh          # refinement sub-step
│   ├── run_deterministic_judge_list.sh    # llm judge sub-step
│   └── run_smoketest.sh
├── eval_data/
│   ├── cognition/
│   └── listen_labs/
├── src/
│   ├── llm_api.py
│   ├── deterministic_judge.py
│   ├── summarize_judge_output.py
│   ├── rubric_creation.py
│   ├── harbor_rubric_task/                # v1 Harbor task
│   ├── harbor_rubric_opt_task/            # v2 Harbor task
│   ├── harbor_rubric_refine_task/         # refinement sub-step Harbor task
│   └── harbor_rubric_judge_task/          # judge sub-step Harbor task
└── jobs/                                  # generated Harbor artifacts/logs
```

## Methods

Three methods:

1. **Agent-only rubric creation**
   - Agent analyzes the system prompt and creates a rubric.
   - Rubric-design principles are injected via skill/config files.

2. **Agent + judge + iterative rubric refinement**
   - Agent analyzes the system prompt and creates an initial rubric.
   - A separate LLM judge uses that rubric to evaluate user-provided responses.
   - Agent analyzes judge reasoning/scores and modifies the rubric.
   - This can be repeated for `n` iterations.

3. **Agent-designed multi-agent eval system**
   - Agent analyzes the system prompt and designs a multi-agent evaluation system.
   - Principles/patterns for system design are injected via files.

## Possible Improvements

- Compare responses from multiple LLM judge models and choose the strongest judge.
- Add a diff agent dedicated to summarizing differences between agent and judge outputs.
- Explicitly separate **evidence extraction** from **scoring**.
- Speed improvements (current pipeline is too slow).

## Auto-Eval Alternatives

- DSPy prompt optimization.
- Text-to-LoRA.
- Self-distillation with LLM feedback.

## Usage

### Prerequisites

- Python 3.10+
- `uv` installed
- `harbor` CLI installed and available in shell
- API key set (at minimum):
  - `export ANTHROPIC_API_KEY='...'`

Install dependencies:

```bash
uv sync
```

### v1: Single-pass rubric creation

```bash
./harbor_scripts/run_rubric_task.sh eval_data/listen_labs/systemPrompt.txt
```

What it does:
- Copies the provided system prompt into `src/harbor_rubric_task/environment/system_prompt.txt`.
- Runs Harbor on `src/harbor_rubric_task`.
- Produces rubric artifact(s) in `jobs/**/artifacts/rubric.txt`.

### v2: Iterative rubric optimization

```bash
./harbor_scripts/run_rubric_opt_task.sh \
  eval_data/listen_labs/systemPrompt.txt \
  eval_data/listen_labs/eval_dataset_mini.json \
  2
```

Optional args:
- full-dataset local eval mode (runs only after final optimized rubric):
  - arg3: `full_eval_responses.json` (same schema as `responses.json`, usually larger)
- arg4: iterations (default `1`)
- arg5: rubric creation skill override (`.md`)
- arg6: rubric refinement skill override (`.md`)

Example with overrides:

```bash
./harbor_scripts/run_rubric_opt_task.sh \
  eval_data/listen_labs/systemPrompt.txt \
  eval_data/listen_labs/eval_dataset_mini.json \
  3 \
  src/harbor_rubric_opt_task/environment/skills/rubric_creation/SKILL.md \
  src/harbor_rubric_refine_task/environment/skills/rubric_refinement/SKILL.md
```

Example with final full-dataset local eval and no skill overrides:

```bash
./harbor_scripts/run_rubric_opt_task.sh \
  eval_data/listen_labs/systemPrompt.txt \
  eval_data/listen_labs/eval_dataset_mini.json \
  eval_data/listen_labs/eval_dataset_full.json \
  3
```

Model selection:

```bash
export RUBRIC_OPT_MODEL=anthropic/claude-sonnet-4-6
export RUBRIC_REFINE_MODEL=anthropic/claude-sonnet-4-6
```

Final optimized rubric is written to:
- `jobs/**/harbor_rubric_opt_task__*/artifacts/optimization_loop/final/rubric.json`

### Streamlit Demo: v1

```bash
uv run streamlit run streamlit_app_rubric_simple.py
```

### Streamlit Demo: v2

```bash
uv run streamlit run streamlit_app_rubric_opt.py
```

## Notes

- `eval_data/<task>/` should contain a `systemPrompt.txt` and (for v2) JSON response data.
- Keep rubric logic modular through skill files so rubric principles can be swapped quickly.