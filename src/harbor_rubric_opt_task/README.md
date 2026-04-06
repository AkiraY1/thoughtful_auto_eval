## harbor_rubric_judge_task

Harbor task where the agent must:

1. Create a rubric from `system_prompt.txt` using the `rubric_creation` skill.
2. Create a Python parser that extracts each model response from `responses.json`.
3. Use `llm_api.py` plus the generated rubric to judge each extracted response individually.
4. Save per-response judgments to `judged_responses.json`.
