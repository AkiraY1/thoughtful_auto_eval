# Thoughtful Auto Eval

## Table of Contents

- [Work Trial Task](#work-trial-task)
- [Directory / Files Structure](#directory--files-structure)
- [Methods](#methods)
- [Improvements on These Methods](#improvements-on-these-methods)
- [Ideas to Bypass Auto-Eval for Training Models](#ideas-to-bypass-auto-eval-for-training-models)
- [Demo Videos](#demo-videos)
- [How to Run](#how-to-run)
  - [Prerequisites](#prerequisites)
  - [V1 (CLI): Single-pass rubric creation](#v1-cli-single-pass-rubric-creation)
  - [V2 (CLI): Iterative rubric optimization](#v2-cli-iterative-rubric-optimization)
  - [Streamlit Demo: V1](#streamlit-demo-v1)
  - [Streamlit Demo: V2](#streamlit-demo-v2)
- [Notes](#notes)

## Work Trial Task

Create an auto-eval system with x inputs and y inputs.

Current practical framing in this repo:
- **Input:** a `systemPrompt.txt` plus evaluation data (JSON responses/messages).
- **Output:** an evaluation rubric and (optionally) an iteratively refined rubric loop that improves judging quality.

## Directory / Files Structure

```text
thoughtful_auto_eval/
├── README.md
├── pyproject.toml
├── streamlit_app_rubric_simple.py         # V1 UI (single-pass rubric creation)
├── streamlit_app_rubric_opt.py            # V2 UI (iterative optimization loop)
├── harbor_scripts/
│   ├── run_rubric_task.sh                 # V1 CLI entrypoint
│   ├── run_rubric_opt_task.sh             # V2 CLI entrypoint
│   ├── run_rubric_refine_task.sh          # refinement sub-step
│   ├── run_deterministic_judge_list.sh    # deterministic rubric judging
│   └── run_smoketest.sh
├── eval_data/
│   ├── cognition/
│   │   └── systemPrompt.txt
│   └── listen_labs/
│       ├── systemPrompt.txt
│       ├── eval_dataset_full.json
│       ├── eval_dataset_mini.json
│       └── judge_rubric.txt
├── src/
│   ├── llm_api.py
│   ├── deterministic_judge.py
│   ├── summarize_judge_output.py
│   ├── rubric_creation.py
│   ├── harbor_rubric_task/                # V1 Harbor task (rubric creation)
│   │   ├── instruction.md
│   │   ├── task.toml
│   │   ├── environment/
│   │   │   ├── Dockerfile
│   │   │   └── skills/rubric_creation/SKILL.md
│   │   └── tests/
│   ├── harbor_rubric_opt_task/            # V2 Harbor task (create + optimize)
│   │   ├── instruction.md
│   │   ├── task.toml
│   │   ├── environment/
│   │   │   ├── Dockerfile
│   │   │   ├── system_prompt.txt
│   │   │   ├── responses.json
│   │   │   ├── llm_api.py
│   │   │   └── skills/rubric_creation/SKILL.md
│   │   └── tests/
│   ├── harbor_rubric_refine_task/         # rubric refinement task
│   │   ├── instruction.md
│   │   ├── task.toml
│   │   ├── environment/
│   │   │   ├── Dockerfile
│   │   │   ├── rubric.json
│   │   │   ├── responses.json
│   │   │   ├── output.json
│   │   │   ├── change_summary.json
│   │   │   ├── agent_notes.md
│   │   │   ├── old_rubrics/
│   │   │   └── skills/rubric_refinement/SKILL.md
│   │   └── tests/
│   └── harbor_rubric_judge_task/
│       └── solution/
└── jobs/                                   # run artifacts/logs (generated)
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

## Improvements on These Methods

- Compare responses from multiple LLM judge models and choose the strongest judge.
- Add a diff agent dedicated to summarizing differences between agent and judge outputs.
- Explicitly separate **evidence extraction** from **scoring**.
- Speed improvements (current pipeline is too slow).

## Ideas to Bypass Auto-Eval for Training Models

- DSPy prompt optimization.
- Text-to-LoRA.
- Self-distillation with LLM feedback.

## Demo Videos

<p align="center" width="100%">
<video src="assets/demo_v2_part1.mp4" width="80%" controls></video>
</p>

### V2 Demo - Part 1
[Watch Part 1 (MP4)](assets/demo_v2_part1.mp4)

### V2 Demo - Part 2
[Watch Part 2 (MP4)](assets/demo_v2_part2.mp4)

> Note: GitHub README pages do not consistently support inline MP4 playback.  
> Use the links above to open each video.

## How to Run

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

### V1 (CLI): Single-pass rubric creation

```bash
./harbor_scripts/run_rubric_task.sh eval_data/listen_labs/systemPrompt.txt
```

What it does:
- Copies the provided system prompt into `src/harbor_rubric_task/environment/system_prompt.txt`.
- Runs Harbor on `src/harbor_rubric_task`.
- Produces rubric artifact(s) in `jobs/**/artifacts/rubric.txt`.

### V2 (CLI): Iterative rubric optimization

```bash
./harbor_scripts/run_rubric_opt_task.sh \
  eval_data/listen_labs/systemPrompt.txt \
  eval_data/listen_labs/eval_dataset_mini.json \
  2
```

Optional args:
- arg4: rubric creation skill override (`.md`)
- arg5: rubric refinement skill override (`.md`)

Example with overrides:

```bash
./harbor_scripts/run_rubric_opt_task.sh \
  eval_data/listen_labs/systemPrompt.txt \
  eval_data/listen_labs/eval_dataset_mini.json \
  3 \
  src/harbor_rubric_opt_task/environment/skills/rubric_creation/SKILL.md \
  src/harbor_rubric_refine_task/environment/skills/rubric_refinement/SKILL.md
```

Model selection:

```bash
export RUBRIC_OPT_MODEL=anthropic/claude-sonnet-4-6
export RUBRIC_REFINE_MODEL=anthropic/claude-sonnet-4-6
```

Final optimized rubric is written to:
- `jobs/**/harbor_rubric_opt_task__*/artifacts/optimization_loop/final/rubric.json`

### Streamlit Demo: V1

```bash
uv run streamlit run streamlit_app_rubric_simple.py
```

### Streamlit Demo: V2

```bash
uv run streamlit run streamlit_app_rubric_opt.py
```

## Notes

- `eval_data/<task>/` should contain a `systemPrompt.txt` and (for V2) JSON response data.
- Keep rubric logic modular through skill files so rubric principles can be swapped quickly.