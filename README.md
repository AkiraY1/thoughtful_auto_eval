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