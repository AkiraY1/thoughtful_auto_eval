# This document is a mess and outdated. Akira will fix later. Using as random note dump rn.

# Task

Given a system prompt, create a method to train an LLM to do as the system prompt specifies.

Input:
- System prompt

Output:
- Trained LLM which follows the system prompt

## Methods for pure evaluation

1. Agent that can automatically create a rubric for an LLM judge

## Methods for training

1. RL with LLM judge + rubric as a verifier
2. DSPy prompt optimization with LLM judge + rubric as a verifier
3. Text-to-LoRA
4. LLM feedback used for self-distillation

## Overall

We both want methods that can be used to evaluate any LLM (for both training and evaluation), and methods to directly train an LLM on system prompt instructions.

# Code Structure

```eval_data``` contains one directory per eval task. Each task directory must contain a systemPrompt.txt file and an eval_dataset_full.json file. The task directory will be used as input for rubric creation, etc. and also is the destination for file creation, such as judge_rubric.txt files.

For autonomous eval creation, we want:
1. An LLM to create the rubric for the LLM as a judge (define rubric, judge explains reasoning, then output final score)
2. Do very long evaluations of some example data with the agent
3. Call the LLM judge w/ rubric
4. Compare results with the very long agent evaluations of the example data
5. Agent uses feedback to iterate on rubric


Basic modes for auto-eval creation:
- Mode 1: Just have an agent think for a while and create a rubric
- Mode 2: Create rubric, test with LLM judge model like weaker anthropic model, agent iterates, etc.
- Mode 3: DSPy (probably ACE) optimization with LLM as feedback model.
- Mode 4: LLM agent designs its own multi-agent evaluation method. We can give it basic patterns

Make demo w/ streamlit. Upload system prompt and some data.


Judge comparison to:
1. Other models
2. Other rubrics
2. Its own judgements


Dspy requires feedback, to optimize against which you probably don't want.

## Streamlit demo (rubric task)

Run:

```bash
uv run streamlit run streamlit_app.py
```

Notes:
- `ANTHROPIC_API_KEY` must be set in your shell.
- The app lets you edit both `system_prompt.txt` and `environment/skills/rubric_creation/SKILL.md`.
- It runs harbor against a temporary copy of `src/harbor_rubric_task`, so files in your repo are not modified.
- It reads the newest `jobs/**/artifacts/rubric.txt` and shows the output in the UI.


Make everything as modular as possible (like add a modular file which contains principles on how to create a good rubric)


HIL (pause at any point in time, check traces, add feedback, and then continue)
Training model to test rubric performance
Rubric for one response, and rubric for whole conversation