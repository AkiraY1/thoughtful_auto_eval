Create three outputs in `/app`:

1. `rubric.txt`: a rubric for evaluating how well responses align with `system_prompt.txt`.
2. `parse_responses.py`: a Python script that reads `responses.json` and extracts each response individually.
3. `judged_responses.json`: per-response LLM-judge results using the rubric and `llm_api.py`.

Requirements:
- You have a skill named `rubric_creation`; use it to guide rubric quality.
- The parser must preserve one entry per extracted response and write `parsed_responses.json`.
- Run the judge on each extracted response individually (not as one batch judgment).
- Each judgment entry in `judged_responses.json` must include:
  - `response_id`
  - `response_text`
  - `judge_output`
